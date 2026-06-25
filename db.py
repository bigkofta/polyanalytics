"""
Persistent SQLite tracker. Logs every position and classifies strategy patterns.
Builds up day by day — never resets.

Tables:
  positions   — every tracked wallet position (entry + exit if sold same day)
  daily_brief — one row per date, stores the full brief as JSON

Usage:
  from db import DB
  db = DB()
  db.upsert_position(...)
  db.get_wallet_history('0xabc...')
"""

import sqlite3, json, os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'falcon.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    wallet      TEXT NOT NULL,
    label       TEXT,
    group_type  TEXT,         -- CLUSTER / EXPAND
    match_slug  TEXT NOT NULL,
    match_name  TEXT,
    outcome     TEXT,
    entry_price REAL,
    entry_time  TEXT,
    entry_cost  REAL,
    exit_price  REAL,         -- NULL if still holding
    exit_time   TEXT,         -- NULL if still holding
    strategy    TEXT,         -- EARLY_MOVER / DIP_BUYER / CONVICTION / QUICK_FLIP / LATE_ENTRY
    UNIQUE(date, wallet, match_slug, outcome)
);

CREATE TABLE IF NOT EXISTS daily_brief (
    date        TEXT PRIMARY KEY,
    summary     TEXT,         -- human-readable markdown summary
    raw_json    TEXT,         -- full analysis as JSON
    created_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_positions_wallet ON positions(wallet);
CREATE INDEX IF NOT EXISTS idx_positions_date   ON positions(date);
CREATE INDEX IF NOT EXISTS idx_positions_match  ON positions(match_slug);
"""

class DB:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_position(self, date, wallet, label, group_type, match_slug, match_name,
                        outcome, entry_price, entry_time, entry_cost,
                        exit_price=None, exit_time=None, strategy=None):
        self.conn.execute("""
            INSERT INTO positions
              (date, wallet, label, group_type, match_slug, match_name,
               outcome, entry_price, entry_time, entry_cost,
               exit_price, exit_time, strategy)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(date, wallet, match_slug, outcome) DO UPDATE SET
              exit_price = excluded.exit_price,
              exit_time  = excluded.exit_time,
              strategy   = excluded.strategy
        """, (date, wallet, label, group_type, match_slug, match_name,
              outcome, entry_price, entry_time, entry_cost,
              exit_price, exit_time, strategy))
        self.conn.commit()

    def save_brief(self, date, summary, raw):
        self.conn.execute("""
            INSERT OR REPLACE INTO daily_brief (date, summary, raw_json, created_at)
            VALUES (?, ?, ?, ?)
        """, (date, summary, json.dumps(raw), datetime.utcnow().isoformat()))
        self.conn.commit()

    def get_wallet_history(self, wallet, days=30):
        rows = self.conn.execute("""
            SELECT * FROM positions
            WHERE wallet = ? AND date >= date('now', ?)
            ORDER BY date DESC, entry_time
        """, (wallet.lower(), f'-{days} days')).fetchall()
        return [dict(r) for r in rows]

    def get_match_history(self, slug_fragment):
        rows = self.conn.execute("""
            SELECT * FROM positions
            WHERE match_slug LIKE ?
            ORDER BY date DESC, entry_time
        """, (f'%{slug_fragment}%',)).fetchall()
        return [dict(r) for r in rows]

    def get_wallet_stats(self, wallet):
        rows = self.conn.execute("""
            SELECT strategy, COUNT(*) as count,
                   AVG(entry_price) as avg_entry,
                   SUM(entry_cost) as total_spent
            FROM positions WHERE wallet = ?
            GROUP BY strategy
        """, (wallet.lower(),)).fetchall()
        return [dict(r) for r in rows]

    def get_top_wallets(self, days=14):
        """Wallets with most positions in last N days."""
        rows = self.conn.execute("""
            SELECT wallet, label, group_type,
                   COUNT(*) as positions,
                   SUM(entry_cost) as total_spent,
                   COUNT(DISTINCT date) as active_days
            FROM positions
            WHERE date >= date('now', ?)
            GROUP BY wallet
            ORDER BY positions DESC
        """, (f'-{days} days',)).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
