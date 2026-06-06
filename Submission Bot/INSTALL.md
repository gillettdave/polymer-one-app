# Installation Guide

This guide will walk you through setting up the Turkey Man Code Discord Submissions Bot on Windows 11 and Linux.

## Prerequisites

- Python 3.11 or higher
- A Discord account
- Administrator access to a Discord server

## Step 1: Install Python

### Windows 11
1. Download Python from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **Important:** Check "Add Python to PATH" during installation
4. Verify installation:
   ```powershell
   python --version
   ```

### Linux
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Verify
python3 --version
```

## Step 2: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Name it (e.g., "Submissions Bot")
4. Go to the "Bot" section
5. Click "Add Bot" → "Yes, do it!"
6. Under "Privileged Gateway Intents", enable:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
7. Copy the bot token (click "Reset Token" if needed) - **Keep this secret!**
8. Go to "OAuth2" → "URL Generator"
9. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
10. Select bot permissions:
    - ✅ Send Messages
    - ✅ Manage Messages
    - ✅ Embed Links
    - ✅ Attach Files
    - ✅ Read Message History
    - ✅ Create Public Threads
    - ✅ Manage Roles (if using role assignment)
11. Copy the generated URL and open it in your browser
12. Select your server and authorize

## Step 3: Get Discord IDs

You'll need these IDs for configuration:

### Guild (Server) ID
1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click your server name → "Copy Server ID"

### Channel IDs
1. Right-click the channel where reviews should appear → "Copy Channel ID"

### Role IDs
1. Right-click a role → "Copy Role ID"

## Step 4: Set Up the Bot

1. **Clone or download this repository**
   ```bash
   cd "Submission Bot"
   ```

2. **Create a virtual environment (recommended)**
   
   Windows:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
   
   Linux:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create `.env` file**
   - Copy `env.example.txt` to `.env`
   - Edit `.env` with your values:
     ```
     DISCORD_TOKEN=your_bot_token_here
     GUILD_ID=your_guild_id_here
     REVIEW_CHANNEL_ID=your_review_channel_id_here
     REVIEWER_ROLE_IDS=role_id_1,role_id_2
     ADMIN_ROLE_IDS=role_id_1
     ```

5. **Configure submission types**
   - Edit `config/submission_types.json` to match your needs
   - See [CONFIG.md](CONFIG.md) for details

6. **Create directories**
   ```bash
   mkdir data logs
   ```
   (These will be created automatically on first run, but you can create them now)

## Step 5: Run the Bot

```bash
python bot.py
```

You should see:
```
Logged in as YourBotName#1234 (ID: 123456789)
Synced commands to guild 987654321
```

## Step 6: Verify Installation

1. In Discord, type `/submit` - you should see the command appear
2. Try submitting a test submission
3. Check that it appears in your review channel
4. Test the review buttons

## Troubleshooting

If you encounter issues:

- **Bot doesn't respond**: Check that the bot is online and has proper permissions
- **Commands not appearing**: Wait a few minutes for Discord to sync, or restart the bot
- **Permission errors**: Ensure the bot has the required permissions in your server
- **Import errors**: Make sure all dependencies are installed (`pip install -r requirements.txt`)

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more detailed help.

## Running as a Service (Optional)

### Windows (Task Scheduler)
1. Create a batch file `start_bot.bat`:
   ```batch
   @echo off
   cd /d "C:\path\to\Submission Bot"
   venv\Scripts\python.exe bot.py
   ```
2. Set up Task Scheduler to run this on system startup

### Linux (systemd)
Create `/etc/systemd/system/submissions-bot.service`:
```ini
[Unit]
Description=Discord Submissions Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/Submission Bot
ExecStart=/path/to/Submission Bot/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable submissions-bot
sudo systemctl start submissions-bot
```

## Next Steps

- Read [COMMANDS.md](COMMANDS.md) to learn all available commands
- Configure your submission types in `config/submission_types.json`
- Set up reviewer and admin roles
- Test the workflow with a few submissions


