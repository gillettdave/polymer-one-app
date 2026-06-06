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
- Automatically detects if tweet is part of a Twitter thread
- If thread detected: combines all tweets in thread and grades as single submission
- Automatically fetches tweet text (if API configured)
- Automatically grades tweet (if OpenAI configured)
- Awards XP based on grade (only one submission per thread gets XP)
- Rate limited: 30 seconds between submissions

**User Perspective:**
- Submit any tweet URL from a thread
- If you've already submitted other tweets from the same thread, they're automatically combined
- Only the combined thread gets XP (other tweets in thread get 0 XP)
- You see normal submission confirmation messages

**Example:**
```
/submit_tweet url:https://x.com/polymer_zone/status/1234567890
```

**Requirements:**
- Must set Twitter handle first with `/set_twitter`
- Tweet must be accessible (public)
- Rate limit: 30 seconds between submissions

**Thread Detection:**
- Automatically detects tweets in the same conversation/thread
- Combines thread tweets into single grade
- Updates existing thread submissions to mark them as part of thread
- Only first submission in thread receives XP

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
- Awards XP for passing (requires 3+ Discord posts in server)
- Can only be taken once per day
- Bot detection: Users with <3 Discord posts can complete quiz but won't earn XP (shadow ban)

**User Perspective:**
- Take quiz normally in-channel by clicking answer buttons
- See completion message with score
- XP is awarded automatically if you meet requirements
- No indication if you don't meet Discord post requirement (shadow ban)

**Example:**
```
/metrics_quiz num_questions:3
```

**Requirements:**
- Bot must be able to send DMs (for some quiz types)
- User must have DMs enabled from server members (for DM-based quizzes)
- OpenAI API key required for question generation
- **Anti-bot measure:** Users must meet minimum Discord posts requirement to earn XP (configurable via `/bot_set_quiz_min_posts`, default: 3)
- Channel 933812975297527818 is excluded from message counting

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
- Detects and combines Twitter threads automatically
- Updates the sheet with grades and XP
- Shows progress and results
- Can be stopped with `/stop_processing_tweets`

**User Perspective:**
- Admin command - users don't interact with this directly
- Processes tweets in background
- Updates existing submissions with grades
- Provides progress updates during processing

**Example:**
```
/process_ungraded_tweets
```

**Requirements:**
- Twitter Bearer Token must be set
- OpenAI API Key must be set

---

### `/stop_processing_tweets`
**Description:** Stop the currently running /process_ungraded_tweets command (Admin only)

**Usage:**
```
/stop_processing_tweets
```

**What it does:**
- Stops the currently running tweet processing
- Useful if processing is taking too long or needs to be interrupted
- Shows confirmation when stopped

**User Perspective:**
- Admin command - users don't interact with this directly
- Immediately stops tweet processing
- Safe to use at any time

**Example:**
```
/stop_processing_tweets
```

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
- Awards role and XP on passing (requires 3+ Discord posts)
- Supports qualifying roles
- Bot detection: Users with <3 Discord posts can complete quiz but won't earn XP (shadow ban)

**User Perspective:**
- Click button to start quiz in DMs
- Answer questions normally
- See completion message with score
- Role assigned if you pass and meet requirements
- XP awarded automatically if you meet Discord post requirement
- No indication if you don't meet requirement (shadow ban)

**Example:**
```
/post_quiz_button quiz_message:"Complete Chapter 1 Quiz" num_questions:10 required_score:7 role_to_assign:@Chapter1Graduate qualifying_role:@Student
```

**Anti-bot Measure:**
- Users must meet minimum Discord posts requirement to earn XP (configurable via `/bot_set_quiz_min_posts`, default: 3)
- Channel 933812975297527818 is excluded from message counting
- Users can still complete quizzes and earn roles
- XP is silently not awarded if requirement not met (shadow ban)

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

### `/bot_set_quiz_min_posts`
**Description:** Set minimum Discord posts required for quiz XP (Admin only)

**Parameters:**
- `min_posts`: Minimum number of Discord posts required to earn XP from quizzes (default: 3, range: 0-100)

**Usage:**
```
/bot_set_quiz_min_posts min_posts:3
/bot_set_quiz_min_posts min_posts:5
```

**What it does:**
- Sets the minimum number of Discord posts users need to earn XP from quizzes
- This is an anti-bot measure
- Users with fewer posts can still complete quizzes but won't earn XP (shadow ban)
- Channel 933812975297527818 is excluded from message counting
- Changes take effect immediately

**User Perspective:**
- Admin command - users don't interact with this directly
- Affects all future quiz completions
- Users need to meet the new requirement to earn XP

**Example:**
```
/bot_set_quiz_min_posts min_posts:5
```

**Notes:**
- Default value is 3 posts
- Can be set to 0 to disable bot detection (not recommended)
- Excluded channel (933812975297527818) is not counted
- Current value is shown in `/bot_setup` command

---

### `/fix_quiz_bots`
**Description:** Remove XP from users with <3 Discord posts who earned quiz XP (Admin only)

**Parameters:**
- `execute` (optional): Actually remove XP events (default: false, dry run mode)

**Usage:**
```
/fix_quiz_bots execute:false    # Preview changes (default)
/fix_quiz_bots execute:true     # Actually remove XP events
```

**What it does:**
- Scans all XP events in xp_events sheet
- Finds quiz_completion events for users with <3 Discord posts
- Shows summary of affected users and XP to remove
- Removes XP events when execute is true
- Defaults to dry-run mode (preview only)

**User Perspective:**
- Admin command - users don't interact with this directly
- Retroactive fix for bot detection system
- Safe to run multiple times

**Example:**
```
/fix_quiz_bots execute:false    # See what would be removed
/fix_quiz_bots execute:true     # Actually remove XP
```

**Requirements:**
- Admin role or Discord administrator
- Bot must be in server to count Discord posts
- Google Sheets access

---

### `/fix_twitter_threads`
**Description:** Combine and re-grade Twitter thread submissions (Admin only)

**Parameters:**
- `execute` (optional): Actually update tweets (default: false, dry run mode)

**Usage:**
```
/fix_twitter_threads execute:false    # Preview changes (default)
/fix_twitter_threads execute:true     # Actually update tweets
```

**What it does:**
- Finds all tweet submissions grouped by user and conversation_id
- For each thread with multiple tweets, combines them and re-grades
- Updates XP so only one tweet in thread gets XP (others get 0)
- Shows summary of threads found and processing results
- Defaults to dry-run mode (preview only)

**User Perspective:**
- Admin command - users don't interact with this directly
- Retroactive fix for thread detection system
- Updates existing submissions in tweets sheet

**Example:**
```
/fix_twitter_threads execute:false    # See what would be updated
/fix_twitter_threads execute:true     # Actually update tweets
```

**Requirements:**
- Admin role or Discord administrator
- Twitter Bearer Token for fetching conversation data
- OpenAI API Key for re-grading threads
- Google Sheets access

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

## New Features

### Bot Detection for Quizzes
- **Anti-bot measure:** Users must meet minimum Discord posts requirement to earn XP (configurable, default: 3)
- **Configurable:** Admins can set minimum via `/bot_set_quiz_min_posts` command
- **Excluded channel:** Channel 933812975297527818 is excluded from message counting
- **Shadow ban:** Users who don't meet requirement can still complete quizzes but won't earn XP
- **No user notification:** Users don't see any indication they're being filtered
- **Applies to:** All quiz types (Polymer University quizzes, daily metrics quizzes)
- **Retroactive fix:** Use `/fix_quiz_bots` to remove XP from users who don't meet criteria

### Twitter Thread Detection
- **Automatic detection:** System detects when tweets are part of the same thread
- **Combined grading:** Thread tweets are combined and graded as single submission
- **Single XP award:** Only one submission per thread receives XP (others get 0)
- **Retroactive fix:** Use `/fix_twitter_threads` to fix existing thread submissions

## Notes

- All commands are slash commands (type `/` in Discord to see them)
- Commands are case-insensitive
- Most commands support autocomplete for parameters
- Admin commands require admin role or Discord administrator permissions
- Rate limits apply to some commands (shown in command descriptions)
- Commands that modify data are logged for audit purposes
- Bot detection and thread detection work automatically in the background





