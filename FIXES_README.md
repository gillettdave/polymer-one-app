# Bot Detection and Twitter Thread Fixes

This document describes the fixes implemented to address two issues:

1. **Bot Detection for Quizzes**: Prevent bots from gaming the XP system by requiring 3+ Discord posts before earning quiz XP
2. **Twitter Thread Scoring**: Score Twitter threads as a single submission instead of multiple separate tweets

## Changes Made

### Admin Commands Added

Both retroactive fixes are now available as Discord bot commands:

- `/fix_quiz_bots [execute: false]` - Remove XP from users with <3 Discord posts who earned quiz XP
- `/fix_twitter_threads [execute: false]` - Combine and re-grade Twitter thread submissions

Both commands:
- Default to dry-run mode (preview changes without applying)
- Require admin permissions (admin role or Discord administrator)
- Provide progress updates and summaries
- Can be run multiple times safely

**Usage:**
```
/fix_quiz_bots execute:false    # Preview changes (default)
/fix_quiz_bots execute:true     # Actually remove XP events

/fix_twitter_threads execute:false    # Preview changes (default)
/fix_twitter_threads execute:true      # Actually update tweets
```

### 1. Bot Detection for Quizzes

#### Forward-Looking Fix (Active Now)
- Added `count_discord_messages_for_user()` function to count Discord messages for a user
- Channel 933812975297527818 is excluded from message counting
- Added `get_quiz_min_discord_posts()` to get configurable minimum (default: 3)
- Added `/bot_set_quiz_min_posts` command to configure minimum posts requirement
- Modified quiz completion code to check if users meet minimum Discord posts requirement before awarding XP
- Applied to both:
  - Polymer University quizzes (DM-based)
  - Daily metrics quizzes (in-channel)

**How it works:**
- When a user completes a quiz, the system checks their Discord post count
- If they have <3 posts, they can still complete the quiz but won't earn XP
- **Shadow ban:** Users don't see any indication they're being filtered
- Users see normal completion messages (no mention of XP if they didn't earn any)
- The check is logged for monitoring (admins can see in logs)

**User Perspective:**
- Complete quiz normally
- See normal completion message with score
- If you meet requirements: XP is mentioned in completion message
- If you don't meet requirements: No mention of XP (silent filter)
- No warnings or error messages about Discord post requirement

#### Retroactive Fix

**Discord Command:** `/fix_quiz_bots [execute: false]`

This command removes XP from users who earned quiz XP but have <3 Discord posts.

**Usage in Discord:**
```
/fix_quiz_bots execute:false    # Preview changes (default)
/fix_quiz_bots execute:true     # Actually remove XP events
```

**Alternative:** Standalone script `fix_quiz_xp_bots.py` (for command-line use)
```bash
# Dry run (preview changes without applying)
python fix_quiz_xp_bots.py

# Actually remove XP events
python fix_quiz_xp_bots.py --execute
```

**What it does:**
1. Scans all XP events in the `xp_events` sheet
2. Finds all `quiz_completion` events
3. For each user, counts their Discord posts
4. Removes XP events for users with <3 posts
5. Provides a summary of changes

**Requirements:**
- `DISCORD_TOKEN` in `.env`
- `GUILD_ID` in `.env` (optional, will use first guild if not set)
- Google Sheets access configured
- Uses current minimum posts requirement from `/bot_set_quiz_min_posts` setting
- Channel 933812975297527818 is excluded from message counting

### 2. Twitter Thread Scoring

#### Forward-Looking Fix (Active Now)
- Added `fetch_tweet_data_for_thread_detection()` to fetch conversation_id from Twitter API
- Added `detect_thread_tweets()` to identify tweets in the same thread
- Added `combine_thread_text()` to merge thread tweets into single text
- Modified `submit_tweet` command to:
  - Detect when a submitted tweet is part of a thread
  - Check if the user has already submitted other tweets from the same thread
  - Combine all thread tweets and grade as a single submission
  - Set XP to 0 for other tweets in the thread (only the combined submission gets XP)

**How it works:**
- When a user submits a tweet, the system checks its `conversation_id`
- If the user has submitted other tweets from the same thread, they are combined
- The combined thread is graded as a single tweet
- Only one submission in the thread gets XP (the others are marked with 0 XP)
- Existing thread submissions are updated to mark them as part of thread

**User Perspective:**
- Submit tweet URLs normally (no special action needed)
- If you submit multiple tweets from same thread, they're automatically detected
- You see normal submission confirmation messages
- Only one submission per thread receives XP
- Other tweets in thread are marked in notes but don't affect your experience

#### Retroactive Fix

**Discord Command:** `/fix_twitter_threads [execute: false]`

This command finds all thread submissions and re-grades them as combined threads.

**Usage in Discord:**
```
/fix_twitter_threads execute:false    # Preview changes (default)
/fix_twitter_threads execute:true     # Actually update tweets
```

**Alternative:** Standalone script `fix_twitter_threads.py` (for command-line use)
```bash
# Dry run (preview changes without applying)
python fix_twitter_threads.py

# Actually update tweets
python fix_twitter_threads.py --execute
```

**What it does:**
1. Reads all tweets from the `tweets` sheet
2. Fetches conversation_id for each tweet from Twitter API
3. Groups tweets by user and conversation_id (threads)
4. For each thread with multiple tweets:
   - Combines all tweet texts
   - Re-grades the combined thread
   - Updates XP: first tweet gets the score, others get 0
   - Updates notes to indicate thread status

**Requirements:**
- `TWITTER_BEARER_TOKEN` in `.env`
- `OPENAI_API_KEY` in `.env` (for re-grading)
- Google Sheets access configured

## Testing

### Test Bot Detection
1. Create a test user with <3 Discord posts
2. Have them complete a quiz
3. Verify they don't earn XP (check logs)
4. Have them post 3+ messages in Discord
5. Have them complete another quiz
6. Verify they now earn XP

### Test Thread Detection
1. Submit a tweet that's part of a thread
2. Submit another tweet from the same thread
3. Verify the second submission combines with the first
4. Verify only one submission gets XP
5. Check the notes column for thread indicators

## Monitoring

### Logs to Watch
- `[Quiz] User {id} completed quiz but has only {count} Discord posts (need {min}+)`
- `[MetricsQuiz] User {id} completed quiz but has only {count} Discord posts (need {min}+)`
- `[SubmitTweet] Detected thread with {count} tweets. Combining for grading.`
- `[SubmitTweet] Updated {count} existing thread submissions.`

### Google Sheets Columns
- **xp_events sheet**: Check for removed quiz_completion events
- **tweets sheet**: 
  - Check `Notes` column for "Thread submission" or "Part of thread"
  - Check `XP Awarded` column - thread tweets should have 0 except the first

## Notes

- Both fixes are backward-compatible and fail gracefully
- If Discord post count can't be determined, XP is allowed (fail-open)
- If thread detection fails, tweets are processed normally
- Retroactive scripts can be run multiple times safely (idempotent)

## Troubleshooting

### Bot Detection Not Working
- Check that `count_discord_messages_for_user()` has permission to read message history
- Verify the guild is accessible
- Check logs for errors

### Thread Detection Not Working
- Verify `TWITTER_BEARER_TOKEN` is set and valid
- Check Twitter API rate limits
- Verify tweets have `conversation_id` in API response
- Check logs for API errors

### Retroactive Scripts Failing
- Ensure all environment variables are set
- Check Google Sheets permissions
- Verify Discord bot is in the server
- Check API rate limits (Twitter, OpenAI)

