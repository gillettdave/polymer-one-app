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

- Check a user's XP: `/xp_me`
- See the leaderboard: `/xp_leaderboard`

If you add manual XP commands such as `/xp_admin_give`, you will be able to:

- Reward custom contributions
- Correct mistakes
- Run ad–hoc campaigns

All XP events should go through `xp_events` for auditability.

**Bot Detection for Quizzes:**
- Users must meet minimum Discord posts requirement to earn XP (configurable, default: 3)
- Channel 933812975297527818 is excluded from message counting
- Configure minimum via `/bot_set_quiz_min_posts` command
- Users can still complete quizzes and earn roles
- XP is silently not awarded if requirement not met (shadow ban)
- Check logs for: `[Quiz] User {id} completed quiz but has only {count} Discord posts (need {min}+)`
- Use `/fix_quiz_bots` to retroactively remove XP from users who don't meet criteria
- Defaults to dry-run mode (preview changes)
- Run with `execute:true` to actually remove XP events

### 3.3 Tweet Campaigns

For a tweet/X campaign:

1. Instruct users to link their handle: `/set_twitter`
2. Allow submissions via: `/submit_tweet <url>`
3. **Thread Detection:** System automatically detects Twitter threads
   - Multiple tweets from same thread are combined and graded as one
   - Only first submission in thread receives XP
   - Check `Notes` column for "Thread submission" indicators
4. Review the `tweets` sheet for:
   - `Graded` flags
   - `Score`
   - `XP Awarded`
   - `Notes` (thread indicators)
5. Use XP totals from `xp_totals` to decide on:
   - Roles
   - Prizes
   - Allowlist spots

If OpenAI or Twitter API are not available, the bot can still log tweets and you can grade them manually.

**Retroactive Thread Fix:**
- Use `/fix_twitter_threads` to combine and re-grade existing thread submissions
- Defaults to dry-run mode (preview changes)
- Run with `execute:true` to actually update tweets

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
- Use retroactive fix commands: `/fix_quiz_bots` and `/fix_twitter_threads`

Any structural changes to Google Sheets (column names, tab names) should be coordinated with developers,
since the bot relies on consistent headers and tab names.

## 6. Admin Commands Reference

### Retroactive Fix Commands

**`/fix_quiz_bots [execute: false]`**
- Removes XP from users with <3 Discord posts who earned quiz XP
- Defaults to dry-run mode (preview changes)
- Shows summary of affected users and XP to remove
- Safe to run multiple times

**`/fix_twitter_threads [execute: false]`**
- Combines and re-grades Twitter thread submissions
- Defaults to dry-run mode (preview changes)
- Shows thread groups found and processing results
- Requires Twitter Bearer Token and OpenAI API Key
- Safe to run multiple times

**`/bot_set_quiz_min_posts [min_posts]`**
- Sets minimum Discord posts required for quiz XP (default: 3, range: 0-100)
- Channel 933812975297527818 is excluded from message counting
- Changes take effect immediately
- Current value shown in `/bot_setup` command

Both retroactive fix commands provide progress updates and detailed summaries.
