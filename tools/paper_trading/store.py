"""SQLite-backed paper account store: one transaction for state + ledger + order."""
from __future__ import annotations
import json, sqlite3, threading
from dataclasses import asdict
from pathlib import Path
from tools.paper_trading.account import AccountState, Lot, utcnow


class SQLiteAccountStore:
    def __init__(self, root: Path):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "paper.sqlite"; self._lock = threading.RLock()
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS account(id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS orders(order_id TEXT PRIMARY KEY, status TEXT NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ledger(seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS actions(action_id TEXT PRIMARY KEY, data TEXT NOT NULL);
            """)

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=ON")
        return c

    def load(self) -> AccountState:
        with self._lock, self._conn() as c:
            row = c.execute("SELECT state FROM account WHERE id=?", ("PAPER-50000",)).fetchone()
            if row is None:
                st = AccountState(); self.save(st); return st
            d = json.loads(row[0]); d["lots"] = [Lot(**x) for x in d.get("lots", [])]
            return AccountState(**d)

    def save(self, st: AccountState) -> None:
        payload = json.dumps({k: v for k, v in asdict(st).items()}, sort_keys=True)
        with self._lock, self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT INTO account(id,state) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state",
                      (st.account_id, payload))
            c.execute("COMMIT")

    def orders(self) -> dict:
        with self._lock, self._conn() as c:
            rows = c.execute("SELECT order_id,data FROM orders").fetchall()
        return {oid: json.loads(data) for oid, data in rows}

    def save_order(self, order: dict) -> None:
        with self._lock, self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT INTO orders(order_id,status,data) VALUES(?,?,?) "
                      "ON CONFLICT(order_id) DO UPDATE SET status=excluded.status,data=excluded.data",
                      (order["order_id"], order["status"], json.dumps(order, sort_keys=True)))
            c.execute("COMMIT")

    def commit_fill(self, st: AccountState, order: dict, fill: dict) -> None:
        state = json.dumps(asdict(st), sort_keys=True)
        with self._lock, self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT INTO account(id,state) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state",
                      (st.account_id, state))
            cur = c.execute("UPDATE orders SET status=?, data=? WHERE order_id=? AND status='PENDING'",
                            (order["status"], json.dumps(order, sort_keys=True), order["order_id"]))
            if cur.rowcount != 1:
                c.execute("ROLLBACK")
                raise ValueError("order already terminal or missing")
            c.execute("INSERT INTO ledger(data) VALUES(?)", (json.dumps(fill, sort_keys=True),))
            c.execute("COMMIT")

    def append_ledger(self, entry: dict) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO ledger(data) VALUES(?)", (json.dumps(entry, sort_keys=True),))

    def history(self) -> list[dict]:
        with self._lock, self._conn() as c:
            rows = c.execute("SELECT data FROM ledger ORDER BY seq").fetchall()
        return [json.loads(x[0]) for x in rows]

    def save_action(self, action_id: str, entry: dict) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT OR IGNORE INTO actions(action_id,data) VALUES(?,?)",
                      (action_id, json.dumps(entry, sort_keys=True)))

    def action_exists(self, action_id: str) -> bool:
        with self._lock, self._conn() as c:
            return c.execute("SELECT 1 FROM actions WHERE action_id=?", (action_id,)).fetchone() is not None
