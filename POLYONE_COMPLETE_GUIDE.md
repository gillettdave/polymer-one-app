# PolyOne Bot: Complete User & Administrator Guide

## Introduction

**PolyOne** is a comprehensive Discord bot designed for the Polymer University community. It serves as a complete engagement and gamification platform that tracks blockchain metrics, manages an XP (experience points) system, grades social media content, runs educational quizzes, and hosts prediction games—all while maintaining detailed records in Google Sheets.

### What PolyOne Does

PolyOne transforms your Discord server into an interactive learning and engagement hub by:

- **Tracking Real-Time Metrics**: Monitors Polymer blockchain analytics and announces significant events automatically
- **Gamifying Engagement**: Awards XP for various activities including tweet submissions, quiz participation, and predictions
- **Content Grading**: Automatically evaluates Twitter/X submissions using AI to ensure quality content
- **Educational Quizzes**: Runs interactive quizzes based on current blockchain metrics and general knowledge
- **Prediction Games**: Allows users to predict future metrics and compete for accuracy-based rewards
- **Comprehensive Admin Tools**: Provides powerful tools for managing XP, verifying grants, and maintaining data integrity

### Core Philosophy

PolyOne is built on three core principles:

1. **Transparency**: All data is stored in Google Sheets, making it accessible and auditable
2. **Fairness**: Tiered daily XP caps ensure new users can catch up while maintaining competitive balance
3. **Automation**: Once configured, the bot handles most operations automatically, requiring minimal manual intervention

---

## Quick Command Reference

### User Commands (Available to Everyone)

| Command | Description |
|---------|-------------|
| `/polymer_status` | View current Polymer blockchain metrics and statistics |
| `/xp_me` | Check your total XP and current tier |
| `/xp_leaderboard` | View the top XP earners (default: top 10) |
| `/xp_daily_status` | Check your daily XP progress and remaining cap |
| `/xp_history` | View your recent XP earning history |
| `/set_twitter` | Link your Twitter/X handle to your Discord account |
| `/submit_tweet` | Submit a tweet URL for grading and XP rewards |
| `/check_tweets` | View how many tweets you've submitted |
| `/polyu_rank` | Check your rank on the Polymer University leaderboard |
| `/metrics_quiz` | Start an interactive quiz based on current metrics |
| `/predict_volume` | Predict Polymer's total volume for a future date |
| `/predict_top10` | Predict which tokens will enter/leave the top 10 |
| `/my_predictions` | View your active (unresolved) predictions |
| `/prediction_leaderboard` | View top predictors by accuracy |

### Admin Commands (Admin Role Required)

| Command | Description |
|---------|-------------|
| `/process_ungraded_tweets` | Process all ungraded tweets in the sheet |
| `/stop_processing_tweets` | Stop the currently running tweet processing |
| `/xp_admin_give` | Grant XP to a specific user |
| `/xp_admin_give_role` | Grant XP to all members with a specific role |
| `/xp_admin_verify_role` | Verify and optionally repair XP grants for a role |
| `/xp_admin_check_user` | Check if a user received XP for a role grant |
| `/xp_admin_remove` | Remove XP from a user |
| `/fix_quiz_bots` | Remove XP from users with insufficient Discord activity |
| `/fix_twitter_threads` | Combine and re-grade Twitter thread submissions |
| `/xp_grandfather_bonus` | Award bonus XP to existing contributors |
| `/xp_migrate_historical` | Migrate historical XP from old leaderboard CSV |
| `/xp_migrate_check` | Check migration compatibility with Twitter handles |
| `/bot_component_toggle` | Enable or disable bot components |
| `/bot_component_status` | View status of all bot components |
| `/bot_setup` | Configure bot channels, admin role, and settings |
| `/bot_setup_metrics_channel` | Set the channel for metrics announcements |
| `/bot_setup_volume_channel` | Set the voice channel for volume counter |
| `/bot_set_min_posts` | Set minimum Discord posts required for XP activities |
| `/bot_manual_quiz_post` | Manually post a metrics quiz announcement |
| `/clean_threads` | Clean all bot-created threads in a channel |

---

## Detailed Command Explanations

### User Commands

#### `/polymer_status`
**Purpose**: Displays real-time Polymer blockchain statistics

**What it shows**:
- Total volume (in USD and billions)
- Daily volume (past 24 hours)
- Biggest transfer of the day
- Top transactions

**Use cases**:
- Quick check of network activity
- Understanding current metrics before making predictions
- Reference for quiz questions

**How it works**: Fetches data from Polymer analytics API and formats it into an easy-to-read summary.

---

#### `/xp_me`
**Purpose**: View your personal XP statistics

**What it shows**:
- Total XP
- Current tier (affects daily cap)
- Daily XP earned today
- Daily XP cap remaining

**Use cases**:
- Check if you've hit your daily cap
- See your progress toward the next tier
- Verify XP was awarded correctly

**How it works**: Reads from the `xp_totals` Google Sheet, which automatically calculates totals from `xp_events`.

---

#### `/xp_leaderboard`
**Purpose**: View top XP earners

**Parameters**:
- `limit` (optional): Number of users to show (default: 10, max: 25)

**What it shows**:
- Ranked list of top users
- Total XP for each user
- Your position (if not in top list)

**Use cases**:
- See who's leading
- Check your ranking
- Competitive motivation

**How it works**: Reads from `xp_totals` sheet, sorts by total XP, and displays top N users.

---

#### `/xp_daily_status`
**Purpose**: Check your daily XP progress and cap

**What it shows**:
- Current tier and daily cap
- XP earned today
- XP remaining in today's cap
- When the cap resets (midnight UTC)

**Use cases**:
- Plan your activities for the day
- Understand why you're not earning XP (cap reached)
- See your tier progression

**How it works**: Calculates daily XP from `xp_events` filtered by today's date, compares against tier-based cap.

---

#### `/xp_history`
**Purpose**: View your recent XP earning history

**Parameters**:
- `limit` (optional): Number of events to show (default: 10, max: 50)

**What it shows**:
- Recent XP events
- Source of each XP (tweet, quiz, prediction, etc.)
- Amount earned
- Timestamp

**Use cases**:
- Verify XP was awarded
- Track which activities earn the most XP
- Debug missing XP

**How it works**: Reads from `xp_events` sheet, filters by your Discord ID, sorts by timestamp (newest first).

---

#### `/set_twitter`
**Purpose**: Link your Twitter/X handle to your Discord account

**Parameters**:
- `handle`: Your Twitter/X handle (with or without @)

**Why it's needed**: Required before submitting tweets. Links your Discord account to your Twitter identity for verification.

**How it works**: Stores the mapping in `twitter_handles.csv` locally. This mapping is used to verify tweet ownership.

---

#### `/submit_tweet`
**Purpose**: Submit a tweet URL for grading and XP rewards

**Parameters**:
- `url`: Full Twitter/X status URL

**What happens**:
1. Validates the URL format
2. Extracts tweet ID
3. Checks for duplicates
4. Fetches tweet text via Twitter API
5. Grades tweet using OpenAI (if configured)
6. Awards XP based on score (0-5 scale)
7. Saves to `tweets` sheet

**XP Calculation**:
- Score 0-5 (in 0.5 increments) from AI grading
- XP = rounded score (e.g., 4.5 score = 5 XP)
- Subject to daily tweet XP limit (default: 3 tweets/day with XP)

**Thread Detection**:
- Automatically detects if tweet is part of a thread
- Combines thread tweets for grading
- Only first tweet in thread gets XP (others get 0)

**Use cases**:
- Submit content for community engagement
- Earn XP for quality posts
- Track your content submissions

**Requirements**:
- Must have set Twitter handle via `/set_twitter`
- Tweet must be publicly accessible
- Twitter API Bearer Token must be configured (for text fetching)
- OpenAI API Key must be configured (for grading)

---

#### `/check_tweets`
**Purpose**: View your tweet submission statistics

**Parameters**:
- `user` (optional, admin only): View another user's stats

**What it shows**:
- Total tweets submitted
- Tweets with XP today
- Daily tweet XP limit status

**Use cases**:
- Track your submission activity
- Verify tweet submissions were recorded
- Check if you've hit daily limit

---

#### `/polyu_rank`
**Purpose**: Check your rank on Polymer University leaderboard

**What it shows**:
- Your rank number
- Total XP
- Position relative to others

**How it works**: Reads from optional `leaderboard` sheet if configured, otherwise uses `xp_totals`.

---

#### `/metrics_quiz`
**Purpose**: Start an interactive quiz based on current Polymer metrics

**What happens**:
1. Bot sends you a DM with quiz questions
2. Questions are based on real-time blockchain data
3. Multiple choice format (A, B, C, D)
4. You answer by clicking buttons
5. Score is calculated
6. XP is awarded based on performance

**XP Rewards**:
- Based on quiz score
- Requires minimum Discord posts (configurable, default: 3)
- One quiz per day limit

**Use cases**:
- Test your knowledge
- Learn about current metrics
- Earn XP through education

**Requirements**:
- Bot must be able to DM you
- Must have minimum Discord posts (prevents bot abuse)

---

#### `/predict_volume`
**Purpose**: Predict Polymer's total volume for a future date

**Parameters**:
- `volume_billions`: Predicted volume in billions (e.g., 2.5 for $2.5B)
- `target_date` (optional): Date in YYYY-MM-DD format (defaults to tomorrow)

**What happens**:
1. Prediction is saved to `predictions` sheet
2. At resolution time (configurable, default: 2:00 UTC), actual volume is fetched
3. Accuracy is calculated
4. XP is awarded based on accuracy

**XP Calculation**:
- Accuracy = 1.0 - (error percentage)
- XP = base_xp × (0.5 + 1.5 × accuracy)
- Perfect prediction (0% error) = 2× base XP

**Deadlines**:
- Must submit before 1 hour before resolution time
- One prediction per date per user

**Use cases**:
- Test your market knowledge
- Compete for accuracy
- Earn XP through predictions

---

#### `/predict_top10`
**Purpose**: Predict which tokens will enter or leave the top 10 transactions

**Parameters**:
- `target_date` (optional): Date in YYYY-MM-DD format
- `new_entries`: Comma-separated token symbols that will enter top 10
- `removed_entries`: Comma-separated token symbols that will leave top 10

**What happens**:
1. Prediction is saved
2. At resolution, actual top 10 is compared
3. Accuracy calculated based on correct predictions
4. XP awarded proportionally

**XP Calculation**:
- Based on precision and recall
- Bonus for perfect precision
- Similar to volume predictions

**Use cases**:
- Predict market movements
- Test understanding of transaction patterns
- Compete on leaderboard

---

#### `/my_predictions`
**Purpose**: View your active (unresolved) predictions

**What it shows**:
- All predictions you've made
- Target dates
- Prediction values
- Status (active/unresolved)

**Use cases**:
- Track your predictions
- See what's pending resolution
- Plan future predictions

---

#### `/prediction_leaderboard`
**Purpose**: View top predictors ranked by accuracy

**Parameters**:
- `limit` (optional): Number of users to show (default: 10, max: 25)

**What it shows**:
- Top predictors by accuracy
- Number of predictions made
- Average accuracy
- Total XP from predictions

**Use cases**:
- See who's best at predicting
- Competitive motivation
- Learn from top predictors

---

### Admin Commands

#### `/process_ungraded_tweets`
**Purpose**: Process all tweets in the sheet that haven't been graded yet

**What it does**:
1. Scans `tweets` sheet for ungraded entries
2. Fetches tweet text via Twitter API
3. Grades each tweet using OpenAI
4. Updates scores and XP in the sheet
5. Marks as graded

**Progress Updates**:
- Console logs every 10 seconds or 10% progress
- Shows processed/failed/skipped counts

**Use cases**:
- Backfill grading for old tweets
- Process tweets that failed initial grading
- Bulk operations

**Requirements**:
- Twitter API Bearer Token
- OpenAI API Key
- Admin role

---

#### `/stop_processing_tweets`
**Purpose**: Gracefully stop the running tweet processing

**What it does**:
- Sets a stop flag
- Current tweet finishes processing
- Summary of progress is sent

**Use cases**:
- Stop long-running operations
- Emergency stop if needed

---

#### `/xp_admin_give`
**Purpose**: Grant XP directly to a specific user

**Parameters**:
- `user`: Discord user to grant XP to
- `amount`: Amount of XP to grant

**What it does**:
- Bypasses daily caps
- Creates XP event with source "admin_grant"
- Logs who granted it and when

**Use cases**:
- Reward special contributions
- Compensate for errors
- Manual adjustments

**Note**: Admin grants bypass all daily caps and restrictions.

---

#### `/xp_admin_give_role`
**Purpose**: Grant XP to all members with a specific role

**Parameters**:
- `role`: Discord role to grant XP to
- `amount`: XP amount per member
- `notes` (optional): Notes for the grant
- `require_messages` (optional): Only grant to members who have posted (default: True)

**What it does**:
1. Gets all members with the role
2. Optionally filters to active members (who have posted)
3. Grants XP to each member in batches
4. Shows progress in console (every 10 seconds or 10%)

**Progress Updates**:
- Console logs during channel scanning (if filtering active members)
- Console logs during batch XP granting
- Final summary with success/error counts

**Use cases**:
- Reward all members of a role
- Bulk XP grants for events
- Compensate groups of users

**Performance**:
- Handles large operations (10k+ members)
- Batches API calls to avoid rate limits
- Pre-expands sheets for efficiency

---

#### `/xp_admin_verify_role`
**Purpose**: Verify that all members with a role received XP from a previous grant

**Parameters**:
- `role`: Role to verify
- `amount`: Expected XP amount
- `notes` (optional): Notes to match (for filtering)
- `repair` (optional): If True, grant missing XP (default: False)
- `require_messages` (optional): Only check active members (default: True)

**What it does**:
1. Gets all members with the role
2. Optionally filters to active members
3. Scans `xp_events` for matching grants
4. Identifies members missing XP
5. Optionally repairs by granting missing XP

**Progress Updates**:
- Console logs during channel scanning
- Console logs during XP events processing (every 10 seconds or 10%)
- Console logs during repair (if enabled)

**Output**:
- Report showing:
  - Total members with role
  - Members checked
  - Members with XP
  - Members missing XP
  - List of missing members (first 20)
  - Repair results (if repair was enabled)

**Use cases**:
- Verify bulk grants completed successfully
- Find and fix missing grants
- Audit XP distribution

---

#### `/xp_admin_check_user`
**Purpose**: Check if a specific user received XP for a role grant

**Parameters**:
- `user`: User to check
- `role` (optional): Specific role to check
- `amount` (optional): Expected amount
- `notes` (optional): Expected notes

**What it shows**:
- Whether user has the role
- Whether user received the XP grant
- Details of the grant if found
- Explanation if not found

**Use cases**:
- Debug individual user issues
- Verify specific grants
- Help users understand why they didn't receive XP

---

#### `/xp_admin_remove`
**Purpose**: Remove XP from a user

**Parameters**:
- `user`: User to remove XP from
- `amount`: Amount to remove

**What it does**:
- Creates negative XP event
- Logs who removed it and why
- Respects daily caps (negative XP counts toward cap)

**Use cases**:
- Correct errors
- Remove incorrectly awarded XP
- Penalties (if implemented)

---

#### `/fix_quiz_bots`
**Purpose**: Remove XP from users who earned quiz XP but have insufficient Discord activity

**Parameters**:
- `min_posts` (optional): Minimum posts required (default: 3)
- `dry_run` (optional): Preview changes without applying (default: True)

**What it does**:
1. Finds users who earned quiz XP
2. Checks their Discord message count
3. Removes quiz XP if below threshold
4. Shows detailed report

**Use cases**:
- Clean up bot accounts
- Enforce activity requirements
- Maintain data integrity

---

#### `/fix_twitter_threads`
**Purpose**: Combine and re-grade Twitter thread submissions

**Parameters**:
- `execute` (optional): Actually apply changes (default: False, dry run)

**What it does**:
1. Scans `tweets` sheet for threads
2. Groups tweets by conversation_id
3. Combines thread text
4. Re-grades combined thread
5. Updates XP (first tweet gets combined score, others get 0)

**Progress Updates**:
- Console logs during tweet fetching
- Console logs during thread processing
- Final summary

**Use cases**:
- Fix threads that were graded separately
- Consolidate thread submissions
- Ensure fair XP distribution

---

#### `/xp_grandfather_bonus`
**Purpose**: Award bonus XP to existing contributors based on historical tweet count

**Parameters**:
- `tweet_count_threshold`: Minimum tweets to qualify
- `bonus_per_tweet`: XP per qualifying tweet
- `dry_run` (optional): Preview without applying (default: True)

**What it does**:
- Counts historical tweets per user
- Awards bonus XP based on count
- Respects daily caps (unless bypassed)

**Use cases**:
- Reward early contributors
- Recognize historical activity
- One-time bonuses

---

#### `/xp_migrate_historical`
**Purpose**: Migrate XP from an old leaderboard CSV file

**Parameters**:
- `csv_path`: Path to CSV file
- `dry_run` (optional): Preview without applying (default: True)

**What it does**:
1. Reads old leaderboard CSV
2. Matches users by Twitter handle or Discord username
3. Creates XP events for historical XP
4. Shows detailed migration report

**Use cases**:
- Migrate from old systems
- Import historical data
- Consolidate XP records

---

#### `/xp_migrate_check`
**Purpose**: Check how many old leaderboard entries can be matched to registered Twitter handles

**Parameters**:
- `csv_path`: Path to old leaderboard CSV

**What it shows**:
- Total entries in old leaderboard
- Matched by Twitter handle
- Matched by username
- Not in handles CSV

**Use cases**:
- Preview migration compatibility
- Identify missing mappings
- Plan migration strategy

---

#### `/bot_component_toggle`
**Purpose**: Enable or disable bot components

**Parameters**:
- `component`: Component name (leaderboard_checking, daily_summary, auto_process_tweets, metrics_quiz)
- `enabled`: True to enable, False to disable

**What it does**:
- Updates component status in state
- Takes effect immediately
- Persists across restarts

**Use cases**:
- Temporarily disable features
- Maintenance mode
- Feature rollouts

---

#### `/bot_component_status`
**Purpose**: View status of all bot components

**What it shows**:
- List of all components
- Enabled/disabled status
- Description of each component

**Use cases**:
- Check current configuration
- Debug issues
- Audit settings

---

#### `/bot_setup`
**Purpose**: Main configuration command for bot settings

**Parameters**:
- `metrics_channel`: Channel for metrics announcements
- `volume_channel`: Voice channel for volume counter
- `admin_role`: Admin role name

**What it does**:
- Configures all main bot settings
- Updates state file
- Validates inputs

**Use cases**:
- Initial setup
- Reconfiguration
- Channel changes

---

#### `/bot_setup_metrics_channel`
**Purpose**: Set the channel for metrics announcements

**Parameters**:
- `channel`: Text channel for announcements

**What it does**:
- Updates metrics channel ID
- Validates channel exists
- Saves to state

---

#### `/bot_setup_volume_channel`
**Purpose**: Set the voice channel for volume counter

**Parameters**:
- `channel`: Voice channel (or None to disable)

**What it does**:
- Updates volume channel ID
- Renames channel with current volume
- Updates every poll interval

---

#### `/bot_set_min_posts`
**Purpose**: Set minimum Discord posts required for XP-earning activities

**Parameters**:
- `min_posts`: Minimum number of posts required

**What it does**:
- Updates global minimum posts setting
- Affects all XP-earning activities
- Prevents bot abuse

**Use cases**:
- Enforce community participation
- Prevent bot accounts
- Adjust activity requirements

---

#### `/bot_manual_quiz_post`
**Purpose**: Manually post a metrics quiz announcement

**What it does**:
- Posts quiz button to metrics channel
- Users can click to start quiz
- Triggers same quiz flow as automatic posts

**Use cases**:
- Manual quiz triggers
- Testing
- Special events

---

#### `/clean_threads`
**Purpose**: Clean all bot-created threads in a channel

**Parameters**:
- `channel`: Channel to clean (defaults to current channel)

**What it does**:
- Finds all threads created by bot
- Archives or deletes them
- Shows count of cleaned threads

**Use cases**:
- Cleanup old quiz threads
- Maintenance
- Channel organization

---

## How Everything Works Together

### The XP System

The XP system is the core gamification engine. Here's how it all connects:

1. **XP Events** (`xp_events` sheet): Every XP award creates a row with:
   - Timestamp
   - Discord ID and name
   - Twitter handle (if applicable)
   - Source (tweet_grade, quiz, prediction, admin_grant, etc.)
   - Amount
   - Reference information (tweet ID, quiz type, etc.)
   - Notes

2. **XP Totals** (`xp_totals` sheet): Automatically calculates totals using formulas that sum from `xp_events`. This provides:
   - Real-time totals
   - Efficient leaderboard queries
   - Historical tracking

3. **Daily Caps**: Tiered system that:
   - Helps new users catch up (higher caps at lower tiers)
   - Maintains competitive balance
   - Resets at midnight UTC
   - Admin grants bypass caps

4. **Activity Requirements**: Minimum Discord posts required to:
   - Prevent bot abuse
   - Ensure community participation
   - Maintain data quality

### The Tweet Grading System

1. **Submission** (`/submit_tweet`):
   - User submits tweet URL
   - Bot extracts tweet ID
   - Checks for duplicates
   - Fetches tweet text via Twitter API

2. **Thread Detection**:
   - Checks if tweet is part of a thread
   - If so, fetches all tweets in thread
   - Combines text for grading
   - Only first submission gets XP

3. **Grading**:
   - Uses OpenAI to grade on 0-5 scale
   - Considers relevance, quality, engagement
   - Returns score and rationale

4. **XP Award**:
   - Score converted to XP (rounded)
   - Subject to daily tweet limit (default: 3/day)
   - Saved to `tweets` sheet with full details

5. **Bulk Processing** (`/process_ungraded_tweets`):
   - Scans for ungraded tweets
   - Processes in batches
   - Updates scores and XP
   - Handles rate limits automatically

### The Quiz System

1. **Quiz Types**:
   - **Metrics Quiz**: Questions based on current blockchain data
   - **General Quiz**: Questions from CSV file

2. **Quiz Flow**:
   - User clicks button or uses `/metrics_quiz`
   - Bot sends DM with questions
   - User answers via buttons
   - Score calculated
   - XP awarded based on performance

3. **Requirements**:
   - Minimum Discord posts
   - One quiz per day limit
   - Bot must be able to DM user

4. **Automatic Posting**:
   - Can be scheduled or manual
   - Posts button to metrics channel
   - Users click to start

### The Prediction System

1. **Prediction Types**:
   - **Volume**: Predict total volume for a date
   - **Top 10**: Predict token changes in top 10

2. **Submission**:
   - User submits prediction
   - Saved to `predictions` sheet
   - Must submit before deadline (1 hour before resolution)

3. **Resolution**:
   - Automatic at configured time (default: 2:00 UTC)
   - Fetches actual data
   - Calculates accuracy
   - Awards XP based on accuracy

4. **XP Calculation**:
   - Accuracy-based formula
   - Perfect predictions get bonus
   - Tracks leaderboard

### The Metrics System

1. **Automatic Monitoring**:
   - Polls analytics API every interval (default: 10 minutes)
   - Checks for new top 10 transactions
   - Monitors volume milestones

2. **Announcements**:
   - New top 10 entries
   - Volume milestone crossings
   - Daily summary at 23:59 UTC

3. **Volume Channel**:
   - Optional voice channel
   - Renamed with current volume
   - Updates automatically

### Admin Tools Integration

All admin tools work together to maintain system integrity:

1. **Verification Tools** (`/xp_admin_verify_role`):
   - Audit XP distribution
   - Find missing grants
   - Repair issues automatically

2. **Bulk Operations** (`/xp_admin_give_role`):
   - Grant XP to groups
   - Filter by activity
   - Progress tracking

3. **Data Integrity** (`/fix_quiz_bots`, `/fix_twitter_threads`):
   - Clean up bot accounts
   - Fix thread submissions
   - Maintain quality

4. **Migration Tools** (`/xp_migrate_historical`):
   - Import from old systems
   - Match users automatically
   - Preserve history

### Component System

The bot uses a component system for modularity:

- **leaderboard_checking**: Monitors top 10 transactions
- **daily_summary**: Posts daily summary
- **auto_process_tweets**: Automatically processes ungraded tweets
- **metrics_quiz**: Automatic quiz posting

Each component can be enabled/disabled independently via `/bot_component_toggle`.

---

## Best Practices

### For Users

1. **Set Your Twitter Handle Early**: Required before submitting tweets
2. **Check Daily Status**: Know your cap before submitting content
3. **Submit Quality Content**: Higher scores = more XP
4. **Participate in Quizzes**: Easy way to earn XP and learn
5. **Make Predictions**: Test your knowledge and compete
6. **Be Active in Discord**: Minimum posts required for most activities

### For Administrators

1. **Verify Bulk Grants**: Always use `/xp_admin_verify_role` after bulk operations
2. **Monitor Console Logs**: Progress updates help track long operations
3. **Use Dry Run First**: Test commands with `dry_run: True` before executing
4. **Check Component Status**: Verify components are enabled as expected
5. **Regular Maintenance**: Use fix commands periodically to maintain data quality
6. **Backup Sheets**: Google Sheets are the source of truth—keep backups

### For Setup

1. **Start with Required APIs**: Discord token and Google Sheets
2. **Add Optional APIs Gradually**: Twitter and OpenAI can be added later
3. **Test with Small Operations**: Verify everything works before bulk operations
4. **Configure Channels**: Set up metrics and volume channels
5. **Set Admin Role**: Configure who can use admin commands
6. **Monitor First Day**: Watch for any issues during initial operation

---

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| Commands not appearing | Wait 1-2 minutes for sync, check permissions |
| XP not updating | Check daily cap, verify source, check `xp_events` sheet |
| Tweets not grading | Verify API keys, check `/process_ungraded_tweets` |
| Quiz not starting | Check DM permissions, verify minimum posts |
| Predictions not resolving | Check resolution time, verify API access |
| Sheet errors | Verify service account access, check worksheet names |
| Rate limit errors | Bot handles automatically, wait and retry |

---

## Conclusion

PolyOne is a powerful, flexible bot that can transform your Discord server into an engaging, gamified community. With proper setup and understanding of its features, it can:

- Increase community engagement
- Reward quality content
- Educate members about blockchain metrics
- Create competitive elements through leaderboards
- Maintain transparent, auditable records

The key to success is understanding how the systems work together and using the right tools for your needs. Start with basic features, gradually enable more advanced functionality, and use the admin tools to maintain data quality.

For technical support, check the console logs (`logs/polyone.log` and `logs/polyone_errors.log`) and verify your configuration matches the requirements outlined in this guide.

---

*This guide covers PolyOne bot version as of December 2024. Features and commands may evolve over time. Always refer to the latest documentation for your specific version.*






