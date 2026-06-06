# PolyOne Developer & Extension Guide

This guide is for developers who want to extend PolyOne, debug behavior, or integrate new XP sources.

---

## 1. Codebase Overview

The core bot is a single Python file built around:

- `discord.py` – for commands, events, tasks
- `aiohttp` – async HTTP
- `gspread` – Google Sheets I/O
- `openai` – AI tweet grading (optional)
- Local `state.json` – small persistent state

Key sections include:

1. Configuration & environment handling
2. Google Sheets helpers
3. XP helpers
4. Twitter handle helpers
5. State load/save
6. Metrics tasks (`check_leaderboard`, `check_volume`)
7. Volume channel update
8. Status builder & daily summary
9. Slash commands
10. Startup (`on_ready`)

---

## 2. Adding a New XP Source

To add a new way for users to earn XP:

1. Decide on a `source` string, e.g.:
   - `metrics_quiz`
   - `prediction_game`
   - `poly_u_quiz`
   - `content_review`

2. Identify where in the code the event is “completed”:
   - A slash command handler
   - A background task resolving predictions
   - A quiz completion callback

3. Call `add_xp(...)`:

```python
add_xp(
    discord_id=user.id,
    discord_name=str(user),
    amount=xp_amount,
    source="metrics_quiz",
    twitter_handle=optional_handle,
    reference_type="quiz",
    reference_id="quiz_id_or_name",
    notes="Any extra context you want stored"
)
```

4. That’s it. The XP will appear in `xp_events`, and `xp_totals` will pick it up automatically via formulas.

---

## 3. Extending Tweet Grading

### 3.1 Grading Rubric

The tweet grading logic lives in a helper similar to:

```python
async def grade_tweet(tweet_text: str) -> tuple[float, str]:
    ...
```

The system prompt encodes the rubric, including:

- Score range: –1 to 5
- Penalties for irrelevant or spammy tweets
- Bonuses for clearly explaining Polymer, Prove API, value props, and CTAs

To adjust grading rules, edit the system prompt string and re–deploy.

### 3.2 XP Mapping

XP is mapped from score with a simple function, e.g.:

```python
xp_amount = max(0, int(round(max(0.0, score) * 10)))
```

You can change this to:

- Non–linear mapping (e.g., higher weight on 4–5)
- Thresholding (e.g., no XP below 3.0)
- Campaign–based multipliers

Just keep the side effects clear and documented so the community understands how XP is computed.

---

## 4. Adding Prediction Games

A prediction game might look like:

- `/predict_volume target=1.5B by=2025-08-31`
- Bot stores prediction in a sheet or database
- A scheduled task later compares reality against predictions
- Winners get XP, logged via `add_xp`

Implementation steps:

1. Create a new worksheet (`predictions`) or DB table
2. Add a slash command to accept predictions and store them
3. Add a scheduled task that runs at resolution time:
   - Reads predictions
   - Reads actual metrics from Polymer API
   - Computes winners
   - Calls `add_xp(...)` for winners
4. Optionally post a summary in Discord

---

## 5. Error Handling & Logging

Best practices for extending PolyOne:

- Wrap external calls (HTTP, Sheets, OpenAI) in `try/except` blocks
- Log errors with enough context to debug, e.g.:
  - Endpoint URL
  - Response status code
  - Exception type and message
- Avoid crashing the entire bot from a single failing task:
  - Use `discord.ext.tasks` and let it continue on next iteration

For critical failures (e.g., repeated OpenAI failures), you can DM admins or log into a dedicated “bot–errors” channel.

---

## 6. Dependency Management

Dependencies are listed in `requirements.txt`. Typical entries include:

- `discord.py`
- `aiohttp`
- `gspread`
- `google-auth`
- `python-dotenv`
- `openai`

When adding new features, pin versions where possible and test locally before deploying in production.

---

## 7. Deployment Notes

PolyOne can be deployed on:

- A small VPS
- A container (Docker)
- A serverless environment that supports long–running tasks (less ideal for Discord bots)

General steps:

1. Clone the repo or upload the code
2. Create `.env` with secret keys and IDs
3. Place `service_account.json` in the working directory
4. Install dependencies: `pip install -r requirements.txt`
5. Run the bot: `python PolyOne.py`
6. Use a process manager (e.g., `systemd`, `pm2`, `supervisord`, or Docker restart policies)

Make sure automatic restarts are configured in case of crashes or host reboots.
