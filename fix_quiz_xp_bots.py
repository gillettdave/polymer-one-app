"""
Retroactive fix script: Remove XP from users who earned quiz XP but don't meet minimum Discord posts requirement.

This script:
1. Reads all XP events from the xp_events sheet
2. For each quiz_completion XP event, checks if the user meets minimum Discord posts requirement
3. Uses configurable minimum from state.json (default: 3, set via /bot_set_quiz_min_posts)
4. Excludes channel 933812975297527818 from message counting
5. Removes XP events for users who don't meet the criteria
6. Updates the xp_events sheet to remove those entries
"""

import os
import sys
import asyncio
import discord
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Tuple

# Load environment variables
load_dotenv()

# Import from PolyOne.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PolyOne import (
    get_xp_events_ws,
    count_discord_messages_for_user,
    get_min_discord_posts,
    log_or_print,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_SPREADSHEET_NAME,
    XP_EVENTS_SHEET_NAME,
)

# Discord bot setup
TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))  # Add this to your .env if not present

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = discord.Client(intents=intents)


async def get_guild():
    """Get the Discord guild."""
    if not bot.is_ready():
        await bot.wait_until_ready()
    
    if GUILD_ID:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            return guild
    
    # Fallback: get first guild
    if bot.guilds:
        return bot.guilds[0]
    
    return None


async def find_quiz_xp_events_to_remove() -> List[Dict[str, Any]]:
    """Find all quiz XP events for users who don't meet minimum Discord posts requirement."""
    ws = get_xp_events_ws()
    rows = ws.get_all_values()
    
    if not rows or len(rows) < 2:
        print("No XP events found.")
        return []
    
    header = rows[0]
    
    # Find column indices
    discord_id_col = None
    source_col = None
    amount_col = None
    reference_type_col = None
    
    for idx, col_name in enumerate(header):
        col_lower = col_name.lower()
        if "discord_id" in col_lower or (col_name == "ID" and discord_id_col is None):
            discord_id_col = idx
        elif "source" in col_lower:
            source_col = idx
        elif "amount" in col_lower or "xp" in col_lower:
            amount_col = idx
        elif "reference_type" in col_lower or "reference" in col_lower:
            reference_type_col = idx
    
    if discord_id_col is None or source_col is None:
        print("Error: Could not find required columns in xp_events sheet.")
        return []
    
    # Get guild
    guild = await get_guild()
    if not guild:
        print("Error: Could not find Discord guild.")
        return []
    
    print(f"Found guild: {guild.name}")
    print(f"Scanning {len(rows) - 1} XP events...")
    
    events_to_remove = []
    checked_users = {}  # Cache: user_id -> (post_count, meets_requirement)
    
    for row_idx, row in enumerate(rows[1:], start=2):  # Start at 2 (row 1 is header)
        if len(row) <= max(discord_id_col, source_col):
            continue
        
        source = row[source_col].lower() if len(row) > source_col else ""
        discord_id_str = row[discord_id_col] if len(row) > discord_id_col else ""
        
        # Only check quiz_completion events
        if source != "quiz_completion":
            continue
        
        if not discord_id_str:
            continue
        
        try:
            discord_id = int(discord_id_str)
        except (ValueError, TypeError):
            continue
        
        # Check if we've already checked this user
        if discord_id in checked_users:
            post_count, meets_requirement = checked_users[discord_id]
        else:
            # Count Discord posts for this user
            try:
                post_count = await count_discord_messages_for_user(guild, discord_id)
                min_posts_required = get_min_discord_posts()
                meets_requirement = post_count >= min_posts_required
                checked_users[discord_id] = (post_count, meets_requirement)
                
                if row_idx % 100 == 0:
                    print(f"Checked {row_idx - 1} events, found {len(events_to_remove)} to remove...")
            except Exception as e:
                print(f"Error checking user {discord_id}: {e}")
                # On error, don't remove (fail safe)
                checked_users[discord_id] = (0, True)
                continue
        
        # If user doesn't meet requirement, mark this event for removal
        if not meets_requirement:
            amount = 0
            if amount_col is not None and len(row) > amount_col:
                try:
                    amount = int(row[amount_col])
                except (ValueError, TypeError):
                    pass
            
            events_to_remove.append({
                "row_index": row_idx,
                "discord_id": discord_id,
                "amount": amount,
                "source": source,
            })
    
    return events_to_remove


async def remove_xp_events(events_to_remove: List[Dict[str, Any]], dry_run: bool = True):
    """Remove XP events from the sheet."""
    if not events_to_remove:
        print("No events to remove.")
        return
    
    min_posts_required = get_min_discord_posts()
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Found {len(events_to_remove)} quiz XP events to remove:")
    print(f"  Minimum posts required: {min_posts_required}")
    print(f"  Excluded channel: 933812975297527818")
    
    # Group by user for summary
    by_user = {}
    total_xp_to_remove = 0
    for event in events_to_remove:
        user_id = event["discord_id"]
        if user_id not in by_user:
            by_user[user_id] = {"count": 0, "total_xp": 0}
        by_user[user_id]["count"] += 1
        by_user[user_id]["total_xp"] += event["amount"]
        total_xp_to_remove += event["amount"]
    
    print(f"\nSummary:")
    print(f"  - {len(by_user)} unique users affected")
    print(f"  - {len(events_to_remove)} XP events to remove")
    print(f"  - {total_xp_to_remove} total XP to remove")
    print(f"  - Minimum posts required: {min_posts_required}")
    
    print(f"\nTop 10 users by XP to remove:")
    sorted_users = sorted(by_user.items(), key=lambda x: x[1]["total_xp"], reverse=True)[:10]
    for user_id, data in sorted_users:
        post_count = checked_users.get(user_id, (0, False))[0]
        print(f"  - User {user_id}: {data['count']} events, {data['total_xp']} XP (has {post_count} posts, need {min_posts_required}+)")
    
    if dry_run:
        print("\n[DRY RUN] No changes made. Run with --execute to actually remove events.")
        return
    
    # Actually remove the events
    ws = get_xp_events_ws()
    
    # Sort by row index in descending order (so we can delete from bottom to top)
    events_to_remove.sort(key=lambda x: x["row_index"], reverse=True)
    
    print(f"\nRemoving {len(events_to_remove)} events...")
    removed_count = 0
    
    for event in events_to_remove:
        try:
            row_idx = event["row_index"]
            ws.delete_rows(row_idx)
            removed_count += 1
            
            if removed_count % 50 == 0:
                print(f"  Removed {removed_count}/{len(events_to_remove)} events...")
        except Exception as e:
            print(f"  Error removing row {event['row_index']}: {e}")
    
    print(f"\n✅ Removed {removed_count} XP events.")


async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Remove quiz XP from users with <3 Discord posts")
    parser.add_argument("--execute", action="store_true", help="Actually remove events (default is dry run)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Quiz XP Bot Removal Script")
    print("=" * 60)
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print()
    
    # Start bot
    print("Connecting to Discord...")
    await bot.start(TOKEN)
    
    try:
        # Find events to remove
        events_to_remove = await find_quiz_xp_events_to_remove()
        
        # Remove events
        await remove_xp_events(events_to_remove, dry_run=not args.execute)
        
    finally:
        await bot.close()
    
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())

