# Turkey Man Code — Discord Submissions & Review Workflow Bot

A self-hosted Discord bot that collects structured user submissions via slash commands and routes them through an admin review workflow with buttons, optional role assignment, and file-based logging/storage.

## Features

- ✅ **Slash Commands** - Modern Discord interactions
- 📝 **Structured Submissions** - Configurable submission types with validation
- 🔄 **Review Workflow** - Button-based approval/rejection system
- 🎯 **Role Assignment** - Optional automatic role assignment on approval
- 📊 **File-Based Storage** - No database required (JSON/CSV)
- 🔒 **Permission-Based** - Admin and reviewer role checks
- 📱 **DM Notifications** - Automatic user notifications with fallback
- ⏱️ **Rate Limiting** - Cooldowns and daily limits per user
- 📎 **Attachment Support** - Optional file/image attachments
- 🧵 **Thread Support** - Optional thread-per-submission mode

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   - Copy `env.example.txt` to `.env`
   - Fill in your Discord bot token, guild ID, and channel IDs

3. **Configure Submission Types**
   - Edit `config/submission_types.json` to define your submission types

4. **Run the Bot**
   ```bash
   python bot.py
   ```

For detailed installation instructions, see [INSTALL.md](INSTALL.md).

## Documentation

- [INSTALL.md](INSTALL.md) - Step-by-step installation guide
- [COMMANDS.md](COMMANDS.md) - All available commands
- [CONFIG.md](CONFIG.md) - Configuration reference
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues and solutions
- [SECURITY.md](SECURITY.md) - Security and privacy information
- [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) - Gumroad release checklist

## Requirements

- Python 3.11+
- discord.py 2.x
- Windows 11 or Linux
- Discord Bot Token (from Discord Developer Portal)

## License

See [LICENSE.md](LICENSE.md) for license information.

## Support

For issues, questions, or contributions, please refer to the troubleshooting guide or open an issue in the repository.


