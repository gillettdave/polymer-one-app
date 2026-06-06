# PolyOne Bot - Use Case Examples

Practical examples for common scenarios and workflows.

## Table of Contents

- [Getting Started](#getting-started)
- [Daily User Activities](#daily-user-activities)
- [Admin Management](#admin-management)
- [Troubleshooting Scenarios](#troubleshooting-scenarios)
- [Advanced Use Cases](#advanced-use-cases)

---

## Getting Started

### First-Time User Setup

**Scenario:** A new user wants to start earning XP and participating in the community.

**Steps:**
1. Set your Twitter handle:
   ```
   /set_twitter handle:your_twitter_handle
   ```

2. Check your starting XP:
   ```
   /xp_me
   ```

3. Submit your first tweet:
   ```
   /submit_tweet url:https://x.com/your_handle/status/1234567890
   ```

4. Check your daily status:
   ```
   /xp_daily_status
   ```

**Expected Results:**
- Twitter handle linked to Discord account
- Starting XP displayed (likely 0)
- Tweet submitted and graded automatically
- XP awarded based on tweet quality
- Daily progress shown

---

### Setting Up Admin Role

**Scenario:** Setting up the bot for the first time and configuring admin permissions.

**Steps:**
1. Set admin role via environment variable (in `.env`):
   ```env
   ADMIN_ROLE_NAME=Admin
   ```

2. Or set via bot command:
   ```
   /bot_setup admin_role:"Admin"
   ```

3. Verify admin role is set:
   ```
   /bot_setup
   ```

**Expected Results:**
- Admin role configured
- Users with that role can use admin commands
- Discord administrators always have access

---

## Daily User Activities

### Daily XP Grinding Routine

**Scenario:** A user wants to maximize their daily XP earnings.

**Morning Routine:**
1. Check daily status:
   ```
   /xp_daily_status
   ```

2. Take the daily metrics quiz:
   ```
   /metrics_quiz num_questions:5
   ```

3. Submit quality tweets throughout the day:
   ```
   /submit_tweet url:https://x.com/.../status/...
   ```

4. Check progress:
   ```
   /xp_me
   ```

**Tips:**
- Submit tweets with quality content about Polymer
- Take the quiz early (can only do once per day)
- Check your tier to know your daily cap
- Higher tier = lower daily cap (catch-up mechanics)

---

### Participating in Prediction Game

**Scenario:** A user wants to participate in the prediction game and earn XP.

**Steps:**
1. Check current metrics:
   ```
   /polymer_status
   ```

2. Make a volume prediction:
   ```
   /predict_volume volume_billions:2.75 target_date:2024-12-20
   ```

3. Make a top 10 prediction:
   ```
   /predict_top10 new_entries:USDC,ETH removed_entries:BTC
   ```

4. Check your predictions:
   ```
   /my_predictions
   ```

5. View leaderboard:
   ```
   /prediction_leaderboard limit:20
   ```

**Tips:**
- Submit predictions at least 1 hour before resolution (23:00 UTC)
- One prediction per type per day
- Accuracy determines XP reward
- Check leaderboard to see top predictors

---

### Tracking Progress Over Time

**Scenario:** A user wants to track their XP growth and see their history.

**Steps:**
1. View current status:
   ```
   /xp_me
   ```

2. Check recent XP events:
   ```
   /xp_history limit:30
   ```

3. See your rank:
   ```
   /xp_leaderboard
   ```

4. Check daily progress:
   ```
   /xp_daily_status
   ```

**What to Look For:**
- XP breakdown by source
- Recent activity in history
- Rank progression over time
- Daily cap remaining

---

## Admin Management

### Initial Bot Configuration

**Scenario:** Setting up the bot for the first time in a new server.

**Steps:**
1. Configure all channels at once:
   ```
   /bot_setup main_metrics_channel:#announcements metrics_quiz_channel:#quizzes leaderboard_channel:#leaderboard admin_role:"Admin"
   ```

2. Set volume channel:
   ```
   /bot_setup_volume_channel channel:#Polymer Volume
   ```

3. Verify configuration:
   ```
   /bot_component_status
   ```

4. Test a command:
   ```
   /polymer_status
   ```

**Expected Results:**
- All channels configured
- Components enabled
- Bot responding to commands
- Volume channel updating

---

### Awarding XP to Users

**Scenario:** Admin wants to reward users for special contributions.

**Single User:**
```
/xp_admin_give user:@username amount:100
```

**Entire Role:**
```
/xp_admin_give_role role:@Contributor amount:50 notes:Monthly bonus
```

**Verify Grant:**
```
/xp_history user:@username
```

**Tips:**
- Admin grants bypass daily caps
- All grants are logged
- Use notes to track reason for grant
- Bulk grants process in batches

---

### Processing Ungraded Tweets

**Scenario:** Tweets were submitted but not automatically graded (API issues, etc.).

**Steps:**
1. Check for ungraded tweets (manual check in Google Sheets)

2. Process all ungraded tweets:
   ```
   /process_ungraded_tweets
   ```

3. Monitor progress (command shows results)

4. Verify in sheet that tweets are now graded

**Requirements:**
- Twitter Bearer Token must be set
- OpenAI API Key must be set
- May take time for large batches

---

### Managing Bot Components

**Scenario:** Temporarily disable a feature for maintenance.

**Steps:**
1. Check current status:
   ```
   /bot_component_status
   ```

2. Disable a component:
   ```
   /bot_component_toggle component:prediction_resolution enabled:false
   ```

3. Verify disabled:
   ```
   /bot_component_status
   ```

4. Re-enable when ready:
   ```
   /bot_component_toggle component:prediction_resolution enabled:true
   ```

**Available Components:**
- `leaderboard_checking` - Top 10 transaction alerts
- `volume_checking` - Volume milestones
- `daily_summary` - Daily status posts
- `prediction_resolution` - Prediction game resolution
- `metrics_quiz` - Daily metrics quiz
- `thread_cleanup` - Automatic thread cleanup

---

### Historical Data Migration

**Scenario:** Migrating XP from an old leaderboard system.

**Steps:**
1. Prepare CSV file with old data (Member column with Twitter handles)

2. Check what would be migrated:
   ```
   /xp_migrate_check csv_file:old_leaderboard.csv
   ```

3. Dry run to preview:
   ```
   /xp_migrate_historical csv_file:old_leaderboard.csv dry_run:true
   ```

4. Perform actual migration:
   ```
   /xp_migrate_historical csv_file:old_leaderboard.csv dry_run:false
   ```

5. Verify migration:
   ```
   /xp_history user:@username
   ```

**Tips:**
- Always do dry run first
- Verify CSV format matches expected structure
- Check Twitter handles are registered
- Migration bypasses daily caps

---

## Troubleshooting Scenarios

### Bot Not Responding to Commands

**Symptoms:** Commands don't appear or return errors.

**Diagnosis Steps:**
1. Check bot is online in server member list
2. Verify bot has necessary permissions
3. Check logs: `logs/polyone_errors.log`
4. Try restarting the bot

**Solutions:**
- Ensure bot has "Use Application Commands" permission
- Check bot's role hierarchy
- Verify channel permissions
- Wait 1-2 minutes after bot start for command sync

---

### Tweet Grading Not Working

**Symptoms:** Tweets submitted but not graded automatically.

**Diagnosis Steps:**
1. Check if API keys are set:
   - `TWITTER_BEARER_TOKEN`
   - `OPENAI_API_KEY`

2. Check logs for errors:
   ```
   logs/polyone_errors.log
   ```

3. Try processing manually:
   ```
   /process_ungraded_tweets
   ```

**Solutions:**
- Verify API keys are valid and active
- Check API quotas haven't been exceeded
- Use manual processing if automatic fails
- Check tweet URLs are accessible

---

### XP Not Updating

**Symptoms:** XP should have been awarded but didn't update.

**Diagnosis Steps:**
1. Check daily cap:
   ```
   /xp_daily_status
   ```

2. Check XP history:
   ```
   /xp_history limit:10
   ```

3. Verify in Google Sheets (xp_events tab)

**Solutions:**
- Daily cap may have been reached
- Check if event was logged in xp_events
- Verify xp_totals formulas are working
- Check for errors in logs

---

### Quiz Not Starting

**Symptoms:** Quiz command doesn't work or times out.

**Diagnosis Steps:**
1. Check if bot can send DMs:
   - Try `/xp_me` (should work)
   - Check user's DM settings

2. Check component status:
   ```
   /bot_component_status
   ```

3. Check logs for errors

**Solutions:**
- Enable DMs from server members
- Verify metrics_quiz component is enabled
- Check OpenAI API key is set (for question generation)
- Wait 30 seconds between quiz attempts

---

## Advanced Use Cases

### Running a Community Event

**Scenario:** Organizing a special event with custom XP rewards.

**Steps:**
1. Create event role:
   - Create role in Discord: `@EventParticipant`

2. Award XP to participants:
   ```
   /xp_admin_give_role role:@EventParticipant amount:100 notes:Community Event Bonus
   ```

3. Track participation:
   ```
   /xp_history user:@participant
   ```

4. Announce winners:
   ```
   /xp_leaderboard
   ```

---

### Setting Up Custom Quiz

**Scenario:** Creating a custom quiz for a specific topic.

**Steps:**
1. Prepare CSV file with questions:
   - Columns: question, option_a, option_b, option_c, option_d, correct

2. Post quiz button:
   ```
   /post_quiz_button quiz_message:"Chapter 1 Quiz" num_questions:10 required_score:7 role_to_assign:@Chapter1Graduate
   ```

3. Monitor completions:
   - Check quiz results in Google Sheets
   - Use `/xp_history` to see completions

---

### Monitoring Bot Health

**Scenario:** Regular maintenance and health checks.

**Daily Checks:**
1. Check component status:
   ```
   /bot_component_status
   ```

2. Review error logs:
   ```
   logs/polyone_errors.log
   ```

3. Test key commands:
   ```
   /polymer_status
   /xp_me
   ```

**Weekly Checks:**
1. Process ungraded tweets:
   ```
   /process_ungraded_tweets
   ```

2. Clean up old threads:
   ```
   /clean_threads target_channel:#quizzes
   ```

3. Review configuration:
   ```
   /bot_setup
   ```

---

### Bulk User Management

**Scenario:** Awarding XP to multiple users based on criteria.

**By Role:**
```
/xp_admin_give_role role:@EarlyAdopter amount:200 notes:Early supporter bonus
```

**Individual Users (if needed):**
```
/xp_admin_give user:@user1 amount:50
/xp_admin_give user:@user2 amount:50
/xp_admin_give user:@user3 amount:50
```

**Verify:**
- Check each user's history
- Verify totals updated correctly
- Check logs for any errors

---

## Best Practices

### For Users
- Set your Twitter handle early
- Submit quality content for better grades
- Take the daily quiz every day
- Make thoughtful predictions
- Check your daily status regularly

### For Admins
- Test commands in a test server first
- Always do dry runs for migrations
- Monitor error logs regularly
- Keep API keys secure
- Document custom configurations
- Use notes when awarding XP
- Verify grants after awarding

### General
- Keep bot updated
- Backup state.json regularly
- Monitor log file sizes
- Review component status weekly
- Test after configuration changes

---

## Tips and Tricks

1. **Maximize Daily XP:**
   - Take quiz early (once per day)
   - Submit multiple quality tweets
   - Make accurate predictions
   - Check your tier for daily cap

2. **Better Tweet Grades:**
   - Explain Polymer clearly
   - Include value propositions
   - Add call-to-action
   - Use relevant hashtags

3. **Accurate Predictions:**
   - Check current metrics first
   - Consider trends
   - Submit early (before deadline)
   - Review past predictions

4. **Admin Efficiency:**
   - Use bulk role grants when possible
   - Set up channels once via `/bot_setup`
   - Use component toggles for maintenance
   - Monitor logs proactively

---

## Getting Help

If you encounter issues not covered here:

1. Check `POLYONE_BOT_DOCUMENTATION.md` for setup guide
2. Review `COMMANDS_REFERENCE.md` for command details
3. Check `logs/polyone_errors.log` for errors
4. Use `/bot_component_status` to verify bot health
5. Review troubleshooting section in documentation





