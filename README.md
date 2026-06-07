# Polyanalytics

Polymarket wallet intelligence — track profitable wallets, scan markets, detect whales.

## Files

| File | Purpose |
|------|---------|
| `falcon_api.py` | Heisenberg API client (markets, trades, PnL, leaderboard) |
| `wallet_analyzer.py` | Deep fingerprint a wallet — dip score, behavior, similar wallets |
| `alert_monitor.py` | Live whale + new position + leaderboard alerts |
| `query.py` | Query watchlist — by market, active today, top performers |
| `watchlist.json` | Tracked wallets with labels and cluster info |
| `server.py` + `dashboard.html` | Local web dashboard |

## Quick Start

```bash
pip install requests flask

# Run dashboard
python server.py

# Run live alerts
python alert_monitor.py --whale 50000 --new-pos 20000

# Query watchlist
python query.py list
python query.py active
python query.py market atp-
python query.py top --min-pnl 100000
python query.py scan --market atp- --min-cost 50000
python query.py profile 0x...

# Add wallet to watchlist
python query.py add 0x... "My label"

# Full wallet analysis
python wallet_analyzer.py 0x... --find-similar --top 20
```

## Alert Methods

| Alert | What it catches |
|-------|----------------|
| `WHALE-BUY` | Wallet accumulates >$50K in one sports market within 2h |
| `NEW-POSITION` | First buy in a sports market >$20K |
| `LEADERBOARD-NEW` | New wallet enters top 20 h-score leaderboard |

Set `WEBHOOK_URL` env var for Discord/Telegram alerts.
