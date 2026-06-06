# Recent Changes Summary

This document summarizes all recent changes to the PolyOne bot, including bot detection, Twitter thread handling, and new admin commands.

## Overview

Two major features were added to address system gaming and improve fairness:

1. **Bot Detection for Quizzes** - Prevents bots from gaming the XP system
2. **Twitter Thread Detection** - Scores threads as single submissions

Both features work automatically in the background and include retroactive fix commands for admins.

---

## 1. Bot Detection for Quizzes

### Problem
Thousands of bots were taking daily quizzes to game the XP system without contributing to the community.

### Solution
Users must meet a **minimum Discord posts requirement** (configurable, default: 3) in the server to earn XP from quizzes. Channel 933812975297527818 is excluded from message counting.

### How It Works

**From User's Perspective:**
- Complete quizzes normally (no change in experience)
- See normal completion messages with scores
- If you meet requirements: XP is mentioned in completion message
- If you don't meet requirements: No mention of XP (silent filter)
- **Shadow ban:** No indication you're being filtered

**Technical Details:**
- System checks Discord post count when quiz is completed
- Count includes all non-bot messages across all channels (except excluded channels)
- Channel 933812975297527818 is excluded from message counting
- Minimum posts requirement is configurable via `/bot_set_quiz_min_posts` (default: 3)
- Check happens before XP is awarded
- If requirement not met: Quiz completes normally but XP is not awarded
- Logged for monitoring: `[Quiz] User {id} completed quiz but has only {count} Discord posts (need {min}+)`

**Applies To:**
- Polymer University quizzes (DM-based)
- Daily metrics quizzes (in-channel)
- All quiz types

### Admin Commands

**`/fix_quiz_bots [execute: false]`**
- Removes XP from users who don't meet minimum posts requirement (uses current setting)
- Defaults to dry-run mode (preview changes)
- Shows summary of affected users and XP to remove
- Uses current minimum posts requirement from `/bot_set_quiz_min_posts` setting
- Safe to run multiple times

**`/bot_set_quiz_min_posts [min_posts]`**
- Sets minimum Discord posts required for quiz XP (default: 3, range: 0-100)
- Channel 933812975297527818 is excluded from message counting
- Changes take effect immediately
- Current value shown in `/bot_setup` command

**Usage:**
```
/fix_quiz_bots execute:false    # Preview changes (default)
/fix_quiz_bots execute:true     # Actually remove XP events
```

**What It Does:**
1. Scans all XP events in `xp_events` sheet
2. Finds all `quiz_completion` events
3. For each user, counts their Discord posts
4. Removes XP events for users with <3 posts
5. Provides detailed summary

**Requirements:**
- Admin role or Discord administrator
- Bot must be in server to count Discord posts
- Google Sheets access

---

## 2. Twitter Thread Detection

### Problem
Users were submitting multiple tweets from the same thread, getting multiple scores and XP for what should be a single submission.

### Solution
Twitter threads are automatically detected and scored as a single submission.

### How It Works

**From User's Perspective:**
- Submit tweet URLs normally (no special action needed)
- If you submit multiple tweets from same thread, they're automatically detected
- You see normal submission confirmation messages
- Only one submission per thread receives XP
- Other tweets in thread are marked in notes but don't affect your experience

**Technical Details:**
- System uses Twitter API `conversation_id` to detect threads
- When a tweet is submitted, system checks if user has submitted other tweets from same thread
- All thread tweets are combined into single text
- Combined thread is graded as one submission
- Only first submission in thread receives XP (others get 0 XP)
- Existing thread submissions are updated to mark them as part of thread

**Detection Process:**
1. User submits tweet URL
2. System fetches tweet data including `conversation_id`
3. Checks if user has submitted other tweets with same `conversation_id`
4. If found: Combines all tweets and grades as one
5. Updates existing submissions to mark them as thread tweets

### Admin Commands

**`/fix_twitter_threads [execute: false]`**
- Combines and re-grades Twitter thread submissions
- Defaults to dry-run mode (preview changes)
- Shows thread groups found and processing results
- Safe to run multiple times

**Usage:**
```
/fix_twitter_threads execute:false    # Preview changes (default)
/fix_twitter_threads execute:true     # Actually update tweets
```

**What It Does:**
1. Reads all tweets from `tweets` sheet
2. Fetches `conversation_id` for each tweet from Twitter API
3. Groups tweets by user and `conversation_id` (threads)
4. For each thread with multiple tweets:
   - Combines all tweet texts
   - Re-grades the combined thread
   - Updates XP: first tweet gets score, others get 0
   - Updates notes to indicate thread status

**Requirements:**
- Admin role or Discord administrator
- Twitter Bearer Token for fetching conversation data
- OpenAI API Key for re-grading threads
- Google Sheets access

---

## Updated Commands

### `/submit_tweet`
**New Behavior:**
- Automatically detects if tweet is part of a thread
- If thread detected: combines all tweets in thread and grades as single submission
- Only one submission per thread receives XP
- Other tweets in thread get 0 XP

**User Experience:**
- No change in how you submit tweets
- System handles thread detection automatically
- You see normal confirmation messages

### `/metrics_quiz`
**New Behavior:**
- Requires 3+ Discord posts to earn XP
- Users can still complete quiz normally
- Shadow ban: No indication if you don't meet requirement

**User Experience:**
- Complete quiz normally
- See normal completion message
- XP mentioned only if you earned it

### `/post_quiz_button` (Admin)
**New Behavior:**
- Requires 3+ Discord posts to earn XP
- Users can still complete quiz and earn roles
- Shadow ban: No indication if you don't meet requirement

**User Experience:**
- Click button to start quiz
- Complete quiz normally
- Role assigned if you pass
- XP mentioned only if you earned it

---

## Monitoring

### Logs to Watch

**Bot Detection:**
- `[Quiz] User {id} completed quiz but has only {count} Discord posts (need 3+)`
- `[MetricsQuiz] User {id} completed quiz but has only {count} Discord posts (need 3+)`

**Thread Detection:**
- `[SubmitTweet] Detected thread with {count} tweets. Combining for grading.`
- `[SubmitTweet] Updated {count} existing thread submissions.`

### Google Sheets Indicators

**xp_events sheet:**
- Check for removed `quiz_completion` events (after running `/fix_quiz_bots`)

**tweets sheet:**
- `Notes` column: Look for "Thread submission" or "Part of thread"
- `XP Awarded` column: Thread tweets should have 0 except the first

---

## Best Practices

### For Admins

1. **Run Retroactive Fixes:**
   - Start with dry-run mode to preview changes
   - Review summaries before executing
   - Run fixes during low-traffic periods

2. **Monitor Logs:**
   - Check for bot detection logs regularly
   - Monitor thread detection success rate
   - Watch for API errors

3. **Verify Results:**
   - Check `xp_events` sheet after running `/fix_quiz_bots`
   - Check `tweets` sheet after running `/fix_twitter_threads`
   - Verify XP totals are correct

### For Users

1. **Quizzes:**
   - Make sure you have 3+ posts in Discord before taking quizzes
   - Complete quizzes normally - system handles everything automatically
   - Check `/xp_me` to verify XP was awarded

2. **Tweets:**
   - Submit tweets normally - no special action needed
   - If submitting thread tweets, only one will receive XP
   - Check `/check_tweets` to see your submissions

---

## Troubleshooting

### Bot Detection Not Working
- Check bot has permission to read message history
- Verify guild is accessible
- Check logs for errors
- Ensure bot is in the server

### Thread Detection Not Working
- Verify `TWITTER_BEARER_TOKEN` is set and valid
- Check Twitter API rate limits
- Verify tweets have `conversation_id` in API response
- Check logs for API errors

### Retroactive Commands Failing
- Ensure all environment variables are set
- Check Google Sheets permissions
- Verify Discord bot is in the server
- Check API rate limits (Twitter, OpenAI)
- Start with dry-run mode to identify issues

---

## Technical Implementation

### Functions Added

**Bot Detection:**
- `count_discord_messages_for_user()` - Counts Discord messages for a user (excludes channel 933812975297527818)
- `get_quiz_min_discord_posts()` - Gets configurable minimum posts requirement (default: 3)

**Thread Detection:**
- `fetch_tweet_data_for_thread_detection()` - Fetches conversation_id from Twitter API
- `detect_thread_tweets()` - Identifies tweets in same thread
- `combine_thread_text()` - Merges thread tweets into single text

### Code Changes

**Quiz Completion:**
- Added Discord post count check before awarding XP
- Shadow ban: No XP mention if requirement not met
- Applied to both quiz types

**Tweet Submission:**
- Added thread detection on submission
- Automatic combination of thread tweets
- Updates existing thread submissions

---

## Files Modified

- `PolyOne.py` - Main bot code with all new features
- `fix_quiz_xp_bots.py` - Standalone script for retroactive fix
- `fix_twitter_threads.py` - Standalone script for retroactive fix
- `COMMANDS_REFERENCE.md` - Updated command documentation
- `POLYONE_BOT_DOCUMENTATION.md` - Updated troubleshooting
- `FIXES_README.md` - Detailed fix documentation
- `polyone_docs_bundle/POLYONE_ADMIN_GUIDE.md` - Updated admin guide

---

## Backward Compatibility

- All changes are backward-compatible
- Features fail gracefully if APIs unavailable
- Existing functionality unchanged
- Retroactive fixes are safe to run multiple times

---

## Configuration

### Minimum Discord Posts Requirement

**Command:** `/bot_set_quiz_min_posts [min_posts]`

- **Default:** 3 posts
- **Range:** 0-100
- **Excluded Channel:** 933812975297527818 (not counted)
- **Effect:** Immediate (affects all future quiz completions)
- **View Current:** Shown in `/bot_setup` command

**Usage:**
```
/bot_set_quiz_min_posts min_posts:3    # Set to 3 (default)
/bot_set_quiz_min_posts min_posts:5    # Set to 5
/bot_set_quiz_min_posts min_posts:0     # Disable bot detection (not recommended)
```

## Future Considerations

- May want to add time-based requirement (e.g., posts in last 30 days)
- Could add similar detection for tweet submissions
- May want to add admin override for special cases
- Could make excluded channels configurable via command

---

For detailed command documentation, see `COMMANDS_REFERENCE.md`.
For troubleshooting, see `POLYONE_BOT_DOCUMENTATION.md`.
For admin operations, see `polyone_docs_bundle/POLYONE_ADMIN_GUIDE.md`.

