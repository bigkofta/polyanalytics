"""
Wallet Analyzer — Reverse-engineer profitable wallets on Polymarket.

Usage:
    python wallet_analyzer.py 0xf8831548531d56ad6a4331493243c447a827cd1f
    python wallet_analyzer.py 0x... --find-similar --top 20
    python wallet_analyzer.py 0x... --days 15
"""

import sys
import time
import argparse
from datetime import datetime, timezone
from collections import defaultdict
from falcon_api import FalconAPI

api = FalconAPI()


# ── Helpers ───────────────────────────────────────────────────────────────────

def ts_to_str(ts):
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)

def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def pct(v):
    return f"{v*100:.1f}%"

def usd(v):
    return f"${v:>10,.0f}"


# ── Core analysis ─────────────────────────────────────────────────────────────

def fetch_all_trades(wallet: str, days_back: int = 15) -> list:
    """Pull every trade for this wallet, paginated."""
    print(f"  Fetching trades for {wallet[:10]}...")
    results = []
    offset = 0
    limit = 200
    while True:
        r = api.trades(wallet=wallet, limit=limit, offset=offset)
        batch = r.get("data", {}).get("results", [])
        results.extend(batch)
        if not r.get("pagination", {}).get("has_more") or len(batch) < limit:
            break
        offset += limit
        time.sleep(0.1)
    print(f"  Got {len(results)} trades")
    return results


def compute_dip_score(trade: dict) -> float | None:
    """
    Pull 24x 1h candles ending at the trade timestamp.
    Return where the entry price sits in the high-low range: 0.0 = bottom, 1.0 = top.
    Returns None if candle data unavailable.
    """
    token_id = trade.get("asset_id") or trade.get("token_id") or trade.get("outcome_token_id")
    if not token_id:
        return None

    trade_ts = safe_float(trade.get("timestamp") or trade.get("created_at") or trade.get("time"))
    if not trade_ts:
        return None

    price = safe_float(trade.get("price") or trade.get("avg_price"))
    if not price:
        return None

    # 24h window ending at trade time
    start_ts = int(trade_ts) - 86400
    end_ts   = int(trade_ts)

    try:
        r = api.candlesticks(str(token_id), interval="1h",
                             start_time=start_ts, end_time=end_ts, limit=24)
        candles = r.get("data", {}).get("results", [])
    except Exception:
        return None

    if not candles:
        return None

    highs = [safe_float(c.get("high") or c.get("h")) for c in candles]
    lows  = [safe_float(c.get("low")  or c.get("l")) for c in candles]
    highs = [h for h in highs if h > 0]
    lows  = [l for l in lows  if l > 0]

    if not highs or not lows:
        return None

    range_high = max(highs)
    range_low  = min(lows)
    spread = range_high - range_low

    if spread < 0.0001:
        return 0.5  # flat market

    return max(0.0, min(1.0, (price - range_low) / spread))


def analyze_trades(trades: list, sample_candles: int = 40) -> dict:
    """
    Extract behavioral fingerprint from trade list.
    sample_candles: max trades to fetch candle data for (API cost control).
    """
    if not trades:
        return {}

    # -- Basic stats
    sides = defaultdict(int)
    # Key: (slug, outcome) — NEVER slug alone, to prevent confusing same-player
    # appearances across different matches (e.g. "chwalin" in two slugs).
    market_data: dict[tuple, dict] = defaultdict(lambda: {
        "trades": 0, "cost": 0.0, "shares": 0.0,
        "prices": [], "timestamps": []
    })
    sizes = []
    prices = []
    timestamps = []

    for t in trades:
        side = (t.get("side") or "?").upper()
        sides[side] += 1

        slug    = t.get("slug") or t.get("market_slug") or t.get("condition_id") or "unknown"
        outcome = t.get("outcome") or "?"
        key     = (slug, outcome)

        size  = safe_float(t.get("size") or t.get("amount") or t.get("shares"))
        price = safe_float(t.get("price") or t.get("avg_price"))
        ts_raw = t.get("timestamp") or t.get("created_at") or t.get("time") or ""

        if size:
            sizes.append(size)
            market_data[key]["shares"] += size
        if price:
            prices.append(price)
            market_data[key]["prices"].append(price)
        if size and price:
            market_data[key]["cost"] += size * price
        if ts_raw:
            market_data[key]["timestamps"].append(ts_raw)
        market_data[key]["trades"] += 1

        if ts_raw:
            try:
                ts_dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                timestamps.append(ts_dt.timestamp())
            except Exception:
                pass

    # -- Timing analysis (hour-of-day distribution)
    hours = defaultdict(int)
    for ts in timestamps:
        try:
            h = datetime.fromtimestamp(ts, tz=timezone.utc).hour
            hours[h] += 1
        except Exception:
            pass

    peak_hours = sorted(hours.items(), key=lambda x: -x[1])[:3]

    # -- Dip score (sample to limit API calls)
    buy_trades = [t for t in trades
                  if (t.get("side") or t.get("outcome") or "").upper() in ("BUY", "YES", "NO")]
    sample = buy_trades[:sample_candles]

    print(f"  Calculating dip scores on {len(sample)} trades (of {len(buy_trades)} buys)...")
    dip_scores = []
    for i, t in enumerate(sample):
        score = compute_dip_score(t)
        if score is not None:
            dip_scores.append(score)
        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{len(sample)} done")
        time.sleep(0.05)

    avg_dip_score = sum(dip_scores) / len(dip_scores) if dip_scores else None
    dip_buyer_pct = sum(1 for s in dip_scores if s < 0.25) / len(dip_scores) if dip_scores else None
    top_buyer_pct = sum(1 for s in dip_scores if s > 0.75) / len(dip_scores) if dip_scores else None

    # -- Market diversity — build display rows sorted by cost descending
    # Each row: (slug, outcome, cost, shares, p_lo, p_hi, n_trades, first_ts, last_ts)
    market_rows = []
    for (slug, outcome), d in market_data.items():
        p_lo = min(d["prices"]) if d["prices"] else 0
        p_hi = max(d["prices"]) if d["prices"] else 0
        first_ts = min(d["timestamps"]) if d["timestamps"] else ""
        last_ts  = max(d["timestamps"]) if d["timestamps"] else ""
        market_rows.append({
            "slug": slug, "outcome": outcome,
            "cost": d["cost"], "shares": d["shares"],
            "p_lo": p_lo, "p_hi": p_hi,
            "trades": d["trades"],
            "first_ts": first_ts, "last_ts": last_ts,
        })
    market_rows.sort(key=lambda x: -x["cost"])
    unique_markets = len(set(r["slug"] for r in market_rows))

    return {
        "total_trades":      len(trades),
        "unique_markets":    unique_markets,
        "market_rows":       market_rows,
        "top_markets":       [(f"{r['slug']} | BET: {r['outcome']}", r["trades"])
                              for r in market_rows[:5]],
        "buy_count":         sides.get("BUY", 0) + sides.get("YES", 0) + sides.get("NO", 0),
        "sides":             dict(sides),
        "avg_price":         sum(prices) / len(prices) if prices else None,
        "avg_size":          sum(sizes) / len(sizes) if sizes else None,
        "total_volume":      sum(sizes),
        "peak_hours":        peak_hours,
        "dip_scores_sample": len(dip_scores),
        "avg_dip_score":     avg_dip_score,
        "dip_buyer_pct":     dip_buyer_pct,    # fraction of buys in bottom 25%
        "top_buyer_pct":     top_buyer_pct,    # fraction of buys in top 25%
        "timestamps":        sorted(timestamps),
    }


def fetch_wallet_360(wallet: str, window_days: int = 15) -> dict:
    print(f"  Fetching wallet_360 ({window_days}d)...")
    try:
        r = api.wallet_360(wallet, window_days=window_days)
        results = r.get("data", {}).get("results", [])
        return results[0] if results else {}
    except Exception as e:
        print(f"  wallet_360 failed: {e}")
        return {}


def fetch_pnl_series(wallet: str) -> list:
    print("  Fetching PnL series...")
    try:
        r = api.pnl(wallet, granularity="1d")
        return r.get("data", {}).get("results", [])
    except Exception as e:
        print(f"  PnL fetch failed: {e}")
        return []


# ── Similarity search ─────────────────────────────────────────────────────────

def find_similar_wallets(fingerprint: dict, w360: dict, top_n: int = 20) -> list:
    """
    Use h_score leaderboard with metric ranges derived from the target wallet,
    then score each candidate by similarity.
    """
    print(f"\n  Scanning leaderboard for similar wallets...")

    # Extract anchor metrics
    win_rate = safe_float(w360.get("win_rate_pct") or w360.get("win_rate") or
                          w360.get("win_rate_15d") or 0)
    # Normalise: if stored as 0-100, convert to 0-1
    if win_rate > 1:
        win_rate /= 100

    roi = safe_float(w360.get("roi_pct") or w360.get("roi_pct_15d") or
                     w360.get("roi") or 0)
    if roi > 1:
        roi /= 100

    pnl_val = safe_float(w360.get("total_pnl") or w360.get("total_pnl_15d") or 0)

    # Widen the net ±30% on win rate, floor ROI/PnL at 0
    wr_lo = max(0.0, win_rate - 0.15)
    wr_hi = min(1.0, win_rate + 0.15)

    print(f"  Anchor: win_rate={pct(win_rate)}  roi={pct(roi)}  pnl={usd(pnl_val)}")
    print(f"  Search band: win_rate [{pct(wr_lo)} - {pct(wr_hi)}]")

    candidates = []
    for period in ["7d", "30d"]:
        try:
            r = api.h_score_leaderboard(
                min_win_rate=wr_lo,
                max_win_rate=wr_hi,
                min_roi=max(0, roi - 0.2),
                min_pnl=max(0, pnl_val * 0.2),
                min_trades=max(10, fingerprint.get("total_trades", 50) // 3),
                limit=100,
            )
            batch = r.get("data", {}).get("results", [])
            for w in batch:
                w["_period"] = period
            candidates.extend(batch)
            time.sleep(0.1)
        except Exception as e:
            print(f"  Leaderboard ({period}) failed: {e}")

    # Deduplicate by wallet address
    seen = set()
    unique = []
    for c in candidates:
        addr = c.get("wallet") or c.get("proxy_wallet") or ""
        if addr and addr.lower() not in seen:
            seen.add(addr.lower())
            unique.append(c)

    # Score similarity
    target_dip = fingerprint.get("dip_buyer_pct") or 0

    def similarity(c):
        c_wr   = safe_float(c.get("win_rate_pct") or c.get("win_rate_15d") or 0)
        if c_wr > 1: c_wr /= 100
        c_roi  = safe_float(c.get("roi_pct_15d") or c.get("roi_pct") or 0)
        if c_roi > 1: c_roi /= 100
        c_h    = safe_float(c.get("h_score") or 0)

        wr_diff  = abs(c_wr - win_rate)
        roi_diff = abs(c_roi - roi)

        score = 100 - (wr_diff * 200) - (roi_diff * 100) + (c_h * 0.1)
        return score

    ranked = sorted(unique, key=similarity, reverse=True)
    return ranked[:top_n]


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_report(wallet: str, w360: dict, fp: dict, pnl_series: list,
                 similars: list = None):
    div = "─" * 70

    print(f"\n{div}")
    print(f"  WALLET FINGERPRINT REPORT")
    print(f"  {wallet}")
    print(f"{div}")

    # -- Wallet 360
    if w360:
        print("\n  [PERFORMANCE METRICS]")
        fields = [
            ("total_pnl_15d",    "Total PnL (15d)"),
            ("roi_pct_15d",      "ROI (15d)"),
            ("win_rate_pct",     "Win Rate"),
            ("sharpe_ratio",     "Sharpe Ratio"),
            ("total_trades_15d", "Total Trades (15d)"),
            ("h_score",          "H-Score"),
            ("avg_position_size","Avg Position"),
            ("markets_traded",   "Markets Traded"),
        ]
        for key, label in fields:
            val = w360.get(key)
            if val is not None:
                print(f"    {label:<25} {val}")

    # -- PnL trend
    if pnl_series:
        print("\n  [PNL TREND — last 10 days]")
        for row in pnl_series[-10:]:
            date = row.get("date") or row.get("time") or row.get("timestamp") or ""
            pnl  = safe_float(row.get("realized_pnl") or row.get("pnl") or row.get("cumulative_pnl") or 0)
            bar  = "+" * min(30, max(0, int(pnl / 500))) if pnl >= 0 else "-" * min(30, max(0, int(-pnl / 500)))
            print(f"    {str(date)[:10]}  {usd(pnl)}  {bar}")

    # -- Behavioral fingerprint
    if fp:
        print("\n  [BEHAVIORAL FINGERPRINT]")
        print(f"    Total trades analyzed:   {fp.get('total_trades', 0)}")
        print(f"    Unique markets:          {fp.get('unique_markets', 0)}")
        print(f"    Avg entry price:         {fp.get('avg_price', 0):.3f}" if fp.get('avg_price') else "")
        print(f"    Avg position size:       {fp.get('avg_size', 0):.1f}" if fp.get('avg_size') else "")

        if fp.get("dip_scores_sample"):
            print(f"\n  [DIP SCORE ANALYSIS]  (n={fp['dip_scores_sample']})")
            avg = fp.get("avg_dip_score")
            dip = fp.get("dip_buyer_pct")
            top = fp.get("top_buyer_pct")

            print(f"    Avg range percentile:    {pct(avg) if avg is not None else 'N/A'}")
            print(f"    % buys in bottom 25%:    {pct(dip) if dip is not None else 'N/A'}  <- dip buyer signal")
            print(f"    % buys in top 25%:       {pct(top) if top is not None else 'N/A'}  <- momentum signal")

            if dip is not None:
                if dip > 0.5:
                    style = "STRONG DIP BUYER"
                elif dip > 0.35:
                    style = "MODERATE DIP BUYER"
                elif top is not None and top > 0.5:
                    style = "MOMENTUM BUYER"
                elif top is not None and top > 0.35:
                    style = "MODERATE MOMENTUM BUYER"
                else:
                    style = "NEUTRAL / MIXED"
                print(f"\n    >> TRADING STYLE: {style}")

        if fp.get("peak_hours"):
            print(f"\n  [ACTIVITY PATTERN]")
            print(f"    Peak trading hours (UTC):")
            for hour, count in fp["peak_hours"]:
                bar = "#" * (count * 20 // max(c for _, c in fp["peak_hours"]))
                print(f"      {hour:02d}:00  {bar} ({count})")

        if fp.get("market_rows"):
            print(f"\n  [MARKETS — sorted by $ invested]")
            print(f"    {'DATE':<12} {'SLUG':<42} {'BET ON':<25} {'COST':>10} {'SHARES':>12} {'P_LO':>6} {'P_HI':>6}")
            print(f"    {'-'*12} {'-'*42} {'-'*25} {'-'*10} {'-'*12} {'-'*6} {'-'*6}")
            for r in fp["market_rows"]:
                date = (r["first_ts"] or "")[:10]
                print(f"    {date:<12} {r['slug']:<42} {r['outcome']:<25} "
                      f"{r['cost']:>10,.0f} {r['shares']:>12,.0f} "
                      f"{r['p_lo']:>6.3f} {r['p_hi']:>6.3f}")

    # -- Similar wallets
    if similars:
        print(f"\n{div}")
        print(f"  SIMILAR WALLETS  (top {len(similars)})")
        print(f"{div}")
        print(f"  {'WALLET':<44} {'H':>6} {'WIN%':>7} {'ROI%':>7} {'PNL':>12}")
        print(f"  {'─'*44} {'─'*6} {'─'*7} {'─'*7} {'─'*12}")
        for c in similars:
            addr   = c.get("wallet") or c.get("proxy_wallet") or "?"
            h      = safe_float(c.get("h_score") or 0)
            wr     = safe_float(c.get("win_rate_pct") or c.get("win_rate_15d") or 0)
            roi    = safe_float(c.get("roi_pct_15d") or c.get("roi_pct") or 0)
            pnl_v  = safe_float(c.get("total_pnl_15d") or c.get("total_pnl") or 0)
            print(f"  {addr:<44} {h:>6.1f} {wr:>6.1f}% {roi:>6.1f}% {pnl_v:>12,.0f}")

    print(f"\n{div}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Polymarket wallet reverse-engineer")
    parser.add_argument("wallet", help="0x wallet address")
    parser.add_argument("--days",         type=int, default=15,
                        help="Lookback window in days (default 15)")
    parser.add_argument("--candle-sample",type=int, default=40,
                        help="Max trades to compute dip scores for (default 40)")
    parser.add_argument("--find-similar", action="store_true",
                        help="Scan leaderboard for wallets with similar metrics")
    parser.add_argument("--top",          type=int, default=20,
                        help="How many similar wallets to return (default 20)")
    args = parser.parse_args()

    wallet = args.wallet.strip().lower()
    print(f"\nAnalyzing wallet: {wallet}")
    print("=" * 70)

    # 1. Pull all data
    w360       = fetch_wallet_360(wallet, window_days=args.days)
    trades     = fetch_all_trades(wallet, days_back=args.days)
    pnl_series = fetch_pnl_series(wallet)

    # 2. Build fingerprint
    print("\n  Building behavioral fingerprint...")
    fp = analyze_trades(trades, sample_candles=args.candle_sample)

    # 3. Similar wallets (optional)
    similars = None
    if args.find_similar:
        similars = find_similar_wallets(fp, w360, top_n=args.top)

    # 4. Report
    print_report(wallet, w360, fp, pnl_series, similars)


if __name__ == "__main__":
    main()
