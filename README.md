# Polymer One — Community Discord Bot

An all-in-one Discord bot built for the Polymer University community. Handles metrics tracking, XP leaderboards, tweet grading, quiz competitions, and a predictions game — all backed by Google Sheets.

## Features

- **Metrics & announcements** — polls on-chain volume data and posts formatted updates to Discord
- **XP leaderboard** — tracks engagement points with daily caps, tier multipliers, and grandfather bonuses
- **Tweet grading** — members submit tweets, OpenAI grades them for quality and awards XP
- **Quiz system** — timed multi-question quizzes with role rewards and result tracking
- **Predictions game** — members predict volume/top-10 rankings, scored after the fact
- **Google Sheets backend** — all data stored in configurable spreadsheets
- **Rate limiting** — per-user DM throttling, API call management
- **Admin commands** — role-gated management and configuration

## Stack

Python · discord.py · OpenAI API · Twitter/X API v2 · Google Sheets API · DeFiLlama API · aiohttp

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your tokens and sheet names
python PolyOne.py
```

You'll need:
- A Discord bot token with appropriate guild permissions
- A Google service account JSON file with Sheets access
- An OpenAI API key for tweet grading
- Twitter Bearer token for tweet fetching (optional)

## Configuration

All configuration is via `.env`. See `.env.example` for the full list of options including sheet names, channel IDs, quiz settings, and logging configuration.
