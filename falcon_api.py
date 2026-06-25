"""
Falcon API Client
Base URL: https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized
Auth: Bearer token in Authorization header
"""

from dotenv import load_dotenv
import os
load_dotenv()

import requests

API_URL = "https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized"
TOKEN = os.environ['HEISENBERG_TOKEN']


class FalconAPI:
    def __init__(self, token: str = TOKEN):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _post(self, agent_id: int, params: dict, limit: int = 50, offset: int = 0) -> dict:
        payload = {
            "agent_id": agent_id,
            "params": params,
            "pagination": {"limit": limit, "offset": offset},
            "formatter_config": {"format_type": "raw"},
        }
        r = requests.post(API_URL, json=payload, headers=self.headers)
        r.raise_for_status()
        return r.json()

    def _all(self, agent_id: int, params: dict, limit: int = 200) -> list:
        """Fetch all pages."""
        results, offset = [], 0
        while True:
            data = self._post(agent_id, params, limit=limit, offset=offset)
            batch = data.get("data", {}).get("results", [])
            results.extend(batch)
            if not data.get("pagination", {}).get("has_more") or len(batch) < limit:
                break
            offset += limit
        return results

    # ── Market Data ───────────────────────────────────────────────────────────

    def markets(self, min_volume=0, condition_id="ALL", market_slug="ALL",
                event_slug="ALL", closed="BOTH",
                end_date_min="1600000000", end_date_max="2200000000",
                limit=50, offset=0) -> dict:
        """agent_id 574 — Polymarket markets."""
        return self._post(574, {
            "min_volume": str(min_volume),
            "condition_id": str(condition_id),
            "market_slug": str(market_slug),
            "event_slug": str(event_slug),
            "closed": str(closed),
            "end_date_min": str(end_date_min),
            "end_date_max": str(end_date_max),
        }, limit, offset)

    def candlesticks(self, token_id: str, interval="1h",
                     start_time=None, end_time=None,
                     limit=200, offset=0) -> dict:
        """agent_id 568 — OHLCV bars. interval: 1m/5m/1h/1d."""
        params = {"token_id": token_id, "interval": interval}
        if start_time: params["start_time"] = str(start_time)
        if end_time:   params["end_time"]   = str(end_time)
        return self._post(568, params, limit, offset)

    def orderbook(self, token_id: str, start_time=None, end_time=None,
                  limit=50, offset=0) -> dict:
        """agent_id 572 — Order book snapshots."""
        params = {"token_id": token_id}
        if start_time: params["start_time"] = str(start_time)
        if end_time:   params["end_time"]   = str(end_time)
        return self._post(572, params, limit, offset)

    # ── Trade Data ────────────────────────────────────────────────────────────

    def trades(self, wallet="ALL", condition_id="ALL", market_slug="ALL",
               side="ALL", start_time=None, end_time=None,
               limit=50, offset=0) -> dict:
        """agent_id 556 — Polymarket historical trades."""
        params = {
            "wallet_proxy": str(wallet),
            "condition_id": str(condition_id),
            "market_slug": str(market_slug),
            "side": str(side),
        }
        if start_time: params["start_time"] = str(start_time)
        if end_time:   params["end_time"]   = str(end_time)
        return self._post(556, params, limit, offset)

    def pnl(self, wallet: str, granularity="1d",
            start_date=None, end_date=None, condition_id=None,
            limit=50, offset=0) -> dict:
        """agent_id 569 — Realized PnL time series. Dates: YYYY-MM-DD."""
        params = {"wallet": wallet, "granularity": granularity}
        if start_date:   params["start_time"]   = str(start_date)
        if end_date:     params["end_time"]      = str(end_date)
        if condition_id: params["condition_id"]  = str(condition_id)
        return self._post(569, params, limit, offset)

    # ── Traders ───────────────────────────────────────────────────────────────

    def leaderboard(self, period="1d", wallet="ALL",
                    min_pnl=None, min_win_rate=None, min_sharpe=None,
                    limit=50, offset=0) -> dict:
        """agent_id 579 — Official Polymarket PnL leaderboard.
        period: 1d / 3d / 7d / 30d"""
        params = {
            "leaderboard_period": period,
            "wallet_address": str(wallet),
            "min_total_pnl": str(min_pnl)  if min_pnl      else "-1.0",
            "max_total_pnl": "-1.0",
            "min_win_rate":  str(min_win_rate) if min_win_rate else "-1.0",
            "max_win_rate":  "-1.0",
            "min_sharpe_ratio": str(min_sharpe) if min_sharpe else "-1.0",
            "max_sharpe_ratio": "-1.0",
        }
        return self._post(579, params, limit, offset)

    def h_score_leaderboard(self, min_win_rate=0.45, max_win_rate=0.95,
                             min_roi=0, min_pnl=0,
                             min_trades=50, max_trades=100000,
                             sort_by="h_score", limit=50, offset=0) -> dict:
        """agent_id 584 — Falcon H-Score (skill-filtered) leaderboard."""
        return self._post(584, {
            "min_win_rate_15d":    str(min_win_rate),
            "max_win_rate_15d":    str(max_win_rate),
            "min_roi_15d":         str(min_roi),
            "min_pnl_15d":         str(min_pnl),
            "min_total_trades_15d": str(min_trades),
            "max_total_trades_15d": str(max_trades),
            "sort_by":             sort_by,
        }, limit, offset)

    def wallet_360(self, wallet: str, window_days=7) -> dict:
        """agent_id 581 — 60+ metrics for a wallet. window_days: 1/3/7/15."""
        return self._post(581, {
            "proxy_wallet": wallet,
            "window_days": str(window_days),
        }, limit=1)

    # ── Market Intelligence ───────────────────────────────────────────────────

    def market_insights(self, condition_id: str, min_volume_24h=0,
                        volume_trend="ALL", min_liquidity_percentile=0,
                        limit=50, offset=0) -> dict:
        """agent_id 575 — Liquidity, volume trend, concentration signals."""
        return self._post(575, {
            "condition_id": str(condition_id),
            "min_volume_24h": str(min_volume_24h),
            "volume_trend": volume_trend,
            "min_liquidity_percentile": str(min_liquidity_percentile),
        }, limit, offset)

    def social_pulse(self, keywords: list[str], hours_back=12,
                     limit=50, offset=0) -> dict:
        """agent_id 585 — Tweet sentiment / momentum.
        keywords: list of strings, e.g. ['Trump', 'election']"""
        kw_str = "{" + ",".join(keywords) + "}"
        return self._post(585, {
            "keywords": kw_str,
            "hours_back": str(hours_back),
        }, limit, offset)

    # ── Kalshi ────────────────────────────────────────────────────────────────

    def kalshi_markets(self, ticker=None, event_ticker=None, title=None,
                       status="open", close_time_min=None, close_time_max=None,
                       limit=50, offset=0) -> dict:
        """agent_id 565 — Kalshi market catalog."""
        params = {"status": status}
        if ticker:          params["ticker"]          = ticker
        if event_ticker:    params["event_ticker"]    = event_ticker
        if title:           params["title"]           = title
        if close_time_min:  params["close_time_min"]  = str(close_time_min)
        if close_time_max:  params["close_time_max"]  = str(close_time_max)
        return self._post(565, params, limit, offset)

    def kalshi_trades(self, ticker: str, start_time=None, end_time=None,
                      limit=50, offset=0) -> dict:
        """agent_id 573 — Kalshi trade history."""
        params = {"ticker": ticker}
        if start_time: params["start_time"] = str(start_time)
        if end_time:   params["end_time"]   = str(end_time)
        return self._post(573, params, limit, offset)


# ── Quick demo ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    api = FalconAPI()

    print("=== Top 5 Markets by Volume ===")
    r = api.markets(min_volume=100_000, closed="False", limit=5)
    for m in r["data"]["results"]:
        print(f"  ${m['volume_total']:>12,.0f}  {m['question'][:70]}")

    print("\n=== H-Score Leaderboard Top 5 ===")
    r = api.h_score_leaderboard(min_pnl=10_000, limit=5)
    for t in r["data"]["results"]:
        print(f"  #{t['leaderboard_rank']:3d}  H={t['h_score']}  ROI={t['roi_pct_15d']}%  PnL=${float(t['total_pnl_15d']):>10,.0f}  {t['wallet']}")

    print("\n=== Social Pulse: Trump ===")
    r = api.social_pulse(["Trump", "election"], hours_back=6)
    results = r.get("data", {}).get("results", [])
    if results:
        s = results[0]
        print(f"  tweets={s.get('tweet_count')}  accel={s.get('acceleration')}  diversity={s.get('author_diversity_pct')}%")
    else:
        print("  No results")
