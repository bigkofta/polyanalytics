"""
Falcon Daily Intelligence Brief

Runs every day. Answers:
  - What sharp moves happened today?
  - Which matches had real money on them?
  - Who entered at what price and time — and who got out vs held?
  - What strategy patterns played out? (dip buyer / early mover / conviction / quick flip)
  - Cluster vs expansion — did they agree or diverge?

Saves to:
  sessions/YYYY-MM-DD-brief.md   — readable log, builds over time
  falcon.db                      — SQLite, queryable, cumulative

Run:
  python daily_brief.py              # today
  python daily_brief.py 2026-06-13   # specific date
"""

import sys, json, os, requests, time
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

import tg
from db import DB

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

# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_all_trades(wallet):
    """Fetch both buys and sells for today."""
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
    return 'atp' in slug.lower() or 'wta' in slug.lower() or 'tennis' in slug.lower()

def match_name(slug):
    parts = slug.split('-')
    if len(parts) >= 3:
        return f"{parts[1].title()} vs {parts[2].title()}"
    return slug

# ── Strategy classifier ───────────────────────────────────────────────────────

def classify(entry_time, entry_price, sold_same_day):
    """
    EARLY_MOVER  — entered before 08:00 UTC (2+ hrs before cluster window)
    DIP_BUYER    — entry price < 0.55 (bought when market was against them)
    QUICK_FLIP   — bought and sold same day
    CONVICTION   — still holding at end of day
    LATE_ENTRY   — entered at price >= 0.85 (match already live/decided)
    """
    hour = int(entry_time[11:13]) if len(entry_time) > 12 else 12

    if sold_same_day:
        return 'QUICK_FLIP'
    if hour < 8:
        return 'EARLY_MOVER'
    if entry_price < 0.55:
        return 'DIP_BUYER'
    if entry_price >= 0.85:
        return 'LATE_ENTRY'
    return 'CONVICTION'

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db = DB()
    print(f'\n{"="*80}')
    print(f'  FALCON DAILY BRIEF — {TODAY}')
    print(f'{"="*80}\n')

    # wallet -> match -> {buys: [...], sells: [...]}
    wallet_activity = {}

    for wallet, label in ALL_WALLETS.items():
        group  = 'CLUSTER' if wallet in CLUSTER else 'EXPAND'
        trades = fetch_all_trades(wallet)
        today  = [t for t in trades if t.get('timestamp','').startswith(TODAY) and is_tennis(t.get('slug',''))]

        if not today:
            print(f'  [{group}] {label:<22} — quiet')
            time.sleep(0.1)
            continue

        by_market = defaultdict(lambda: {'buys': [], 'sells': []})
        for t in today:
            slug = t.get('slug','')
            side = t.get('side','').upper()
            px   = float(t.get('price', 0))
            sz   = float(t.get('size', 0))
            out  = t.get('outcome','?')
            ts   = t.get('timestamp','')[:16]
            record = {'outcome': out, 'price': px, 'size': sz, 'cost': px*sz, 'time': ts}
            if side == 'SELL':
                by_market[slug]['sells'].append(record)
            else:
                by_market[slug]['buys'].append(record)

        wallet_activity[wallet] = {'label': label, 'group': group, 'markets': dict(by_market)}

        total_bought = sum(
            b['cost'] for m in by_market.values() for b in m['buys']
        )
        print(f'  [{group}] {label:<22} — {len(by_market)} match(es)  ${total_bought:,.0f} bought')
        time.sleep(0.12)

    # ── Per-match analysis ────────────────────────────────────────────────────
    # Aggregate across all wallets per match
    match_data = defaultdict(lambda: {
        'entries': [],   # {wallet, label, group, outcome, price, time, cost}
        'exits':   [],   # {wallet, label, group, outcome, price, time}
    })

    for wallet, data in wallet_activity.items():
        label = data['label']
        group = data['group']
        for slug, trades in data['markets'].items():
            for b in trades['buys']:
                match_data[slug]['entries'].append({
                    'wallet': wallet, 'label': label, 'group': group,
                    'outcome': b['outcome'], 'price': b['price'],
                    'time': b['time'], 'cost': b['cost'],
                })
            for s in trades['sells']:
                match_data[slug]['exits'].append({
                    'wallet': wallet, 'label': label, 'group': group,
                    'outcome': s['outcome'], 'price': s['price'],
                    'time': s['time'],
                })

    # ── Build brief ───────────────────────────────────────────────────────────
    lines    = []
    tg_lines = [f'*Falcon Brief — {TODAY}*\n']

    # Sort matches by total cluster spend
    def cluster_spend(slug):
        return sum(e['cost'] for e in match_data[slug]['entries'] if e['group'] == 'CLUSTER')

    hot_matches = sorted(
        [s for s, d in match_data.items() if len(d['entries']) >= 1],
        key=cluster_spend, reverse=True
    )

    lines.append(f'# Falcon Daily Brief — {TODAY}\n')
    lines.append(f'**Wallets active:** {len(wallet_activity)}/{len(ALL_WALLETS)}\n\n')

    # -- Cluster section
    lines.append('---\n\n## CLUSTER Activity\n')
    cluster_matches = [s for s in hot_matches if any(e['group']=='CLUSTER' for e in match_data[s]['entries'])]
    tg_lines.append(f'*{len(cluster_matches)} matches with cluster money*\n')

    for slug in cluster_matches:
        d         = match_data[slug]
        entries   = d['entries']
        exits     = d['exits']
        cl_entries= [e for e in entries if e['group']=='CLUSTER']
        exp_entries=[e for e in entries if e['group']=='EXPAND']

        cl_spend  = sum(e['cost'] for e in cl_entries)
        exp_spend = sum(e['cost'] for e in exp_entries)

        # Group by outcome
        by_out = defaultdict(list)
        for e in entries:
            by_out[e['outcome']].append(e)

        # Find exits per wallet
        exited_wallets = {e['wallet'] for e in exits}

        name = match_name(slug)
        lines.append(f'\n### {name}\n')
        lines.append(f'`{slug}`  \n')
        lines.append(f'Cluster ${cl_spend:,.0f} | Expansion ${exp_spend:,.0f} | '
                     f'{len(cl_entries)} cluster wallets | {len(exp_entries)} expansion wallets\n\n')

        # Money line — what each side bet
        for out, wallets in sorted(by_out.items(), key=lambda x: -sum(w['cost'] for w in x[1])):
            out_spend = sum(w['cost'] for w in wallets)
            lines.append(f'**{out.upper()}** — ${out_spend:,.0f}\n')

            for e in sorted(wallets, key=lambda x: x['time']):
                sold = e['wallet'] in exited_wallets
                sold_str = ' → SOLD' if sold else ' → HELD'
                strategy = classify(e['time'], e['price'], sold)
                tag = f'[{strategy}]'
                lines.append(
                    f'- `{e["time"][11:16]}` **{e["label"]}** ({e["group"]}) '
                    f'@ {e["price"]:.3f} ${e["cost"]:,.0f} {sold_str} {tag}\n'
                )

                # Persist to DB
                exit_rec = next((x for x in exits if x['wallet'] == e['wallet'] and x['outcome'] == e['outcome']), None)
                db.upsert_position(
                    date=TODAY, wallet=e['wallet'].lower(), label=e['label'],
                    group_type=e['group'], match_slug=slug, match_name=name,
                    outcome=e['outcome'], entry_price=e['price'],
                    entry_time=e['time'], entry_cost=e['cost'],
                    exit_price=exit_rec['price'] if exit_rec else None,
                    exit_time=exit_rec['time'] if exit_rec else None,
                    strategy=strategy,
                )

        # Exits summary
        if exits:
            exited = ', '.join(
                f'{e["label"]}@{e["price"]:.3f}'
                for e in sorted(exits, key=lambda x: x['time'])
            )
            lines.append(f'\n*Exits detected:* {exited}\n')

        lines.append('\n')

        # TG: top matches only (cluster spend > $1000)
        if cl_spend >= 1000:
            top_out = max(by_out.items(), key=lambda x: sum(w['cost'] for w in x[1]), default=(None,[]))
            if top_out[0]:
                tg_lines.append(
                    f'• {name} → *{top_out[0].upper()}* ${cl_spend:,.0f} '
                    f'({len(cl_entries)} wallets)'
                )

    # -- Expansion-only section
    exp_only = [s for s in hot_matches if not any(e['group']=='CLUSTER' for e in match_data[s]['entries'])]
    if exp_only:
        lines.append('---\n\n## EXPANSION Only (cluster not here)\n')
        for slug in exp_only:
            d = match_data[slug]
            entries = d['entries']
            spend = sum(e['cost'] for e in entries)
            name  = match_name(slug)
            lines.append(f'\n### {name} — ${spend:,.0f}\n')
            for e in sorted(entries, key=lambda x: x['time']):
                sold = e['wallet'] in {x['wallet'] for x in d['exits']}
                strategy = classify(e['time'], e['price'], sold)
                lines.append(
                    f'- `{e["time"][11:16]}` **{e["label"]}** '
                    f'@ {e["price"]:.3f} ${e["cost"]:,.0f} '
                    f'{"→ SOLD" if sold else "→ HELD"} [{strategy}]\n'
                )
                db.upsert_position(
                    date=TODAY, wallet=e['wallet'].lower(), label=e['label'],
                    group_type=e['group'], match_slug=slug, match_name=name,
                    outcome=e['outcome'], entry_price=e['price'],
                    entry_time=e['time'], entry_cost=e['cost'],
                    exit_price=None, exit_time=None, strategy=strategy,
                )

    # -- Strategy summary
    strats = defaultdict(list)
    for slug in hot_matches:
        for e in match_data[slug]['entries']:
            sold = e['wallet'] in {x['wallet'] for x in match_data[slug]['exits']}
            s = classify(e['time'], e['price'], sold)
            strats[s].append(f'{e["label"]} on {match_name(slug)}')

    lines.append('---\n\n## Strategy Patterns Today\n\n')
    for s, examples in sorted(strats.items(), key=lambda x: -len(x[1])):
        lines.append(f'**{s}** ({len(examples)})  \n')
        for ex in examples[:5]:
            lines.append(f'- {ex}\n')
        lines.append('\n')

    tg_lines.append(f'\n*Patterns:* ' + ' | '.join(f'{s}={len(v)}' for s,v in sorted(strats.items())))

    # -- Save markdown session
    os.makedirs('sessions', exist_ok=True)
    md_path = f'sessions/{TODAY}-brief.md'
    with open(md_path, 'w') as f:
        f.writelines(lines)
    print(f'\nSaved: {md_path}')

    # -- Save to DB
    db.save_brief(TODAY, ''.join(lines), {
        'matches': len(hot_matches),
        'wallets_active': len(wallet_activity),
        'cluster_matches': len(cluster_matches),
    })
    print(f'Logged to falcon.db')

    # -- Telegram
    tg.send('\n'.join(tg_lines))
    print('Telegram sent.')
    db.close()

if __name__ == '__main__':
    main()
