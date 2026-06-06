# PolyOne Documentation Bundle

This bundle includes:

- PolyOne Overview
- Technical Architecture
- Admin Guide
- Developer Guide

---


---

## POLYONE OVERVIEW

# PolyOne: The Unified Growth & XP Bot for the Polymer Community

PolyOne is an all–in–one Discord bot designed to turn Polymer’s protocol growth into an interactive community experience.
It combines real–time on–chain metrics, an XP system, content–creation rewards, and (optionally) quizzes and prediction games
into a single, unified system.

---

## 1. What PolyOne Does

### 1.1 Live Metrics & Milestones

PolyOne connects to Polymer’s public analytics endpoints and regularly checks:

- **Top Transactions Leaderboard**  
  From `https://analytics.polymer.zone/api/metrics/leaderboard/top-transactions?environment=mainnet`  
  PolyOne watches the top 10 transactions by USD volume and alerts the community when a **new transaction** enters the top 10.

- **Total Volume & Milestones**  
  From `https://analytics.polymer.zone/api/analytics?environment=mainnet`  
  PolyOne tracks total USD volume and posts a celebration message every time total volume crosses a new **0.1B milestone**
  (e.g., $1.0B → $1.1B → $1.2B, etc.).

- **Daily Status Summary**  
  Once per day at 23:59 UTC, PolyOne posts a concise summary of:
  - **Total Daily Volume (24h)** - Total volume transacted in the past 24 hours
  - **Biggest Transfer Today** - The largest individual transaction from the past 24 hours
  - **Average Transaction Size (24h)** - Average size of all transactions from the past 24 hours (calculated from total volume and transaction count)
  - Total volume and its equivalent in billions
  - Last recorded milestone
  - Top 10 transactions (all-time)
  - Dashboard's last update time

- **Volume Counter Channel**  
  PolyOne can update a voice channel name to reflect current volume and 24h percentage change, e.g.:  
  `Polymer Volume: $1.063B (+4.2%)`

### 1.2 Unified XP System

PolyOne introduces a **single XP ledger** for all community actions.  
XP is logged as events in a Google Sheet (`xp_events`) and aggregated into totals (`xp_totals`).

XP can be earned from:
- High–quality tweets about Polymer
- Polymer University quizzes (optional integration)
- Future prediction games or on–chain metrics quizzes
- Manual XP awards from admins

This allows the community to see a single, consistent measure of contribution.

### 1.3 Tweet Submission & Grading

PolyOne lets members submit tweets using two commands:

- `/set_twitter @handle` – link your Discord account to an X/Twitter handle
- `/submit_tweet <tweet_url>` – submit a tweet for review and XP

The bot:
1. Validates and normalizes the tweet URL
2. Extracts the tweet ID
3. Optionally fetches tweet text via the X/Twitter API (if a bearer token is configured)
4. Uses an AI–based rubric to grade the tweet (if OpenAI is configured)
5. Writes the tweet, grade, and XP into the `tweets` sheet
6. Logs a corresponding XP event into `xp_events`

Users can then see their progress via:
- `/xp_me` – show total XP
- `/xp_leaderboard` – show top XP holders
- `/check_tweets` – see how many tweets they’ve submitted
- `/polyu_rank` – look up their Polymer University rank (if the sheet is set up)

---

## 2. Why PolyOne Exists

Polymer’s growth story can be hard to follow just by looking at dashboards. PolyOne brings that story into Discord, where
the community already lives, and rewards people for helping tell it.

It aims to:

- Make blockchain growth feel tangible and exciting
- Reward people for learning, teaching, and creating content
- Align incentives around long–term participation, not one–off events
- Provide a single, extensible XP system the team can build on over time

---

## 3. How XP Fits into the Community Journey

PolyOne is designed to be flexible enough to support:

- **Ambassador programs**
- **Campaigns and seasons**
- **Tiered roles and perks**
- **Early access and allowlists**
- **Polymer University “graduates” and advanced contributors**

By centralising XP, the community team can plug in new initiatives without reinventing scoring every time.

---

## 4. How to Use This Bot

For everyday community members:

- Link your X account: `/set_twitter @your_handle`
- Share content: `/submit_tweet <url>`
- Track your progress: `/xp_me`, `/xp_leaderboard`
- Follow Polymer’s growth: watch the metrics channel for milestones & top transactions

For more technical details, see the **Technical Architecture**, **Admin Guide**, and **Developer Guide** documents.


---

## POLYONE TECHNICAL ARCHITECTURE

# PolyOne Technical Architecture

This document describes the internal design of the PolyOne Discord bot, its main components, data flows, and
integrations with external services.

---

## 1. High–Level Design

PolyOne is a single Python application built around:

- `discord.py` (v2) – for slash commands, tasks, channel updates
- `aiohttp` – for calling Polymer analytics APIs and Twitter/X API
- `gspread` + Google service accounts – for reading/writing Google Sheets
- `openai` – for tweet grading (optional but recommended)
- A small local CSV file for Discord ↔ Twitter handle mapping

It is designed as a **monolithic bot** with clearly separated modules:

1. Metrics & Milestones
2. Volume Channel Renaming
3. XP Ledger
4. Tweet Submission & Grading
5. (Optional) Polymer University integrations
6. (Future) Prediction games and metrics quizzes

The bot is configured via environment variables (`.env`) and uses a local JSON `state.json` to track persistent runtime state
such as last milestones and announced transaction IDs.

---

## 2. External Integrations

### 2.1 Polymer Analytics Endpoints

PolyOne uses two key endpoints:

- **Top 10 Transactions**  
  `GET https://analytics.polymer.zone/api/metrics/leaderboard/top-transactions?environment=mainnet`  
  Response contains an array `transactions` where each item includes:
  - TransactionID, UserAddress, AmountUSD, TokenName, TokenSymbol,
    Application, SourceChain, DestinationChain, Timestamp

- **Analytics Overview**  
  `GET https://analytics.polymer.zone/api/analytics?environment=mainnet`  
  Response contains an `analytics` object with at least `totalValue` (total volume in USD).  
  May also include `transactionCount` or similar fields for total transaction count.

These calls are made via `aiohttp` inside background tasks.

### 2.2 Discord

The bot uses:

- Slash commands via `bot.tree.command`
- Background tasks via `discord.ext.tasks.loop`
- Channel updates for:
  - Posting messages in a configured text channel
  - Renaming a configured voice channel to show volume and 24h change

### 2.3 Google Sheets

A Google service account is used to authenticate with the Sheets API:
- The service account is granted **Editor** access to the target Sheet
- `gspread` is used for all read/write operations

Core worksheets:

- `xp_events` – append–only XP ledger
- `xp_totals` – aggregate XP per user (via formulas)
- `tweets` – raw tweet submissions + grading results
- `leaderboard` – existing Polymer University leaderboard (optional for `/polyu_rank`)

### 2.4 Twitter/X API (optional)

If a `TWITTER_BEARER_TOKEN` is configured, the bot can call the Twitter/X v2 API to fetch tweet text for grading.

### 2.5 OpenAI (optional but recommended)

If `OPENAI_API_KEY` is set, the bot uses the OpenAI Chat Completions API to evaluate tweet content against
a rubric and assign a numerical score. That score is then mapped to XP.

---

## 3. Internal Modules

### 3.1 State Management

File: `state.json`

Tracks:

- `last_top10_ids` – IDs of the current top 10 transactions
- `announced_top10_ids` – transaction IDs already announced to avoid duplicates
- `last_milestone` – last celebrated volume milestone in billions
- `initialized_milestone` – whether initial baseline was set
- `initialized_leaderboard` – whether initial top 10 snapshot was taken
- `volume_history` – recent history of total volume snapshots for 24h change calculation
- `transaction_count_history` – recent history of total transaction count snapshots for daily metrics calculation
- `biggest_transaction_history` – recent history of biggest transaction seen at each snapshot for daily metrics

### 3.2 Metrics & Milestones

**Task:** `check_leaderboard`

- Runs every `POLL_INTERVAL` seconds (default: 600)
- Fetches top transactions
- On first run: records baseline, marks them as announced without alerts
- On subsequent runs:
  - Filters out transactions older than 24h
  - If a new, fresh TransactionID appears in top 10:
    - Posts an `@everyone` announcement with full details
    - Stores that TransactionID in `announced_top10_ids`

**Task:** `check_volume`

- Runs every `POLL_INTERVAL` seconds
- Fetches analytics overview and leaderboard data
- Extracts totalValue (total USD volume) and transaction count (if available)
- Extracts biggest transaction from leaderboard
- Maintains `last_milestone` in billions with a 0.1B step
- If a new milestone is reached:
  - Posts an `@everyone` celebration message
  - Updates `last_milestone`

This task also:
- Feeds volume data into the volume history for 24h change calculation
- Tracks transaction count and biggest transaction history for daily metrics
- Calls `update_volume_channel` to update the voice channel name

**Daily Summary Task:**

- Runs once per day at 23:59 UTC
- Calculates 24h metrics by comparing current values with values from 24 hours ago:
  - **Total Daily Volume (24h)** = current_total_volume - volume_24h_ago
  - **Daily Transaction Count** = current_count - count_24h_ago (if available)
  - **Average Transaction Size (24h)** = total_daily_volume / daily_transaction_count
  - **Biggest Transfer Today** = largest transaction from `biggest_transaction_history` in past 24h

### 3.3 Volume Channel Renaming

Function: `update_volume_channel(total_value, pct_change)`

- Computes `billions = total_value / 1_000_000_000`
- Computes sign and absolute 24h percentage change
- Renames the configured voice channel to:  
  `Polymer Volume: $X.XXXB (+Y.Y%)`

### 3.4 XP Engine

#### 3.4.1 xp_events

Each XP event is a row with:

- timestamp
- discord_id
- discord_name
- twitter_handle (optional)
- source (e.g., `tweet_grade`, `poly_u_quiz`, `manual`)
- amount (integer XP)
- reference_type (e.g., `tweet`, `quiz`)
- reference_id (e.g., tweet_id, quiz_id)
- notes

Function: `add_xp(...)` appends rows to this sheet.

#### 3.4.2 xp_totals

Uses Google Sheets formulas to compute total XP per user:

- Column A: `discord_id`
- Column B: `discord_name`
- Column C: `total_xp` (SUM of all xp_events for that id)

`get_total_xp(discord_id)` looks up total XP here.

#### 3.4.3 Discord Commands

- `/xp_me` – shows the caller’s total XP
- `/xp_leaderboard` – shows the top users by XP

### 3.5 Tweet Submission & Grading

#### 3.5.1 Twitter Handle Mapping

A local CSV (`twitter_handles.csv`) stores mappings of:
- discord_id
- discord_name
- twitter_handle

Commands:

- `/set_twitter @handle`
  - Normalizes and saves handle
- Helpers:
  - `upsert_twitter_handle(...)`
  - `get_twitter_handle_for_user(discord_id)`

#### 3.5.2 tweets Sheet

Columns typically include:

- Date
- Tweet ID
- Member
- URL
- Graded
- Score
- XP Awarded
- Tweet Text

#### 3.5.3 `/submit_tweet` Flow

1. Validates the caller has set a Twitter handle
2. Validates and normalizes tweet URL
3. Extracts Tweet ID
4. Checks if Tweet ID already exists in the sheet
5. Appends a new row with Date, Tweet ID, Member, URL
6. Optionally:
   - Fetches tweet text from X API
   - Grades the tweet via OpenAI using a rubric
   - Writes grading fields to the row
   - Logs XP via `add_xp(...)`

#### 3.5.4 Supporting Commands

- `/check_tweets` – counts tweets submitted by the caller
- `/polyu_rank` – shows your rank in the XP leaderboard (based on `xp_totals` sheet)

---

## 4. Configuration & Deployment

### 4.1 Environment Variables

Key variables include:

- `DISCORD_TOKEN`
- `METRICS_CHANNEL_ID`
- `VOLUME_CHANNEL_ID`
- `GOOGLE_SERVICE_ACCOUNT_FILE`
- `GOOGLE_SPREADSHEET_NAME`
- `XP_EVENTS_SHEET_NAME`, `XP_TOTALS_SHEET_NAME`
- `TWEETS_SHEET_NAME`
- `TWITTER_HANDLES_CSV`
- `OPENAI_API_KEY` (optional)
- `TWITTER_BEARER_TOKEN` (optional)
- `POLL_INTERVAL`

### 4.2 Requirements

- `discord.py`
- `aiohttp`
- `gspread`
- `google-auth`
- `python-dotenv`
- `openai` (if grading is enabled)

---

## 5. Extensibility

New XP sources can be added by:

1. Implementing logic to detect the event (e.g., quiz completion)
2. Calling `add_xp(...)` with appropriate metadata
3. Adding optional Google Sheet columns/visualizations

New Discord functionality (e.g., prediction games) can be integrated as new slash commands and background tasks reusing
the same XP and state infrastructure.


---

## POLYONE ADMIN GUIDE

# PolyOne Admin & Operations Guide

This guide is for community managers, moderators, and operators who run PolyOne in production.

---

## 1. What Admins Control

As an admin, you mainly control:

- Where the bot posts (metrics channel, volume channel)
- Who can use which commands
- When you enable or disable certain modules (e.g., tweets, quizzes)
- How XP is interpreted (for roles, perks, or campaigns)

PolyOne is intentionally conservative: most of what it does is **read** public data and **append** records to Google Sheets.
It does not delete or overwrite existing rows by default.

---

## 2. Initial Setup Checklist

1. **Invite the bot** to your Discord server with:
   - `Send Messages`
   - `Embed Links`
   - `Manage Channels` (if using the volume channel rename)
   - `Use Application Commands`

2. Create or select a **metrics text channel** and record its ID as `METRICS_CHANNEL_ID` in `.env`.

3. Create a **voice channel** for the volume counter (optional) and record its ID as `VOLUME_CHANNEL_ID`.

4. Set up a **Google service account**, download its JSON key, and:
   - Save it as `service_account.json` beside the bot
   - Share the target Google Sheet with the service account email (Editor access)

5. Configure the `.env` file with:
   - Discord token
   - Sheet names
   - Optional: OpenAI API key, Twitter bearer token

6. Ensure the worksheets exist with the correct headers:
   - `xp_events`
   - `xp_totals`
   - `tweets`
   - `leaderboard` (if using Polymer University rank)

7. Run the bot and verify:
   - No exceptions in logs
   - Commands appear in Discord (might take a minute to sync)

---

## 3. Everyday Operation

### 3.1 Watching Metrics

PolyOne will automatically:

- Announce new top 10 transactions (under 24h old)
- Announce when total volume crosses 0.1B steps
- Post a daily summary at 23:59 UTC

As an admin, you mainly need to:

- Keep an eye on the metrics channel for activity
- Adjust channel permissions if you want to reduce pings
- Optionally pin important announcements

### 3.2 Managing XP

Typical flows:

- Check a user’s XP: `/xp_me`
- See the leaderboard: `/xp_leaderboard`

If you add manual XP commands such as `/xp_admin_give`, you will be able to:

- Reward custom contributions
- Correct mistakes
- Run ad–hoc campaigns

All XP events should go through `xp_events` for auditability.

### 3.3 Tweet Campaigns

For a tweet/X campaign:

1. Instruct users to link their handle: `/set_twitter`
2. Allow submissions via: `/submit_tweet <url>`
3. Review the `tweets` sheet for:
   - `Graded` flags
   - `Score`
   - `XP Awarded`
4. Use XP totals from `xp_totals` to decide on:
   - Roles
   - Prizes
   - Allowlist spots

If OpenAI or Twitter API are not available, the bot can still log tweets and you can grade them manually.

---

## 4. Troubleshooting & Common Issues

### 4.1 Bot Not Responding to Commands

- Ensure the bot is online in Discord
- Check logs for errors when syncing slash commands
- Confirm the bot has permission to use application commands in that server

### 4.2 No Metrics Announcements

- Check that `METRICS_CHANNEL_ID` is correct and points to a text channel
- Verify the Polymer endpoints are reachable from the host
- Look at logs for `[Leaderboard]` or `[Analytics]` errors

### 4.3 Google Sheets Errors

- Confirm the service account has Editor access to the Sheet
- Check that worksheet names in `.env` match exactly
- Look for `gspread` or permissions errors in the logs

### 4.4 Tweet Grading Issues

- If tweet text cannot be fetched:
  - Check `TWITTER_BEARER_TOKEN`
  - Verify your Twitter/X API access level
- If grading fails:
  - Check `OPENAI_API_KEY`
  - Look for `[TweetGrade]` errors in logs

---

## 5. Safe Changes Admins Can Make

Admins can safely:

- Update message copy (embeds, strings)
- Change which channel IDs are used
- Pause certain tasks by commenting out their `.start()` calls
- Adjust the XP mapping logic (e.g., how scores map to XP)
- Adjust volume milestone step size (e.g., 0.05B instead of 0.1B)

Any structural changes to Google Sheets (column names, tab names) should be coordinated with developers,
since the bot relies on consistent headers and tab names.


---

## POLYONE DEVELOPER GUIDE

# PolyOne Developer & Extension Guide

This guide is for developers who want to extend PolyOne, debug behavior, or integrate new XP sources.

---

## 1. Codebase Overview

The core bot is a single Python file built around:

- `discord.py` – for commands, events, tasks
- `aiohttp` – async HTTP
- `gspread` – Google Sheets I/O
- `openai` – AI tweet grading (optional)
- Local `state.json` – small persistent state

Key sections include:

1. Configuration & environment handling
2. Google Sheets helpers
3. XP helpers
4. Twitter handle helpers
5. State load/save
6. Metrics tasks (`check_leaderboard`, `check_volume`)
7. Volume channel update
8. Status builder & daily summary
9. Slash commands
10. Startup (`on_ready`)

---

## 2. Adding a New XP Source

To add a new way for users to earn XP:

1. Decide on a `source` string, e.g.:
   - `metrics_quiz`
   - `prediction_game`
   - `poly_u_quiz`
   - `content_review`

2. Identify where in the code the event is “completed”:
   - A slash command handler
   - A background task resolving predictions
   - A quiz completion callback

3. Call `add_xp(...)`:

```python
add_xp(
    discord_id=user.id,
    discord_name=str(user),
    amount=xp_amount,
    source="metrics_quiz",
    twitter_handle=optional_handle,
    reference_type="quiz",
    reference_id="quiz_id_or_name",
    notes="Any extra context you want stored"
)
```

4. That’s it. The XP will appear in `xp_events`, and `xp_totals` will pick it up automatically via formulas.

---

## 3. Extending Tweet Grading

### 3.1 Grading Rubric

The tweet grading logic lives in a helper similar to:

```python
async def grade_tweet(tweet_text: str) -> tuple[float, str]:
    ...
```

The system prompt encodes the rubric, including:

- Score range: –1 to 5
- Penalties for irrelevant or spammy tweets
- Bonuses for clearly explaining Polymer, Prove API, value props, and CTAs

To adjust grading rules, edit the system prompt string and re–deploy.

### 3.2 XP Mapping

XP is mapped from score with a simple function, e.g.:

```python
xp_amount = max(0, int(round(max(0.0, score) * 10)))
```

You can change this to:

- Non–linear mapping (e.g., higher weight on 4–5)
- Thresholding (e.g., no XP below 3.0)
- Campaign–based multipliers

Just keep the side effects clear and documented so the community understands how XP is computed.

---

## 4. Adding Prediction Games

A prediction game might look like:

- `/predict_volume target=1.5B by=2025-08-31`
- Bot stores prediction in a sheet or database
- A scheduled task later compares reality against predictions
- Winners get XP, logged via `add_xp`

Implementation steps:

1. Create a new worksheet (`predictions`) or DB table
2. Add a slash command to accept predictions and store them
3. Add a scheduled task that runs at resolution time:
   - Reads predictions
   - Reads actual metrics from Polymer API
   - Computes winners
   - Calls `add_xp(...)` for winners
4. Optionally post a summary in Discord

---

## 5. Error Handling & Logging

Best practices for extending PolyOne:

- Wrap external calls (HTTP, Sheets, OpenAI) in `try/except` blocks
- Log errors with enough context to debug, e.g.:
  - Endpoint URL
  - Response status code
  - Exception type and message
- Avoid crashing the entire bot from a single failing task:
  - Use `discord.ext.tasks` and let it continue on next iteration

For critical failures (e.g., repeated OpenAI failures), you can DM admins or log into a dedicated “bot–errors” channel.

---

## 6. Dependency Management

Dependencies are listed in `requirements.txt`. Typical entries include:

- `discord.py`
- `aiohttp`
- `gspread`
- `google-auth`
- `python-dotenv`
- `openai`

When adding new features, pin versions where possible and test locally before deploying in production.

---

## 7. Deployment Notes

PolyOne can be deployed on:

- A small VPS
- A container (Docker)
- A serverless environment that supports long–running tasks (less ideal for Discord bots)

General steps:

1. Clone the repo or upload the code
2. Create `.env` with secret keys and IDs
3. Place `service_account.json` in the working directory
4. Install dependencies: `pip install -r requirements.txt`
5. Run the bot: `python PolyOne.py`
6. Use a process manager (e.g., `systemd`, `pm2`, `supervisord`, or Docker restart policies)

Make sure automatic restarts are configured in case of crashes or host reboots.
