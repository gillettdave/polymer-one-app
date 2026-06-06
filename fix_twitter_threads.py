"""
Retroactive fix script: Combine Twitter thread submissions and re-grade as single threads.

This script:
1. Reads all tweets from the tweets sheet
2. Groups tweets by user and conversation_id (thread)
3. For each thread with multiple tweets, combines them and re-grades as a single thread
4. Updates XP so only one tweet in the thread gets XP (the rest get 0)
"""

import os
import sys
import asyncio
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import from PolyOne.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PolyOne import (
    get_tweets_ws,
    fetch_tweet_data_for_thread_detection,
    combine_thread_text,
    grade_tweet,
    log_or_print,
    throttle_sheets_api,
    retry_with_backoff,
    asyncio,
)

# OpenAI (for re-grading)
from PolyOne import OPENAI_API_KEY, openai_client


async def find_thread_groups() -> Dict[str, List[Dict[str, Any]]]:
    """Find all tweet submissions grouped by user and conversation_id.
    
    Returns:
        Dictionary mapping "{user_id}_{conversation_id}" -> list of tweet rows
    """
    ws = get_tweets_ws()
    rows = ws.get_all_values()
    
    if not rows or len(rows) < 2:
        print("No tweets found.")
        return {}
    
    header = rows[0]
    
    # Find column indices
    tweet_id_col = None
    member_col = None
    graded_col = None
    score_col = None
    xp_col = None
    text_col = None
    notes_col = None
    
    for idx, col_name in enumerate(header):
        if col_name == "Tweet ID":
            tweet_id_col = idx
        elif col_name == "Member":
            member_col = idx
        elif col_name == "Graded":
            graded_col = idx
        elif col_name == "Score":
            score_col = idx
        elif col_name == "XP Awarded":
            xp_col = idx
        elif col_name == "Tweet Text":
            text_col = idx
        elif col_name == "Notes" or "notes" in col_name.lower():
            notes_col = idx
    
    if tweet_id_col is None or member_col is None:
        print("Error: Could not find required columns in tweets sheet.")
        return {}
    
    print(f"Scanning {len(rows) - 1} tweet submissions...")
    
    # Collect all tweet IDs to fetch conversation data
    all_tweet_ids = []
    tweet_rows = {}  # tweet_id -> row data
    
    for row_idx, row in enumerate(rows[1:], start=2):
        if len(row) <= max(tweet_id_col, member_col):
            continue
        
        tweet_id = row[tweet_id_col] if len(row) > tweet_id_col else ""
        member = row[member_col] if len(row) > member_col else ""
        
        if not tweet_id or not member:
            continue
        
        all_tweet_ids.append(tweet_id)
        tweet_rows[tweet_id] = {
            "row_index": row_idx,
            "tweet_id": tweet_id,
            "member": member,
            "row": row,
            "tweet_id_col": tweet_id_col,
            "member_col": member_col,
            "graded_col": graded_col,
            "score_col": score_col,
            "xp_col": xp_col,
            "text_col": text_col,
            "notes_col": notes_col,
        }
    
    print(f"Fetching conversation data for {len(all_tweet_ids)} tweets...")
    
    # Fetch conversation data in batches
    all_tweet_data = {}
    batch_size = 100
    for i in range(0, len(all_tweet_ids), batch_size):
        batch = all_tweet_ids[i:i+batch_size]
        print(f"  Fetching batch {i//batch_size + 1}/{(len(all_tweet_ids) + batch_size - 1)//batch_size}...")
        try:
            batch_data = await fetch_tweet_data_for_thread_detection(batch)
            all_tweet_data.update(batch_data)
        except Exception as e:
            print(f"  Error fetching batch: {e}")
            continue
    
    # Group by user and conversation_id
    thread_groups = defaultdict(list)
    
    for tweet_id, row_data in tweet_rows.items():
        if tweet_id not in all_tweet_data:
            # No data for this tweet, skip it
            continue
        
        tweet_info = all_tweet_data[tweet_id]
        conversation_id = tweet_info.get("conversation_id", "")
        member = row_data["member"]
        
        if conversation_id:
            # Group by user and conversation_id
            key = f"{member}_{conversation_id}"
            thread_groups[key].append(row_data)
        else:
            # No conversation_id, treat as standalone (but still include for potential grouping)
            key = f"{member}_{tweet_id}"
            thread_groups[key].append(row_data)
    
    # Filter to only groups with multiple tweets (actual threads)
    actual_threads = {k: v for k, v in thread_groups.items() if len(v) > 1}
    
    return actual_threads


async def process_thread_group(group_key: str, thread_rows: List[Dict[str, Any]], dry_run: bool = True) -> Dict[str, Any]:
    """Process a single thread group: combine and re-grade.
    
    Returns:
        Dictionary with processing results
    """
    tweet_ids = [row["tweet_id"] for row in thread_rows]
    member = thread_rows[0]["member"]
    
    print(f"\nProcessing thread: {member} ({len(tweet_ids)} tweets)")
    print(f"  Tweet IDs: {', '.join(tweet_ids[:5])}{'...' if len(tweet_ids) > 5 else ''}")
    
    # Fetch tweet data
    try:
        tweet_data = await fetch_tweet_data_for_thread_detection(tweet_ids)
    except Exception as e:
        print(f"  Error fetching tweet data: {e}")
        return {"success": False, "error": str(e)}
    
    # Combine thread text
    combined_text = combine_thread_text(tweet_ids, tweet_data)
    
    if not combined_text:
        print(f"  Error: Could not combine thread text")
        return {"success": False, "error": "Could not combine thread text"}
    
    # Re-grade the combined thread
    try:
        score, rationale = await grade_tweet(combined_text)
        xp_amount = max(0, round(score)) if score > 0 else 0
        print(f"  Combined score: {score:.1f}, XP: {xp_amount}")
    except Exception as e:
        print(f"  Error grading thread: {e}")
        return {"success": False, "error": str(e)}
    
    if dry_run:
        print(f"  [DRY RUN] Would update {len(thread_rows)} rows")
        return {
            "success": True,
            "score": score,
            "xp": xp_amount,
            "tweet_count": len(thread_rows),
            "dry_run": True,
        }
    
    # Update rows: first tweet gets XP, others get 0
    ws = get_tweets_ws()
    batch_updates = []
    
    def _get_column_letter(col_index: int) -> str:
        result = ""
        col_index += 1
        while col_index > 0:
            col_index -= 1
            result = chr(65 + (col_index % 26)) + result
            col_index //= 26
        return result
    
    # Sort by row index to process in order
    thread_rows_sorted = sorted(thread_rows, key=lambda x: x["row_index"])
    
    for idx, row_data in enumerate(thread_rows_sorted):
        row_idx = row_data["row_index"]
        
        # First tweet gets the combined score and XP
        # Others get score 0 and XP 0
        if idx == 0:
            # Update first tweet with combined score and XP
            if row_data["score_col"] is not None:
                batch_updates.append({
                    "range": f"{_get_column_letter(row_data['score_col'])}{row_idx}",
                    "values": [[score]]
                })
            if row_data["xp_col"] is not None:
                batch_updates.append({
                    "range": f"{_get_column_letter(row_data['xp_col'])}{row_idx}",
                    "values": [[xp_amount]]
                })
            if row_data["text_col"] is not None:
                # Update with combined text
                truncated_text = combined_text[:49000] if len(combined_text) > 49000 else combined_text
                batch_updates.append({
                    "range": f"{_get_column_letter(row_data['text_col'])}{row_idx}",
                    "values": [[truncated_text]]
                })
            if row_data["notes_col"] is not None:
                note = f"Thread submission ({len(tweet_ids)} tweets combined). {rationale[:400]}"
                batch_updates.append({
                    "range": f"{_get_column_letter(row_data['notes_col'])}{row_idx}",
                    "values": [[note[:500]]]
                })
        else:
            # Other tweets in thread get 0 XP
            if row_data["score_col"] is not None:
                batch_updates.append({
                    "range": f"{_get_column_letter(row_data['score_col'])}{row_idx}",
                    "values": [[0]]
                })
            if row_data["xp_col"] is not None:
                batch_updates.append({
                    "range": f"{_get_column_letter(row_data['xp_col'])}{row_idx}",
                    "values": [[0]]
                })
            if row_data["notes_col"] is not None:
                existing_notes = row_data["row"][row_data["notes_col"]] if len(row_data["row"]) > row_data["notes_col"] else ""
                note = f"Part of thread (scored as combined thread). {existing_notes}"
                if "Part of thread" not in existing_notes:
                    batch_updates.append({
                        "range": f"{_get_column_letter(row_data['notes_col'])}{row_idx}",
                        "values": [[note[:500]]]
                    })
    
    # Apply updates
    if batch_updates:
        try:
            await throttle_sheets_api()
            await retry_with_backoff(
                lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                max_retries=3,
                initial_delay=1.0,
            )
            print(f"  ✅ Updated {len(thread_rows)} rows")
            return {
                "success": True,
                "score": score,
                "xp": xp_amount,
                "tweet_count": len(thread_rows),
                "dry_run": False,
            }
        except Exception as e:
            print(f"  Error updating rows: {e}")
            return {"success": False, "error": str(e)}
    
    return {"success": True, "dry_run": False}


async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix Twitter thread submissions (combine and re-grade)")
    parser.add_argument("--execute", action="store_true", help="Actually update tweets (default is dry run)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Twitter Thread Fix Script")
    print("=" * 60)
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print()
    
    # Find thread groups
    thread_groups = await find_thread_groups()
    
    if not thread_groups:
        print("No threads found (all tweets are standalone).")
        return
    
    print(f"\nFound {len(thread_groups)} thread groups with multiple submissions:")
    total_tweets = sum(len(rows) for rows in thread_groups.values())
    print(f"  Total tweets in threads: {total_tweets}")
    print(f"  Average tweets per thread: {total_tweets / len(thread_groups):.1f}")
    
    # Process each thread group
    results = []
    for group_key, thread_rows in thread_groups.items():
        result = await process_thread_group(group_key, thread_rows, dry_run=not args.execute)
        results.append(result)
        
        # Small delay between threads to avoid rate limits
        await asyncio.sleep(1)
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful
    print(f"Processed: {len(results)} threads")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    
    if args.execute:
        print("\n✅ Updates applied to tweets sheet.")
    else:
        print("\n[DRY RUN] No changes made. Run with --execute to apply updates.")
    
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())










