# Metrics Quiz Troubleshooting Guide

If `/bot_manual_quiz_post` reports success but the quiz doesn't appear in the channel, check the following:

## Quick Checklist

1. ✅ **Check Bot Logs** - Most important!
2. ✅ **Verify Channel Configuration**
3. ✅ **Check OpenAI API Key**
4. ✅ **Verify Bot Permissions**
5. ✅ **Check Component Status**
6. ✅ **Verify Channel Type**

---

## 1. Check Bot Logs (Most Important!)

The function logs warnings/errors that explain why it failed. Check:

**Log Files:**
- `logs/polyone.log` - All activity
- `logs/polyone_errors.log` - Errors only

**Look for these messages:**
- `[MetricsQuiz] Metrics quiz channel not found` - Channel ID issue
- `[MetricsQuiz] Channel X is not a text channel` - Wrong channel type
- `[MetricsQuiz] Bot missing 'Send Messages' permission` - Permission issue
- `[MetricsQuiz] Bot missing 'Embed Links' permission` - Permission issue
- `[MetricsQuiz] Failed to generate questions` - OpenAI API issue
- `[MetricsQuiz] OpenAI client not initialized` - Missing API key
- `[MetricsQuiz] Error posting announcement` - General error

**How to check:**
```bash
# Windows PowerShell
Get-Content logs\polyone_errors.log -Tail 50

# Or open the file in a text editor and scroll to the bottom
```

---

## 2. Verify Channel Configuration

**Check if channel is set correctly:**
```
/bot_setup
```

This will show the current `metrics_quiz_channel_id`. Verify it matches your intended channel.

**If not set, set it:**
```
/bot_setup metrics_quiz_channel:#your-channel-name
```

**Or use the dedicated command:**
The metrics quiz channel should be set via `/bot_setup` with the `metrics_quiz_channel` parameter.

**Verify channel ID:**
- Right-click the channel → Copy ID (Developer Mode must be enabled)
- Compare with what `/bot_setup` shows
- Make sure the channel ID in state.json matches

---

## 3. Check OpenAI API Key (Required!)

**The quiz requires OpenAI API to generate questions.**

**Check if API key is set:**
- Look in your `.env` file for `OPENAI_API_KEY`
- Verify it's not empty
- Verify it's valid and active

**Test API key:**
- Try using `/metrics_quiz` command (user command) - if this fails, API key is likely the issue
- Check logs for: `[MetricsQuiz] OpenAI client not initialized`

**If missing:**
1. Get API key from: https://platform.openai.com/api-keys
2. Add to `.env`: `OPENAI_API_KEY=sk-...`
3. Restart the bot

**If API key fails:**
- Check quota/credits on OpenAI dashboard
- Verify API key hasn't been revoked
- Check for rate limit errors in logs

---

## 4. Verify Bot Permissions

The bot needs these permissions in the quiz channel:

**Required Permissions:**
- ✅ **Send Messages** - To post the quiz
- ✅ **Embed Links** - To post embeds with questions
- ✅ **Read Message History** - To read channel
- ✅ **Manage Messages** - To delete old quiz messages (optional but recommended)

**How to check:**
1. Right-click the channel → Edit Channel → Permissions
2. Find your bot's role
3. Verify all required permissions are enabled

**How to fix:**
1. Go to Server Settings → Roles
2. Find bot's role
3. Enable required permissions
4. Make sure bot's role is high enough in hierarchy

**Check logs for:**
- `[MetricsQuiz] Bot missing 'Send Messages' permission`
- `[MetricsQuiz] Bot missing 'Embed Links' permission`

---

## 5. Check Component Status

**Verify metrics quiz component is enabled:**
```
/bot_component_status
```

**If disabled, enable it:**
```
/bot_component_toggle component:metrics_quiz enabled:true
```

**Note:** The component toggle affects scheduled quizzes, but manual posting should work regardless. However, it's good to verify it's enabled.

---

## 6. Verify Channel Type

**The quiz can only be posted in text channels.**

**Check:**
- Is the channel a text channel? (not voice, stage, or forum)
- Check logs for: `[MetricsQuiz] Channel X is not a text channel`

**Fix:**
- Use a text channel for the quiz
- Update channel configuration: `/bot_setup metrics_quiz_channel:#text-channel`

---

## 7. Check for Exceptions

**The function catches exceptions but logs them. Check for:**

**Permission Errors:**
- `discord.Forbidden` - Bot lacks permissions
- Check error message for specific missing permission

**Network/API Errors:**
- OpenAI API errors (quota, rate limit, invalid key)
- Discord API errors (rate limit, connection issues)

**How to see full error:**
- Check `logs/polyone_errors.log` for full stack traces
- Look for `[MetricsQuiz] Error posting announcement` messages

---

## Step-by-Step Debugging Process

1. **Run the command:**
   ```
   /bot_manual_quiz_post
   ```

2. **Immediately check logs:**
   - Open `logs/polyone_errors.log`
   - Look for `[MetricsQuiz]` messages
   - Note any warnings or errors

3. **Verify configuration:**
   ```
   /bot_setup
   ```
   - Check `metrics_quiz_channel_id` is set
   - Verify it matches your intended channel

4. **Test OpenAI API:**
   ```
   /metrics_quiz
   ```
   - If this works, API is fine
   - If this fails, fix API key first

5. **Check permissions:**
   - Verify bot has all required permissions
   - Check bot's role hierarchy

6. **Try again:**
   ```
   /bot_manual_quiz_post
   ```

---

## Common Issues and Solutions

### Issue: "Success" message but no quiz posted

**Cause:** Function returned early without raising exception

**Solution:**
1. Check logs for warnings/errors
2. Most likely: Missing OpenAI API key or failed question generation
3. Check: `[MetricsQuiz] Failed to generate questions` in logs

---

### Issue: Channel not found error

**Cause:** Channel ID is incorrect or channel was deleted

**Solution:**
1. Verify channel exists
2. Re-set channel: `/bot_setup metrics_quiz_channel:#channel-name`
3. Check state.json for correct channel ID

---

### Issue: Permission denied

**Cause:** Bot missing required permissions

**Solution:**
1. Check which permission is missing (from logs)
2. Grant missing permission in channel settings
3. Ensure bot's role is high enough in hierarchy

---

### Issue: Questions not generating

**Cause:** OpenAI API key missing or invalid

**Solution:**
1. Verify `OPENAI_API_KEY` in `.env`
2. Test API key validity
3. Check OpenAI dashboard for quota/credits
4. Restart bot after adding key

---

### Issue: Component disabled

**Cause:** Metrics quiz component is disabled

**Solution:**
```
/bot_component_toggle component:metrics_quiz enabled:true
```

---

## Testing the Fix

After making changes:

1. **Restart the bot** (if you changed .env or permissions)

2. **Test question generation:**
   ```
   /metrics_quiz
   ```
   This tests if OpenAI API is working

3. **Test manual posting:**
   ```
   /bot_manual_quiz_post
   ```

4. **Check logs again:**
   - Should see: `[MetricsQuiz] Posted daily metrics quiz with X questions`
   - No errors or warnings

5. **Verify in channel:**
   - Quiz header message should appear
   - Question messages with buttons should appear below

---

## Still Not Working?

If none of the above fixes the issue:

1. **Check full error logs:**
   - `logs/polyone_errors.log` - Look for full stack traces
   - `logs/polyone.log` - Look for all `[MetricsQuiz]` messages

2. **Verify bot is in the server:**
   - Bot must be a member of the server
   - Not just invited, but actually joined

3. **Check Discord API status:**
   - https://discordstatus.com/
   - Temporary outages can cause issues

4. **Try a different channel:**
   - Test with a simple text channel
   - Verify it works there first

5. **Check bot's role:**
   - Bot's role must be below @everyone or have explicit permissions
   - Role hierarchy matters for permissions

---

## Quick Command Reference

```bash
# Check configuration
/bot_setup

# Check component status
/bot_component_status

# Enable component
/bot_component_toggle component:metrics_quiz enabled:true

# Set quiz channel
/bot_setup metrics_quiz_channel:#your-channel

# Test question generation (user command)
/metrics_quiz

# Post quiz manually (admin)
/bot_manual_quiz_post
```

---

## Expected Behavior

When working correctly, `/bot_manual_quiz_post` should:

1. ✅ Return success message immediately
2. ✅ Post a header embed message in the channel
3. ✅ Post 3 question messages with answer buttons
4. ✅ Log success: `[MetricsQuiz] Posted daily metrics quiz with 3 questions`
5. ✅ Store message IDs in state.json

If any of these don't happen, check the logs for the specific failure point.





