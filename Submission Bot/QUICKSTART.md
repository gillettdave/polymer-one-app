# Quick Start Guide

Get the bot running in 5 minutes!

## Prerequisites Checklist

- [ ] Python 3.11+ installed
- [ ] Discord account
- [ ] Admin access to a Discord server

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application" → Name it → Create
3. Go to "Bot" → "Add Bot" → "Yes, do it!"
4. Enable these intents:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
5. Copy the bot token (keep it secret!)

## Step 3: Get IDs

Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode), then:

- Right-click server → Copy Server ID → This is your `GUILD_ID`
- Right-click review channel → Copy Channel ID → This is your `REVIEW_CHANNEL_ID`
- Right-click reviewer role → Copy Role ID → Add to `REVIEWER_ROLE_IDS`
- Right-click admin role → Copy Role ID → Add to `ADMIN_ROLE_IDS`

## Step 4: Configure

1. Copy `env.example.txt` to `.env`
2. Edit `.env` with your values:
   ```
   DISCORD_TOKEN=your_token_here
   GUILD_ID=your_guild_id_here
   REVIEW_CHANNEL_ID=your_channel_id_here
   REVIEWER_ROLE_IDS=role_id_1,role_id_2
   ADMIN_ROLE_IDS=role_id_1
   ```

## Step 5: Invite Bot

1. In Discord Developer Portal → OAuth2 → URL Generator
2. Select scopes: `bot`, `applications.commands`
3. Select permissions:
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Create Public Threads
   - Manage Roles (if using role assignment)
4. Copy URL → Open in browser → Select server → Authorize

## Step 6: Run

```bash
python bot.py
```

You should see:
```
Logged in as YourBot#1234 (ID: 123456789)
Synced commands to guild 987654321
```

## Step 7: Test

1. In Discord, type `/submit`
2. Fill out the form
3. Check your review channel - submission should appear!
4. Click the review buttons to test the workflow

## Next Steps

- Customize submission types in `config/submission_types.json`
- Read [COMMANDS.md](COMMANDS.md) for all commands
- Read [CONFIG.md](CONFIG.md) for advanced configuration
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if you have issues

## Common Issues

**Bot doesn't respond?**
- Check bot is online (green status)
- Verify bot has permissions in server
- Check `logs/bot.log` for errors

**Commands not showing?**
- Wait a few minutes (Discord sync can be slow)
- Restart the bot
- Verify bot has "Use Application Commands" permission

**Permission errors?**
- Check role IDs in `.env` are correct
- Verify bot's role is high enough in hierarchy
- Ensure bot has required channel permissions

For more help, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).


