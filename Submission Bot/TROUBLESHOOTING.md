# Troubleshooting Guide

Common issues and solutions for the Turkey Man Code Discord Submissions Bot.

## Bot Won't Start

### "Configuration error: DISCORD_TOKEN is required"
**Problem:** The `.env` file is missing or doesn't contain `DISCORD_TOKEN`.

**Solution:**
1. Ensure `.env` file exists in the bot directory
2. Copy from `env.example.txt` if needed
3. Add your bot token: `DISCORD_TOKEN=your_token_here`

### "Configuration error: GUILD_ID is required"
**Problem:** The `GUILD_ID` is missing or invalid.

**Solution:**
1. Enable Developer Mode in Discord
2. Right-click your server → Copy Server ID
3. Add to `.env`: `GUILD_ID=your_guild_id`

### Import Errors
**Problem:** `ModuleNotFoundError` or similar import errors.

**Solution:**
```bash
pip install -r requirements.txt
```

Ensure you're using Python 3.11+:
```bash
python --version
```

## Commands Not Appearing

### Commands Don't Show Up in Discord
**Problem:** Slash commands don't appear when typing `/`.

**Solutions:**
1. **Wait a few minutes** - Discord can take up to an hour to sync commands globally
2. **Restart the bot** - This forces a sync
3. **Check bot permissions** - Bot needs "Use Application Commands" permission
4. **Verify guild sync** - Check bot logs for "Synced commands to guild" message

### Commands Show But Don't Work
**Problem:** Commands appear but return errors.

**Solution:**
- Check bot logs in `logs/bot.log` for error messages
- Ensure bot has required permissions in the server
- Verify the bot is online (green status)

## Permission Issues

### "You don't have permission to review submissions"
**Problem:** User can't use review buttons or reviewer commands.

**Solutions:**
1. **Check roles:** User needs a role listed in `REVIEWER_ROLE_IDS` or `ADMIN_ROLE_IDS`
2. **Check permissions:** Users with "Manage Server" can always review
3. **Verify role IDs:** Ensure role IDs in `.env` are correct (right-click role → Copy ID)

### Bot Can't Post in Review Channel
**Problem:** Submissions aren't appearing in the review channel.

**Solutions:**
1. **Check channel permissions:**
   - Bot needs "Send Messages"
   - Bot needs "Embed Links"
   - Bot needs "Attach Files"
2. **Check channel ID:** Verify `REVIEW_CHANNEL_ID` in `.env` is correct
3. **Check thread permissions:** If using threads, bot needs "Create Public Threads"

### Bot Can't Assign Roles
**Problem:** Role assignment on approval fails.

**Solutions:**
1. **Check bot role hierarchy:** Bot's role must be higher than the role being assigned
2. **Check permissions:** Bot needs "Manage Roles" permission
3. **Verify role ID:** Check `default_approval_role_id` in submission type config
4. **Check allowlist:** Only roles in submission type configs can be assigned

## Submission Issues

### "You are on cooldown"
**Problem:** User tries to submit too soon after previous submission.

**Solution:**
- Wait for the cooldown period (default 5 minutes)
- Check `COOLDOWN_SECONDS` in `.env`
- Some submission types may have custom cooldowns

### "You have reached the daily limit"
**Problem:** User has submitted too many times today.

**Solution:**
- Wait until tomorrow (resets at UTC midnight)
- Check `MAX_SUBMISSIONS_PER_DAY` in `.env`
- Limit is per submission type

### "Invalid submission type"
**Problem:** Submission type doesn't exist.

**Solution:**
1. Check `config/submission_types.json` for available types
2. Use autocomplete in the `/submit` command
3. Reload config: `/reload_config` (admin only)

### "This submission type requires a link"
**Problem:** Submission type is configured to require a link.

**Solution:**
- Provide a valid URL in the `link` parameter
- URL must start with `http://` or `https://`

## Review Workflow Issues

### Buttons Don't Work
**Problem:** Review buttons don't respond or show errors.

**Solutions:**
1. **Check permissions:** User needs reviewer/admin role
2. **Check submission status:** Buttons only work on pending submissions
3. **Restart bot:** If the bot was restarted, persistent views are re-registered on startup; restart the bot again if buttons were posted before the restart and are unresponsive
4. **Check logs:** Look for errors in `logs/bot.log`

### Submission Already Reviewed
**Problem:** Trying to review a submission that's already been reviewed.

**Solution:**
- Each submission can only be reviewed once
- Check submission status with `/submission_lookup`
- Buttons are disabled after review

### DM Notifications Not Working
**Problem:** Users don't receive DMs about submission decisions.

**Solutions:**
1. **User has DMs closed:** Bot will use fallback channel if `NOTIFY_CHANNEL_ID` is set
2. **Check fallback channel:** Ensure `NOTIFY_CHANNEL_ID` is configured
3. **Check bot permissions:** Bot needs to send messages in notification channel
4. **User left server:** Bot can't DM users who left the server

## Thread Issues

### Threads Not Creating
**Problem:** Submissions aren't creating threads.

**Solutions:**
1. **Check `USE_THREADS`:** Ensure it's `true` in `.env`
2. **Check permissions:** Bot needs "Create Public Threads" permission
3. **Check channel type:** Threads only work in text channels
4. **Fallback:** Bot will post to channel if thread creation fails

### Can't Post in Thread
**Problem:** Bot can't post outcome messages in threads.

**Solution:**
- Ensure bot has "Send Messages in Threads" permission
- Check that thread still exists (threads can be archived)

## Data Storage Issues

### "File not found" Errors
**Problem:** Data files are missing.

**Solution:**
- Files are created automatically on first run
- Ensure `DATA_DIR` path exists and is writable
- Check file permissions (Linux)

### Data Corruption
**Problem:** JSON files are malformed.

**Solution:**
1. **Backup:** Always backup `data/submissions.json` before editing
2. **Validate JSON:** Use a JSON validator to check syntax
3. **Restore:** Restore from backup if corrupted
4. **Atomic writes:** Bot uses atomic writes to prevent corruption

### Storage Growing Large
**Problem:** `submissions.json` file is getting very large.

**Solution:**
- Consider archiving old submissions periodically
- Export to CSV for long-term storage
- The file-based approach is designed for moderate volumes (<10k submissions)

## Configuration Issues

### Submission Types Not Loading
**Problem:** `/reload_config` fails or types don't appear.

**Solutions:**
1. **Check JSON syntax:** Validate `config/submission_types.json`
2. **Check file path:** Ensure file is in `config/` directory
3. **Check permissions:** Ensure file is readable
4. **Check logs:** Look for JSON parsing errors

### Role IDs Not Working
**Problem:** Roles aren't being recognized.

**Solutions:**
1. **Verify IDs:** Right-click role → Copy ID (not the name)
2. **Check format:** In `.env`, use comma-separated: `ROLE_IDS=123,456,789`
3. **Check roles exist:** Ensure roles haven't been deleted
4. **Restart bot:** Role IDs are loaded at startup

## Performance Issues

### Bot Responding Slowly
**Problem:** Commands take a long time to respond.

**Solutions:**
1. **Check file locks:** Multiple instances may cause lock contention
2. **Check disk I/O:** Ensure data directory is on fast storage
3. **Check network:** Discord API may be slow
4. **Check logs:** Look for errors or warnings

### High Memory Usage
**Problem:** Bot uses a lot of memory.

**Solution:**
- File-based storage keeps all data in memory when loading
- For very large datasets, consider periodic archiving
- Restart bot periodically if needed

## General Debugging

### Enable Debug Logging
Edit `bot.py` to change log level:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    ...
)
```

### Check Bot Logs
```bash
# View recent logs
tail -f logs/bot.log

# Windows PowerShell
Get-Content logs/bot.log -Wait -Tail 50
```

### Test Configuration
Use `/status` command to verify:
- Configuration validity
- File paths
- Submission statistics

### Verify Permissions
1. Check bot's role in server
2. Verify channel permissions
3. Test with a user account that has reviewer/admin role

## Still Having Issues?

1. **Check logs:** `logs/bot.log` contains detailed error messages
2. **Verify configuration:** Use `/status` command
3. **Test permissions:** Ensure bot and users have correct roles
4. **Restart bot:** Many issues are resolved by restarting
5. **Check Discord status:** Discord API may be experiencing issues

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Configuration error" | Missing .env variable | Check .env file |
| "Permission denied" | Bot lacks permission | Grant required permissions |
| "Channel not found" | Invalid channel ID | Update REVIEW_CHANNEL_ID |
| "Role not found" | Invalid role ID | Update role IDs in .env |
| "Submission not found" | Invalid submission ID | Check submission ID format |
| "Already reviewed" | Submission already processed | Check submission status |

