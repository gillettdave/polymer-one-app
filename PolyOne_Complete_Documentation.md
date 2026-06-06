# PolyOne Bot - Complete Documentation


**Version:** 1.3.0  

**Generated:** 2025-12-04 10:00:44


---


# Table of Contents


1. [Quick Start Guide](#quick-start-guide)
2. [Environment Variables Reference](#environment-variables-reference)
3. [Commands Reference](#commands-reference)
4. [Use Case Examples](#use-case-examples)
5. [Deployment Guide](#deployment-guide)
6. [Changelog](#changelog)


---


<a name='quick-start-guide'></a>


# Quick Start Guide


# PolyOne Bot - Quick Start Guide

## Overview

PolyOne is a Discord bot for the Polymer University community that tracks metrics, manages XP, grades tweets, runs quizzes, and more. This guide will help you get the bot up and running quickly.

## Prerequisites

- Python 3.8 or higher
- A Discord bot application (get token from [Discord Developer Portal](https://discord.com/developers/applications))
- A Google Cloud service account with access to Google Sheets
- (Optional) Twitter/X API Bearer Token for tweet grading
- (Optional) OpenAI API Key for automatic tweet grading

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Copy `env.example.txt` to `.env` and fill in your values:

```bash
cp env.example.txt .env
```

**Required variables:**
- `DISCORD_TOKEN` - Your Discord bot token
- `GOOGLE_SERVICE_ACCOUNT_FILE` - Path to your Google service account JSON file
- `GOOGLE_SPREADSHEET_NAME` - Name of your Google Spreadsheet

**Recommended variables:**
- `METRICS_CHANNEL_ID` - Discord channel ID for metrics announcements
- `TWITTER_BEARER_TOKEN` - For tweet text fetching
- `OPENAI_API_KEY` - For automatic tweet grading

See `ENV_VARIABLES.md` for a complete list of all configuration options.

### 3. Set Up Google Sheets

1. Create a Google Spreadsheet with the name specified in `GOOGLE_SPREADSHEET_NAME`
2. Create the following worksheets (they will be created automatically if missing):
   - `xp_events` - Tracks XP events
   - `xp_totals` - Stores user XP totals
   - `tweets` - Stores tweet submissions
   - `predictions` - Stores prediction game entries
   - `leaderboard` - (Optional) Leaderboard data

3. Share the spreadsheet with your Google service account email (found in `service_account.json`)

### 4. Configure Admin Role

The admin role is configurable via environment variable or bot command:

**Via Environment Variable:**
```env
ADMIN_ROLE_NAME=manager perms
```

**Via Bot Command (after bot is running):**
Use `/bot_setup` command to set the admin role name. Users with this role (or Discord administrators) can use admin commands.

### 5. Run the Bot

```bash
python PolyOne.py
```

The bot will:
- Validate configuration on startup
- Log to console and `logs/polyone.log`
- Connect to Discord and sync commands
- Start background tasks for metrics checking, quizzes, etc.

## First-Time Setup Checklist

- [ ] Installed Python dependencies
- [ ] Created `.env` file with required variables
- [ ] Set `DISCORD_TOKEN` in `.env`
- [ ] Set `GOOGLE_SERVICE_ACCOUNT_FILE` path
- [ ] Set `GOOGLE_SPREADSHEET_NAME`
- [ ] Created Google Spreadsheet and shared with service account
- [ ] Set `METRICS_CHANNEL_ID` (Discord channel for announcements)
- [ ] (Optional) Set `TWITTER_BEARER_TOKEN` for tweet grading
- [ ] (Optional) Set `OPENAI_API_KEY` for automatic grading
- [ ] (Optional) Set `ADMIN_ROLE_NAME` or configure via `/bot_setup`
- [ ] Invited bot to Discord server with necessary permissions

## Bot Permissions

The bot needs the following Discord permissions:
- **Send Messages** - To post announcements and respond to commands
- **Embed Links** - To send rich embeds
- **Read Message History** - To read previous messages
- **Manage Messages** - (Optional) For message cleanup
- **Manage Roles** - (Optional) For role assignment in quizzes
- **Connect** - (Optional) For voice channel volume counter

## Configuration Validation

The bot validates configuration on startup. If there are errors, the bot will not start and will display what needs to be fixed. Warnings are logged but won't prevent startup.

**Common Issues:**
- Missing `DISCORD_TOKEN` - Bot cannot connect to Discord
- Missing Google service account file - Cannot access Google Sheets
- Invalid channel IDs - Features using those channels will be disabled
- Missing API keys - Related features (tweet grading) will be disabled

## Logging

Logs are written to:
- Console (INFO level and above)
- `logs/polyone.log` (all levels)
- `logs/polyone_errors.log` (ERROR level and above)

Log files rotate automatically when they reach the configured size limit.

## Next Steps

After the bot is running:

1. **Configure channels** - Use `/bot_setup` to set up channels
2. **Set admin role** - Use `/bot_setup` to configure admin role name
3. **Test commands** - Try `/submit_tweet` or `/xp_history` to test functionality
4. **Check logs** - Monitor `logs/polyone.log` for any issues

## Troubleshooting

### Bot Won't Start

**Configuration Validation Errors:**
- **"DISCORD_TOKEN is not set"**
  - Solution: Add `DISCORD_TOKEN=your_token_here` to your `.env` file
  - Get token from: https://discord.com/developers/applications

- **"Google service account file not found"**
  - Solution: Verify the path in `GOOGLE_SERVICE_ACCOUNT_FILE` is correct
  - Ensure the file exists and is readable
  - Check file permissions

- **"METRICS_CHANNEL_ID is using default value"**
  - This is a warning, not an error
  - Solution: Set `METRICS_CHANNEL_ID` in `.env` to your desired channel ID
  - Get channel ID: Right-click channel → Copy ID (Developer Mode must be enabled)

**Startup Crashes:**
- Check `logs/polyone_errors.log` for detailed error messages
- Verify Python version: `python --version` (requires 3.8+)
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check for syntax errors: `python -m py_compile PolyOne.py`

### Bot Starts But Commands Don't Work

**Commands Not Appearing:**
- Wait 1-2 minutes after bot starts for command sync
- Check bot has "Use Application Commands" permission
- Verify bot is in the server (not just invited)
- Try restarting the bot to force command sync

**Permission Errors:**
- Ensure bot has required permissions in server settings
- Check bot's role is high enough in role hierarchy
- Verify admin role name matches your server's role name
- Use `/bot_setup` to configure admin role if needed

**Channel Not Found Errors:**
- Verify channel IDs are correct (use Developer Mode to copy IDs)
- Ensure bot can see the channel (check channel permissions)
- Use `/bot_setup` to reconfigure channels

### Tweet Grading Not Working

**"TWITTER_BEARER_TOKEN not set"**
- Solution: Add `TWITTER_BEARER_TOKEN=your_token` to `.env`
- Get token from: https://developer.twitter.com/en/portal/dashboard
- Note: Tweets will still be submitted but won't be automatically graded

**"OPENAI_API_KEY not set"**
- Solution: Add `OPENAI_API_KEY=your_key` to `.env`
- Get key from: https://platform.openai.com/api-keys
- Note: Tweets will be saved but require manual grading

**API Errors:**
- **"OpenAI quota exceeded"**: Wait for quota reset or upgrade plan
- **"OpenAI rate limit exceeded"**: Wait a few moments and try again
- **"Non-200 from X API"**: Check Twitter API status, verify bearer token is valid
- Check API keys are active and have necessary permissions

**Tweets Not Being Graded:**
- Use `/process_ungraded_tweets` (admin) to manually process ungraded tweets
- Check logs for specific error messages
- Verify tweet URLs are valid and accessible

### Google Sheets Errors

**"Worksheet not found"**
- Solution: Worksheets are created automatically on first use
- Verify spreadsheet name matches `GOOGLE_SPREADSHEET_NAME`
- Check service account has edit access to the spreadsheet

**"Permission denied" or "Access denied"**
- Solution: Share spreadsheet with service account email
- Find service account email in `service_account.json` (look for "client_email")
- Grant "Editor" access to the service account

**"Rate limit exceeded"**
- The bot includes automatic rate limiting
- If errors persist, increase `SHEETS_API_MIN_INTERVAL` in code
- Reduce frequency of operations that write to sheets

**Data Not Appearing:**
- Check worksheet names match configuration
- Verify formulas in `xp_totals` sheet are working
- Use `/xp_me` to test if data is being read correctly

### XP System Issues

**XP Not Updating:**
- Check daily cap hasn't been reached: `/xp_daily_status`
- Verify XP source is valid (tweet grading, quiz, etc.)
- Check `xp_events` sheet for new entries
- Verify `xp_totals` formulas are calculating correctly

**Leaderboard Not Showing:**
- Ensure `xp_totals` sheet has data
- Check formulas are working (should auto-sum from `xp_events`)
- Try `/xp_leaderboard` to test

**Daily Cap Issues:**
- Check your tier: `/xp_daily_status`
- Daily caps reset at midnight UTC
- Admin grants bypass daily caps

### Quiz Issues

**Quiz Not Starting:**
- Check bot has permission to send DMs
- Verify user has DMs enabled from server members
- Check rate limiting (wait 30 seconds between attempts)

**Role Not Assigned:**
- Verify bot has "Manage Roles" permission
- Check bot's role is higher than the role being assigned
- Ensure role hierarchy is correct in server settings

**Quiz Questions Not Generating:**
- Check `OPENAI_API_KEY` is set and valid
- Verify API quota hasn't been exceeded
- Check logs for specific error messages

### Prediction Game Issues

**Prediction Not Submitting:**
- Check deadline (must submit at least 1 hour before resolution)
- Verify you haven't already submitted for that date
- Check rate limiting (10 second cooldown)

**Predictions Not Resolving:**
- Verify `PREDICTION_RESOLUTION_HOUR` is set correctly (default: 23:00 UTC)
- Check component is enabled: `/bot_component_status`
- Ensure bot has access to analytics API

### General Issues

**High Memory Usage:**
- Check log file sizes (rotate if needed)
- Review state.json size (should be small)
- Restart bot periodically if running 24/7

**Bot Disconnects Frequently:**
- Check internet connection stability
- Verify Discord API status
- Check for rate limiting from Discord
- Review error logs for connection issues

**Commands Timeout:**
- Check Google Sheets API response times
- Verify network connectivity
- Increase timeout values if needed (in code)

### Getting Help

1. **Check Logs First:**
   - `logs/polyone.log` - All activity
   - `logs/polyone_errors.log` - Errors only

2. **Use Bot Commands:**
   - `/bot_component_status` - Check which features are enabled
   - `/bot_setup` - View current configuration

3. **Review Documentation:**
   - See `polyone_docs_bundle/` for detailed guides
   - Check `ENV_VARIABLES.md` for configuration options

4. **Common Solutions:**
   - Restart the bot
   - Verify all environment variables are set
   - Check Discord and API service status
   - Review recent code changes

For more detailed information, see the other documentation files in the `polyone_docs_bundle/` directory.



---


<a name='environment-variables-reference'></a>


# Environment Variables Reference


# PolyOne Bot - Environment Variables Reference

This document lists all environment variables used by the PolyOne bot.

## Required Variables

These variables **must** be set for the bot to function:

| Variable | Description | Example |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Discord bot token | `YOUR_DISCORD_BOT_TOKEN_HERE` |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to Google service account JSON file | `service_account.json` |
| `GOOGLE_SPREADSHEET_NAME` | Name of the Google Spreadsheet | `Polymer University Dashboard` |

## Recommended Variables

These are recommended for full functionality:

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `METRICS_CHANNEL_ID` | Discord channel ID for metrics announcements | `123456789012345678` | Get from Discord (right-click channel > Copy ID) |
| `TWITTER_BEARER_TOKEN` | Twitter/X API bearer token | (empty) | Required for tweet text fetching and grading |
| `OPENAI_API_KEY` | OpenAI API key | (empty) | Required for automatic tweet grading |

## Optional Variables

### Feature Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `VOLUME_CHANNEL_ID` | Voice channel ID for volume counter | `0` (disabled) |
| `LEADERBOARD_URL` | URL for leaderboard API | `https://analytics.polymer.zone/api/metrics/leaderboard/top-transactions?environment=mainnet` |
| `ANALYTICS_URL` | URL for analytics API | `https://analytics.polymer.zone/api/analytics?environment=mainnet` |
| `POLL_INTERVAL` | Poll interval in seconds | `600` (10 minutes) |

### Google Sheets Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `XP_EVENTS_SHEET_NAME` | Name of XP events sheet | `xp_events` |
| `XP_TOTALS_SHEET_NAME` | Name of XP totals sheet | `xp_totals` |
| `TWEETS_SHEET_NAME` | Name of tweets sheet | `tweets` |
| `OLD_TWEETS_SHEET_NAME` | Name of old tweets sheet (optional) | (empty) |
| `LEADERBOARD_SHEET_NAME` | Name of leaderboard sheet | `leaderboard` |
| `PREDICTIONS_SHEET_NAME` | Name of predictions sheet | `predictions` |

### Twitter Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TWITTER_HANDLES_CSV` | Path to Twitter handles CSV file | `twitter_handles.csv` |

### Quiz Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `QUIZ_DATA_FILE` | Path to quiz questions CSV | `questions.csv` |
| `QUIZ_RESULTS_FILE` | Path to quiz results CSV | `results.csv` |
| `METRICS_QUIZ_CSV` | Path to custom metrics quiz CSV | `metrics_quiz_custom.csv` |
| `MAX_QUIZ_PARTICIPANTS` | Maximum quiz participants | `50` |
| `QUIZ_COOLDOWN_SECONDS` | Quiz cooldown in seconds | `600` |

### XP System Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GRANDFATHER_BONUS_ENABLED` | Enable grandfather bonus | `true` |

### DeFiLlama Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DEFI_LLAMA_API_KEY` | DeFiLlama API key (optional) | (empty) |
| `CHAIN_ICON_BASE_URL` | Base URL for chain icons | `https://icons.llama.fi` |

### Logging Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO` |
| `LOG_DIR` | Log directory | `logs` |
| `LOG_FILE_MAX_BYTES` | Max log file size in bytes | `10485760` (10MB) |
| `LOG_FILE_BACKUP_COUNT` | Number of backup log files | `5` |

### Error Notifications

| Variable | Description | Default |
|----------|-------------|---------|
| `ERROR_NOTIFICATION_ENABLED` | Enable error notifications via DM | `true` |
| `ADMIN_DM_USER_IDS` | Comma-separated Discord user IDs for error notifications | (empty) |

## Example .env File

```env
# Required
DISCORD_TOKEN=your_discord_bot_token_here
GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
GOOGLE_SPREADSHEET_NAME=Polymer University Dashboard

# Recommended
METRICS_CHANNEL_ID=123456789012345678
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional - only set if you want to change defaults
VOLUME_CHANNEL_ID=0
POLL_INTERVAL=600
LOG_LEVEL=INFO
```

## Notes

- All variables are optional except the three **Required** variables
- If a variable is not set, the bot will use the default value shown in the table
- For Discord IDs, enable Developer Mode in Discord settings, then right-click the channel/user and select "Copy ID"
- The bot will work without `TWITTER_BEARER_TOKEN` and `OPENAI_API_KEY`, but tweet grading will be disabled
- Empty strings mean the feature is disabled or uses a fallback





---


<a name='commands-reference'></a>


# Commands Reference


# PolyOne Bot - Commands Reference

Complete reference for all slash commands available in the PolyOne bot.

## Table of Contents

- [User Commands](#user-commands)
- [Admin Commands](#admin-commands)
- [Command Examples](#command-examples)

---

## User Commands

Commands available to all users.

### `/polymer_status`
**Description:** Show current Polymer dashboard stats

**Usage:**
```
/polymer_status
```

**What it does:**
- Displays current Polymer network metrics
- Shows total volume, top transactions, and other analytics
- Updates in real-time from Polymer analytics API

**Example:**
```
/polymer_status
```

---

### `/xp_me`
**Description:** Show your total Polymer XP

**Usage:**
```
/xp_me
```

**What it does:**
- Shows your total XP across all sources
- Displays your current rank
- Breaks down XP by source (Polymer University, Twitter, Quizzes, etc.)

**Example:**
```
/xp_me
```

**Output includes:**
- Total XP
- Rank (#X out of Y users)
- XP breakdown by category

---

### `/xp_leaderboard`
**Description:** Show the top XP leaderboard

**Usage:**
```
/xp_leaderboard
```

**What it does:**
- Displays top 25 users by XP
- Shows Discord names and total XP
- Updates in real-time

**Example:**
```
/xp_leaderboard
```

---

### `/xp_daily_status`
**Description:** Check your daily XP progress and cap

**Usage:**
```
/xp_daily_status
```

**What it does:**
- Shows your daily XP progress
- Displays your tier and daily cap
- Shows how much XP you can still earn today

**Example:**
```
/xp_daily_status
```

**Output includes:**
- Total XP
- Current tier
- Today's progress (earned/remaining)
- Daily cap information

---

### `/xp_history`
**Description:** View your XP history (recent events)

**Parameters:**
- `limit` (optional): Number of recent events to show (default: 20, max: 50)
- `user` (optional, admin only): View another user's history

**Usage:**
```
/xp_history
/xp_history limit:10
/xp_history limit:30 user:@username
```

**What it does:**
- Shows recent XP events with timestamps
- Displays source, amount, and notes for each event
- Admins can view other users' history

**Example:**
```
/xp_history limit:15
```

---

### `/set_twitter`
**Description:** Link your Twitter/X handle to your Discord account

**Parameters:**
- `handle`: Your Twitter/X handle (with or without @)

**Usage:**
```
/set_twitter handle:yourhandle
/set_twitter handle:@yourhandle
```

**What it does:**
- Links your Twitter handle to your Discord account
- Required before submitting tweets
- Handle is normalized (removes @ if present)

**Example:**
```
/set_twitter handle:polymer_zone
```

---

### `/submit_tweet`
**Description:** Submit a tweet URL for the Polymer content campaign

**Parameters:**
- `url`: Full URL of the tweet (e.g., https://twitter.com/... or https://x.com/...)

**Usage:**
```
/submit_tweet url:https://twitter.com/user/status/1234567890
```

**What it does:**
- Submits a tweet for grading
- Automatically fetches tweet text (if API configured)
- Automatically grades tweet (if OpenAI configured)
- Awards XP based on grade
- Rate limited: 30 seconds between submissions

**Example:**
```
/submit_tweet url:https://x.com/polymer_zone/status/1234567890
```

**Requirements:**
- Must set Twitter handle first with `/set_twitter`
- Tweet must be accessible (public)
- Rate limit: 30 seconds between submissions

---

### `/check_tweets`
**Description:** Check how many tweets you have submitted

**Usage:**
```
/check_tweets
```

**What it does:**
- Shows total count of your submitted tweets
- Includes tweets from current and old sheets (if configured)

**Example:**
```
/check_tweets
```

---

### `/polyu_rank`
**Description:** Show your Polymer University leaderboard rank (sheet-based)

**Usage:**
```
/polyu_rank
```

**What it does:**
- Shows your rank in the Polymer University leaderboard
- Based on data from Google Sheets

**Example:**
```
/polyu_rank
```

---

### `/metrics_quiz`
**Description:** Start a quiz based on current Polymer metrics

**Parameters:**
- `num_questions` (optional): Number of questions (default: 3, max: 5)

**Usage:**
```
/metrics_quiz
/metrics_quiz num_questions:5
```

**What it does:**
- Generates quiz questions based on current Polymer network data
- Questions are AI-generated using current metrics
- Awards XP for passing
- Can only be taken once per day

**Example:**
```
/metrics_quiz num_questions:3
```

**Requirements:**
- Bot must be able to send DMs
- User must have DMs enabled from server members
- OpenAI API key required for question generation

---

### `/predict_volume`
**Description:** Predict Polymer's total volume for a future date

**Parameters:**
- `volume_billions`: Predicted volume in billions (e.g., 2.5 for $2.5B)
- `target_date` (optional): Date to predict for (YYYY-MM-DD format, defaults to tomorrow)

**Usage:**
```
/predict_volume volume_billions:2.5
/predict_volume volume_billions:3.2 target_date:2024-12-25
```

**What it does:**
- Submits a volume prediction
- Predictions are resolved at 23:00 UTC on target date
- XP awarded based on accuracy
- One prediction per day per user

**Example:**
```
/predict_volume volume_billions:2.75 target_date:2024-12-20
```

**Requirements:**
- Must submit at least 1 hour before resolution time
- One volume prediction per day
- Rate limit: 10 seconds between predictions

---

### `/predict_top10`
**Description:** Predict changes to the top 10 transactions

**Parameters:**
- `target_date` (optional): Date to predict for (YYYY-MM-DD format, defaults to tomorrow)
- `new_entries` (optional): Comma-separated list of token symbols that will enter top 10
- `removed_entries` (optional): Comma-separated list of token symbols that will leave top 10

**Usage:**
```
/predict_top10 new_entries:USDC,ETH removed_entries:BTC
/predict_top10 target_date:2024-12-25 new_entries:MATIC
```

**What it does:**
- Submits a top 10 change prediction
- Predicts which tokens will enter/leave top 10
- XP awarded based on accuracy
- One prediction per day per user

**Example:**
```
/predict_top10 new_entries:USDC,ETH,WBTC removed_entries:MATIC,AVAX
```

**Requirements:**
- Must submit at least 1 hour before resolution time
- One top10 prediction per day
- Rate limit: 10 seconds between predictions

---

### `/my_predictions`
**Description:** View your active predictions

**Usage:**
```
/my_predictions
```

**What it does:**
- Shows all your active (unresolved) predictions
- Displays prediction type, target date, and values
- Shows when predictions will be resolved

**Example:**
```
/my_predictions
```

---

### `/prediction_leaderboard`
**Description:** View the prediction game leaderboard

**Parameters:**
- `limit` (optional): Number of users to show (default: 10)

**Usage:**
```
/prediction_leaderboard
/prediction_leaderboard limit:20
```

**What it does:**
- Shows top users by prediction accuracy
- Displays average accuracy and total XP earned
- Updates as predictions are resolved

**Example:**
```
/prediction_leaderboard limit:15
```

---

## Admin Commands

Commands available only to users with admin role or Discord administrators.

### `/xp_admin_give`
**Description:** Give XP to a user (Admin only)

**Parameters:**
- `user`: The user to give XP to
- `amount`: Amount of XP to give

**Usage:**
```
/xp_admin_give user:@username amount:100
```

**What it does:**
- Awards XP directly to a user
- Bypasses daily caps
- Logs the action with admin source

**Example:**
```
/xp_admin_give user:@polymer_user amount:50
```

---

### `/xp_admin_give_role`
**Description:** Give XP to all members with a specific role (Admin only)

**Parameters:**
- `role`: The role to give XP to
- `amount`: Amount of XP to give to each member
- `notes` (optional): Notes for the XP grant

**Usage:**
```
/xp_admin_give_role role:@Contributor amount:25
/xp_admin_give_role role:@EarlyAdopter amount:100 notes:Early supporter bonus
```

**What it does:**
- Awards XP to all members with the specified role
- Processes members in batches
- Bypasses daily caps
- Logs each grant

**Example:**
```
/xp_admin_give_role role:@PolymerMember amount:50 notes:Monthly bonus
```

---

### `/xp_admin_remove`
**Description:** Remove XP from a user (Admin only)

**Parameters:**
- `user`: The user to remove XP from
- `amount`: Amount of XP to remove

**Usage:**
```
/xp_admin_remove user:@username amount:50
```

**What it does:**
- Removes XP from a user
- Logs the action with admin removal source
- Can result in negative XP if amount exceeds current total

**Example:**
```
/xp_admin_remove user:@user amount:25
```

---

### `/xp_migrate_check`
**Description:** Check how many old leaderboard entries match registered Twitter handles (Admin only)

**Parameters:**
- `csv_file`: Name of the CSV file to check

**Usage:**
```
/xp_migrate_check csv_file:leaderboard_old.csv
```

**What it does:**
- Analyzes old leaderboard CSV
- Matches entries with registered Twitter handles
- Shows statistics on potential migrations

**Example:**
```
/xp_migrate_check csv_file:old_leaderboard.csv
```

---

### `/xp_grandfather_bonus`
**Description:** Award grandfather bonus to existing contributors based on tweet count (Admin only)

**Parameters:**
- `user`: The user to award bonus to
- `tweet_count`: Number of historical tweets
- `bonus_per_tweet` (optional): Bonus XP per tweet (default: 2)

**Usage:**
```
/xp_grandfather_bonus user:@username tweet_count:50
/xp_grandfather_bonus user:@username tweet_count:100 bonus_per_tweet:3
```

**What it does:**
- Awards bonus XP for historical contributions
- Calculates based on tweet count
- Bypasses daily caps

**Example:**
```
/xp_grandfather_bonus user:@early_contributor tweet_count:75
```

---

### `/xp_migrate_historical`
**Description:** Migrate historical XP from old leaderboard CSV (Admin only)

**Parameters:**
- `csv_file`: Name of the CSV file to migrate from
- `dry_run` (optional): If true, only shows what would be migrated (default: true)

**Usage:**
```
/xp_migrate_historical csv_file:leaderboard_old.csv dry_run:true
/xp_migrate_historical csv_file:leaderboard_old.csv dry_run:false
```

**What it does:**
- Migrates historical XP from old leaderboard
- Matches users by Twitter handle
- Shows preview in dry-run mode
- Actually migrates when dry_run is false

**Example:**
```
/xp_migrate_historical csv_file:old_data.csv dry_run:true
```

---

### `/process_ungraded_tweets`
**Description:** Process all ungraded tweets in the sheet (Admin only)

**Usage:**
```
/process_ungraded_tweets
```

**What it does:**
- Processes all tweets that haven't been graded yet
- Fetches tweet text and grades them
- Updates the sheet with grades and XP
- Shows progress and results

**Example:**
```
/process_ungraded_tweets
```

**Requirements:**
- Twitter Bearer Token must be set
- OpenAI API Key must be set

---

### `/post_quiz_button`
**Description:** Post a quiz button for users to click (Admin only)

**Parameters:**
- `quiz_message`: The message that will appear above the button
- `num_questions`: Number of questions to ask
- `required_score`: Number of correct answers needed to pass
- `role_to_assign`: Role to assign if user passes
- `qualifying_role` (optional): Optional role user must already have to receive reward

**Usage:**
```
/post_quiz_button quiz_message:"Take the quiz!" num_questions:5 required_score:3 role_to_assign:@Graduate
```

**What it does:**
- Posts a quiz button in the channel
- Users click to start quiz via DM
- Awards role and XP on passing
- Supports qualifying roles

**Example:**
```
/post_quiz_button quiz_message:"Complete Chapter 1 Quiz" num_questions:10 required_score:7 role_to_assign:@Chapter1Graduate qualifying_role:@Student
```

---

### `/clean_threads`
**Description:** Clean all threads in a channel created by this bot (Admin only)

**Parameters:**
- `target_channel`: The channel to clean threads from

**Usage:**
```
/clean_threads target_channel:#quiz-channel
```

**What it does:**
- Deletes all threads created by the bot in the specified channel
- Useful for cleanup after quizzes
- Shows count of deleted threads

**Example:**
```
/clean_threads target_channel:#quizzes
```

---

### `/bot_component_toggle`
**Description:** Enable or disable a bot component (Admin only)

**Parameters:**
- `component`: Component to toggle (autocomplete shows available options)
- `enabled`: Whether to enable (true) or disable (false) the component

**Usage:**
```
/bot_component_toggle component:leaderboard_checking enabled:false
/bot_component_toggle component:metrics_quiz enabled:true
```

**What it does:**
- Enables or disables specific bot features
- Components include: leaderboard_checking, volume_checking, daily_summary, prediction_resolution, metrics_quiz, thread_cleanup
- Changes are saved to state.json

**Example:**
```
/bot_component_toggle component:prediction_resolution enabled:true
```

---

### `/bot_component_status`
**Description:** View status of all bot components (Admin only)

**Usage:**
```
/bot_component_status
```

**What it does:**
- Shows enabled/disabled status of all bot components
- Displays current configuration

**Example:**
```
/bot_component_status
```

---

### `/bot_setup`
**Description:** Configure bot channels and settings (Admin only)

**Parameters:**
- `main_metrics_channel` (optional): Main channel for metrics announcements
- `metrics_quiz_channel` (optional): Channel for daily metrics quiz posts
- `volume_channel` (optional): Voice channel for volume counter
- `leaderboard_channel` (optional): Channel for daily XP leaderboard posts
- `admin_role` (optional): Admin role name

**Usage:**
```
/bot_setup main_metrics_channel:#announcements
/bot_setup admin_role:"manager perms" main_metrics_channel:#metrics
```

**What it does:**
- Configures bot channels and settings
- Updates state.json with new configuration
- Shows current configuration if no parameters provided

**Example:**
```
/bot_setup main_metrics_channel:#polymer-metrics metrics_quiz_channel:#quizzes admin_role:"Admin"
```

---

### `/bot_setup_metrics_channel`
**Description:** Set the channel for metrics announcements (Admin only)

**Parameters:**
- `channel`: Text channel for metrics announcements

**Usage:**
```
/bot_setup_metrics_channel channel:#announcements
```

**What it does:**
- Sets the main channel for metrics announcements
- Used for daily summaries, top 10 transactions, milestones

**Example:**
```
/bot_setup_metrics_channel channel:#polymer-updates
```

---

### `/bot_setup_volume_channel`
**Description:** Set the voice channel for volume counter (Admin only)

**Parameters:**
- `channel` (optional): Voice channel to use (or None to disable)

**Usage:**
```
/bot_setup_volume_channel channel:#Polymer Volume
/bot_setup_volume_channel channel:None
```

**What it does:**
- Sets voice channel that displays current volume
- Channel name updates with volume and 24h change
- Set to None to disable

**Example:**
```
/bot_setup_volume_channel channel:#Polymer Stats
```

---

### `/bot_manual_quiz_post`
**Description:** Manually post a metrics quiz announcement (Admin only)

**Usage:**
```
/bot_manual_quiz_post
```

**What it does:**
- Manually triggers a metrics quiz announcement
- Posts quiz button in configured metrics quiz channel
- Useful for testing or manual scheduling

**Example:**
```
/bot_manual_quiz_post
```

---

## Command Examples

### Common User Workflows

**First-time setup:**
```
1. /set_twitter handle:yourhandle
2. /xp_me (check your starting XP)
3. /submit_tweet url:https://x.com/... (submit your first tweet)
```

**Daily activities:**
```
1. /xp_daily_status (check your progress)
2. /submit_tweet url:... (submit tweets)
3. /metrics_quiz (take daily quiz)
4. /xp_me (check updated XP)
```

**Tracking progress:**
```
1. /xp_history limit:10 (see recent XP events)
2. /xp_leaderboard (see your rank)
3. /my_predictions (check your predictions)
```

**Prediction game:**
```
1. /predict_volume volume_billions:2.5 target_date:2024-12-20
2. /predict_top10 new_entries:USDC,ETH removed_entries:BTC
3. /my_predictions (check your predictions)
4. /prediction_leaderboard (see leaderboard)
```

### Common Admin Workflows

**Initial setup:**
```
1. /bot_setup admin_role:"Admin" main_metrics_channel:#announcements
2. /bot_setup_volume_channel channel:#Polymer Volume
3. /bot_component_status (verify all components enabled)
```

**XP management:**
```
1. /xp_admin_give user:@user amount:100
2. /xp_admin_give_role role:@Contributor amount:50
3. /xp_history user:@user (verify grant)
```

**Maintenance:**
```
1. /process_ungraded_tweets (process pending tweets)
2. /bot_component_status (check component status)
3. /clean_threads target_channel:#quizzes (cleanup)
```

---

## Notes

- All commands are slash commands (type `/` in Discord to see them)
- Commands are case-insensitive
- Most commands support autocomplete for parameters
- Admin commands require admin role or Discord administrator permissions
- Rate limits apply to some commands (shown in command descriptions)
- Commands that modify data are logged for audit purposes




---


<a name='use-case-examples'></a>


# Use Case Examples


# PolyOne Bot - Use Case Examples

Practical examples for common scenarios and workflows.

## Table of Contents

- [Getting Started](#getting-started)
- [Daily User Activities](#daily-user-activities)
- [Admin Management](#admin-management)
- [Troubleshooting Scenarios](#troubleshooting-scenarios)
- [Advanced Use Cases](#advanced-use-cases)

---

## Getting Started

### First-Time User Setup

**Scenario:** A new user wants to start earning XP and participating in the community.

**Steps:**
1. Set your Twitter handle:
   ```
   /set_twitter handle:your_twitter_handle
   ```

2. Check your starting XP:
   ```
   /xp_me
   ```

3. Submit your first tweet:
   ```
   /submit_tweet url:https://x.com/your_handle/status/1234567890
   ```

4. Check your daily status:
   ```
   /xp_daily_status
   ```

**Expected Results:**
- Twitter handle linked to Discord account
- Starting XP displayed (likely 0)
- Tweet submitted and graded automatically
- XP awarded based on tweet quality
- Daily progress shown

---

### Setting Up Admin Role

**Scenario:** Setting up the bot for the first time and configuring admin permissions.

**Steps:**
1. Set admin role via environment variable (in `.env`):
   ```env
   ADMIN_ROLE_NAME=Admin
   ```

2. Or set via bot command:
   ```
   /bot_setup admin_role:"Admin"
   ```

3. Verify admin role is set:
   ```
   /bot_setup
   ```

**Expected Results:**
- Admin role configured
- Users with that role can use admin commands
- Discord administrators always have access

---

## Daily User Activities

### Daily XP Grinding Routine

**Scenario:** A user wants to maximize their daily XP earnings.

**Morning Routine:**
1. Check daily status:
   ```
   /xp_daily_status
   ```

2. Take the daily metrics quiz:
   ```
   /metrics_quiz num_questions:5
   ```

3. Submit quality tweets throughout the day:
   ```
   /submit_tweet url:https://x.com/.../status/...
   ```

4. Check progress:
   ```
   /xp_me
   ```

**Tips:**
- Submit tweets with quality content about Polymer
- Take the quiz early (can only do once per day)
- Check your tier to know your daily cap
- Higher tier = lower daily cap (catch-up mechanics)

---

### Participating in Prediction Game

**Scenario:** A user wants to participate in the prediction game and earn XP.

**Steps:**
1. Check current metrics:
   ```
   /polymer_status
   ```

2. Make a volume prediction:
   ```
   /predict_volume volume_billions:2.75 target_date:2024-12-20
   ```

3. Make a top 10 prediction:
   ```
   /predict_top10 new_entries:USDC,ETH removed_entries:BTC
   ```

4. Check your predictions:
   ```
   /my_predictions
   ```

5. View leaderboard:
   ```
   /prediction_leaderboard limit:20
   ```

**Tips:**
- Submit predictions at least 1 hour before resolution (23:00 UTC)
- One prediction per type per day
- Accuracy determines XP reward
- Check leaderboard to see top predictors

---

### Tracking Progress Over Time

**Scenario:** A user wants to track their XP growth and see their history.

**Steps:**
1. View current status:
   ```
   /xp_me
   ```

2. Check recent XP events:
   ```
   /xp_history limit:30
   ```

3. See your rank:
   ```
   /xp_leaderboard
   ```

4. Check daily progress:
   ```
   /xp_daily_status
   ```

**What to Look For:**
- XP breakdown by source
- Recent activity in history
- Rank progression over time
- Daily cap remaining

---

## Admin Management

### Initial Bot Configuration

**Scenario:** Setting up the bot for the first time in a new server.

**Steps:**
1. Configure all channels at once:
   ```
   /bot_setup main_metrics_channel:#announcements metrics_quiz_channel:#quizzes leaderboard_channel:#leaderboard admin_role:"Admin"
   ```

2. Set volume channel:
   ```
   /bot_setup_volume_channel channel:#Polymer Volume
   ```

3. Verify configuration:
   ```
   /bot_component_status
   ```

4. Test a command:
   ```
   /polymer_status
   ```

**Expected Results:**
- All channels configured
- Components enabled
- Bot responding to commands
- Volume channel updating

---

### Awarding XP to Users

**Scenario:** Admin wants to reward users for special contributions.

**Single User:**
```
/xp_admin_give user:@username amount:100
```

**Entire Role:**
```
/xp_admin_give_role role:@Contributor amount:50 notes:Monthly bonus
```

**Verify Grant:**
```
/xp_history user:@username
```

**Tips:**
- Admin grants bypass daily caps
- All grants are logged
- Use notes to track reason for grant
- Bulk grants process in batches

---

### Processing Ungraded Tweets

**Scenario:** Tweets were submitted but not automatically graded (API issues, etc.).

**Steps:**
1. Check for ungraded tweets (manual check in Google Sheets)

2. Process all ungraded tweets:
   ```
   /process_ungraded_tweets
   ```

3. Monitor progress (command shows results)

4. Verify in sheet that tweets are now graded

**Requirements:**
- Twitter Bearer Token must be set
- OpenAI API Key must be set
- May take time for large batches

---

### Managing Bot Components

**Scenario:** Temporarily disable a feature for maintenance.

**Steps:**
1. Check current status:
   ```
   /bot_component_status
   ```

2. Disable a component:
   ```
   /bot_component_toggle component:prediction_resolution enabled:false
   ```

3. Verify disabled:
   ```
   /bot_component_status
   ```

4. Re-enable when ready:
   ```
   /bot_component_toggle component:prediction_resolution enabled:true
   ```

**Available Components:**
- `leaderboard_checking` - Top 10 transaction alerts
- `volume_checking` - Volume milestones
- `daily_summary` - Daily status posts
- `prediction_resolution` - Prediction game resolution
- `metrics_quiz` - Daily metrics quiz
- `thread_cleanup` - Automatic thread cleanup

---

### Historical Data Migration

**Scenario:** Migrating XP from an old leaderboard system.

**Steps:**
1. Prepare CSV file with old data (Member column with Twitter handles)

2. Check what would be migrated:
   ```
   /xp_migrate_check csv_file:old_leaderboard.csv
   ```

3. Dry run to preview:
   ```
   /xp_migrate_historical csv_file:old_leaderboard.csv dry_run:true
   ```

4. Perform actual migration:
   ```
   /xp_migrate_historical csv_file:old_leaderboard.csv dry_run:false
   ```

5. Verify migration:
   ```
   /xp_history user:@username
   ```

**Tips:**
- Always do dry run first
- Verify CSV format matches expected structure
- Check Twitter handles are registered
- Migration bypasses daily caps

---

## Troubleshooting Scenarios

### Bot Not Responding to Commands

**Symptoms:** Commands don't appear or return errors.

**Diagnosis Steps:**
1. Check bot is online in server member list
2. Verify bot has necessary permissions
3. Check logs: `logs/polyone_errors.log`
4. Try restarting the bot

**Solutions:**
- Ensure bot has "Use Application Commands" permission
- Check bot's role hierarchy
- Verify channel permissions
- Wait 1-2 minutes after bot start for command sync

---

### Tweet Grading Not Working

**Symptoms:** Tweets submitted but not graded automatically.

**Diagnosis Steps:**
1. Check if API keys are set:
   - `TWITTER_BEARER_TOKEN`
   - `OPENAI_API_KEY`

2. Check logs for errors:
   ```
   logs/polyone_errors.log
   ```

3. Try processing manually:
   ```
   /process_ungraded_tweets
   ```

**Solutions:**
- Verify API keys are valid and active
- Check API quotas haven't been exceeded
- Use manual processing if automatic fails
- Check tweet URLs are accessible

---

### XP Not Updating

**Symptoms:** XP should have been awarded but didn't update.

**Diagnosis Steps:**
1. Check daily cap:
   ```
   /xp_daily_status
   ```

2. Check XP history:
   ```
   /xp_history limit:10
   ```

3. Verify in Google Sheets (xp_events tab)

**Solutions:**
- Daily cap may have been reached
- Check if event was logged in xp_events
- Verify xp_totals formulas are working
- Check for errors in logs

---

### Quiz Not Starting

**Symptoms:** Quiz command doesn't work or times out.

**Diagnosis Steps:**
1. Check if bot can send DMs:
   - Try `/xp_me` (should work)
   - Check user's DM settings

2. Check component status:
   ```
   /bot_component_status
   ```

3. Check logs for errors

**Solutions:**
- Enable DMs from server members
- Verify metrics_quiz component is enabled
- Check OpenAI API key is set (for question generation)
- Wait 30 seconds between quiz attempts

---

## Advanced Use Cases

### Running a Community Event

**Scenario:** Organizing a special event with custom XP rewards.

**Steps:**
1. Create event role:
   - Create role in Discord: `@EventParticipant`

2. Award XP to participants:
   ```
   /xp_admin_give_role role:@EventParticipant amount:100 notes:Community Event Bonus
   ```

3. Track participation:
   ```
   /xp_history user:@participant
   ```

4. Announce winners:
   ```
   /xp_leaderboard
   ```

---

### Setting Up Custom Quiz

**Scenario:** Creating a custom quiz for a specific topic.

**Steps:**
1. Prepare CSV file with questions:
   - Columns: question, option_a, option_b, option_c, option_d, correct

2. Post quiz button:
   ```
   /post_quiz_button quiz_message:"Chapter 1 Quiz" num_questions:10 required_score:7 role_to_assign:@Chapter1Graduate
   ```

3. Monitor completions:
   - Check quiz results in Google Sheets
   - Use `/xp_history` to see completions

---

### Monitoring Bot Health

**Scenario:** Regular maintenance and health checks.

**Daily Checks:**
1. Check component status:
   ```
   /bot_component_status
   ```

2. Review error logs:
   ```
   logs/polyone_errors.log
   ```

3. Test key commands:
   ```
   /polymer_status
   /xp_me
   ```

**Weekly Checks:**
1. Process ungraded tweets:
   ```
   /process_ungraded_tweets
   ```

2. Clean up old threads:
   ```
   /clean_threads target_channel:#quizzes
   ```

3. Review configuration:
   ```
   /bot_setup
   ```

---

### Bulk User Management

**Scenario:** Awarding XP to multiple users based on criteria.

**By Role:**
```
/xp_admin_give_role role:@EarlyAdopter amount:200 notes:Early supporter bonus
```

**Individual Users (if needed):**
```
/xp_admin_give user:@user1 amount:50
/xp_admin_give user:@user2 amount:50
/xp_admin_give user:@user3 amount:50
```

**Verify:**
- Check each user's history
- Verify totals updated correctly
- Check logs for any errors

---

## Best Practices

### For Users
- Set your Twitter handle early
- Submit quality content for better grades
- Take the daily quiz every day
- Make thoughtful predictions
- Check your daily status regularly

### For Admins
- Test commands in a test server first
- Always do dry runs for migrations
- Monitor error logs regularly
- Keep API keys secure
- Document custom configurations
- Use notes when awarding XP
- Verify grants after awarding

### General
- Keep bot updated
- Backup state.json regularly
- Monitor log file sizes
- Review component status weekly
- Test after configuration changes

---

## Tips and Tricks

1. **Maximize Daily XP:**
   - Take quiz early (once per day)
   - Submit multiple quality tweets
   - Make accurate predictions
   - Check your tier for daily cap

2. **Better Tweet Grades:**
   - Explain Polymer clearly
   - Include value propositions
   - Add call-to-action
   - Use relevant hashtags

3. **Accurate Predictions:**
   - Check current metrics first
   - Consider trends
   - Submit early (before deadline)
   - Review past predictions

4. **Admin Efficiency:**
   - Use bulk role grants when possible
   - Set up channels once via `/bot_setup`
   - Use component toggles for maintenance
   - Monitor logs proactively

---

## Getting Help

If you encounter issues not covered here:

1. Check `POLYONE_BOT_DOCUMENTATION.md` for setup guide
2. Review `COMMANDS_REFERENCE.md` for command details
3. Check `logs/polyone_errors.log` for errors
4. Use `/bot_component_status` to verify bot health
5. Review troubleshooting section in documentation




---


<a name='deployment-guide'></a>


# Deployment Guide


# PolyOne Bot - Deployment Guide

## Prerequisites

- Docker and Docker Compose installed
- Discord Bot Token
- Google Service Account JSON file
- (Optional) OpenAI API Key for tweet grading
- (Optional) Twitter/X Bearer Token for tweet fetching

## Quick Start

### 1. Environment Setup

Create a `.env` file in the project root:

```env
# Required
DISCORD_TOKEN=your_discord_bot_token_here
GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
GOOGLE_SPREADSHEET_NAME=Polymer University Dashboard

# Optional - API Keys
OPENAI_API_KEY=your_openai_key_here
TWITTER_BEARER_TOKEN=your_twitter_token_here

# Optional - Channel IDs
METRICS_CHANNEL_ID=123456789012345678
VOLUME_CHANNEL_ID=123456789012345678

# Optional - Admin Notifications
ADMIN_DM_USER_IDS=123456789,987654321
ERROR_NOTIFICATION_ENABLED=true

# Optional - Logging
LOG_LEVEL=INFO
LOG_DIR=logs
LOG_FILE_MAX_BYTES=10485760
LOG_FILE_BACKUP_COUNT=5

# Optional - Polling
POLL_INTERVAL=600
```

### 2. Required Files

Ensure these files are in the project directory:

- `PolyOne.py` - Main bot file
- `service_account.json` - Google Service Account credentials
- `twitter_handles.csv` - Twitter handle mappings (will be created if missing)
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (see above)

### 3. Build and Run

#### Using Docker Compose (Recommended)

```bash
# Build and start the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

#### Using Docker Directly

```bash
# Build the image
docker build -t polyone-bot .

# Run the container
docker run -d \
  --name polyone-bot \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/state.json:/app/state.json \
  polyone-bot
```

#### Running Locally (Without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python PolyOne.py
```

## Configuration

### Google Sheets Setup

1. Create a Google Cloud Project
2. Enable Google Sheets API and Google Drive API
3. Create a Service Account
4. Download the JSON key file as `service_account.json`
5. Share your Google Spreadsheet with the service account email

### Discord Bot Setup

1. Go to https://discord.com/developers/applications
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token to `.env` as `DISCORD_TOKEN`
5. Enable required intents:
   - Server Members Intent
   - Message Content Intent
6. Invite bot to your server with appropriate permissions

### Admin Notifications

To receive error notifications via DM:

1. Get your Discord User ID (enable Developer Mode, right-click your profile, "Copy ID")
2. Add your User ID(s) to `.env`:
   ```
   ADMIN_DM_USER_IDS=123456789,987654321
   ```
3. Ensure error notifications are enabled:
   ```
   ERROR_NOTIFICATION_ENABLED=true
   ```

## Monitoring

### Logs

Logs are stored in the `logs/` directory:

- `polyone.log` - All logs (INFO and above)
- `polyone_errors.log` - Errors only

View logs:
```bash
# Docker Compose
docker-compose logs -f

# Docker
docker logs -f polyone-bot

# Local
tail -f logs/polyone.log
```

### Health Checks

The Docker Compose setup includes a health check that verifies the bot is running and creating log files.

Check health status:
```bash
docker-compose ps
```

### State File

The bot state is saved in `state.json`. This file is automatically created and updated. Make sure it's persisted (mounted as a volume in Docker).

## Troubleshooting

### Bot Not Starting

1. Check logs: `docker-compose logs`
2. Verify `.env` file has all required variables
3. Ensure `service_account.json` exists and is valid
4. Check Discord token is correct

### Google Sheets Errors

1. Verify service account JSON is valid
2. Check spreadsheet is shared with service account email
3. Ensure sheet names match configuration

### Rate Limiting Issues

If you see rate limit errors:
- The bot includes rate limiting protection
- Some operations may be delayed automatically
- Check logs for specific rate limit messages

### Missing Permissions

Ensure the bot has these permissions in Discord:
- Send Messages
- Embed Links
- Manage Messages (for cleanup)
- Manage Channels (for volume counter)
- Read Message History

## Updates

To update the bot:

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

## Backup

Important files to backup:

- `state.json` - Bot state and configuration
- `logs/` - Log files
- `twitter_handles.csv` - User mappings
- `service_account.json` - Google credentials
- `.env` - Environment variables (keep secure!)

## Security Notes

- Never commit `.env` or `service_account.json` to version control
- Keep your Discord bot token secret
- Regularly rotate API keys
- Use Docker secrets or environment variable managers in production

## Support

For issues or questions:
1. Check logs first: `logs/polyone.log` and `logs/polyone_errors.log`
2. Review error notifications (if configured)
3. Check component status: `/bot_component_status` (admin command)








---


<a name='changelog'></a>


# Changelog


# Changelog

All notable changes to the PolyOne bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Configuration validation on startup
- Comprehensive error messages with actionable guidance
- Type hints throughout codebase for better maintainability
- Enhanced docstrings for all major functions
- Quick start guide with troubleshooting section
- Complete commands reference documentation
- Changelog for tracking changes

### Changed
- Admin role is now configurable via environment variable or bot command
- All print statements replaced with proper logging
- Improved error messages for better debugging
- Enhanced configuration validation with warnings and errors

### Fixed
- Code review and cleanup after crash recovery
- Improved error handling in various functions
- Better type safety with proper type hints

## [Recent Updates]

### Code Quality Improvements
- Added type hints to 15+ functions
- Added/improved docstrings for 10+ functions
- Improved error messages in 5+ locations
- Standardized logging throughout codebase

### Documentation Enhancements
- Expanded troubleshooting section with detailed solutions
- Created comprehensive commands reference
- Added examples for common use cases
- Improved quick start guide

### Configuration
- Admin role configurable via `ADMIN_ROLE_NAME` env var
- Admin role can be changed via `/bot_setup` command
- Configuration validation on startup prevents common issues

### Logging
- All print statements replaced with logger calls
- Structured logging with file rotation
- Separate error log file for easier debugging
- Log levels configurable via `LOG_LEVEL` env var

## [Previous Features]

### Core Features
- XP system with tiered daily caps
- Tweet submission and automatic grading
- Metrics quiz with AI-generated questions
- Prediction game (volume and top 10)
- Daily leaderboard and summaries
- Volume channel counter
- Top 10 transaction alerts
- Milestone celebrations

### Admin Features
- XP management (give, remove, bulk grants)
- Component toggling
- Channel configuration
- Historical data migration
- Ungraded tweet processing

### Integrations
- Google Sheets for data storage
- Twitter/X API for tweet fetching
- OpenAI API for tweet grading and quiz generation
- Polymer Analytics API for metrics
- DeFiLlama API for chain metadata

---

## Version History

### v1.0.0 (Initial Release)
- Basic XP tracking
- Tweet submission system
- Google Sheets integration
- Discord slash commands
- Admin commands

### v1.1.0
- Added prediction game
- Metrics quiz feature
- Daily caps system
- Volume channel counter

### v1.2.0
- Component toggling
- Enhanced error handling
- Improved logging
- Configuration validation

### v1.3.0 (Current)
- Code quality improvements
- Enhanced documentation
- Configurable admin role
- Standardized logging

---

## Migration Notes

### Upgrading to v1.3.0

**Breaking Changes:**
- None

**New Requirements:**
- Python 3.8+ (no change)
- All existing environment variables still supported

**Configuration Changes:**
- New optional env var: `ADMIN_ROLE_NAME` (defaults to "manager perms")
- Admin role can now be changed via `/bot_setup` command

**Action Required:**
- Review and update admin role name if needed
- Check logs for any new warnings during startup
- Verify configuration validation passes

---

## Future Plans

### Planned Features
- [ ] Web dashboard for analytics
- [ ] Additional quiz types
- [ ] Enhanced prediction game features
- [ ] API endpoints for external integrations
- [ ] Automated testing suite
- [ ] Performance optimizations

### Known Issues
- None currently documented

---

## Contributing

When adding new features or fixing bugs, please:
1. Update this changelog
2. Add appropriate type hints
3. Include docstrings
4. Update relevant documentation
5. Test thoroughly

---

## Support

For issues or questions:
- Check `POLYONE_BOT_DOCUMENTATION.md` for setup guide
- Review `COMMANDS_REFERENCE.md` for command usage
- Check logs in `logs/` directory
- Use `/bot_component_status` to verify bot health




---

