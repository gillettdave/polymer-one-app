# Gumroad Release Checklist

This checklist is for preparing the Turkey Man Code Discord Submissions Bot for release on Gumroad.

## Pre-Release Preparation

### Code Quality
- [ ] All files are present and properly structured
- [ ] No hardcoded tokens or sensitive data
- [ ] `.gitignore` properly configured
- [ ] Code is commented and readable
- [ ] No TODO comments or debug code left in

### Documentation
- [ ] README.md is complete and accurate
- [ ] INSTALL.md has step-by-step instructions
- [ ] COMMANDS.md lists all commands
- [ ] CONFIG.md explains all configuration options
- [ ] TROUBLESHOOTING.md covers common issues
- [ ] SECURITY.md explains data handling
- [ ] LICENSE.md is included

### Configuration
- [ ] `.env.example` (or `env.example.txt`) is provided
- [ ] `config/submission_types.json` has example types
- [ ] `config/config.schema.json` is included
- [ ] Default values are sensible and documented

### Testing
- [ ] Bot starts without errors
- [ ] All commands work correctly
- [ ] Review workflow functions properly
- [ ] Role assignment works (if configured)
- [ ] DM notifications work
- [ ] Fallback notifications work
- [ ] Rate limiting works
- [ ] File storage works correctly
- [ ] Bot survives restart (data persists)

## Screenshots Required

### Setup Screenshots
- [ ] Discord Developer Portal - Application creation
- [ ] Discord Developer Portal - Bot section (intents enabled)
- [ ] Discord Developer Portal - OAuth2 URL Generator (scopes/permissions)
- [ ] Bot invite URL being used
- [ ] Bot appearing in server member list

### Configuration Screenshots
- [ ] `.env` file example (with placeholders, not real tokens)
- [ ] `config/submission_types.json` example
- [ ] Bot running in terminal/console (startup messages)

### Command Screenshots
- [ ] `/submit` command autocomplete
- [ ] `/submit` command with all fields filled
- [ ] Submission confirmation message
- [ ] `/my_submissions` command output
- [ ] `/status` command output

### Review Workflow Screenshots
- [ ] Submission appearing in review channel (with embed)
- [ ] Review buttons visible (Approve/Reject/Request Changes)
- [ ] Review note modal (for reject/request changes)
- [ ] Approved submission (updated embed with status)
- [ ] Rejected submission (updated embed with status)
- [ ] Request changes submission (updated embed with status)

### Notification Screenshots
- [ ] DM notification to user (approved)
- [ ] DM notification to user (rejected)
- [ ] DM notification to user (changes requested)
- [ ] Fallback notification in channel (if DMs closed)

### Admin Commands Screenshots
- [ ] `/set_review_channel` command
- [ ] `/set_notify_channel` command
- [ ] `/reload_config` command
- [ ] `/submission_lookup` command
- [ ] Permission error (non-admin trying admin command)

### Data Storage Screenshots
- [ ] `data/submissions.json` structure (example, anonymized)
- [ ] `data/decisions.csv` structure (example, anonymized)
- [ ] `logs/bot.log` example (anonymized)

## Package Contents

### Required Files
- [ ] `bot.py` - Main bot file
- [ ] `config.py` - Configuration management
- [ ] `storage.py` - File storage
- [ ] `review.py` - Review workflow
- [ ] `ui_components.py` - UI components
- [ ] `permissions.py` - Permission checks
- [ ] `utils.py` - Utility functions
- [ ] `requirements.txt` - Dependencies
- [ ] `.gitignore` - Git ignore rules

### Configuration Files
- [ ] `config/submission_types.json` - Example submission types
- [ ] `config/config.schema.json` - Configuration schema
- [ ] `env.example.txt` - Environment variables template

### Documentation Files
- [ ] `README.md`
- [ ] `INSTALL.md`
- [ ] `COMMANDS.md`
- [ ] `CONFIG.md`
- [ ] `TROUBLESHOOTING.md`
- [ ] `SECURITY.md`
- [ ] `LICENSE.md`
- [ ] `RELEASE_CHECKLIST.md` (this file)

### Optional Files
- [ ] `test_smoke.py` - Smoke test script (if created)
- [ ] `start_bot.bat` - Windows startup script (optional)
- [ ] `start_bot.sh` - Linux startup script (optional)

## Gumroad Listing

### Product Title
- [ ] Clear and descriptive title
- [ ] Includes "Discord Bot" or similar
- [ ] Mentions key features (submissions, review workflow)

### Product Description
- [ ] What the bot does (clear explanation)
- [ ] Key features listed
- [ ] Requirements (Python version, Discord account)
- [ ] What's included (files, documentation)
- [ ] Use cases/examples

### Pricing
- [ ] Price set appropriately
- [ ] License terms clear (single-server commercial license)

### Tags/Keywords
- [ ] discord
- [ ] bot
- [ ] submissions
- [ ] review
- [ ] workflow
- [ ] python
- [ ] self-hosted

### Images/Videos
- [ ] Main product image (bot in action)
- [ ] Screenshot gallery (all screenshots from checklist)
- [ ] Video demo (optional but recommended)
  - [ ] Installation walkthrough
  - [ ] Basic usage demo
  - [ ] Review workflow demo

## Post-Release

### Support Preparation
- [ ] Support channel/email ready
- [ ] Common questions documented
- [ ] Update process documented (if applicable)

### Updates
- [ ] Version numbering system established
- [ ] Changelog process defined
- [ ] Update delivery method (Gumroad updates, email)

## Quality Assurance

### Final Checks
- [ ] Download and test the complete package
- [ ] Follow INSTALL.md from scratch (fresh environment)
- [ ] Verify all screenshots are current
- [ ] Check all links in documentation
- [ ] Verify code works on both Windows and Linux
- [ ] Test with minimal permissions (security)
- [ ] Test with maximum permissions (full features)

### Documentation Review
- [ ] No broken links
- [ ] All commands documented
- [ ] All configuration options explained
- [ ] Troubleshooting covers common issues
- [ ] Installation works for beginners
- [ ] Examples are clear and helpful

## Screenshot Checklist Details

### Screenshot 1: Developer Portal - Application
- Show: New Application dialog or application list
- Highlight: Application name

### Screenshot 2: Developer Portal - Bot Section
- Show: Bot token section (blurred/redacted)
- Highlight: Privileged Gateway Intents checkboxes (enabled)

### Screenshot 3: Developer Portal - OAuth2
- Show: URL Generator with scopes selected
- Highlight: `bot` and `applications.commands` scopes
- Show: Bot permissions selected

### Screenshot 4: Bot Invite
- Show: Bot appearing in server
- Highlight: Bot is online

### Screenshot 5: Configuration Files
- Show: `.env` file (with placeholders)
- Show: `submission_types.json` structure
- Anonymize: Any real IDs or tokens

### Screenshot 6: Bot Startup
- Show: Terminal with bot running
- Highlight: "Logged in as..." and "Synced commands" messages

### Screenshot 7-12: Commands
- Show each command in action
- Include autocomplete where applicable
- Show both success and error cases

### Screenshot 13-18: Review Workflow
- Show complete workflow from submission to decision
- Include all three decision types
- Show updated embeds with status

### Screenshot 19-22: Notifications
- Show DM notifications
- Show fallback channel notifications
- Anonymize user information

## Notes

- **Anonymize all screenshots:** Remove real user IDs, server names, tokens
- **Use placeholders:** Show example data, not real data
- **Consistent styling:** Use same Discord theme for all screenshots
- **Clear annotations:** Add arrows/text to highlight important parts
- **High resolution:** Ensure screenshots are clear and readable

## Final Reminders

1. **Never include real tokens** in screenshots or code
2. **Test everything** before release
3. **Document edge cases** in troubleshooting
4. **Provide clear support** contact information
5. **Keep it simple** - don't overcomplicate the listing

Good luck with your release! 🚀


