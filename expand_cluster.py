"""
Cluster Expansion — Jun 10 2026
Find wallets appearing in 2+ of the same markets as our cluster wallets today.
These are candidates for cluster expansion.
"""
from dotenv import load_dotenv
import os
load_dotenv()

import requests, json, time
from collections import defaultdict

API_URL = 'https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized'
TOKEN = os.environ['HEISENBERG_TOKEN']
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

TODAY = '2026-06-10'

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
    '0xcf6c5492124794394dd9eac46498a8babbe47e66': 'BU Sharp #1',
    '0xafac3978537771688598b0b65b9bb222e8318730': 'BU Sharp #2',
    '0x42c99f38d2b951b0dc8e8bd5371fa80c9dd19623': 'BU Sharp #3',
    '0xccd81fbd3395dc43a0531f8484b21c2462daf4de': 'BU Sharp #4',
}

def fetch_market_all(slug):
    """Fetch all trades for a market slug."""
    all_trades, offset = [], 0
    while True:
        r = requests.post(API_URL, json={
            'agent_id': 556,
            'params': {'proxy_wallet': 'ALL', 'condition_id': 'ALL',
                       'market_slug': slug, 'side': 'ALL'},
            'pagination': {'limit': 200, 'offset': offset},
            'formatter_config': {'format_type': 'raw'},
        }, headers=headers, timeout=20)
        data = r.json()
        batch = data.get('data', {}).get('results', [])
        all_trades.extend(batch)
        if not data.get('pagination', {}).get('has_more') or len(batch) < 200:
            break
        offset += 200
        time.sleep(0.1)
    return all_trades

def fetch_wallet_today(wallet):
    """Fetch all trades for a wallet, return today's tennis slugs."""
    r = requests.post(API_URL, json={
        'agent_id': 556,
        'params': {'proxy_wallet': wallet, 'condition_id': 'ALL',
                   'market_slug': 'ALL', 'side': 'ALL'},
        'pagination': {'limit': 200, 'offset': 0},
        'formatter_config': {'format_type': 'raw'},
    }, headers=headers, timeout=20)
    trades = r.json().get('data', {}).get('results', [])
    slugs = set()
    for t in trades:
        if t.get('timestamp', '').startswith(TODAY):
            slug = t.get('slug', '')
            if 'atp' in slug or 'wta' in slug or 'tennis' in slug:
                slugs.add(slug)
    return slugs

# Step 1: Collect which markets cluster wallets are in today
print('=== STEP 1: Collect cluster wallet markets today ===', flush=True)
cluster_market_activity = defaultdict(list)  # slug -> [cluster_labels]

for wallet, label in CLUSTER.items():
    print(f'  Scanning {label}...', flush=True)
    slugs = fetch_wallet_today(wallet)
    for slug in slugs:
        cluster_market_activity[slug].append(label)
    time.sleep(0.15)

print(f'\nCluster active in {len(cluster_market_activity)} markets today:', flush=True)
for slug, labels in sorted(cluster_market_activity.items(), key=lambda x: -len(x[1])):
    print(f'  {len(labels):2d} cluster wallets  {slug}  [{", ".join(labels)}]', flush=True)

# Step 2: For markets with 2+ cluster wallets, fetch all participants
TARGET_MARKETS = [slug for slug, labels in cluster_market_activity.items() if len(labels) >= 2]
print(f'\n=== STEP 2: Fetching all participants in {len(TARGET_MARKETS)} hot markets ===', flush=True)

market_wallets = {}  # slug -> {wallet: {cost, outcome, type}}

for slug in TARGET_MARKETS:
    print(f'\n  Fetching {slug}...', flush=True)
    trades = fetch_market_all(slug)
    today_trades = [t for t in trades if t.get('timestamp', '').startswith(TODAY)]
    print(f'    {len(today_trades)} trades today', flush=True)

    by_wallet = defaultdict(lambda: {'cost': 0.0, 'shares': 0.0, 'outcome': '', 'first': ''})
    for t in today_trades:
        w   = t.get('proxy_wallet') or t.get('wallet') or '?'
        px  = float(t.get('price', 0))
        sz  = float(t.get('size', 0))
        out = t.get('outcome', '?')
        ts  = t.get('timestamp', '')[:16]
        by_wallet[w]['cost']    += px * sz
        by_wallet[w]['shares']  += sz
        by_wallet[w]['outcome']  = out
        if not by_wallet[w]['first'] or ts < by_wallet[w]['first']:
            by_wallet[w]['first'] = ts

    market_wallets[slug] = dict(by_wallet)
    print(f'    {len(by_wallet)} unique wallets', flush=True)
    time.sleep(0.2)

# Step 3: Find non-cluster wallets in 2+ of the same markets
print('\n=== STEP 3: Non-cluster wallets in 2+ markets ===', flush=True)

non_cluster_markets = defaultdict(list)  # wallet -> [slugs]
for slug, wmap in market_wallets.items():
    for w in wmap:
        if w not in CLUSTER:
            non_cluster_markets[w].append(slug)

# Sort by how many hot markets they appear in
candidates = [(w, slugs) for w, slugs in non_cluster_markets.items() if len(slugs) >= 2]
candidates.sort(key=lambda x: -len(x[1]))

print(f'\nFound {len(candidates)} non-cluster wallets in 2+ markets:', flush=True)
print(f'\n{"WALLET":<46} {"MKTS":>4}  MARKETS + SPEND', flush=True)
print('-' * 110, flush=True)

output_rows = []
for w, slugs in candidates[:50]:
    total_spend = sum(market_wallets[s].get(w, {}).get('cost', 0) for s in slugs)
    market_detail = []
    for s in sorted(slugs):
        d = market_wallets[s].get(w, {})
        cluster_count = len(cluster_market_activity.get(s, []))
        market_detail.append(f'{s}(${d.get("cost",0):,.0f},c={cluster_count})')
    print(f'  {w}  [{len(slugs)}]  ${total_spend:>8,.0f}  {" | ".join(market_detail)}', flush=True)
    output_rows.append({
        'wallet': w,
        'markets_count': len(slugs),
        'total_spend': total_spend,
        'markets': {s: {'cost': market_wallets[s].get(w, {}).get('cost', 0),
                        'outcome': market_wallets[s].get(w, {}).get('outcome', ''),
                        'first': market_wallets[s].get(w, {}).get('first', ''),
                        'cluster_wallets_in_market': len(cluster_market_activity.get(s, []))}
                    for s in slugs}
    })

# Step 4: Among top candidates, find wallets in 3+ markets (strongest signal)
in3plus = [(w, s) for w, s in candidates if len(s) >= 3]
print(f'\n=== STEP 4: Wallets in 3+ markets ({len(in3plus)}) — STRONGEST CANDIDATES ===', flush=True)
for w, slugs in in3plus[:20]:
    total_spend = sum(market_wallets[s].get(w, {}).get('cost', 0) for s in slugs)
    print(f'  {w}  [{len(slugs)} markets]  ${total_spend:,.0f}', flush=True)
    for s in sorted(slugs):
        d = market_wallets[s].get(w, {})
        print(f'    {s}  ${d.get("cost",0):,.0f}  {d.get("outcome","?")}  {d.get("first","")}', flush=True)

# Save results
import os
os.makedirs('market_sessions', exist_ok=True)
json.dump({
    'date': TODAY,
    'cluster_markets': {s: labels for s, labels in cluster_market_activity.items()},
    'expansion_candidates': output_rows,
    'in_3plus_markets': [{'wallet': w, 'markets': s} for w, s in in3plus],
}, open(f'market_sessions/expansion_{TODAY}.json', 'w'), indent=2)
print(f'\nSaved: market_sessions/expansion_{TODAY}.json', flush=True)
