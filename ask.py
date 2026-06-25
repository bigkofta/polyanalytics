"""
Query the falcon DB. Ask questions about wallets and matches.

Usage:
  python ask.py match krejcikova          # all history for that match
  python ask.py wallet WTA_Sharp          # wallet history + strategy breakdown
  python ask.py today                     # today's brief summary
  python ask.py patterns                  # which strategies are working lately
  python ask.py top                       # most active wallets last 14 days
"""

import sys
from db import DB
from collections import defaultdict

db = DB()

def match_query(fragment):
    rows = db.get_match_history(fragment)
    if not rows:
        print(f'No history for: {fragment}')
        return
    print(f'\n=== Match history: "{fragment}" ({len(rows)} positions) ===\n')
    by_date = defaultdict(list)
    for r in rows:
        by_date[r['date']].append(r)
    for date in sorted(by_date.keys(), reverse=True):
        print(f'  {date}')
        for r in sorted(by_date[date], key=lambda x: x['entry_time'] or ''):
            held = 'HELD' if not r['exit_time'] else f'SOLD @ {r["exit_price"]:.3f}'
            print(f'    {r["label"]:<22} {r["outcome"].upper():<20} @ {r["entry_price"]:.3f}  '
                  f'${r["entry_cost"]:,.0f}  {held}  [{r["strategy"]}]')
        print()

def wallet_query(name_fragment):
    # Find wallet by label
    rows = db.get_top_wallets(days=90)
    matches = [r for r in rows if name_fragment.lower() in r['label'].lower()]
    if not matches:
        print(f'No wallet matching: {name_fragment}')
        return
    wallet = matches[0]['wallet']
    label  = matches[0]['label']
    history = db.get_wallet_history(wallet, days=60)
    stats   = db.get_wallet_stats(wallet)
    print(f'\n=== {label} ({wallet[:16]}...) ===\n')
    print(f'Strategy breakdown:')
    for s in stats:
        print(f'  {s["strategy"]:<15} {s["count"]:>3}x  avg_entry={s["avg_entry"]:.3f}  ${s["total_spent"]:,.0f} total')
    print(f'\nRecent positions ({len(history)}):')
    for r in history[:20]:
        held = 'HELD' if not r['exit_time'] else f'SOLD @ {r["exit_price"]:.3f}'
        print(f'  {r["date"]}  {r["match_name"]:<35} {r["outcome"].upper():<20} '
              f'@ {r["entry_price"]:.3f}  ${r["entry_cost"]:,.0f}  {held}  [{r["strategy"]}]')

def patterns_query():
    rows = db.get_top_wallets(days=14)
    print(f'\n=== Strategy patterns (last 14 days) ===\n')
    from db import DB_PATH
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    strats = conn.execute("""
        SELECT strategy, COUNT(*) as count, GROUP_CONCAT(DISTINCT label) as wallets
        FROM positions
        WHERE date >= date('now', '-14 days')
        GROUP BY strategy ORDER BY count DESC
    """).fetchall()
    for s in strats:
        print(f'  {s["strategy"]:<15} {s["count"]:>3}x')
        print(f'    wallets: {s["wallets"]}')
    conn.close()

def top_query():
    rows = db.get_top_wallets(days=14)
    print(f'\n=== Most active wallets (last 14 days) ===\n')
    for r in rows[:20]:
        print(f'  {r["label"]:<22} {r["group_type"]:<8} '
              f'{r["positions"]:>3} positions  ${r["total_spent"]:,.0f}  '
              f'{r["active_days"]} days active')

def today_query():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    import sqlite3
    from db import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM daily_brief WHERE date = ?", (today,)
    ).fetchall()
    if rows:
        import json
        brief = rows[0]
        meta = json.loads(brief['raw_json'])
        print(f"\n=== Today's brief ({today}) ===")
        print(f"  {meta.get('wallets_active','?')} wallets active")
        print(f"  {meta.get('cluster_matches','?')} cluster matches")
        print(f"  {meta.get('matches','?')} total matches\n")
        print(brief['summary'][:3000])
    else:
        print(f'No brief logged for {today} yet. Run: python daily_brief.py')
    conn.close()

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == 'match' and len(args) > 1:
        match_query(args[1])
    elif args[0] == 'wallet' and len(args) > 1:
        wallet_query(' '.join(args[1:]))
    elif args[0] == 'patterns':
        patterns_query()
    elif args[0] == 'top':
        top_query()
    elif args[0] == 'today':
        today_query()
    else:
        print(__doc__)

    db.close()
