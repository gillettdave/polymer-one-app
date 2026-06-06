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









