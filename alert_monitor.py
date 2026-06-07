"""
Polymarket Whale Alert Monitor
Runs three detection methods in parallel:

  METHOD 1 — Live market whale scanner
    Polls recent trades every 2 min. Alerts when any wallet
    spends >$WHALE_THRESHOLD in a single sports market within a 2h window.

  METHOD 2 — New position opener
    Alerts immediately when a wallet opens a NEW position in a
    sports/tennis market with a single trade >$NEW_POS_THRESHOLD.

  METHOD 3 — Leaderboard watcher
    Checks h_score leaderboard every 15 min. Alerts when a new
    wallet enters the top N.

Usage:
    python alert_monitor.py
    python alert_monitor.py --whale 100000 --new-pos 30000 --top-n 15

Alerts print to terminal and append to alerts.log.
Set WEBHOOK_URL env var to also POST alerts to a Discord/Telegram webhook.
"""

import os
import sys
import time
import json
import argparse
import requests
import threading
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from falcon_api import FalconAPI, TOKEN, API_URL

api = FalconAPI()
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# ── Config ─────────────────────────────────────────────────────────────────────

SPORTS_KEYWORDS = ["atp-", "wta-", "epl-", "sea-", "bun-", "nba-", "nfl-",
                   "mlb-", "nhl-", "ufc-", "mma-", "tennis", "soccer", "football"]

LOG_FILE = os.path.join(os.path.dirname(__file__), "alerts.log")

# ── Helpers ────────────────────────────────────────────────────────────────────

def is_sports(slug: str) -> bool:
    sl = (slug or "").lower()
    return any(kw in sl for kw in SPORTS_KEYWORDS)

def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)

def ts_str() -> str:
    return now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")

def alert(method: str, msg: str, data: dict = None):
    line = f"[{ts_str()}] [{method}] {msg}"
    print(line)
    if data:
        print(f"  {json.dumps(data)}")
    # Append to log
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
        if data:
            f.write(f"  {json.dumps(data)}\n")
    # Optional webhook (Discord or Telegram)
    webhook = os.getenv("WEBHOOK_URL")
    if webhook:
        try:
            payload = {"content": line}
            if "discord" in webhook:
                requests.post(webhook, json=payload, timeout=5)
            else:
                # Telegram: POST to /sendMessage
                requests.post(webhook, json={"text": line}, timeout=5)
        except Exception:
            pass

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


# ── Method 1 & 2: Trade scanner ────────────────────────────────────────────────

class TradeScanner:
    """
    Polls recent global trades every POLL_INTERVAL seconds.
    Maintains a rolling 2h window of (wallet, market) spending.
    Triggers whale alert when cumulative spend crosses WHALE_THRESHOLD.
    Triggers new-position alert on first large buy in a sports market.
    """

    POLL_INTERVAL = 120  # seconds between polls

    def __init__(self, whale_threshold: float, new_pos_threshold: float):
        self.whale_threshold   = whale_threshold
        self.new_pos_threshold = new_pos_threshold

        # wallet -> market_slug -> list of (timestamp, cost)
        self.window: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        # wallets we've already alerted on for a given market (reset when market resolves)
        self.alerted_whale: set[tuple] = set()
        # (wallet, market) pairs we've seen before (for new-position detection)
        self.seen_positions: set[tuple] = set()
        # track last seen trade timestamp to avoid re-processing
        self.last_seen_ts: str | None = None

    def _fetch_recent_trades(self) -> list:
        """Pull the latest batch of global trades."""
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
        """Remove entries older than cutoff from the rolling window."""
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
            ts_str_raw = t.get("timestamp") or t.get("created_at") or ""
            if self.last_seen_ts and ts_str_raw <= self.last_seen_ts:
                continue
            new_trades.append(t)

        if not new_trades:
            return

        # Update last_seen_ts
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

            # ── Method 2: New position alert ───────────────────────────────────
            pos_key = (wallet.lower(), slug.lower())
            is_new  = pos_key not in self.seen_positions
            self.seen_positions.add(pos_key)

            if is_new and is_sports(slug) and cost >= self.new_pos_threshold:
                alert("NEW-POSITION", f"${cost:,.0f} first buy | {slug} | {t.get('outcome')} @ {price:.3f}",
                      {"wallet": wallet, "slug": slug, "outcome": t.get("outcome"),
                       "price": price, "size": size, "cost": cost,
                       "timestamp": t.get("timestamp")})

            # ── Accumulate into rolling window ─────────────────────────────────
            ts_val = t.get("timestamp") or ""
            try:
                ts_dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
            except Exception:
                ts_dt = now_utc()

            if ts_dt >= cutoff:
                self.window[wallet.lower()][slug.lower()].append((ts_dt, cost))

        # ── Method 1: Whale threshold check ────────────────────────────────────
        for wallet, markets in self.window.items():
            for slug, entries in markets.items():
                if not is_sports(slug):
                    continue
                total_cost = sum(c for _, c in entries)
                key = (wallet, slug)
                if total_cost >= self.whale_threshold and key not in self.alerted_whale:
                    self.alerted_whale.add(key)
                    alert("WHALE-BUY",
                          f"${total_cost:,.0f} accumulated in 2h | {slug}",
                          {"wallet": wallet, "slug": slug,
                           "total_cost": total_cost, "trades": len(entries)})

    def run(self):
        print(f"[TradeScanner] Started | whale=${self.whale_threshold:,.0f} | "
              f"new_pos=${self.new_pos_threshold:,.0f} | poll={self.POLL_INTERVAL}s")
        while True:
            try:
                trades = self._fetch_recent_trades()
                self._process(trades)
            except Exception as e:
                print(f"  [TradeScanner] error: {e}")
            time.sleep(self.POLL_INTERVAL)


# ── Method 3: Leaderboard watcher ─────────────────────────────────────────────

class LeaderboardWatcher:
    """
    Checks h_score leaderboard every POLL_INTERVAL seconds.
    Alerts when a wallet newly enters the top N.
    """

    POLL_INTERVAL = 900  # 15 min

    def __init__(self, top_n: int):
        self.top_n   = top_n
        self.known   = set()   # wallets we've seen in top N before
        self.seeded  = False

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
        print(f"[LeaderboardWatcher] Started | top_n={self.top_n} | poll={self.POLL_INTERVAL}s")
        while True:
            try:
                top = self._fetch_top()
                current = set()
                for i, w in enumerate(top):
                    addr = (w.get("wallet") or w.get("proxy_wallet") or "").lower()
                    if addr:
                        current.add(addr)
                        if not self.seeded and addr not in self.known:
                            # On first run, just seed the known set
                            pass
                        elif self.seeded and addr not in self.known:
                            h     = w.get("h_score", "?")
                            wr    = w.get("win_rate_pct") or w.get("win_rate_15d") or "?"
                            roi   = w.get("roi_pct_15d") or w.get("roi_pct") or "?"
                            pnl   = w.get("total_pnl_15d") or w.get("total_pnl") or "?"
                            rank  = i + 1
                            alert("LEADERBOARD-NEW",
                                  f"New wallet in top {self.top_n} (rank #{rank}) | "
                                  f"H={h} WR={wr} ROI={roi} PnL={pnl}",
                                  {"wallet": addr, "rank": rank, "h_score": h,
                                   "win_rate": wr, "roi": roi, "pnl": pnl})

                if not self.seeded:
                    print(f"  [LeaderboardWatcher] Seeded {len(current)} known wallets in top {self.top_n}")
                    self.seeded = True

                self.known = current

            except Exception as e:
                print(f"  [LeaderboardWatcher] error: {e}")
            time.sleep(self.POLL_INTERVAL)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Polymarket whale alert monitor")
    parser.add_argument("--whale",   type=float, default=50_000,
                        help="Whale threshold: cumulative $ in one market/2h (default 50000)")
    parser.add_argument("--new-pos", type=float, default=20_000,
                        help="New position alert: single trade $ in sports market (default 20000)")
    parser.add_argument("--top-n",  type=int,   default=20,
                        help="Leaderboard top-N to watch (default 20)")
    args = parser.parse_args()

    print("=" * 60)
    print("  POLYMARKET WHALE ALERT MONITOR")
    print(f"  Method 1 — Whale buy:    >${args.whale:,.0f} in 2h window")
    print(f"  Method 2 — New position: >${args.new_pos:,.0f} first trade")
    print(f"  Method 3 — Leaderboard:  top {args.top_n} new entrants")
    print(f"  Log file: {LOG_FILE}")
    if os.getenv("WEBHOOK_URL"):
        print(f"  Webhook:  {os.getenv('WEBHOOK_URL')[:40]}...")
    print("=" * 60)
    print()

    scanner  = TradeScanner(whale_threshold=args.whale, new_pos_threshold=args.new_pos)
    watcher  = LeaderboardWatcher(top_n=args.top_n)

    t1 = threading.Thread(target=scanner.run,  daemon=True, name="TradeScanner")
    t2 = threading.Thread(target=watcher.run,  daemon=True, name="LeaderboardWatcher")

    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
