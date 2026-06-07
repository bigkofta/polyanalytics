"""
Polyanalytics Query Tool

Usage:
    python query.py list                          # show all watched wallets
    python query.py add 0x123... "My label"       # add to watchlist
    python query.py remove 0x123...               # remove from watchlist
    python query.py market tennis                 # wallets profitable in markets matching keyword
    python query.py active                        # wallets that traded today
    python query.py top --period 30d --min-pnl 50000   # top performers from watchlist
    python query.py scan --market atp- --min-cost 50000  # scan ALL wallets in a market
    python query.py profile 0x123...              # quick profile of any wallet
"""

import sys
import json
import time
import argparse
import requests
from datetime import datetime, timezone
from collections import defaultdict

from falcon_api import TOKEN, API_URL

headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
WL_FILE = "watchlist.json"


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_wl():
    try:
        return json.load(open(WL_FILE))
    except FileNotFoundError:
        return {"wallets": [], "clusters": {}}

def save_wl(wl):
    json.dump(wl, open(WL_FILE, "w"), indent=2)

def post(agent_id, params, limit=200, offset=0):
    r = requests.post(API_URL, json={
        "agent_id": agent_id, "params": params,
        "pagination": {"limit": limit, "offset": offset},
        "formatter_config": {"format_type": "raw"},
    }, headers=headers, timeout=20)
    return r.json()

def today():
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

def fetch_trades(wallet, limit=200):
    data = post(556, {"proxy_wallet": wallet, "condition_id": "ALL",
                      "market_slug": "ALL", "side": "ALL"}, limit=limit)
    return data.get("data", {}).get("results", [])

def leaderboard_lookup(wallet):
    data = post(579, {
        "leaderboard_period": "30d", "wallet_address": wallet,
        "min_total_pnl": "-1.0", "max_total_pnl": "-1.0",
        "min_win_rate": "-1.0", "max_win_rate": "-1.0",
        "min_sharpe_ratio": "-1.0", "max_sharpe_ratio": "-1.0",
    }, limit=1)
    results = data.get("data", {}).get("results", [])
    return results[0] if results else {}


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_list(args):
    wl = load_wl()
    wallets = wl.get("wallets", [])
    if not wallets:
        print("Watchlist is empty. Use: python query.py add 0x... \"Label\"")
        return
    print(f"\n{'LABEL':<35} {'ADDRESS':<44} {'CLUSTER':<25} ADDED")
    print("-" * 120)
    for w in wallets:
        print(f"  {w.get('label',''):<33} {w['address']:<44} {w.get('cluster',''):<25} {w.get('added','')}")
    print(f"\nTotal: {len(wallets)} wallets")

    clusters = wl.get("clusters", {})
    if clusters:
        print("\nClusters:")
        for name, c in clusters.items():
            print(f"  {name}: {c.get('description','')}")


def cmd_add(args):
    wl = load_wl()
    addr = args.address.strip().lower()
    label = args.label or addr[:20] + "..."
    if any(w["address"].lower() == addr for w in wl["wallets"]):
        print(f"Already in watchlist: {addr}")
        return
    wl["wallets"].append({"address": addr, "label": label,
                           "notes": "", "added": today()})
    save_wl(wl)
    print(f"Added: {label} ({addr})")


def cmd_remove(args):
    wl = load_wl()
    addr = args.address.strip().lower()
    before = len(wl["wallets"])
    wl["wallets"] = [w for w in wl["wallets"] if w["address"].lower() != addr]
    save_wl(wl)
    print(f"Removed {before - len(wl['wallets'])} wallet(s)")


def cmd_market(args):
    """Which watched wallets traded in markets matching a keyword, and were profitable."""
    keyword = args.keyword.lower()
    wl = load_wl()
    wallets = wl.get("wallets", [])
    print(f"\nScanning {len(wallets)} watched wallets for markets matching '{keyword}'...\n")

    print(f"  {'LABEL':<30} {'SLUG':<42} {'BET ON':<22} {'COST':>10} {'P_LO':>6} {'P_HI':>6}")
    print(f"  {'-'*30} {'-'*42} {'-'*22} {'-'*10} {'-'*6} {'-'*6}")

    for w in wallets:
        trades = fetch_trades(w["address"], limit=200)
        mkts = defaultdict(lambda: {"cost": 0.0, "out": "", "plo": 1.0, "phi": 0.0, "first": ""})
        for t in trades:
            slug = t.get("slug", "")
            if keyword not in slug.lower():
                continue
            key = (slug, t.get("outcome", ""))
            p, s = float(t.get("price", 0)), float(t.get("size", 0))
            m = mkts[key]
            m["cost"] += p * s
            m["out"] = key[1]
            m["plo"] = min(m["plo"], p) if p else m["plo"]
            m["phi"] = max(m["phi"], p)
            ts = t.get("timestamp", "")
            if not m["first"] or ts < m["first"]:
                m["first"] = ts
        for (slug, out), m in sorted(mkts.items(), key=lambda x: -x[1]["cost"]):
            print(f"  {w.get('label','')[:28]:<30} {slug[:42]:<42} {out[:22]:<22} "
                  f"{m['cost']:>10,.0f} {m['plo']:>6.3f} {m['phi']:>6.3f}")
        time.sleep(0.1)


def cmd_active(args):
    """Show watched wallets that placed trades today."""
    td = today()
    wl = load_wl()
    print(f"\nChecking for activity today ({td})...\n")
    for w in wl.get("wallets", []):
        trades = fetch_trades(w["address"], limit=50)
        today_trades = [t for t in trades if t.get("timestamp", "").startswith(td)]
        if today_trades:
            cost = sum(float(t.get("price", 0)) * float(t.get("size", 0)) for t in today_trades)
            slugs = set(t.get("slug", "") for t in today_trades)
            print(f"  ACTIVE  {w.get('label',''):<35} ${cost:>12,.0f}  {', '.join(list(slugs)[:2])}")
        else:
            print(f"  quiet   {w.get('label',''):<35}")
        time.sleep(0.1)


def cmd_top(args):
    """Leaderboard stats for all watched wallets."""
    wl = load_wl()
    rows = []
    for w in wl.get("wallets", []):
        lb = leaderboard_lookup(w["address"])
        if lb:
            pnl = float(lb.get("total_pnl", 0))
            if pnl >= args.min_pnl:
                rows.append((w.get("label", ""), w["address"], lb))
        time.sleep(0.1)
    rows.sort(key=lambda x: -float(x[2].get("total_pnl", 0)))
    print(f"\n  {'LABEL':<35} {'RANK':>6} {'PNL':>14} {'WIN%':>7} {'ROI%':>7}")
    print(f"  {'-'*35} {'-'*6} {'-'*14} {'-'*7} {'-'*7}")
    for label, addr, lb in rows:
        wr = float(lb.get("win_rate", 0)) * 100
        roi = float(lb.get("roi", 0)) * 100
        print(f"  {label:<35} #{lb.get('rank','?'):>5} {float(lb.get('total_pnl',0)):>14,.0f} {wr:>6.1f}% {roi:>6.1f}%")


def cmd_scan(args):
    """Scan a market for ALL wallets over a spend threshold — find new whales."""
    keyword = (args.market or "").lower()
    min_cost = args.min_cost or 10000
    print(f"\nScanning market '{keyword}' for wallets spending >${min_cost:,.0f}...\n")

    data = post(556, {"proxy_wallet": "ALL", "condition_id": "ALL",
                      "market_slug": "ALL", "side": "ALL"}, limit=200)
    trades = data.get("data", {}).get("results", [])

    wallets = defaultdict(lambda: defaultdict(float))
    for t in trades:
        slug = t.get("slug", "")
        if keyword and keyword not in slug.lower():
            continue
        wallet = t.get("proxy_wallet", "")
        wallets[wallet][slug] += float(t.get("price", 0)) * float(t.get("size", 0))

    found = [(w, slugs) for w, slugs in wallets.items()
             if sum(slugs.values()) >= min_cost]
    found.sort(key=lambda x: -sum(x[1].values()))

    wl = load_wl()
    known = {w["address"].lower() for w in wl.get("wallets", [])}

    print(f"  {'WALLET':<44} {'TOTAL':>12}  MARKETS  STATUS")
    print(f"  {'-'*44} {'-'*12}  {'-'*30}  {'-'*10}")
    for wallet, slugs in found[:30]:
        total = sum(slugs.values())
        mkt_list = ", ".join(list(slugs.keys())[:2])[:35]
        status = "WATCHED" if wallet.lower() in known else "NEW"
        print(f"  {wallet:<44} {total:>12,.0f}  {mkt_list:<35}  {status}")


def cmd_profile(args):
    """Quick profile of any wallet."""
    wallet = args.address.strip().lower()
    print(f"\nProfiling {wallet}...")
    lb = leaderboard_lookup(wallet)
    if lb:
        print(f"  Rank:      #{lb.get('rank','?')}")
        print(f"  PnL (30d): ${float(lb.get('total_pnl',0)):,.0f}")
        print(f"  Win Rate:  {float(lb.get('win_rate',0))*100:.1f}%")
        print(f"  ROI:       {float(lb.get('roi',0))*100:.2f}%")
        print(f"  Trades:    {lb.get('total_trades','?')}")
    else:
        print("  Not found on 30d leaderboard")
    trades = fetch_trades(wallet, limit=50)
    mkts = defaultdict(lambda: {"cost": 0.0, "out": "", "first": ""})
    for t in trades:
        key = (t.get("slug", ""), t.get("outcome", ""))
        p, s = float(t.get("price", 0)), float(t.get("size", 0))
        mkts[key]["cost"] += p * s
        mkts[key]["out"] = key[1]
        ts = t.get("timestamp", "")
        if not mkts[key]["first"] or ts < mkts[key]["first"]:
            mkts[key]["first"] = ts
    print(f"\n  Recent markets ({len(trades)} trades):")
    for (slug, out), m in sorted(mkts.items(), key=lambda x: -x[1]["cost"])[:10]:
        print(f"    {m['first'][:10]}  {slug[:40]:<40}  {out[:20]:<20}  ${m['cost']:>10,.0f}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Polyanalytics query tool")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("list")

    a = sub.add_parser("add")
    a.add_argument("address")
    a.add_argument("label", nargs="?")

    r = sub.add_parser("remove")
    r.add_argument("address")

    m = sub.add_parser("market")
    m.add_argument("keyword")

    sub.add_parser("active")

    t = sub.add_parser("top")
    t.add_argument("--period", default="30d")
    t.add_argument("--min-pnl", type=float, default=0)

    sc = sub.add_parser("scan")
    sc.add_argument("--market", default="")
    sc.add_argument("--min-cost", type=float, default=10000)

    pr = sub.add_parser("profile")
    pr.add_argument("address")

    args = p.parse_args()
    cmds = {"list": cmd_list, "add": cmd_add, "remove": cmd_remove,
            "market": cmd_market, "active": cmd_active, "top": cmd_top,
            "scan": cmd_scan, "profile": cmd_profile}

    if args.cmd in cmds:
        cmds[args.cmd](args)
    else:
        p.print_help()

if __name__ == "__main__":
    main()
