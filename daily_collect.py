"""
Daily collection + analysis — runs automatically via launchd every morning.

What it does:
  1. Fetches all trades for 28 cluster wallets for today
  2. Shows per-wallet activity: markets, outcomes, timing, spend
  3. Builds consensus view: markets with 2+ wallets, who fired when
  4. Identifies early movers (fired >1h before cluster window)
  5. Saves market_sessions/today_expanded_YYYY-MM-DD.json  (raw data)
  6. Saves sessions/YYYY-MM-DD-daily.md                    (readable log)
  7. Sends Telegram briefing with top consensus picks

Run manually:
    python daily_collect.py              # uses today's UTC date
    python daily_collect.py 2026-06-13   # specific date
"""

import sys, json, os, requests, time
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

import tg

API_URL = 'https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized'
TOKEN   = os.environ['HEISENBERG_TOKEN']
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

EXPANSION = {
    '0x4b493d8ea89203ecfa5ac53ff8fc4a45aa050397': 'Exp#1',
    '0xdd5ef115f801999575b03d78d0115ad8b2d59040': 'Exp#2',
    '0x84ad9c5c547a82ec9a08547b94bd922446e5bfb7': 'Exp#3',
    '0xa42f127d7e8df9f16881ffcc9ed0bc0326875f5a': 'Exp#4',
    '0x98db8cca55c32b24cfb414b5b43d273f4e1fdd17': 'Exp#5',
    '0x0d2d845a6ff64e31e04a70afce8a573940767ff5': 'Exp#6',
    '0xdb83e85ffd22faa4009273034770f96ffc5b1e50': 'Exp#7',
    '0x5b6331e7ff0831a3fe2ed12004747db1a9c911a4': 'Exp#8',
    '0x1e3bb7def89b002d45fd86d37f35918c2618e232': 'Exp#9',
    '0xf7f0b0b1e9c0fe02ccad926916ee31aef74b912c': 'Exp#10',
    '0xeea3f08e8a36081233e4c4b4142fd61a7b56a6a2': 'Exp#11',
    '0x908aad3bfbd70410e73f1db6a3e46c2a917cad16': 'Exp#12',
    '0x0adedcb79423aed988a849827ff80b8cc7b3ed94': 'Exp#13',
    '0x076daa87c4fe1a85402a9b6b8e0a866224388d4c': 'Exp#14',
}

ALL_WALLETS = {**CLUSTER, **EXPANSION}

# ── Fetch ────────────────────────────────────────────────────────────────────────

def fetch_trades(wallet):
    try:
        r = requests.post(API_URL, json={
            'agent_id': 556,
            'params': {
                'proxy_wallet': wallet,
                'condition_id': 'ALL',
                'market_slug':  'ALL',
                'side':         'ALL',
            },
            'pagination': {'limit': 200, 'offset': 0},
            'formatter_config': {'format_type': 'raw'},
        }, headers=headers, timeout=20)
        return r.json().get('data', {}).get('results', [])
    except Exception as e:
        print(f'  fetch error {wallet[:10]}: {e}')
        return []

def is_tennis(slug):
    return 'atp' in slug or 'wta' in slug or 'tennis' in slug

def match_name(slug):
    parts = slug.split('-')
    if len(parts) >= 3:
        return f"{parts[1].title()} vs {parts[2].title()}"
    return slug

# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    print(f'\n{"="*80}', flush=True)
    print(f'  FALCON DAILY COLLECTION — {TODAY}', flush=True)
    print(f'  {len(ALL_WALLETS)} wallets ({len(CLUSTER)} cluster + {len(EXPANSION)} expansion)', flush=True)
    print(f'{"="*80}\n', flush=True)

    market_activity = defaultdict(list)   # slug -> [{wallet, label, group, outcome, cost, price, time}]
    wallet_picks    = {}
    session_lines   = [f'# Falcon Daily Session — {TODAY}\n']

    for wallet, label in ALL_WALLETS.items():
        group  = 'CLUSTER' if wallet in CLUSTER else 'EXPAND'
        trades = fetch_trades(wallet)
        today_tennis = [
            t for t in trades
            if t.get('timestamp', '').startswith(TODAY)
            and is_tennis(t.get('slug', ''))
        ]

        if not today_tennis:
            print(f'  [{group}] {label:<22} -- quiet', flush=True)
            wallet_picks[wallet] = {'label': label, 'group': group, 'markets': {}}
            time.sleep(0.1)
            continue

        # Aggregate by (slug, outcome)
        by_market = defaultdict(lambda: {'cost': 0.0, 'shares': 0.0, 'outcome': '', 'prices': [], 'times': []})
        for t in today_tennis:
            slug    = t.get('slug', '')
            out     = t.get('outcome', '?')
            px      = float(t.get('price', 0))
            sz      = float(t.get('size', 0))
            ts      = t.get('timestamp', '')[:16]
            key     = (slug, out)
            by_market[key]['cost']    += px * sz
            by_market[key]['shares']  += sz
            by_market[key]['outcome']  = out
            by_market[key]['prices'].append(px)
            by_market[key]['times'].append(ts)
            market_activity[slug].append({
                'wallet': wallet, 'label': label, 'group': group,
                'outcome': out, 'cost': px * sz, 'price': px, 'time': ts,
            })

        total_spend = sum(v['cost'] for v in by_market.values())
        print(f'  [{group}] {label:<22}  {len(set(k[0] for k in by_market))} markets  ${total_spend:,.0f}', flush=True)

        session_lines.append(f'\n## {label} ({group}) — ${total_spend:,.0f}\n')
        for (slug, out), d in sorted(by_market.items(), key=lambda x: -x[1]['cost']):
            avg_px = sum(d['prices']) / len(d['prices'])
            first  = min(d['times'])
            print(f'           {first}  {slug[:42]:<42}  {out[:20]:<20}  ${d["cost"]:>7,.0f}  px={avg_px:.3f}', flush=True)
            session_lines.append(f'- `{first}` **{match_name(slug)}** → {out.upper()} @ {avg_px:.3f} | ${d["cost"]:,.0f}\n')

        wallet_picks[wallet] = {
            'label': label, 'group': group,
            'markets': {str(k): v for k, v in by_market.items()}
        }
        time.sleep(0.15)

    # ── Consensus ─────────────────────────────────────────────────────────────────
    print(f'\n{"="*80}', flush=True)
    print(f'  CONSENSUS — MARKETS WITH 2+ WALLETS', flush=True)
    print(f'{"="*80}', flush=True)

    session_lines.append(f'\n---\n\n## Consensus Picks (2+ wallets)\n')

    hot = {s: a for s, a in market_activity.items() if len(a) >= 2}
    consensus_for_tg = []

    for slug in sorted(hot, key=lambda s: -len(hot[s])):
        acts          = hot[slug]
        total         = sum(a['cost'] for a in acts)
        cluster_count = sum(1 for a in acts if a['group'] == 'CLUSTER')
        expand_count  = sum(1 for a in acts if a['group'] == 'EXPAND')
        by_out        = defaultdict(list)
        for a in acts:
            by_out[a['outcome']].append(a)

        print(f'\n  {slug}', flush=True)
        print(f'  {len(acts)} wallets (cluster={cluster_count}, expand={expand_count})  ${total:,.0f}', flush=True)
        session_lines.append(f'\n### {match_name(slug)} (`{slug}`)\n')
        session_lines.append(f'_{len(acts)} wallets — cluster={cluster_count} expand={expand_count} — ${total:,.0f}_\n\n')

        top_out = None
        top_out_total = 0
        for out, wlist in sorted(by_out.items(), key=lambda x: -sum(w['cost'] for w in x[1])):
            out_total   = sum(w['cost'] for w in wlist)
            wallets_str = ', '.join(
                f'{w["label"]}@{w["price"]:.3f}'
                for w in sorted(wlist, key=lambda x: x['time'])
            )
            first_entry = min(w['time'] for w in wlist)
            print(f'    {out[:28]:<28}  ${out_total:>8,.0f}  [{wallets_str}]', flush=True)
            session_lines.append(f'| {out.upper()} | ${out_total:,.0f} | {wallets_str} |\n')

            if out_total > top_out_total:
                top_out       = out
                top_out_total = out_total
                top_first     = first_entry

        if top_out and cluster_count >= 2:
            consensus_for_tg.append({
                'slug': slug, 'outcome': top_out,
                'total': top_out_total, 'wallets': len(acts),
                'first': top_first,
            })

    # ── Early movers ─────────────────────────────────────────────────────────────
    print(f'\n{"="*80}', flush=True)
    print(f'  EARLY MOVERS (fired before 08:00 UTC)', flush=True)
    print(f'{"="*80}', flush=True)

    session_lines.append(f'\n---\n\n## Early Movers (before 08:00 UTC)\n\n')
    early_cutoff = f'{TODAY}T08:00'
    early_found  = False

    for slug, acts in market_activity.items():
        early = [a for a in acts if a['time'] < early_cutoff]
        if early:
            early_found = True
            for a in sorted(early, key=lambda x: x['time']):
                line = f'  {a["time"]}  {a["label"]:<22}  {match_name(slug):<35}  {a["outcome"].upper():<20}  ${a["cost"]:,.0f}'
                print(line, flush=True)
                session_lines.append(f'- `{a["time"]}` **{a["label"]}** — {match_name(slug)} → {a["outcome"].upper()} @ {a["price"]:.3f} | ${a["cost"]:,.0f}\n')

    if not early_found:
        print('  None.', flush=True)
        session_lines.append('_None._\n')

    # ── Save raw JSON (same format as today_expanded_*.json) ─────────────────────
    os.makedirs('market_sessions', exist_ok=True)
    json_path = f'market_sessions/today_expanded_{TODAY}.json'
    with open(json_path, 'w') as f:
        json.dump({
            'date': TODAY,
            'market_activity': {s: acts for s, acts in market_activity.items()},
            'wallet_picks': wallet_picks,
        }, f, indent=2)
    print(f'\nSaved: {json_path}', flush=True)

    # ── Save readable session log ─────────────────────────────────────────────────
    os.makedirs('sessions', exist_ok=True)
    md_path = f'sessions/{TODAY}-daily.md'
    with open(md_path, 'w') as f:
        f.writelines(session_lines)
    print(f'Saved: {md_path}', flush=True)

    # ── Telegram summary ──────────────────────────────────────────────────────────
    active = sum(1 for v in wallet_picks.values() if v['markets'])
    lines  = [f'*Falcon Daily — {TODAY}*', f'{active}/{len(ALL_WALLETS)} wallets active\n']

    if consensus_for_tg:
        lines.append('*Consensus Picks:*')
        for c in sorted(consensus_for_tg, key=lambda x: -x['total'])[:8]:
            lines.append(
                f'• {match_name(c["slug"])} → *{c["outcome"].upper()}* '
                f'| ${c["total"]:,.0f} | {c["wallets"]} wallets | first: {c["first"][11:16]}'
            )
    else:
        lines.append('_No consensus picks yet._')

    tg.send('\n'.join(lines))
    print('\nTelegram briefing sent.', flush=True)

if __name__ == '__main__':
    main()
