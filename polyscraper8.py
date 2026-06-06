import discord
import tweepy
import pandas as pd
import asyncio
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import os
import requests
import gspread
from google.oauth2.service_account import Credentials

# 🔹 Twitter API Credentials
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAALmTzgEAAAAAf4intzxlqvcj3fBIK01%2FyzjEs2g%3DjWPBwfrrl4PBbLft9lZWkb2jAZrk944FYkvEkq7Wt4Q8ZilvGh"

# 🔹 Discord Bot Token
DISCORD_BOT_TOKEN = "MTM0NTQxODEwNjA5MjEyNjM0OQ.G9rdJJ.Dx9f21Snle2udCYedimZBj0MLhiCWuHD3FJagI"
YOUR_DISCORD_USER_ID = 1152387252232663091  # Replace with your Discord user ID for notifications

# 🔹 Twitter Client
twitter_client = tweepy.Client(bearer_token=BEARER_TOKEN)

# 🔹 Discord Bot Setup
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# 🔹 CSV Storage
CSV_FILE = "tweets.csv"

# 🔹 List of Banned Keywords
BANNED_WORDS = ["scam", "giveaway", "airdrop", "free money"]

# 🔹 Scheduler for Automated Engagement Tracking
scheduler = AsyncIOScheduler()

# ====================== HELPERS =============================

def get_google_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1CxpNczgrKYZib6MC_ucZW3uj_BhkKWPpH8hsHprKtPI/edit?usp=sharing")
    worksheet = sheet.worksheet("filtered_tweets_updated")
    return worksheet

def validate_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

# Autocomplete for Query
async def query_autocomplete(interaction: discord.Interaction, current: str):
    options = [
        "@polymer_labs",
        "#polymer_university",
        "Polymer Labs",
        "Prove API"
    ]

    combined_option = '(@polymer_labs OR #polymer_university OR "Polymer Labs" OR "Prove API")'

    choices = [
        app_commands.Choice(name="All Polymer Queries", value=combined_option)
    ]

    # Add individual options matching current input
    choices.extend([
        app_commands.Choice(name=option, value=option)
        for option in options if current.lower() in option.lower()
    ])

    return choices

# ====================== MAIN FUNCTION =============================

BANNED_WORDS = ["scam", "airdrop"]  # Example
CSV_FILE = "tweets.csv"

async def search_tweets(query, start_date=None, end_date=None, max_results=None):
    now = datetime.utcnow()
    tweet_data = []
    total_fetched = 0

    # ----- Validate Dates -----
    def validate_date(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

    start_date_valid = validate_date(start_date)
    end_date_valid = validate_date(end_date)

    if not start_date_valid or not end_date_valid:
        return "❌ Invalid date format. Use YYYY-MM-DD."

    if start_date_valid > end_date_valid:
        return "❌ Start date must be before end date."

    if start_date_valid < (now - timedelta(days=7)).date():
        return "❌ Start date too old. Twitter API only allows tweets from the past 7 days."

    # ----- Create 12-hour intervals -----
    seven_day_cutoff = now - timedelta(days=7)
    interval_start = max(datetime.combine(start_date_valid, datetime.min.time()), seven_day_cutoff)
    interval_end = datetime.combine(end_date_valid, datetime.max.time())

    blocks = []
    while interval_start < interval_end:
        next_block = interval_start + timedelta(hours=12)
        # Ensure no future dates
        block_end = min(next_block, now - timedelta(seconds=10))
        if interval_start >= block_end:
            break
        blocks.append((interval_start, block_end))
        interval_start = next_block

    print(f"🔍 Dividing into {len(blocks)} time blocks...")

    for idx, (block_start, block_end) in enumerate(blocks):
        print(f"⏱ Block {idx+1}: {block_start} to {block_end}")
        result = await search_block(query, block_start, block_end, max_results, tweet_data, total_fetched)
        if isinstance(result, str):  # Error
            print(result)
            continue
        total_fetched += result
        await asyncio.sleep(2)  # Throttle between blocks

    # Save to CSV
    if tweet_data:
        df = pd.DataFrame(tweet_data, columns=["Date", "User ID", "Username", "URL", "Likes", "Retweets", "Replies"])
        df.to_csv(CSV_FILE, mode="a", header=False, index=False)

    return f"✅ Collected {total_fetched} tweets."

# ----- Helper function for each block -----
async def search_block(query, start_dt, end_dt, max_results, tweet_data, total_fetched):
    start_time = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_time = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    next_token = None
    block_fetched = 0

    try:
        while True:
            tweets = twitter_client.search_recent_tweets(
                query=f"{query} -is:retweet",
                tweet_fields=["created_at", "text", "author_id", "id"],
                expansions="author_id",
                user_fields=["username"],
                start_time=start_time,
                end_time=end_time,
                max_results=100,
                next_token=next_token
            )

            if not tweets.data:
                break

            users = {u.id: u.username for u in tweets.includes["users"]} if "users" in tweets.includes else {}

            for tweet in tweets.data:
                if any(word.lower() in tweet.text.lower() for word in BANNED_WORDS):
                    continue
                tweet_url = f"https://twitter.com/{users.get(tweet.author_id, 'unknown')}/status/{tweet.id}"
                tweet_data.append([
                    tweet.created_at,
                    tweet.author_id,
                    users.get(tweet.author_id, 'unknown'),
                    tweet_url,
                    0, 0, 0
                ])
                block_fetched += 1

            total_fetched += block_fetched
            next_token = tweets.meta.get("next_token")
            if not next_token:
                break

            if max_results and total_fetched >= max_results:
                break

            await asyncio.sleep(1)  # Throttle

    except tweepy.errors.TooManyRequests:
        return "⚠️ Twitter rate limit hit. Try again later."
    except tweepy.errors.BadRequest as e:
        return f"❌ Bad Request Error: {e}"
    except Exception as e:
        return f"❌ Unexpected error: {e}"

    return block_fetched
# ====================== SLASH COMMANDS =============================

@tree.command(name="clear_csv", description="Clear the contents of the tweets.csv file.")
async def clear_csv(interaction: discord.Interaction):
    try:
        with open(CSV_FILE, "w") as f:
            f.truncate(0)  # Clears the file
        await interaction.response.send_message("🧹 `tweets.csv` has been cleared.", ephemeral=True)
        print("✅ tweets.csv cleared by slash command")
    except Exception as e:
        print(f"❌ Error clearing CSV file: {e}")
        await interaction.response.send_message(f"❌ Failed to clear CSV file: {e}", ephemeral=True)


@tree.command(name="run_test", description="Fetch up to 10 tweets with a specified query and date range.")
@app_commands.describe(
    query="Search by hashtag, mention, or account",
    start_date="Start date (YYYY-MM-DD, optional)",
    end_date="End date (YYYY-MM-DD, optional)",
    include_replies="Include replies (default: No)"
)
@app_commands.autocomplete(query=query_autocomplete)
async def run_test(interaction: discord.Interaction, query: str, start_date: str = None, end_date: str = None, include_replies: bool = False):
    await interaction.response.send_message(f"🔍 Running test fetch for up to 10 tweets with query: `{query}`", ephemeral=True)

    if include_replies:
        query += " is:reply"
    else:
        query += " -is:reply"

    result = await search_tweets(query, start_date=start_date, end_date=end_date, max_results=10)

    if isinstance(result, str):
        await interaction.followup.send(result)
    elif result > 0:
        user = await bot.fetch_user(YOUR_DISCORD_USER_ID)
        await user.send(f"✅ Test fetch collected **{result}** tweets. Check `{CSV_FILE}`.")
    else:
        await interaction.followup.send("❌ No new tweets found.")

@tree.command(name="run_scraper", description="Run full scraper with a specified query and date range.")
@app_commands.describe(
    query="Search by hashtag, mention, or account",
    start_date="Start date (YYYY-MM-DD, optional)",
    end_date="End date (YYYY-MM-DD, optional)",
    include_replies="Include replies (default: No)"
)
@app_commands.autocomplete(query=query_autocomplete)
async def run_scraper(interaction: discord.Interaction, query: str, start_date: str = None, end_date: str = None, include_replies: bool = False):
    await interaction.response.send_message(f"🔍 Running full scraper with query: `{query}`", ephemeral=True)

    if include_replies:
        query += " is:reply"
    else:
        query += " -is:reply"

    result = await search_tweets(query, start_date=start_date, end_date=end_date, max_results=500)

    if isinstance(result, str):
        await interaction.followup.send(result)
    elif result > 0:
        user = await bot.fetch_user(YOUR_DISCORD_USER_ID)
        await user.send(f"✅ Scraper collected **{result}** tweets. Check `{CSV_FILE}`.")
    else:
        await interaction.followup.send("❌ No new tweets found.")

@tree.command(name="update_metrics_from_sheet", description="Update tweet engagement metrics from Google Sheet.")
@app_commands.describe(start_row="Row to start reading tweet URLs from (default: 2)")
async def update_metrics_from_sheet(interaction: discord.Interaction, start_row: int = 2):
    await interaction.response.send_message("📊 Starting tweet metric update...", ephemeral=True)
    print("🔧 /update_metrics_from_sheet called")

    try:
        worksheet = get_google_sheet()
        print("✅ Connected to Google Sheet")

        # Calculate range: rows start from `start_row`, get up to 1000 rows
        end_row = start_row + 999
        urls = worksheet.col_values(4)[start_row - 1:end_row]  # adjust for 0-based index
        print(f"📝 Found {len(urls)} tweet URLs from row {start_row} to {end_row}")

        tweet_id_map = []
        tweet_ids = []

        for idx, url in enumerate(urls):
            row_number = start_row + idx
            try:
                tweet_id = url.strip().split("/")[-1].strip()
                if tweet_id.isdigit():
                    tweet_ids.append(tweet_id)
                    tweet_id_map.append((row_number, tweet_id))
                else:
                    print(f"⚠️ Skipped invalid tweet ID at row {row_number}: {tweet_id}")
            except Exception as e:
                print(f"⚠️ Error parsing tweet ID at row {row_number}: {url} -> {e}")

        print(f"🔢 Parsed {len(tweet_ids)} tweet IDs")

        def chunks(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        results = {}
        for batch_index, batch in enumerate(chunks(tweet_ids, 100)):
            retries = 0
            while retries < 3:
                try:
                    print(f"📤 Fetching batch {batch_index + 1} (size {len(batch)})")
                    response = twitter_client.get_tweets(ids=batch, tweet_fields=["public_metrics"])
                    if not response.data:
                        print(f"⚠️ Empty response in batch {batch_index + 1}")
                    for tweet in response.data:
                        metrics = tweet.data["public_metrics"]
                        results[str(tweet.id)] = [
                            metrics.get("retweet_count", 0),
                            metrics.get("reply_count", 0),
                            metrics.get("like_count", 0),
                            metrics.get("quote_count", 0),
                            metrics.get("impression_count", 0),
                        ]
                    print(f"📦 Got metrics for {len(response.data)} tweets in batch {batch_index + 1}")
                    await asyncio.sleep(2)
                    break
                except tweepy.errors.TooManyRequests:
                    wait_time = 60
                    retries += 1
                    print(f"⏳ Rate limit hit. Waiting {wait_time}s before retrying (attempt {retries}/3)...")
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    print(f"❌ Error fetching batch {batch_index + 1}: {e}")
                    break

        print(f"🧠 Result keys (sample): {list(results.keys())[:5]}")
        print(f"📊 Total tweet metrics fetched: {len(results)}")

        updates = []
        for row, tweet_id in tweet_id_map:
            tweet_id_str = str(tweet_id).strip()
            if tweet_id_str in results:
                metrics = results[tweet_id_str]
                updates.append({
                    "range": f"I{row}:M{row}",
                    "values": [metrics]
                })
            else:
                print(f"⛔ tweet_id {tweet_id_str} not found in results.keys()")

        print(f"🧾 Prepared {len(updates)} row updates for the sheet")
        if updates:
            try:
                worksheet.batch_update([{
                    "range": update["range"],
                    "values": update["values"]
                } for update in updates])
                print("✅ Google Sheet successfully updated")
            except Exception as e:
                print(f"❌ Google Sheets update failed: {e}")
        else:
            print("⚠️ No updates to write")

        await interaction.followup.send("✅ Tweet metrics update attempt complete. Check your sheet and logs.")

    except Exception as e:
        print(f"❌ General error in update_metrics_from_sheet: {e}")
        await interaction.followup.send(f"❌ Failed to update sheet: {e}")



# ====================== RATE LIMIT CHECK =============================

@tree.command(name="check_limit", description="Check your Twitter API rate limits.")
async def check_limit(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Checking Twitter API rate limits...", ephemeral=True)

    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        limit = response.headers.get("x-rate-limit-limit")
        remaining = response.headers.get("x-rate-limit-remaining")
        reset_time = int(response.headers.get("x-rate-limit-reset"))
        reset_timestamp = datetime.fromtimestamp(reset_time).strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f"📊 **Twitter API Rate Limits:**\n"
            f"- 🔄 Limit: `{limit}` requests\n"
            f"- 🟢 Remaining: `{remaining}` requests\n"
            f"- 🕒 Resets at: `{reset_timestamp}` (UTC)"
        )
        await interaction.followup.send(message)
    else:
        await interaction.followup.send(f"⚠️ Error: {response.status_code} - {response.text}")

        # ====================== Text Scraper =============================

@tree.command(name="update_text_from_sheet", description="Update tweet text and time from Google Sheet into columns A and S.")
@app_commands.describe(
    starting_row="Row number to begin from (default is 2)"
)
async def update_text_from_sheet(interaction: discord.Interaction, starting_row: int = 2):
    await interaction.response.send_message(f"📝 Starting tweet text & time update from row {starting_row} on 'tweets' sheet...", ephemeral=True)
    print(f"🔧 /update_text_from_sheet called (starting from row {starting_row})")

    try:
        worksheet = get_google_sheet().spreadsheet.worksheet("filtered_tweets_updated")
        print("✅ Connected to Google Sheet 'filtered_tweets_updated'")
        urls = worksheet.col_values(4)  # Column D
        texts = worksheet.col_values(19)  # Column S
        times = worksheet.col_values(1)   # Column A

        max_row = len(urls)
        tweet_ids = []
        row_map = []

        for i in range(starting_row - 1, max_row):
            url = urls[i].strip() if i < len(urls) else ""
            text = texts[i].strip() if i < len(texts) else ""

            if not url:
                continue

            if text:
                continue  # skip rows with text already present

            try:
                tweet_id = url.split("/")[-1].strip()
                if tweet_id.isdigit():
                    tweet_ids.append(tweet_id)
                    row_map.append(i + 1)  # Google Sheets is 1-indexed
                else:
                    print(f"⚠️ Skipped invalid tweet ID at row {i + 1}: {tweet_id}")
            except Exception as e:
                print(f"⚠️ Error parsing tweet ID at row {i + 1}: {e}")

        print(f"🔢 Will fetch text for {len(tweet_ids)} tweets")

        def chunks(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        for batch_index, batch in enumerate(chunks(list(zip(row_map, tweet_ids)), 50)):
            retries = 0
            while retries < 3:
                try:
                    print(f"📤 Fetching batch {batch_index + 1} (size {len(batch)})")
                    response = twitter_client.get_tweets(
                        ids=[tid for _, tid in batch],
                        tweet_fields=["text", "created_at"]
                    )

                    if not response.data:
                        print(f"⚠️ Empty response in batch {batch_index + 1}")
                        break

                    id_to_data = {str(tweet.id): (tweet.text, tweet.created_at.strftime("%Y-%m-%d %H:%M:%S")) for tweet in response.data}

                    batch_updates = []

                    for row, tid in batch:
                        data = id_to_data.get(tid)
                        if data:
                            tweet_text, created_at = data
                            batch_updates.append({
                                "range": f"S{row}",
                                "values": [[tweet_text]]
                            })
                            batch_updates.append({
                                "range": f"A{row}",
                                "values": [[created_at]]
                            })

                    if batch_updates:
                        worksheet.batch_update(batch_updates)
                        print(f"✅ Updated {len(batch)//2} rows with text and time (batch {batch_index + 1})")
                    else:
                        print(f"⚠️ No updates to write for batch {batch_index + 1}")

                    await asyncio.sleep(10)
                    break

                except tweepy.errors.TooManyRequests:
                    wait_time = 60
                    retries += 1
                    print(f"⏳ Rate limit hit. Waiting {wait_time}s before retrying (attempt {retries}/3)...")
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    print(f"❌ Error in batch {batch_index + 1}: {e}")
                    break

        await interaction.followup.send("✅ Tweet text & time update complete. Check columns A and S of your sheet.")

    except Exception as e:
        print(f"❌ General error in update_text_from_sheet: {e}")
        await interaction.followup.send(f"❌ Failed to update sheet: {e}")

        # ====================== BOT EVENTS =============================

@bot.event
async def on_ready():
    await tree.sync()
    scheduler.start()
    print(f"✅ Bot is online as {bot.user}")

# 🔹 Run the Bot
bot.run("MTM0NTQxODEwNjA5MjEyNjM0OQ.G9rdJJ.Dx9f21Snle2udCYedimZBj0MLhiCWuHD3FJagI")
