"""
Check today's tennis picks for original cluster + top expansion candidates.
"""
from dotenv import load_dotenv
import os
load_dotenv()

import requests, json, time
from collections import defaultdict

API_URL = 'https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized'
TOKEN = os.environ['HEISENBERG_TOKEN']
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

TODAY = '2026-06-13'

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

# Top expansion candidates from Jun-10 (by spend, 3+ markets)
EXPANSION = {
    '0x4b493d8ea89203ecfa5ac53ff8fc4a45aa050397': 'Exp#1($21k,9m)',
    '0xdd5ef115f801999575b03d78d0115ad8b2d59040': 'Exp#2($18k,9m)',
    '0x84ad9c5c547a82ec9a08547b94bd922446e5bfb7': 'Exp#3($17k,13m)',
    '0xa42f127d7e8df9f16881ffcc9ed0bc0326875f5a': 'Exp#4($17k,9m)',
    '0x98db8cca55c32b24cfb414b5b43d273f4e1fdd17': 'Exp#5($13k,15m)',
    '0x0d2d845a6ff64e31e04a70afce8a573940767ff5': 'Exp#6($10k,13m)',
    '0xdb83e85ffd22faa4009273034770f96ffc5b1e50': 'Exp#7($9k,10m)',
    '0x5b6331e7ff0831a3fe2ed12004747db1a9c911a4': 'Exp#8($9k,14m)',
    '0x1e3bb7def89b002d45fd86d37f35918c2618e232': 'Exp#9($6k,18m)',
    '0xf7f0b0b1e9c0fe02ccad926916ee31aef74b912c': 'Exp#10($5k,19m)',
    '0xeea3f08e8a36081233e4c4b4142fd61a7b56a6a2': 'Exp#11($4k,11m)',
    '0x908aad3bfbd70410e73f1db6a3e46c2a917cad16': 'Exp#12($3k,9m)',
    '0x0adedcb79423aed988a849827ff80b8cc7b3ed94': 'Exp#13($3k,14m)',
    '0x076daa87c4fe1a85402a9b6b8e0a866224388d4c': 'Exp#14($2k,15m)',
}

ALL_WALLETS = {**CLUSTER, **EXPANSION}

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

market_activity = defaultdict(list)  # slug -> [{wallet, label, outcome, cost, price, time}]
wallet_picks = {}

print(f'Checking {len(ALL_WALLETS)} wallets for {TODAY} tennis activity...\n', flush=True)

for wallet, label in ALL_WALLETS.items():
    group = 'CLUSTER' if wallet in CLUSTER else 'EXPAND'
    trades = fetch_trades(wallet)
    today = [t for t in trades
             if t.get('timestamp', '').startswith(TODAY)
             and is_tennis(t.get('slug', ''))]

    if not today:
        print(f'  [{group}] {label:<22} -- quiet', flush=True)
        wallet_picks[wallet] = {'label': label, 'group': group, 'markets': {}}
        time.sleep(0.1)
        continue

    by_market = defaultdict(lambda: {'cost': 0.0, 'shares': 0.0, 'outcome': '', 'prices': [], 'times': []})
    for t in today:
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
            'wallet': wallet, 'label': label, 'group': group,
            'outcome': out, 'cost': px*sz, 'price': px, 'time': ts
        })

    total_spend = sum(v['cost'] for v in by_market.values())
    print(f'  [{group}] {label:<22}  {len(set(k[0] for k in by_market))} markets  ${total_spend:,.0f}', flush=True)
    for (slug, out), d in sorted(by_market.items(), key=lambda x: -x[1]['cost']):
        avg_px = sum(d['prices']) / len(d['prices'])
        first  = min(d['times'])
        print(f'           {first}  {slug[:40]:<40}  {out[:20]:<20}  ${d["cost"]:>7,.0f}  px={avg_px:.3f}', flush=True)

    wallet_picks[wallet] = {'label': label, 'group': group, 'markets': {str(k): v for k, v in by_market.items()}}
    time.sleep(0.15)

# Cross-market consensus
print(f'\n{"="*90}', flush=True)
print(f'  CONSENSUS — MARKETS WITH 2+ WALLETS TODAY', flush=True)
print(f'{"="*90}', flush=True)

hot = {s: a for s, a in market_activity.items() if len(a) >= 2}
for slug in sorted(hot, key=lambda s: -len(hot[s])):
    acts = hot[slug]
    total = sum(a['cost'] for a in acts)
    cluster_count = sum(1 for a in acts if a['group'] == 'CLUSTER')
    expand_count  = sum(1 for a in acts if a['group'] == 'EXPAND')
    by_out = defaultdict(list)
    for a in acts:
        by_out[a['outcome']].append(a)
    print(f'\n  {slug}', flush=True)
    print(f'  {len(acts)} wallets (cluster={cluster_count}, expand={expand_count})  ${total:,.0f} total', flush=True)
    for out, wlist in sorted(by_out.items(), key=lambda x: -sum(w['cost'] for w in x[1])):
        out_total = sum(w['cost'] for w in wlist)
        wallets_str = ', '.join(f'{w["label"]}@{w["price"]:.3f}' for w in sorted(wlist, key=lambda x: x['time']))
        print(f'    {out[:28]:<28}  ${out_total:>8,.0f}  [{wallets_str}]', flush=True)

import os
os.makedirs('market_sessions', exist_ok=True)
json.dump({
    'date': TODAY,
    'market_activity': {s: acts for s, acts in market_activity.items()},
    'wallet_picks': wallet_picks,
}, open(f'market_sessions/today_expanded_{TODAY}.json', 'w'), indent=2)
print(f'\nSaved: market_sessions/today_expanded_{TODAY}.json', flush=True)
