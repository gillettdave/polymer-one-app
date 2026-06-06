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
- `xp_totals` – aggregate XP per user (via formulas), used for leaderboard rankings
- `tweets` – raw tweet submissions + grading results

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
