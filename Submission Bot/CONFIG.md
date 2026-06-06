# Configuration Reference

This document explains all configuration options for the Turkey Man Code Discord Submissions Bot.

## Environment Variables (.env)

Create a `.env` file in the bot directory (copy from `env.example.txt`).

### Required Variables

#### `DISCORD_TOKEN`
Your Discord bot token from the Developer Portal.
```
DISCORD_TOKEN=your_bot_token_here
```

#### `GUILD_ID`
The Discord server (guild) ID where the bot will operate.
```
GUILD_ID=123456789012345678
```

#### `REVIEW_CHANNEL_ID`
The channel ID where submissions will be posted for review.
```
REVIEW_CHANNEL_ID=987654321098765432
```

### Role Configuration

#### `REVIEWER_ROLE_IDS`
Comma-separated list of role IDs that can review submissions.
```
REVIEWER_ROLE_IDS=111111111111111111,222222222222222222
```

#### `ADMIN_ROLE_IDS`
Comma-separated list of role IDs that can configure the bot.
```
ADMIN_ROLE_IDS=333333333333333333
```

**Note:** Users with "Manage Server" permission can also review and configure, regardless of roles.

### Optional Variables

#### `USE_THREADS`
Whether to create a thread for each submission (default: `true`).
```
USE_THREADS=true
```

If `false`, submissions are posted directly to the review channel.

#### `NOTIFY_CHANNEL_ID`
Channel ID for fallback notifications when DMs fail (optional).
```
NOTIFY_CHANNEL_ID=444444444444444444
```

#### `COOLDOWN_SECONDS`
Default cooldown between submissions in seconds (default: `300` = 5 minutes).
```
COOLDOWN_SECONDS=300
```

#### `MAX_SUBMISSIONS_PER_DAY`
Maximum submissions per user per day (default: `10`).
```
MAX_SUBMISSIONS_PER_DAY=10
```

#### `ALLOW_ATTACHMENTS`
Whether to allow file attachments in submissions (default: `true`).
```
ALLOW_ATTACHMENTS=true
```

#### `DATA_DIR`
Directory for storing submission data (default: `./data`).
```
DATA_DIR=./data
```

#### `LOG_DIR`
Directory for log files (default: `./logs`).
```
LOG_DIR=./logs
```

## Submission Types Configuration

Submission types are defined in `config/submission_types.json`.

### Schema

Each submission type is a JSON object with the following properties:

```json
{
  "type_key": {
    "label": "Human-readable name",
    "description": "Short help text",
    "default_approval_role_id": 123456789012345678,
    "require_link": false,
    "require_attachment": false,
    "cooldown_override_seconds": 600,
    "reviewers_override_role_ids": [111111111111111111]  // (reserved - not enforced in V1)
  }
}
```

**Note:** `reviewers_override_role_ids` shown in the schema example above is reserved for future versions and not enforced in V1.

### Properties

#### `label` (required)
Human-readable name shown in autocomplete and embeds.
```json
"label": "Ambassador Application"
```

#### `description` (required)
Short help text describing the submission type.
```json
"description": "Apply to become a community ambassador"
```

#### `default_approval_role_id` (optional)
Discord role ID to assign when this submission type is approved.
```json
"default_approval_role_id": 123456789012345678
```

**Security:** Only roles listed in submission type configs can be assigned. The bot will not assign arbitrary roles.

#### `require_link` (required)
Whether a URL link is required for this submission type.
```json
"require_link": true
```

#### `require_attachment` (required)
Whether a file attachment is required for this submission type.
```json
"require_attachment": false
```

#### `cooldown_override_seconds` (optional)
Override the global cooldown for this specific submission type.
```json
"cooldown_override_seconds": 600
```

If not provided, uses `COOLDOWN_SECONDS` from `.env`.

#### `reviewers_override_role_ids` (optional, reserved)
Override the global reviewer roles for this submission type.
```json
"reviewers_override_role_ids": [111111111111111111, 222222222222222222]
```

**Note:** `reviewers_override_role_ids` is reserved for future versions and is not enforced in V1. All submissions use the global `REVIEWER_ROLE_IDS` and `ADMIN_ROLE_IDS` from `.env` regardless of this setting.

### Example Configuration

```json
{
  "ambassador_application": {
    "label": "Ambassador Application",
    "description": "Apply to become a community ambassador",
    "default_approval_role_id": 123456789012345678,
    "require_link": false,
    "require_attachment": false,
    "cooldown_override_seconds": null,
    "reviewers_override_role_ids": null
  },
  "content_submission": {
    "label": "Content Submission",
    "description": "Submit content for review and publication",
    "default_approval_role_id": null,
    "require_link": true,
    "require_attachment": false,
    "cooldown_override_seconds": 600,
    "reviewers_override_role_ids": null
  },
  "bug_report": {
    "label": "Bug Report",
    "description": "Report a bug or issue",
    "require_link": false,
    "require_attachment": false,
    "cooldown_override_seconds": null,
    "reviewers_override_role_ids": null
  }
}
```

## Data Storage

### Submissions File
`data/submissions.json`

Stores all submissions in JSON format:
```json
{
  "SUB-20240115-1234A1B2": {
    "submission_id": "SUB-20240115-1234A1B2",
    "guild_id": 123456789012345678,
    "user_id": 987654321098765432,
    "username_at_time": "User#1234",
    "submission_type_key": "content_submission",
    "title": "My Submission",
    "description": "Description here...",
    "link": "https://example.com",
    "attachment_url": "https://cdn.discordapp.com/...",
    "attachment_filename": "file.pdf",
    "created_at": "2024-01-15T12:34:56.789000",
    "status": "pending",
    "review_message_id": 111111111111111111,
    "review_channel_id": 222222222222222222,
    "review_thread_id": 333333333333333333
  }
}
```

### Decisions File
`data/decisions.csv`

Append-only log of all review decisions:
```csv
submission_id,action,reviewer_id,reviewer_name,note,timestamp
SUB-20240115-1234A1B2,approve,444444444444444444,Admin#5678,Great work!,2024-01-15T13:00:00.000000
```

## Getting Discord IDs

1. Enable Developer Mode in Discord:
   - User Settings → Advanced → Developer Mode

2. Right-click and "Copy ID":
   - Server → Copy Server ID
   - Channel → Copy Channel ID
   - Role → Copy Role ID
   - User → Copy User ID

## Validation

The bot validates configuration on startup:

- ✅ `DISCORD_TOKEN` is set
- ✅ `GUILD_ID` is set
- ✅ `REVIEW_CHANNEL_ID` is set
- ✅ At least one of `REVIEWER_ROLE_IDS` or `ADMIN_ROLE_IDS` is set

If validation fails, the bot will exit with an error message.

## Reloading Configuration

- **Submission Types:** Use `/reload_config` command (no restart needed)
- **Environment Variables:** Requires bot restart
- **Channel/Role IDs:** Can be updated via commands or requires restart

## Security Notes

1. **Role Assignment:** Only roles listed in submission type configs can be assigned
2. **Permission Checks:** All review and admin actions check permissions
3. **File Storage:** Data files are stored locally - ensure proper file permissions
4. **Token Security:** Never commit `.env` to version control

## Troubleshooting

- **Bot won't start:** Check `.env` file exists and has all required variables
- **Commands not syncing:** Wait a few minutes or restart the bot
- **Permission errors:** Verify role IDs are correct and bot has required permissions
- **Submission types not loading:** Check JSON syntax in `config/submission_types.json`

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more help.

