from dotenv import load_dotenv
import os
load_dotenv()

import requests, json, time
from collections import defaultdict

API_URL = 'https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized'
TOKEN = os.environ['HEISENBERG_TOKEN']
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

def post(agent_id, params, limit=200, offset=0):
    r = requests.post(API_URL, json={
        'agent_id': agent_id, 'params': params,
        'pagination': {'limit': limit, 'offset': offset},
        'formatter_config': {'format_type': 'raw'},
    }, headers=headers, timeout=20)
    return r.json()

def fetch_all(slug):
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

def build_winner_map(trades, winner_key, live_cutoff='2026-06-08T09:00'):
    winner_trades = [t for t in trades if winner_key in t.get('outcome', '')]
    sorted_w = sorted(winner_trades, key=lambda x: x.get('timestamp', ''))
    current_px = float(sorted_w[-1].get('price', 0)) if sorted_w else 0.99

    # detect live start
    prev, live_start = 0, live_cutoff
    for t in sorted_w:
        px = float(t.get('price', 0))
        if px >= 0.800 and prev < 0.800:
            live_start = t.get('timestamp', '')[:16]
            break
        prev = px

    wallets = defaultdict(lambda: {'cost': 0.0, 'shares': 0.0, 'trades': 0, 'first': '', 'type': 'PRE'})
    for t in winner_trades:
        ts = t.get('timestamp', '')[:16]
        px = float(t.get('price', 0))
        sz = float(t.get('size', 0))
        w = t.get('proxy_wallet') or t.get('wallet') or '?'
        wallets[w]['cost'] += px * sz
        wallets[w]['shares'] += sz
        wallets[w]['trades'] += 1
        if not wallets[w]['first'] or ts < wallets[w]['first']:
            wallets[w]['first'] = ts
        if ts >= live_start:
            wallets[w]['type'] = 'LIVE'

    result = {}
    for w, d in wallets.items():
        if d['shares'] == 0:
            continue
        avg = d['cost'] / d['shares']
        unreal = d['shares'] * current_px - d['cost']
        result[w] = {'cost': d['cost'], 'unreal': unreal, 'avg': avg,
                     'type': d['type'], 'first': d['first'], 'current_px': current_px}
    print(f'  {winner_key}: {len(winner_trades)} trades, {len(result)} bettors, current_px={current_px:.3f}, live_start={live_start}')
    return result

# Fetch Fokina market (Bellucci won)
print('Fetching ATP Fokina/Bellucci market...')
fokina_trades = fetch_all('atp-fokina-bellucc-2026-06-08')
outcomes = set(t.get('outcome', '') for t in fokina_trades)
print(f'  Outcomes: {outcomes}')
bellucci_map = build_winner_map(fokina_trades, 'Bellucc', '2026-06-08T09:00')

# Load saved Udvardy data
udvardy_raw = json.load(open('market_sessions/wta-alexand-udvardy-2026-06-08.json'))
udvardy_map = udvardy_raw['all_wallets']

# Load saved Mertens — use full wallet map if it exists, else top10
import os
mertens_raw = json.load(open('market_sessions/mertens_2026-06-08.json'))
# Re-fetch mertens full wallet set
print('Fetching Mertens market for full wallet set...')
mertens_trades = fetch_all('wta-andrees-mertens-2026-06-08')
mertens_map = build_winner_map(mertens_trades, 'Mertens', '2026-06-08T11:09')

bellucci_set = set(bellucci_map.keys())
udvardy_set  = set(udvardy_map.keys())
mertens_set  = set(mertens_map.keys())

print(f'\nMertens bettors:  {len(mertens_set)}')
print(f'Bellucci bettors: {len(bellucci_set)}')
print(f'Udvardy bettors:  {len(udvardy_set)}')

# ALL 3 WINNERS
all3 = mertens_set & bellucci_set & udvardy_set
print(f'\n{"="*80}')
print(f'  WALLETS WHO BET ON ALL 3 WINNERS: {len(all3)}')
print(f'{"="*80}')

def fmt(d):
    return f'entry={d.get("avg",0):.3f}  cost=${d.get("cost",0):,.0f}  pnl={d.get("unreal",0):+,.0f}  [{d.get("type","?")}]  {d.get("first","")[:16]}'

rows = []
for w in all3:
    m = mertens_map.get(w, {})
    b = bellucci_map.get(w, {})
    u = udvardy_map.get(w, {})
    total = m.get('unreal', 0) + b.get('unreal', 0) + u.get('unreal', 0)
    rows.append((w, total, m, b, u))

rows.sort(key=lambda x: -x[1])
for w, total, m, b, u in rows:
    print(f'\n  {w}')
    print(f'  Mertens:  {fmt(m)}')
    print(f'  Bellucci: {fmt(b)}')
    print(f'  Udvardy:  {fmt(u)}')
    print(f'  NET PnL across all 3: {total:+,.0f}')

# Save
json.dump({'all3': [{'wallet': w, 'net_pnl': total,
                     'mertens': m, 'bellucci': b, 'udvardy': u}
                    for w, total, m, b, u in rows]},
          open('market_sessions/winners_all3.json', 'w'), indent=2)

# 2-of-3 combos
mb = (mertens_set & bellucci_set) - udvardy_set
mu = (mertens_set & udvardy_set) - bellucci_set
bu = (bellucci_set & udvardy_set) - mertens_set

def combo_pnl(w, maps):
    return sum(maps[i].get(w, {}).get('unreal', 0) for i in range(len(maps)))

print(f'\n{"="*80}')
print(f'  MERTENS + BELLUCCI (not Udvardy): {len(mb)}')
print(f'{"="*80}')
for w in sorted(mb, key=lambda x: -(mertens_map.get(x,{}).get('unreal',0)+bellucci_map.get(x,{}).get('unreal',0)))[:10]:
    m = mertens_map.get(w,{}); b = bellucci_map.get(w,{})
    print(f'  {w}  Mertens pnl={m.get("unreal",0):+,.0f} [{m.get("type","?")}]  Bellucci pnl={b.get("unreal",0):+,.0f} [{b.get("type","?")}]  NET={m.get("unreal",0)+b.get("unreal",0):+,.0f}')

print(f'\n{"="*80}')
print(f'  MERTENS + UDVARDY (not Bellucci): {len(mu)}')
print(f'{"="*80}')
for w in sorted(mu, key=lambda x: -(mertens_map.get(x,{}).get('unreal',0)+udvardy_map.get(x,{}).get('unreal',0)))[:10]:
    m = mertens_map.get(w,{}); u = udvardy_map.get(w,{})
    print(f'  {w}  Mertens pnl={m.get("unreal",0):+,.0f} [{m.get("type","?")}]  Udvardy pnl={u.get("unreal",0):+,.0f} [{u.get("type","?")}]  NET={m.get("unreal",0)+u.get("unreal",0):+,.0f}')

print(f'\n{"="*80}')
print(f'  BELLUCCI + UDVARDY (not Mertens): {len(bu)}')
print(f'{"="*80}')
bu_rows = [(w, bellucci_map.get(w,{}).get('unreal',0)+udvardy_map.get(w,{}).get('unreal',0)) for w in bu]
for w, pnl in sorted(bu_rows, key=lambda x: -x[1])[:10]:
    b = bellucci_map.get(w,{}); u = udvardy_map.get(w,{})
    print(f'  {w}  Bellucci pnl={b.get("unreal",0):+,.0f} [{b.get("type","?")}]  Udvardy pnl={u.get("unreal",0):+,.0f} [{u.get("type","?")}]  NET={pnl:+,.0f}')
