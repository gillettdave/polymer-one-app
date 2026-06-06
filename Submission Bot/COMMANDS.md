# Commands Reference

This document lists all available commands for the Turkey Man Code Discord Submissions Bot.

## User Commands

### `/submit`
Submit a new submission for review.

**Parameters:**
- `submission_type` (required) - The type of submission (autocomplete)
- `title` (required) - A short title for your submission
- `description` (required) - A detailed description
- `link` (optional) - A URL link
- `attachment` (optional) - A file attachment

**Example:**
```
/submit submission_type:content_submission title:"My Article" description:"This is a great article about..." link:https://example.com/article
```

**Notes:**
- Submission types are configured in `config/submission_types.json`
- Some submission types may require a link or attachment
- Rate limiting applies (cooldown and daily limits)
- You'll receive a submission ID after submitting

### `/my_submissions`
View your last 5 submissions and their statuses.

**Example:**
```
/my_submissions
```

**Response:**
Shows an embed with your recent submissions, including:
- Submission ID
- Title
- Type
- Status (pending, approved, rejected, changes_requested)
- Creation timestamp

## Admin/Reviewer Commands

### `/set_review_channel`
Set the channel where submissions will be posted for review.

**Parameters:**
- `channel` (required) - The text channel to use

**Example:**
```
/set_review_channel channel:#submissions-review
```

**Permissions:** Admin only (requires admin role or Manage Server permission)

### `/set_notify_channel`
Set a fallback channel for notifications when user DMs are closed.

**Parameters:**
- `channel` (required) - The text channel to use

**Example:**
```
/set_notify_channel channel:#notifications
```

**Permissions:** Admin only

**Notes:**
- This is optional
- Used only when the bot cannot DM a user about their submission decision

### `/reload_config`
Reload the submission types configuration from `config/submission_types.json`.

**Example:**
```
/reload_config
```

**Permissions:** Admin only

**Notes:**
- Useful after editing the submission types file
- No restart required

### `/submission_lookup`
Look up a submission by its ID.

**Parameters:**
- `submission_id` (required) - The submission ID (e.g., SUB-20240101-1234A1B2)

**Example:**
```
/submission_lookup submission_id:SUB-20240101-1234A1B2
```

**Permissions:** Reviewer or Admin

**Response:**
Shows an embed with full submission details.

### `/status`
View bot status, configuration, and statistics.

**Example:**
```
/status
```

**Response:**
Shows an embed with:
- Configuration status
- Total submissions count
- Pending/Approved/Rejected/Changes Requested counts
- Data file paths

**Permissions:** Anyone can use

## Review Actions (Buttons)

When a submission is posted in the review channel, reviewers will see buttons:

### ✅ Approve
- Approves the submission
- Optionally prompts for a note
- Assigns role if configured for the submission type
- Sends DM to submitter

### ❌ Reject
- Rejects the submission
- Requires a note explaining the rejection
- Sends DM to submitter

### 💬 Request Changes
- Marks submission as needing changes
- Requires a note explaining what needs to be changed
- Sends DM to submitter

**Permissions:**
- Requires reviewer role, admin role, or Manage Server permission
- Only works on pending submissions

## Submission ID Format

Submissions use the format: `SUB-YYYYMMDD-XXXXXXXX`

- `YYYYMMDD` - Date in UTC
- `XXXXXXXX` - Collision-resistant suffix (microseconds + random hex)

Example: `SUB-20240115-1234A1B2`

## Rate Limiting

The bot enforces rate limits to prevent spam:

- **Cooldown:** Default 300 seconds (5 minutes) between submissions of the same type
- **Daily Limit:** Default 10 submissions per day per submission type
- **Per-Type Override:** Submission types can override the cooldown

These limits are configurable in `.env`:
- `COOLDOWN_SECONDS`
- `MAX_SUBMISSIONS_PER_DAY`

## Tips

1. **Use autocomplete:** The `/submit` command has autocomplete for submission types
2. **Check status:** Use `/my_submissions` to track your submissions
3. **Submission ID:** Save your submission ID for reference
4. **Reviewers:** Use the buttons directly on the submission embed for quick review
5. **Admins:** Use `/reload_config` after editing submission types (no restart needed)

