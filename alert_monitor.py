"""
Polymarket Alert Monitor

Four detection methods running in parallel:

  METHOD 1 — Cluster wallet watcher (PRIORITY)
    Fires immediately when any of the 28 tracked cluster wallets
    makes a new position in any sports market, regardless of size.

  METHOD 2 — Live market whale scanner
    Polls recent trades every 2 min. Alerts when any wallet
    spends >$WHALE_THRESHOLD in a single sports market within a 2h window.

  METHOD 3 — New position opener
    Alerts immediately when any wallet opens a NEW position in a
    sports/tennis market with a single trade >$NEW_POS_THRESHOLD.

  METHOD 4 — Leaderboard watcher
    Checks h_score leaderboard every 15 min. Alerts when a new
    wallet enters the top N.

Usage:
    python alert_monitor.py
    python alert_monitor.py --whale 100000 --new-pos 30000 --top-n 15

Alerts print to terminal, append to logs/alerts.log, and send to Telegram.
"""

import os, sys, time, json, argparse, requests, threading
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

from falcon_api import FalconAPI, TOKEN, API_URL
import tg

api = FalconAPI()
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# ── Cluster wallets (28) ────────────────────────────────────────────────────────

CLUSTER = {
    '0x204f72f35326db932158cba6adff0b9a1da95e14': 'All3 #1',
    '0x2005d16a84ceefa912d4e380cd32e7ff827875ea': 'RANK16',
    '0x32b484581fc5606de9c1e43af4636b6be9bc8b21': 'All3 #3',
    '0xfe787d2da716d60e8acff57fb87eb13cd4d10319': 'All3 #4',
    '0xde9f7f4e77a1595623ceb58e469f776257ccd43c': 'All3 #5',
    '0x7d9a514f9da9e8aa7fa37306943c7d1720d805e6': 'All3 #6',
    '0x7fea691e28d169a33c500607279f2acb49058f74': 'All3 #7',
    '0x5c2f05f661bc4b3fce17e41b43a06026d0d6499c': 'All3 #8',
    '0xadfb6cba33cebca02eab6111ace1e3924b9cc2ef': 'All3 #9',
    '0xa82a8a824d9102e2309584da10c8622478bda759': 'WTA Sharp',
    '0xcf6c5492124794394dd9eac46498a8babbe47e66': 'BU Sharp#1',
    '0xafac3978537771688598b0b65b9bb222e8318730': 'BU Sharp#2',
    '0x42c99f38d2b951b0dc8e8bd5371fa80c9dd19623': 'BU Sharp#3',
    '0xccd81fbd3395dc43a0531f8484b21c2462daf4de': 'BU Sharp#4',
}
CLUSTER_LOWER = {k.lower(): v for k, v in CLUSTER.items()}

# ── Config ──────────────────────────────────────────────────────────────────────

SPORTS_KEYWORDS = ["atp-", "wta-", "epl-", "sea-", "bun-", "nba-", "nfl-",
                   "mlb-", "nhl-", "ufc-", "mma-", "tennis", "soccer", "football"]

os.makedirs('logs', exist_ok=True)
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "alerts.log")

# ── Helpers ─────────────────────────────────────────────────────────────────────

def is_sports(slug: str) -> bool:
    sl = (slug or "").lower()
    return any(kw in sl for kw in SPORTS_KEYWORDS)

def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)

def ts_str() -> str:
    return now_utc().strftime("%Y-%m-%d %H:%M UTC")

def alert(method: str, msg: str, tg_msg: str = None):
    line = f"[{ts_str()}] [{method}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    tg.send(tg_msg or f"`{method}`\n{msg}")

def post(agent_id, params, limit=200, offset=0):
    payload = {
        "agent_id": agent_id,
        "params": params,
        "pagination": {"limit": limit, "offset": offset},
        "formatter_config": {"format_type": "raw"},
    }
    r = requests.post(API_URL, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


# ── Method 1: Cluster wallet watcher ───────────────────────────────────────────

class ClusterWatcher:
    """
    Polls every 60s. Fires instantly when a cluster wallet opens
    a new position in any sports market.
    Early movers (BU Sharp#2, WTA Sharp) will trigger hours before the rest.
    """
    POLL_INTERVAL = 60

    def __init__(self):
        self.seen: set[tuple] = set()  # (wallet, slug, outcome)
        self.seeded = False

    def _fetch(self, wallet: str) -> list:
        try:
            data = post(556, {
                "wallet_proxy": wallet,
                "condition_id": "ALL",
                "market_slug": "ALL",
                "side": "BUY",
            }, limit=50)
            return data.get("data", {}).get("results", [])
        except Exception as e:
            print(f"  [ClusterWatcher] fetch error {wallet[:10]}: {e}")
            return []

    def run(self):
        print(f"[ClusterWatcher] Watching {len(CLUSTER)} cluster wallets | poll={self.POLL_INTERVAL}s")

        # Seed on first run so we don't spam on startup
        for wallet in CLUSTER_LOWER:
            for t in self._fetch(wallet):
                slug    = (t.get("slug") or t.get("market_slug") or "").lower()
                outcome = (t.get("outcome") or "").lower()
                self.seen.add((wallet, slug, outcome))
        self.seeded = True
        print(f"  [ClusterWatcher] Seeded {len(self.seen)} existing positions")

        while True:
            time.sleep(self.POLL_INTERVAL)
            for wallet, label in CLUSTER_LOWER.items():
                for t in self._fetch(wallet):
                    slug    = (t.get("slug") or t.get("market_slug") or "").lower()
                    outcome = (t.get("outcome") or "").lower()
                    price   = float(t.get("price") or 0)
                    size    = float(t.get("size") or 0)
                    cost    = price * size
                    key     = (wallet, slug, outcome)

                    if key not in self.seen and is_sports(slug) and cost >= 500:
                        self.seen.add(key)
                        short_slug = slug.split('-')
                        match = ' vs '.join(short_slug[1:3]).title() if len(short_slug) > 2 else slug
                        alert(
                            "CLUSTER",
                            f"{label} | {match} | {outcome.upper()} @ {price:.3f} | ${cost:,.0f}",
                            tg_msg=(
                                f"*CLUSTER ALERT* 🎾\n"
                                f"*{label}* opened position\n"
                                f"Match: `{slug}`\n"
                                f"Pick: *{outcome.upper()}* @ {price:.3f}\n"
                                f"Size: ${cost:,.0f}\n"
                                f"Wallet: `{wallet}`"
                            )
                        )


# ── Method 2 & 3: Trade scanner ────────────────────────────────────────────────

class TradeScanner:
    POLL_INTERVAL = 120

    def __init__(self, whale_threshold: float, new_pos_threshold: float):
        self.whale_threshold   = whale_threshold
        self.new_pos_threshold = new_pos_threshold
        self.window: dict      = defaultdict(lambda: defaultdict(list))
        self.alerted_whale: set[tuple] = set()
        self.seen_positions: set[tuple] = set()
        self.last_seen_ts: str | None = None

    def _fetch_recent_trades(self) -> list:
        try:
            data = post(556, {
                "proxy_wallet": "ALL",
                "condition_id": "ALL",
                "market_slug": "ALL",
                "side": "ALL",
            }, limit=200)
            return data.get("data", {}).get("results", [])
        except Exception as e:
            print(f"  [TradeScanner] fetch error: {e}")
            return []

    def _prune_window(self, cutoff: datetime):
        for wallet in list(self.window):
            for market in list(self.window[wallet]):
                self.window[wallet][market] = [
                    (ts, cost) for ts, cost in self.window[wallet][market]
                    if ts >= cutoff
                ]
                if not self.window[wallet][market]:
                    del self.window[wallet][market]
            if not self.window[wallet]:
                del self.window[wallet]

    def _process(self, trades: list):
        cutoff = now_utc() - timedelta(hours=2)
        self._prune_window(cutoff)

        new_trades = []
        for t in trades:
            ts_raw = t.get("timestamp") or t.get("created_at") or ""
            if self.last_seen_ts and ts_raw <= self.last_seen_ts:
                continue
            new_trades.append(t)

        if not new_trades:
            return

        all_ts = [t.get("timestamp") or "" for t in new_trades]
        self.last_seen_ts = max(all_ts) if all_ts else self.last_seen_ts

        for t in new_trades:
            if t.get("side") != "BUY":
                continue

            wallet = t.get("proxy_wallet") or ""
            slug   = t.get("slug") or t.get("market_slug") or ""
            price  = float(t.get("price") or 0)
            size   = float(t.get("size")  or 0)
            cost   = price * size

            if not wallet or not slug or cost <= 0:
                continue

            pos_key = (wallet.lower(), slug.lower())
            is_new  = pos_key not in self.seen_positions
            self.seen_positions.add(pos_key)

            if is_new and is_sports(slug) and cost >= self.new_pos_threshold:
                alert(
                    "NEW-POSITION",
                    f"${cost:,.0f} first buy | {slug} | {t.get('outcome')} @ {price:.3f} | {wallet[:12]}...",
                    tg_msg=(
                        f"*NEW POSITION* 💰\n"
                        f"${cost:,.0f} first entry\n"
                        f"Market: `{slug}`\n"
                        f"Pick: *{t.get('outcome','?').upper()}* @ {price:.3f}\n"
                        f"Wallet: `{wallet}`"
                    )
                )

            ts_val = t.get("timestamp") or ""
            try:
                ts_dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
            except Exception:
                ts_dt = now_utc()

            if ts_dt >= cutoff:
                self.window[wallet.lower()][slug.lower()].append((ts_dt, cost))

        for wallet, markets in self.window.items():
            for slug, entries in markets.items():
                if not is_sports(slug):
                    continue
                total_cost = sum(c for _, c in entries)
                key = (wallet, slug)
                if total_cost >= self.whale_threshold and key not in self.alerted_whale:
                    self.alerted_whale.add(key)
                    alert(
                        "WHALE-BUY",
                        f"${total_cost:,.0f} accumulated in 2h | {slug} | {wallet[:12]}...",
                        tg_msg=(
                            f"*WHALE BUY* 🐋\n"
                            f"${total_cost:,.0f} in 2h window\n"
                            f"Market: `{slug}`\n"
                            f"Wallet: `{wallet}`\n"
                            f"Trades: {len(entries)}"
                        )
                    )

    def run(self):
        print(f"[TradeScanner] whale=${self.whale_threshold:,.0f} | new_pos=${self.new_pos_threshold:,.0f}")
        while True:
            try:
                trades = self._fetch_recent_trades()
                self._process(trades)
            except Exception as e:
                print(f"  [TradeScanner] error: {e}")
            time.sleep(self.POLL_INTERVAL)


# ── Method 4: Leaderboard watcher ──────────────────────────────────────────────

class LeaderboardWatcher:
    POLL_INTERVAL = 900  # 15 min

    def __init__(self, top_n: int):
        self.top_n  = top_n
        self.known  = set()
        self.seeded = False

    def _fetch_top(self) -> list:
        try:
            data = post(584, {
                "min_win_rate_15d":     "0.45",
                "max_win_rate_15d":     "0.95",
                "min_roi_15d":          "0.0",
                "min_pnl_15d":          "5000",
                "min_total_trades_15d": "10",
                "max_total_trades_15d": "100000",
                "sort_by":              "h_score",
            }, limit=self.top_n)
            return data.get("data", {}).get("results", [])
        except Exception as e:
            print(f"  [LeaderboardWatcher] fetch error: {e}")
            return []

    def run(self):
        print(f"[LeaderboardWatcher] top_n={self.top_n} | poll={self.POLL_INTERVAL}s")
        while True:
            try:
                top     = self._fetch_top()
                current = set()
                for i, w in enumerate(top):
                    addr = (w.get("wallet") or w.get("proxy_wallet") or "").lower()
                    if not addr:
                        continue
                    current.add(addr)
                    if self.seeded and addr not in self.known:
                        h   = w.get("h_score", "?")
                        wr  = w.get("win_rate_pct") or w.get("win_rate_15d") or "?"
                        roi = w.get("roi_pct_15d") or w.get("roi_pct") or "?"
                        pnl = w.get("total_pnl_15d") or w.get("total_pnl") or "?"
                        alert(
                            "LEADERBOARD-NEW",
                            f"New wallet rank #{i+1} | H={h} WR={wr} ROI={roi} PnL={pnl} | {addr[:12]}...",
                            tg_msg=(
                                f"*NEW LEADERBOARD ENTRY* 📊\n"
                                f"Rank #{i+1} / top {self.top_n}\n"
                                f"H-Score: {h} | WR: {wr} | ROI: {roi}\n"
                                f"PnL: ${float(pnl or 0):,.0f}\n"
                                f"Wallet: `{addr}`"
                            )
                        )
                if not self.seeded:
                    print(f"  [LeaderboardWatcher] Seeded {len(current)} wallets")
                    self.seeded = True
                self.known = current
            except Exception as e:
                print(f"  [LeaderboardWatcher] error: {e}")
            time.sleep(self.POLL_INTERVAL)


# ── Entry point ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--whale",   type=float, default=50_000)
    parser.add_argument("--new-pos", type=float, default=20_000)
    parser.add_argument("--top-n",   type=int,   default=20)
    args = parser.parse_args()

    print("=" * 60)
    print("  FALCON ALERT MONITOR")
    print(f"  Method 1 — Cluster wallets: {len(CLUSTER)} tracked (60s poll)")
    print(f"  Method 2 — Whale buy:       >${args.whale:,.0f} in 2h window")
    print(f"  Method 3 — New position:    >${args.new_pos:,.0f} first trade")
    print(f"  Method 4 — Leaderboard:     top {args.top_n} new entrants")
    print(f"  Log: {LOG_FILE}")
    tg_ok = bool(os.environ.get('TG_BOT_TOKEN')) and bool(os.environ.get('TG_CHAT_ID'))
    print(f"  Telegram: {'ENABLED' if tg_ok else 'NOT SET (add TG_BOT_TOKEN + TG_CHAT_ID to .env)'}")
    print("=" * 60)

    if tg_ok:
        tg.send("*Falcon monitor started* ✅\nWatching cluster + whale + leaderboard alerts.")

    threads = [
        threading.Thread(target=ClusterWatcher().run,                                      daemon=True, name="ClusterWatcher"),
        threading.Thread(target=TradeScanner(args.whale, args.new_pos).run,                daemon=True, name="TradeScanner"),
        threading.Thread(target=LeaderboardWatcher(args.top_n).run,                        daemon=True, name="LeaderboardWatcher"),
    ]
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
