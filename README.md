# Falcon — Polymarket Tennis Wallet Tracker

Sharp-money radar for Polymarket tennis markets. Tracks a cluster of 28 wallets
identified as consistently profitable, detects their daily positions, and monitors
for alerts when they enter new matches.

**If you're reading this after a gap and have no memory of what was built:** start here.

---

## What This Is

Polymarket is a prediction market where people bet on outcomes including tennis matches.
A hidden API (Heisenberg) exposes the trade history of every wallet on the platform.

This project:
1. **Identified 28 "sharp" wallets** — wallets that called all 3 correct outcomes on
   a specific day (Jun 8, 2026), then cross-validated their win rates
2. **Tracks their daily positions** — run a script each morning to see what they're betting
3. **Alerts when the cluster fires** — the 28 wallets tend to act in a tight 30-40 min
   window around 09:10 UTC daily
4. **Supports counter-trading** — some wallets identified as "bait" (consistently wrong)

---

## Quick Start

```bash
# 1. Copy env template and add your token
cp .env.example .env
# edit .env and set HEISENBERG_TOKEN=your_token_here

# 2. Install deps
pip install requests python-dotenv flask

# 3. Check today's picks (edit TODAY= at top of script first)
python check_today_expanded.py

# 4. Run alert monitor (stays running, notifies on new positions)
python alert_monitor.py --whale 50000 --new-pos 20000

# 5. Ad-hoc API queries
python query.py list
python query.py active
python query.py profile 0x...
```

---

## The API

**Heisenberg** is the backend powering Polymarket's "Tennis Whale" leaderboard feature.
Reverse-engineered in the Jun 7 sessions.

```
URL:  https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized
Auth: Bearer token in Authorization header
```

**Agent IDs** (the `agent_id` param selects what data you get):

| ID  | What it returns |
|-----|-----------------|
| 556 | Trade history for a wallet |
| 568 | OHLCV candlestick data |
| 569 | Realized PnL time series |
| 572 | Order book snapshots |
| 574 | Market catalog |
| 575 | Market insights / liquidity signals |
| 579 | Official PnL leaderboard |
| 581 | Wallet 360 (60+ metrics) |
| 584 | H-Score leaderboard (skill-filtered) |
| 585 | Social pulse / tweet sentiment |

**Key gotcha:** trades endpoint (agent 556) uses param `wallet_proxy`, but wallet_360
(agent 581) uses `proxy_wallet`. Different names. Don't mix them up.

**Market slug pattern:**
- ATP: `atp-player1-player2-YYYY-MM-DD` (names truncated ~7 chars, lowercase)
- WTA: `wta-player1-player2-YYYY-MM-DD`
- Example: `wta-andrees-mertens-2026-06-08`

---

## The 28 Wallet Cluster

### How They Were Found

**Jun 8, 2026** — three matches where the outcome was non-obvious:
- Mertens won `wta-andrees-mertens-2026-06-08`
- Bellucci won `atp-fokina-bellucc-2026-06-08` (not Fokina)
- Udvardy won `wta-alexand-udvardy-2026-06-08`

63 wallets called all 3 correctly. After filtering bots and low-volume accounts: **14 foundation wallets**.
Expanded to **28 wallets** on Jun 13 via co-appearance analysis on 362 expansion candidates.

### Foundation Wallets (14)

| Label | Wallet | Notes |
|-------|--------|-------|
| All3 #1 | `0x204f72f35326db932158cba6adff0b9a1da95e14` | |
| RANK16 | `0x2005d16a84ceefa912d4e380cd32e7ff827875ea` | |
| All3 #3 | `0x32b484581fc5606de9c1e43af4636b6be9bc8b21` | |
| All3 #4 | `0xfe787d2da716d60e8acff57fb87eb13cd4d10319` | |
| All3 #5 | `0xde9f7f4e77a1595623ceb58e469f776257ccd43c` | |
| All3 #6 | `0x7d9a514f9da9e8aa7fa37306943c7d1720d805e6` | |
| All3 #7 | `0x7fea691e28d169a33c500607279f2acb49058f74` | |
| All3 #8 | `0x5c2f05f661bc4b3fce17e41b43a06026d0d6499c` | |
| All3 #9 | `0xadfb6cba33cebca02eab6111ace1e3924b9cc2ef` | |
| WTA Sharp | `0xa82a8a824d9102e2309584da10c8622478bda759` | Early mover, WTA focus, often solo on markets others miss |
| BU Sharp#1 | `0xcf6c5492124794394dd9eac46498a8babbe47e66` | |
| BU Sharp#2 | `0xafac3978537771688598b0b65b9bb222e8318730` | Fires 06:00-06:07 UTC, 2-3 hrs before rest of cluster |
| BU Sharp#3 | `0x42c99f38d2b951b0dc8e8bd5371fa80c9dd19623` | |
| BU Sharp#4 | `0xccd81fbd3395dc43a0531f8484b21c2462daf4de` | |

### Notable Individual Strategies

**WTA Sharp** (`0xa82a8a...`): Fires early pre-match. Often the only wallet in a market
for hours before others arrive. Focuses on WTA. Solo-correct on markets the rest skip.

**BU Sharp#2** (`0xafac39...`): Fires 06:00-06:07 UTC — 2-3 hours before the main cluster
window. Use as an early signal.

**PURE_FLIP_B** (`0x360334761e7cebc80ebf0c01a5d70e0c735422ed`): Not in core cluster but
notable. Jun 13: bought Krejcikova dip at 0.630, added at 0.760, then exited clean after
Set 1 win. No sunk cost, no greed. Smart money behaviour.

### Infrastructure Wallets (do NOT track as sharp money)

| Label | Wallet | Notes |
|-------|--------|-------|
| Tennis Whale (Rank1) | `0xf8831548531d56ad6a4331493243c447a827cd1f` | $2.8M PnL, human, tennis only |
| NHL Bot (Rank11) | `0x03E8a544e97eEff5753BC1E90D46e5EF22af1697` | 110K trades, fully automated |
| Master funder | `0xEAF73C61a0dE2848170C05E834d2829CfFab7110` | Funds multiple wallets, not a trader |
| Daily bot | `0x3a9418b2651c8164DB5EBc56F12008137865e0f7` | Automated daily ops |

---

## Cluster Behaviour Patterns

- **Main firing window:** 09:10-09:45 UTC daily
- **Pre-match entry price:** 0.65-0.80 range
- **Live signal:** price jumps to >=0.80 means match has started
- **Primary strategy:** dip buying during live match price crashes
- **Smart exits:** exits BEFORE result is certain — no emotional sunk-cost hold
- **BU Sharp#2 early signal:** fires 06:00-06:07 UTC, hours before the rest

### Jun 10 Example (consensus picks)

| Player | Cluster Spend |
|--------|--------------|
| Yibing Wu | $16,519 |
| Potapova | $10,557 |
| Boisson | $6,553 |
| Perricard | $5,904 |

WTA Sharp solo early: Daria Snigur $6,801, Katie Boulter $3,489
BU Sharp#2 early (06:01 UTC): Boisson $5,000, Udvardy $5,200

---

## Files

| File | What it does |
|------|-------------|
| `falcon_api.py` | API client class — all Heisenberg endpoints. Start here. |
| `check_today_expanded.py` | **Main daily script.** Check all 28 wallets' picks. Set `TODAY=` at top. |
| `today_tennis.py` | Same but 14 foundation wallets only |
| `alert_monitor.py` | Runs continuously, alerts when cluster fires on new positions |
| `wallet_analyzer.py` | Deep analysis of a single wallet (PnL, patterns, history) |
| `correlate.py` | Cross-market wallet correlation |
| `expand_cluster.py` | Find non-cluster wallets co-appearing in cluster markets |
| `winners3.py` | Find wallets who called all 3 Jun-08 winners (how cluster was built) |
| `query.py` | CLI for ad-hoc API queries |
| `server.py` | Flask dashboard (basic) |

### Data Files

| Path | Contents |
|------|----------|
| `market_sessions/` | Raw API response JSONs |
| `market_sessions/winners_all3.json` | 63 wallets who called Mertens+Bellucci+Udvardy |
| `market_sessions/expansion_2026-06-10.json` | 362 expansion wallet candidates |
| `market_sessions/today_expanded_2026-06-12.json` | Jun 12 positions across 28 wallets |
| `market_sessions/today_expanded_2026-06-13.json` | Jun 13 positions across 28 wallets |
| `sessions/` | Full readable transcripts of every working session |

---

## Session History

Full conversation transcripts are in `sessions/` — readable markdown, every message preserved.

| Date | File | What Happened |
|------|------|---------------|
| Jun 7a | `sessions/2026-06-07a-*.md` | Reverse-engineered Heisenberg API, found Tennis Whale, 3-wallet cluster |
| Jun 7b | `sessions/2026-06-07b-*.md` | Cracked full API, built Flask dashboard, WTA analysis |
| Jun 10 | `sessions/2026-06-10-*.md` | Built 63->14 cluster, tracked Jun 10 picks, ran 362-wallet expansion |
| Jun 13 | `sessions/2026-06-13-*.md` | Expanded to 28, Krejcikova live dip buyers, PURE_FLIP_B pattern |
| Jun 22 | `sessions/2026-06-22-*.md` | Post-crash recovery, session archive |

---

## Environment Setup

```bash
# .env  (never commit this file)
HEISENBERG_TOKEN=eyJhbG...your_token_here

# Optional: alerts webhook
WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Scripts read the token via:
```python
from dotenv import load_dotenv
import os
load_dotenv()
TOKEN = os.environ['HEISENBERG_TOKEN']
```

---

## Next Steps

- [ ] Verify expansion wallet quality — which of 362 candidates are Tier 1 (5+ markets)
- [ ] SQLite DB to track win rates per wallet over time
- [ ] Alert delivery via Telegram/Discord (webhook support already in alert_monitor.py)
- [ ] Auto-resolve match outcomes
- [ ] Counter-trade signal identification (wallets with consistent negative edge)
