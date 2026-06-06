# Security and Privacy

This document outlines security considerations and privacy information for the Turkey Man Code Discord Submissions Bot.

## Data Storage

### What Data is Stored

The bot stores the following data locally in files:

1. **Submissions (`data/submissions.json`)**
   - Submission ID
   - User ID and username (at time of submission)
   - Guild (server) ID
   - Submission content (title, description, link)
   - Attachment URLs and filenames
   - Submission status and timestamps
   - Review message/thread IDs

2. **Decisions (`data/decisions.csv`)**
   - Submission ID
   - Review action (approve/reject/request_changes)
   - Reviewer ID and username
   - Review notes
   - Timestamps

3. **Logs (`logs/bot.log`)**
   - Bot activity logs
   - Error messages
   - Command usage (user IDs may appear)

### Data Location

All data is stored locally on the server where the bot runs:
- `data/submissions.json` - All submissions
- `data/decisions.csv` - Review decision log
- `logs/bot.log` - Application logs

**No data is sent to external services** (except Discord's API for normal bot operation).

## Privacy Considerations

### User Data

- **User IDs** are stored to identify submitters and reviewers
- **Usernames** are stored at the time of submission (for historical reference)
- **Message content** (submission text) is stored as provided by users
- **Attachment URLs** are stored (Discord CDN links, not rehosted)

### Data Retention

- Data is stored indefinitely by default
- Administrators can manually delete or archive data files
- Consider implementing a data retention policy based on your needs

### GDPR / Privacy Rights

If users request data deletion:
1. Remove their submissions from `data/submissions.json`
2. Anonymize or remove their entries from `data/decisions.csv`
3. Consider log rotation to remove old entries

**Note:** This bot does not include automated data deletion features. Manual intervention is required.

## Security Best Practices

### Bot Token Security

**CRITICAL:** Never share or commit your bot token.

1. **Store in `.env` file** (not in code)
2. **Add `.env` to `.gitignore`** (already included)
3. **Never commit tokens** to version control
4. **Rotate token** if accidentally exposed:
   - Discord Developer Portal → Bot → Reset Token

### File Permissions

**Linux:**
```bash
# Restrict access to data files
chmod 600 .env
chmod 700 data/
chmod 600 data/submissions.json
chmod 600 data/decisions.csv
```

**Windows:**
- Use file/folder permissions to restrict access
- Ensure only the bot process can read/write data files

### Role Assignment Safety

The bot includes safety measures for role assignment:

1. **Allowlist Only:** Only roles listed in `config/submission_types.json` can be assigned
2. **Hierarchy Check:** Bot won't assign roles higher than its own role
3. **Permission Check:** Bot verifies it has "Manage Roles" permission
4. **No Arbitrary Assignment:** Users cannot request arbitrary role assignments

### Permission Checks

All sensitive operations check permissions:

- **Review Actions:** Require reviewer/admin role or Manage Server permission
- **Admin Commands:** Require admin role or Manage Server permission
- **Configuration:** Only admins can change bot settings

### Input Validation

The bot validates:

- **URLs:** Must start with `http://` or `https://`
- **Submission Types:** Must exist in configuration
- **Required Fields:** Enforced based on submission type config
- **Rate Limits:** Prevents spam and abuse

### File Operations

- **Atomic Writes:** JSON files are written atomically (temp file then rename)
- **File Locks:** Thread-safe file operations prevent corruption
- **Error Handling:** Graceful handling of file errors

## Discord API Security

### Intents

The bot requires these intents:
- **Server Members Intent:** To check roles and permissions
- **Message Content Intent:** To read submission content

These are privileged intents and must be enabled in the Discord Developer Portal.

### Rate Limiting

The bot respects Discord's rate limits:
- Commands have cooldowns
- File operations are throttled
- No aggressive API polling

## Network Security

### No External Connections

The bot only connects to:
- **Discord API:** For bot functionality (required)
- **No other services:** No analytics, telemetry, or external APIs

### Local Storage Only

- All data stays on your server
- No cloud sync or external storage
- No data transmission to third parties

## Vulnerabilities

### Known Limitations

1. **File-Based Storage:** Not suitable for high-concurrency scenarios
2. **No Encryption:** Data files are stored in plain text (JSON/CSV)
3. **Single Server:** Designed for one Discord server
4. **No Audit Trail:** Limited logging of administrative actions

### Recommendations

1. **Backup Regularly:** Backup `data/` directory regularly
2. **Monitor Logs:** Check `logs/bot.log` for suspicious activity
3. **Restrict Access:** Limit filesystem access to bot process only
4. **Update Dependencies:** Keep `discord.py` and other packages updated
5. **Review Code:** Audit code if making modifications

## Incident Response

If you suspect a security issue:

1. **Rotate Bot Token:** Immediately reset in Developer Portal
2. **Review Logs:** Check `logs/bot.log` for suspicious activity
3. **Check Data Files:** Verify `data/submissions.json` for unauthorized changes
4. **Review Permissions:** Ensure bot and user roles haven't been modified
5. **Backup Data:** Create a backup before making changes

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do not** open a public issue
2. Contact the maintainer privately
3. Provide details of the vulnerability
4. Allow time for a fix before public disclosure

## Compliance

### Data Protection

- **EU GDPR:** Consider data retention and user rights
- **CCPA:** California privacy law considerations
- **Other Jurisdictions:** Review local data protection laws

### Discord Terms of Service

Ensure bot usage complies with:
- [Discord Terms of Service](https://discord.com/terms)
- [Discord Developer Terms](https://discord.com/developers/docs/legal)
- [Discord API Terms](https://discord.com/developers/docs/legal)

## Best Practices Summary

✅ **Do:**
- Keep bot token secret
- Restrict file permissions
- Backup data regularly
- Monitor logs
- Update dependencies
- Use strong server security

❌ **Don't:**
- Commit `.env` to version control
- Share bot tokens
- Run bot with excessive permissions
- Store sensitive data unnecessarily
- Ignore security updates
- Expose data files publicly

## Additional Resources

- [Discord Security Best Practices](https://discord.com/developers/docs/topics/community-resources#security)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security](https://python.readthedocs.io/en/stable/library/security_warnings.html)


