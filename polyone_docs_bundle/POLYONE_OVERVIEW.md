# PolyOne: The Unified Growth & XP Bot for the Polymer Community

PolyOne is an all–in–one Discord bot designed to turn Polymer’s protocol growth into an interactive community experience.
It combines real–time on–chain metrics, an XP system, content–creation rewards, and (optionally) quizzes and prediction games
into a single, unified system.

---

## 1. What PolyOne Does

### 1.1 Live Metrics & Milestones

PolyOne connects to Polymer’s public analytics endpoints and regularly checks:

- **Top Transactions Leaderboard**  
  From `https://analytics.polymer.zone/api/metrics/leaderboard/top-transactions?environment=mainnet`  
  PolyOne watches the top 10 transactions by USD volume and alerts the community when a **new transaction** enters the top 10.

- **Total Volume & Milestones**  
  From `https://analytics.polymer.zone/api/analytics?environment=mainnet`  
  PolyOne tracks total USD volume and posts a celebration message every time total volume crosses a new **0.1B milestone**
  (e.g., $1.0B → $1.1B → $1.2B, etc.).

- **Daily Status Summary**  
  Once per day at 23:59 UTC, PolyOne posts a concise summary of:
  - **Total Daily Volume (24h)** - Total volume transacted in the past 24 hours
  - **Biggest Transfer Today** - The largest individual transaction from the past 24 hours
  - **Average Transaction Size (24h)** - Average size of all transactions from the past 24 hours (calculated from total volume and transaction count)
  - Total volume and its equivalent in billions
  - Last recorded milestone
  - Top 10 transactions (all-time)
  - Dashboard's last update time

- **Volume Counter Channel**  
  PolyOne can update a voice channel name to reflect current volume and 24h percentage change, e.g.:  
  `Polymer Volume: $1.063B (+4.2%)`

### 1.2 Unified XP System

PolyOne introduces a **single XP ledger** for all community actions.  
XP is logged as events in a Google Sheet (`xp_events`) and aggregated into totals (`xp_totals`).

XP can be earned from:
- High–quality tweets about Polymer
- Polymer University quizzes (optional integration)
- Future prediction games or on–chain metrics quizzes
- Manual XP awards from admins

This allows the community to see a single, consistent measure of contribution.

### 1.3 Tweet Submission & Grading

PolyOne lets members submit tweets using two commands:

- `/set_twitter @handle` – link your Discord account to an X/Twitter handle
- `/submit_tweet <tweet_url>` – submit a tweet for review and XP

The bot:
1. Validates and normalizes the tweet URL
2. Extracts the tweet ID
3. Optionally fetches tweet text via the X/Twitter API (if a bearer token is configured)
4. Uses an AI–based rubric to grade the tweet (if OpenAI is configured)
5. Writes the tweet, grade, and XP into the `tweets` sheet
6. Logs a corresponding XP event into `xp_events`

Users can then see their progress via:
- `/xp_me` – show total XP
- `/xp_leaderboard` – show top XP holders
- `/check_tweets` – see how many tweets they’ve submitted
- `/polyu_rank` – look up their Polymer University rank (if the sheet is set up)

---

## 2. Why PolyOne Exists

Polymer’s growth story can be hard to follow just by looking at dashboards. PolyOne brings that story into Discord, where
the community already lives, and rewards people for helping tell it.

It aims to:

- Make blockchain growth feel tangible and exciting
- Reward people for learning, teaching, and creating content
- Align incentives around long–term participation, not one–off events
- Provide a single, extensible XP system the team can build on over time

---

## 3. How XP Fits into the Community Journey

PolyOne is designed to be flexible enough to support:

- **Ambassador programs**
- **Campaigns and seasons**
- **Tiered roles and perks**
- **Early access and allowlists**
- **Polymer University “graduates” and advanced contributors**

By centralising XP, the community team can plug in new initiatives without reinventing scoring every time.

---

## 4. How to Use This Bot

For everyday community members:

- Link your X account: `/set_twitter @your_handle`
- Share content: `/submit_tweet <url>`
- Track your progress: `/xp_me`, `/xp_leaderboard`
- Follow Polymer’s growth: watch the metrics channel for milestones & top transactions

For more technical details, see the **Technical Architecture**, **Admin Guide**, and **Developer Guide** documents.
