# How Falcon Works — Complete Picture

Read this if you want to understand exactly what happens, when, and why.

---

## What runs automatically vs what needs you

| Thing | Automatic? | What triggers it |
|-------|-----------|-----------------|
| Alert monitor | YES — always on | Starts on Mac login, restarts if it crashes |
| Cluster wallet alerts | YES | Any cluster wallet puts $500+ on a match |
| Whale/new position alerts | YES | Any wallet hits the threshold |
| Daily brief | YES — 07:00 UTC | launchd cron fires `daily_brief.py` |
| Telegram message to you | YES | Sent automatically as part of the brief |
| DB logging | YES | Every position written to `falcon.db` |
| Session markdown saved | YES | `sessions/YYYY-MM-DD-brief.md` written every day |
| Querying the data | NO — manual | You run `python ask.py match X` |

**If you ignore everything:** the system keeps running. Data keeps collecting. DB keeps growing. You fall behind on reading it, not on having it.

---

## Exactly what happens each day — step by step

### 07:00 UTC — Daily Brief fires automatically

```
launchd (Mac scheduler)
  → runs python daily_brief.py
      → fetches all trades for 28 wallets from Heisenberg API
      → for each match: who bought what, at what price, at what time
      → detects exits (SELL trades on same market)
      → classifies each position:
            EARLY_MOVER  = entered before 08:00 UTC
            DIP_BUYER    = entry price < 0.55
            QUICK_FLIP   = bought and sold same day
            CONVICTION   = still holding, normal entry
            LATE_ENTRY   = entered at price >= 0.85 (match already live)
      → writes every position to falcon.db (permanent, cumulative)
      → writes sessions/2026-06-25-brief.md (readable log)
      → sends Telegram message to you with top consensus picks
```

### What the Telegram message looks like

```
Falcon Brief — 2026-06-25
18/28 wallets active

Consensus Picks:
• Keys vs Zhu → KEYS  $8,400 | 6 wallets | first: 09:12
• Mochizuki vs Tabur → MOCHIZUKI $5,200 | 4 wallets | first: 06:01
• Sebov vs Shymanova → SEBOV $3,100 | 3 wallets | first: 09:18

Patterns: CONVICTION=12 | EARLY_MOVER=4 | DIP_BUYER=2 | QUICK_FLIP=1
```

### What happens if you ignore the Telegram

Nothing breaks. The data is already:
- Written to `falcon.db`
- Saved as `sessions/YYYY-MM-DD-brief.md`
- Queryable via `python ask.py`

You can check yesterday, last week, or last month at any time. Nothing gets lost.

---

## What the alert monitor does (running right now, always on)

Three things running in parallel every minute:

**1. Cluster Watcher (every 60 seconds)**
Polls each of the 28 wallets. The moment any of them opens a new position >= $500 in a sports market, you get a Telegram instantly:

```
CLUSTER ALERT 🎾
WTA Sharp opened position
Match: wta-keys-zhu-2026-06-25
Pick: KEYS @ 0.662
Size: $2,100
Wallet: 0xa82a8a...
```

**2. Whale Scanner (every 2 minutes)**
Watches ALL wallets globally. If any wallet accumulates >$50,000 in one market within a 2-hour window, you get alerted — even if it's not one of your tracked wallets.

**3. Leaderboard Watcher (every 15 minutes)**
Monitors the H-Score leaderboard top 20. If a new wallet enters the top 20 that wasn't there before, you get alerted. This is how you find new wallets to add to the cluster.

---

## Does it use an LLM / AI to understand the data?

**Currently: No.** Everything is rule-based Python:
- Strategy classification is a set of if/else rules (price thresholds, time checks)
- The Telegram messages are templated strings
- There is no AI parsing or reasoning happening

**What this means:** the brief is structured and consistent but it does not surface surprises, give opinions, or explain *why* something looks interesting. It just reports what happened.

**What could be added (next step):**
An LLM layer via OpenRouter that reads the daily brief and adds commentary:
- "BU Sharp#2 fired 3 hours early on the same match as yesterday — possible inside info"
- "3 wallets took opposing positions — this is a divided market, be cautious"
- "WTA Sharp is the only wallet on this match, historically she's correct 80% of the time when solo"

This would turn the brief from a data dump into actual insight. Not built yet.

---

## Does it understand your Telegram messages?

**Currently: No.** The bot only sends, it does not receive or parse replies.

**What this means:** you can't reply "what did you think of the Keys match" and get an answer. It's one-way.

**What could be added:**
A Telegram webhook listener that receives your messages and routes them:
- "check krejcikova" → runs `ask.py match krejcikova`, replies with results
- "what's WTA Sharp been doing" → runs `ask.py wallet WTA Sharp`, replies
- "brief" → resends today's brief
- "who's been dip buying" → runs `ask.py patterns`, replies

This would make it interactive. Also not built yet.

---

## The database (falcon.db) — what's being tracked

Every position ever seen is stored permanently:

```
positions table:
  date         — 2026-06-25
  wallet       — 0xa82a8a...
  label        — WTA Sharp
  group_type   — CLUSTER
  match_slug   — wta-keys-zhu-2026-06-25
  match_name   — Keys vs Zhu
  outcome      — Madison Keys
  entry_price  — 0.662
  entry_time   — 2026-06-25T09:12
  entry_cost   — 2100.00
  exit_price   — 0.890 (if they sold same day, else NULL)
  exit_time    — 2026-06-25T11:30 (or NULL)
  strategy     — EARLY_MOVER / DIP_BUYER / CONVICTION / QUICK_FLIP / LATE_ENTRY
```

After 30 days you'll be able to answer questions like:
- "Which wallets have the best record on DIP_BUYER plays?"
- "Does BU Sharp#2 early entries tend to be right?"
- "Which expansion wallets should be promoted to the core cluster?"

---

## How to query the data manually

```bash
# What happened in today's brief
python ask.py today

# All history on a specific match/player
python ask.py match krejcikova
python ask.py match keys

# A wallet's full history and strategy breakdown
python ask.py wallet "WTA Sharp"
python ask.py wallet "BU Sharp#2"

# What strategies dominated this week
python ask.py patterns

# Most active wallets last 14 days
python ask.py top
```

---

## File map

```
falcon/
  daily_brief.py      ← runs at 07:00 UTC, builds the daily brief
  alert_monitor.py    ← always running, real-time cluster + whale alerts
  tg.py               ← Telegram sender
  db.py               ← SQLite interface
  ask.py              ← query CLI
  falcon_api.py       ← Heisenberg API client
  falcon.db           ← cumulative database (grows every day)
  .env                ← secrets (gitignored)
  sessions/           ← YYYY-MM-DD-brief.md for every day
  market_sessions/    ← raw JSON data snapshots
  logs/               ← monitor.log, daily.log
```

---

## What's not built yet (honest gaps)

| Gap | Impact | Fix |
|-----|--------|-----|
| LLM analysis layer | Brief is data, not insight | Add OpenRouter call at end of daily_brief.py |
| Two-way Telegram | Can't ask the bot questions | Add webhook listener + command router |
| Win/loss outcome tracking | Don't know if picks were correct | Need to check market resolution via API |
| Wallet auto-promotion | Expansion wallets never graduate to cluster | Add win-rate threshold check weekly |
| Counter-trade signals | Not tracking who's consistently wrong | Add negative win-rate tracking to DB |
| VPS | Brief misses if Mac is asleep | Run on Hetzner/DigitalOcean $5/mo |

---

## If something breaks

**Monitor not running:**
```bash
launchctl list | grep falcon        # check status
tail -50 logs/monitor_err.log       # see errors
bash setup_launchd.sh               # reinstall
```

**No Telegram messages:**
```bash
python tg.py "test"                 # test the connection
cat .env                            # check token + chat ID are set
```

**Missing data for a day:**
```bash
python daily_brief.py 2026-06-24    # re-run for any past date
```

**Re-run from scratch on a new machine:**
```bash
git clone https://github.com/bigkofta/polyanalytics.git falcon
cd falcon
cp .env.example .env                # add your token + TG credentials
pip install requests python-dotenv
bash setup_launchd.sh
```
