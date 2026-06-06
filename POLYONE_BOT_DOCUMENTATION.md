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

**Twitter Thread Issues:**
- **Thread Detection:** System automatically detects tweets in same thread
- If you submit multiple tweets from same thread, they're combined and graded as one
- Only the first submission in thread receives XP (others get 0 XP)
- Check tweets sheet "Notes" column for "Thread submission" or "Part of thread"
- Use `/fix_twitter_threads` (admin) to retroactively fix existing thread submissions

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

**XP Not Awarded from Quiz:**
- **Bot Detection:** Users must have 3+ posts in Discord server to earn XP
- Users can still complete quizzes and earn roles
- XP is silently not awarded if requirement not met (shadow ban)
- Check logs for: `[Quiz] User {id} completed quiz but has only {count} Discord posts`
- Use `/fix_quiz_bots` (admin) to retroactively remove XP from users who don't meet criteria

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
