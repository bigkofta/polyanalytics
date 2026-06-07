import sys, time
sys.path.insert(0, '/Users/steve/falcon')
import requests
from falcon_api import API_URL, TOKEN
from collections import defaultdict

COND = '0x17e2f3347e34d8a13572baf10c9b4eb3291217868a0fb84b37f36c80f8e2105a'
WINNER = 'Knicks'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

def fetch_page(offset, limit=200, retries=5):
    payload = {
        "agent_id": 556,
        "params": {"wallet_proxy": "ALL", "condition_id": COND, "market_slug": "ALL", "side": "ALL"},
        "pagination": {"limit": limit, "offset": offset},
        "formatter_config": {"format_type": "raw"}
    }
    for attempt in range(retries):
        try:
            r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            wait = 2 ** attempt
            print(f"  Retry {attempt+1}/{retries} at offset {offset}: {e} — waiting {wait}s", flush=True)
            time.sleep(wait)
    return None

print("Fetching trades...", flush=True)
all_trades = []
offset = 0
while True:
    data = fetch_page(offset)
    if data is None:
        print(f"Failed at offset {offset}, stopping", flush=True)
        break
    batch = data.get('data', {}).get('results', [])
    all_trades.extend(batch)
    has_more = data.get('pagination', {}).get('has_more', False)
    if offset % 5000 == 0:
        print(f"  {len(all_trades)} trades fetched...", flush=True)
    if not has_more or len(batch) < 200:
        break
    offset += 200

print(f"Total: {len(all_trades)} trades\n", flush=True)

wallets = defaultdict(lambda: {'knicks': 0.0, 'spurs': 0.0, 'cash': 0.0, 'trades': 0})
for t in all_trades:
    w = t['proxy_wallet']
    o = t['outcome']
    s = t['side']
    p = float(t['price'])
    sz = float(t['size'])
    wallets[w]['trades'] += 1
    if s == 'BUY':
        wallets[w]['cash'] -= p * sz
        wallets[w]['knicks' if o == WINNER else 'spurs'] += sz
    else:
        wallets[w]['cash'] += p * sz
        wallets[w]['knicks' if o == WINNER else 'spurs'] -= sz

results = []
for w, d in wallets.items():
    payout = max(0.0, d['knicks'])
    profit = payout + d['cash']
    results.append({'wallet': w, 'profit': profit, 'knicks': d['knicks'],
                    'spurs': d['spurs'], 'trades': d['trades']})

results.sort(key=lambda x: x['profit'], reverse=True)

print(f"{'#':<3} {'Profit':>11} {'Knicks Shs':>11} {'Spurs Shs':>10} {'Trades':>7}  Wallet")
print('-' * 85)
for i, r in enumerate(results[:15], 1):
    print(f"{i:<3} ${r['profit']:>10,.0f}  {r['knicks']:>10,.1f}  {r['spurs']:>9,.1f}  {r['trades']:>6}  {r['wallet']}")

print(f"\nTotal wallets: {len(results)}")
print(f"Profitable:    {sum(1 for x in results if x['profit'] > 0)}")
print(f"Losing:        {sum(1 for x in results if x['profit'] < 0)}")
