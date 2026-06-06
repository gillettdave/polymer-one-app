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


