from dotenv import load_dotenv
import os
load_dotenv()

import requests, json, time, os
from collections import defaultdict

API_URL = 'https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized'
TOKEN = os.environ['HEISENBERG_TOKEN']
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

os.makedirs('market_sessions', exist_ok=True)

def post(agent_id, params, limit=200, offset=0):
    r = requests.post(API_URL, json={
        'agent_id': agent_id, 'params': params,
        'pagination': {'limit': limit, 'offset': offset},
        'formatter_config': {'format_type': 'raw'},
    }, headers=headers, timeout=20)
    return r.json()

def fetch_all_trades(slug):
    all_trades, offset = [], 0
    while True:
        r = post(556, {'proxy_wallet': 'ALL', 'condition_id': 'ALL',
                       'market_slug': slug, 'side': 'ALL'}, limit=200, offset=offset)
        batch = r.get('data', {}).get('results', [])
        all_trades.extend(batch)
        if not r.get('pagination', {}).get('has_more') or len(batch) < 200:
            break
        offset += 200
        time.sleep(0.1)
    return all_trades

def find_live_start(winner_trades):
    sorted_t = sorted(winner_trades, key=lambda x: x.get('timestamp', ''))
    prev = 0
    for t in sorted_t:
        px = float(t.get('price', 0))
        if px >= 0.800 and prev < 0.800:
            return t.get('timestamp', '')[:16]
        prev = px
    return '2026-06-08T09:00'

def analyse_market(slug, winner_key, label):
    print(f'\nFetching {slug}...')
    trades = fetch_all_trades(slug)
    print(f'  {len(trades)} trades total')

    winner_trades = [t for t in trades if winner_key in t.get('outcome', '')]
    live_start = find_live_start(winner_trades)

    sorted_w = sorted(winner_trades, key=lambda x: x.get('timestamp', ''))
    current_px = float(sorted_w[-1].get('price', 0)) if sorted_w else 0.73
    print(f'  Winner: {winner_key}  Live start: {live_start}  Current px: {current_px:.3f}')

    wallets = defaultdict(lambda: {'cost': 0.0, 'shares': 0.0, 'trades': 0, 'first': '', 'type': 'PRE'})
    for t in trades:
        ts = t.get('timestamp', '')[:16]
        px = float(t.get('price', 0))
        sz = float(t.get('size', 0))
        out = t.get('outcome', '?')
        w = t.get('proxy_wallet') or t.get('wallet') or '?'
        if winner_key not in out:
            continue
        wallets[w]['cost'] += px * sz
        wallets[w]['shares'] += sz
        wallets[w]['trades'] += 1
        if not wallets[w]['first'] or ts < wallets[w]['first']:
            wallets[w]['first'] = ts
        if ts >= live_start:
            wallets[w]['type'] = 'LIVE'

    rows = []
    for w, d in wallets.items():
        if d['shares'] == 0:
            continue
        avg = d['cost'] / d['shares']
        unreal = d['shares'] * current_px - d['cost']
        rows.append({'wallet': w, 'cost': d['cost'], 'shares': d['shares'], 'avg': avg,
                     'unreal': unreal, 'trades': d['trades'], 'first': d['first'], 'type': d['type']})
    rows.sort(key=lambda x: -x['unreal'])

    print(f'\n  TOP 10 {label} (px={current_px:.3f})')
    print(f'  {"#":<3} {"TYPE":<5} {"WALLET":<44} {"ENTRY":<6} {"COST":>8} {"UNREAL PnL":>11} {"FIRST BUY"}')
    for i, r in enumerate(rows[:10], 1):
        print(f'  {i:<3} {r["type"]:<5} {r["wallet"]:<44} {r["avg"]:.3f}  {r["cost"]:>8,.0f} {r["unreal"]:>+11,.0f}  {r["first"]}')

    # Save
    out_data = {
        'slug': slug, 'winner': winner_key, 'live_start': live_start,
        'current_px': current_px, 'total_trades': len(trades),
        'top10': rows[:10],
        'all_wallets': {w: {'cost': d['cost'], 'unreal': d['shares']*current_px - d['cost'],
                            'type': d['type'], 'first': d['first']}
                        for w, d in wallets.items() if d['shares'] > 0}
    }
    fname = f'market_sessions/{slug}.json'
    json.dump(out_data, open(fname, 'w'), indent=2)
    print(f'  Saved: {fname}')

    return out_data

# --- Run both new markets ---
fokina_data  = analyse_market('atp-fokina-bellucc-2026-06-08', 'Fokina',  'ATP Fokina vs Bellucci')
udvardy_data = analyse_market('wta-alexand-udvardy-2026-06-08', 'Udvardy', 'WTA Alexandrova vs Udvardy')

# --- Load Mertens full profitable set ---
mertens_raw = json.load(open('market_sessions/mertens_2026-06-08.json'))
mertens_set = {e['wallet'] for e in mertens_raw['top10']}
# Also load if full wallet data exists
mertens_full_path = 'market_sessions/wta-andrees-mertens-2026-06-08.json'
if os.path.exists(mertens_full_path):
    mertens_full = json.load(open(mertens_full_path))
    mertens_all = set(mertens_full.get('all_wallets', {}).keys())
else:
    mertens_all = mertens_set

fokina_all  = set(fokina_data['all_wallets'].keys())
udvardy_all = set(udvardy_data['all_wallets'].keys())

MARKETS = {
    'Mertens':  mertens_all,
    'Fokina':   fokina_all,
    'Udvardy':  udvardy_all,
}

print('\n' + '='*90)
print('  CROSS-MARKET WALLET CORRELATION')
print('='*90)
print(f'  Mertens wallets:  {len(mertens_all)}')
print(f'  Fokina wallets:   {len(fokina_all)}')
print(f'  Udvardy wallets:  {len(udvardy_all)}')

# All wallets with market membership
all_wallets = mertens_all | fokina_all | udvardy_all

wallet_markets = {}
for w in all_wallets:
    markets_in = []
    if w in mertens_all:  markets_in.append('Mertens')
    if w in fokina_all:   markets_in.append('Fokina')
    if w in udvardy_all:  markets_in.append('Udvardy')
    wallet_markets[w] = markets_in

in_all3   = [w for w, m in wallet_markets.items() if len(m) == 3]
in_any2   = [w for w, m in wallet_markets.items() if len(m) == 2]
in_mf     = [w for w, m in wallet_markets.items() if set(m) == {'Mertens','Fokina'}]
in_mu     = [w for w, m in wallet_markets.items() if set(m) == {'Mertens','Udvardy'}]
in_fu     = [w for w, m in wallet_markets.items() if set(m) == {'Fokina','Udvardy'}]

def wallet_summary(w):
    parts = []
    fd = fokina_data['all_wallets'].get(w)
    ud = udvardy_data['all_wallets'].get(w)
    if w in mertens_all:
        # get from top10 if possible
        mt = next((e for e in mertens_raw['top10'] if e['wallet']==w), None)
        pnl = mt['unreal_pnl'] if mt else '?'
        parts.append(f'Mertens pnl={pnl:+,.0f}' if isinstance(pnl, (int,float)) else 'Mertens pnl=?')
    if fd:
        parts.append(f'Fokina ${fd["cost"]:,.0f} pnl={fd["unreal"]:+,.0f} [{fd["type"]}]')
    if ud:
        parts.append(f'Udvardy ${ud["cost"]:,.0f} pnl={ud["unreal"]:+,.0f} [{ud["type"]}]')
    return '  |  '.join(parts)

def total_pnl(w):
    total = 0
    mt = next((e for e in mertens_raw['top10'] if e['wallet']==w), None)
    if mt: total += mt['unreal_pnl']
    fd = fokina_data['all_wallets'].get(w)
    if fd: total += fd['unreal']
    ud = udvardy_data['all_wallets'].get(w)
    if ud: total += ud['unreal']
    return total

print(f'\n--- IN ALL 3 MARKETS ({len(in_all3)}) ---')
for w in sorted(in_all3, key=lambda x: -total_pnl(x)):
    print(f'  {w}')
    print(f'    {wallet_summary(w)}')
    print(f'    TOTAL PnL across all 3: {total_pnl(w):+,.0f}')

print(f'\n--- MERTENS + FOKINA ({len(in_mf)}) ---')
for w in sorted(in_mf, key=lambda x: -total_pnl(x)):
    print(f'  {w}  |  {wallet_summary(w)}')

print(f'\n--- MERTENS + UDVARDY ({len(in_mu)}) ---')
for w in sorted(in_mu, key=lambda x: -total_pnl(x)):
    print(f'  {w}  |  {wallet_summary(w)}')

print(f'\n--- FOKINA + UDVARDY only (not Mertens top10) ({len(in_fu)}) ---')
fu_sorted = sorted(in_fu, key=lambda x: -(
    fokina_data['all_wallets'].get(x,{}).get('cost',0) +
    udvardy_data['all_wallets'].get(x,{}).get('cost',0)
))
for w in fu_sorted[:20]:
    fd = fokina_data['all_wallets'].get(w,{})
    ud = udvardy_data['all_wallets'].get(w,{})
    total = fd.get('cost',0)+ud.get('cost',0)
    pnl = fd.get('unreal',0)+ud.get('unreal',0)
    print(f'  {w}  spend=${total:,.0f}  pnl={pnl:+,.0f}  F:[{fd.get("type","?")}] U:[{ud.get("type","?")}]')

# Save correlation results
corr = {
    'in_all3': in_all3,
    'mertens_fokina': in_mf,
    'mertens_udvardy': in_mu,
    'fokina_udvardy': in_fu,
}
json.dump(corr, open('market_sessions/correlation_2026-06-08.json', 'w'), indent=2)
print('\nCorrelation saved to market_sessions/correlation_2026-06-08.json')
