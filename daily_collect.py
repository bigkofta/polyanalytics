"""
Daily collection script — runs via launchd every morning.
Fetches today's positions for all 28 cluster wallets,
saves to market_sessions/, sends Telegram summary.

Run manually:   python daily_collect.py
Run for date:   python daily_collect.py 2026-06-25
"""

import sys, json, os, requests
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

from falcon_api import FalconAPI, TOKEN, API_URL
import tg

api = FalconAPI()
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

TODAY = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime('%Y-%m-%d')

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

def fetch_trades(wallet):
    payload = {
        "agent_id": 556,
        "params": {
            "wallet_proxy": wallet,
            "condition_id": "ALL",
            "market_slug": "ALL",
            "side": "BUY",
            "start_time": f"{TODAY}T00:00:00Z",
            "end_time":   f"{TODAY}T23:59:59Z",
        },
        "pagination": {"limit": 200, "offset": 0},
        "formatter_config": {"format_type": "raw"},
    }
    r = requests.post(API_URL, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json().get('data', {}).get('results', [])

SPORTS = ['atp-', 'wta-', 'epl-', 'nba-', 'nfl-', 'mlb-', 'nhl-', 'ufc-']

def is_sports(slug):
    return any(slug.lower().startswith(k) for k in SPORTS)

def main():
    print(f"\n=== Falcon Daily Collection: {TODAY} ===\n")
    all_results = {}
    market_totals = defaultdict(lambda: {'wallets': [], 'total': 0, 'outcome': ''})

    for wallet, label in CLUSTER.items():
        trades = fetch_trades(wallet)
        today_sports = [t for t in trades if is_sports(t.get('slug','') or t.get('market_slug',''))]
        if today_sports:
            all_results[wallet] = {'label': label, 'trades': today_sports}
            for t in today_sports:
                slug    = t.get('slug') or t.get('market_slug') or ''
                outcome = t.get('outcome') or ''
                price   = float(t.get('price') or 0)
                size    = float(t.get('size') or 0)
                cost    = price * size
                key     = f"{slug}|{outcome}"
                market_totals[key]['wallets'].append(label)
                market_totals[key]['total'] += cost
                market_totals[key]['outcome'] = outcome
                market_totals[key]['slug'] = slug
            print(f"  {label}: {len(today_sports)} trades")
        else:
            print(f"  {label}: no positions today")

    # Save raw data
    os.makedirs('market_sessions', exist_ok=True)
    out_path = f'market_sessions/daily_{TODAY}.json'
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved: {out_path}")

    # Build summary
    sorted_markets = sorted(market_totals.items(), key=lambda x: x[1]['total'], reverse=True)

    lines = [f"*Falcon Daily Briefing* — {TODAY}"]
    lines.append(f"{len(all_results)}/{len(CLUSTER)} wallets active\n")

    if sorted_markets:
        lines.append("*Top Consensus Picks:*")
        for key, data in sorted_markets[:10]:
            slug    = data['slug']
            parts   = slug.split('-')
            match   = ' vs '.join(parts[1:3]).title() if len(parts) > 2 else slug
            outcome = data['outcome'].upper()
            total   = data['total']
            count   = len(data['wallets'])
            lines.append(f"• {match} — *{outcome}* | ${total:,.0f} | {count} wallets")
    else:
        lines.append("No cluster positions found today.")

    summary = '\n'.join(lines)
    print('\n' + summary)
    tg.send(summary)

if __name__ == '__main__':
    main()
