from dotenv import load_dotenv
import os
load_dotenv()

import requests, json, time
from collections import defaultdict

API_URL = 'https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized'
TOKEN = os.environ['HEISENBERG_TOKEN']
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

TODAY = '2026-06-10'

WALLETS = {
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
    '0xcf6c5492124794394dd9eac46498a8babbe47e66': 'BU Sharp #1',
    '0xafac3978537771688598b0b65b9bb222e8318730': 'BU Sharp #2',
    '0x42c99f38d2b951b0dc8e8bd5371fa80c9dd19623': 'BU Sharp #3',
    '0xccd81fbd3395dc43a0531f8484b21c2462daf4de': 'BU Sharp #4',
}

def fetch_trades(wallet):
    r = requests.post(API_URL, json={
        'agent_id': 556,
        'params': {'proxy_wallet': wallet, 'condition_id': 'ALL',
                   'market_slug': 'ALL', 'side': 'ALL'},
        'pagination': {'limit': 200, 'offset': 0},
        'formatter_config': {'format_type': 'raw'},
    }, headers=headers, timeout=20)
    return r.json().get('data', {}).get('results', [])

def is_tennis(slug):
    return 'atp' in slug or 'wta' in slug or 'tennis' in slug

# Aggregate: market -> list of (wallet, label, outcome, cost, price, time)
market_activity = defaultdict(list)
wallet_summary = {}

for wallet, label in WALLETS.items():
    print(f'Fetching {label} ({wallet[:10]})...', flush=True)
    trades = fetch_trades(wallet)
    today_tennis = [t for t in trades
                    if t.get('timestamp', '').startswith(TODAY)
                    and is_tennis(t.get('slug', ''))]

    if not today_tennis:
        print(f'  -- quiet today', flush=True)
        wallet_summary[wallet] = {'label': label, 'trades': [], 'markets': {}}
        time.sleep(0.1)
        continue

    by_market = defaultdict(lambda: {'cost': 0.0, 'shares': 0.0, 'outcome': '', 'prices': [], 'times': []})
    for t in today_tennis:
        slug = t.get('slug', '')
        out  = t.get('outcome', '?')
        px   = float(t.get('price', 0))
        sz   = float(t.get('size', 0))
        ts   = t.get('timestamp', '')[:16]
        key  = (slug, out)
        by_market[key]['cost']    += px * sz
        by_market[key]['shares']  += sz
        by_market[key]['outcome']  = out
        by_market[key]['prices'].append(px)
        by_market[key]['times'].append(ts)
        market_activity[slug].append({
            'wallet': wallet, 'label': label, 'outcome': out,
            'cost': px*sz, 'price': px, 'time': ts
        })

    print(f'  {len(today_tennis)} trades across {len(set(k[0] for k in by_market))} markets', flush=True)
    for (slug, out), d in sorted(by_market.items(), key=lambda x: -x[1]['cost']):
        avg_px = sum(d['prices']) / len(d['prices'])
        first  = min(d['times'])
        print(f'  {first}  {slug[:42]:<42}  {out[:22]:<22}  ${d["cost"]:>8,.0f}  avg_px={avg_px:.3f}', flush=True)

    wallet_summary[wallet] = {'label': label, 'trades': today_tennis, 'markets': by_market}
    time.sleep(0.15)

# Cross-market: which markets have multiple cluster wallets
print(f'\n{"="*90}')
print(f'  MARKETS WITH MULTIPLE CLUSTER WALLETS TODAY')
print(f'{"="*90}')
hot_markets = {slug: acts for slug, acts in market_activity.items() if len(acts) >= 2}
for slug in sorted(hot_markets, key=lambda s: -len(hot_markets[s])):
    acts = hot_markets[slug]
    total = sum(a['cost'] for a in acts)
    print(f'\n  {slug}  ({len(acts)} cluster wallets, ${total:,.0f} total)')
    # Group by outcome
    by_out = defaultdict(list)
    for a in acts:
        by_out[a['outcome']].append(a)
    for out, wlist in sorted(by_out.items(), key=lambda x: -sum(w['cost'] for w in x[1])):
        out_total = sum(w['cost'] for w in wlist)
        wallets_str = ', '.join(f'{w["label"]}@{w["price"]:.3f}' for w in sorted(wlist, key=lambda x: x['time']))
        print(f'    {out[:28]:<28}  ${out_total:>8,.0f}  [{wallets_str}]')
