"""
db/database.py — Capa de datos con Turso (libSQL) + fallback SQLite local
Turso es SQLite distribuido en la nube con API HTTP — perfecto para GitHub Actions.
"""
import os
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

TURSO_URL        = os.getenv("TURSO_URL", "")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
USE_TURSO        = bool(TURSO_URL and TURSO_AUTH_TOKEN)

# ── Schema SQL (compatible con SQLite y libSQL) ───────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pair      TEXT    NOT NULL,
    timeframe TEXT    NOT NULL,
    timestamp TEXT    NOT NULL,
    open      REAL, high REAL, low REAL, close REAL, volume REAL,
    UNIQUE(pair, timeframe, timestamp)
);
CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pair        TEXT, timeframe TEXT,
    timestamp   TEXT DEFAULT (datetime('now')),
    direction   TEXT, score REAL, price REAL,
    stop_loss   REAL, take_profit REAL,
    reasons     TEXT, executed INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS paper_trades (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id      INTEGER,
    pair           TEXT, direction TEXT,
    open_time      TEXT DEFAULT (datetime('now')),
    close_time     TEXT,
    open_price     REAL, close_price REAL,
    stop_loss      REAL, take_profit REAL,
    position_size  REAL, pnl REAL, pnl_pct REAL,
    status         TEXT DEFAULT 'OPEN',
    close_reason   TEXT
);
CREATE TABLE IF NOT EXISTS portfolio (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    balance   REAL, equity REAL, note TEXT
);
CREATE TABLE IF NOT EXISTS monthly_metrics (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    month          TEXT UNIQUE,
    total_trades   INTEGER, winning_trades INTEGER, losing_trades INTEGER,
    win_rate       REAL, profit_factor REAL, total_pnl REAL,
    max_drawdown   REAL, sharpe_ratio REAL,
    best_pair TEXT, worst_pair TEXT, notes TEXT
);
"""


# ── Turso HTTP client ─────────────────────────────────────────────────────────
class TursoClient:
    """
    Cliente HTTP para Turso libSQL.
    Usa la API HTTP de Turso — no requiere librerías nativas.
    """

    def __init__(self, url: str, token: str):
        import requests
        self.session = requests.Session()
        # Convertir URL de libsql:// a https://
        self.base = url.replace("libsql://", "https://") + "/v2/pipeline"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._pending = []   # batch de statements

    def execute(self, sql: str, params: list = None):
        """Agrega un statement al batch pendiente."""
        stmt = {"type": "execute", "stmt": {"sql": sql}}
        if params:
            stmt["stmt"]["args"] = [
                {"type": "text", "value": str(p)} if p is not None else {"type": "null"}
                for p in params
            ]
        self._pending.append(stmt)

    def commit(self):
        """Envía todos los statements pendientes en una sola llamada HTTP."""
        if not self._pending:
            return []
        payload = {"requests": self._pending + [{"type": "close"}]}
        import requests
        resp = self.session.post(self.base, json=payload, headers=self.headers, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        self._pending = []
        return results

    def query(self, sql: str, params: list = None) -> list:
        """Ejecuta una consulta y devuelve lista de dicts."""
        self._pending = []  # limpiar batch
        self.execute(sql, params)
        results = self.commit()
        if not results or results[0].get("type") == "error":
            return []
        rows_data = results[0].get("response", {}).get("result", {})
        cols  = [c["name"] for c in rows_data.get("cols", [])]
        rows  = rows_data.get("rows", [])
        return [dict(zip(cols, [v.get("value") for v in row])) for row in rows]

    def initialize(self):
        """Crea las tablas si no existen."""
        for stmt in SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self.execute(stmt)
        self.commit()
        logger.info("✅ Turso: tablas inicializadas")


# ── SQLite local fallback ─────────────────────────────────────────────────────
class LocalDB:
    def __init__(self, path="db/local.db"):
        Path(path).parent.mkdir(exist_ok=True)
        self.path = path
        self._conn = None

    def _get(self):
        if not self._conn:
            self._conn = sqlite3.connect(self.path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def execute(self, sql, params=None):
        self._get().execute(sql, params or [])

    def commit(self):
        self._get().commit()

    def query(self, sql, params=None) -> list:
        cur = self._get().execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]

    def initialize(self):
        self._get().executescript(SCHEMA)
        self._get().commit()
        logger.info("✅ SQLite local inicializado")


# ── Instancia global ──────────────────────────────────────────────────────────
def _get_db():
    if USE_TURSO:
        return TursoClient(TURSO_URL, TURSO_AUTH_TOKEN)
    return LocalDB()


_db_instance = None

def db():
    global _db_instance
    if _db_instance is None:
        _db_instance = _get_db()
    return _db_instance


# ── API pública ───────────────────────────────────────────────────────────────

def initialize_database():
    db().initialize()


def save_prices(records: list):
    d = db()
    for r in records:
        d.execute(
            "INSERT OR IGNORE INTO prices (pair,timeframe,timestamp,open,high,low,close,volume) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [r["pair"], r["timeframe"], r["timestamp"],
             r["open"], r["high"], r["low"], r["close"], r["volume"]]
        )
    d.commit()


def save_signal(signal: dict) -> int:
    reasons = signal.get("reasons", [])
    if isinstance(reasons, list):
        reasons = json.dumps(reasons)
    d = db()
    d.execute(
        "INSERT INTO signals (pair,timeframe,timestamp,direction,score,price,stop_loss,take_profit,reasons) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [signal["pair"], signal["timeframe"], signal["timestamp"],
         signal["direction"], signal["score"], signal["price"],
         signal.get("stop_loss"), signal.get("take_profit"), reasons]
    )
    d.commit()
    rows = d.query("SELECT id FROM signals ORDER BY id DESC LIMIT 1")
    return int(rows[0]["id"]) if rows else 0


def open_paper_trade(trade: dict) -> int:
    d = db()
    d.execute(
        "INSERT INTO paper_trades (signal_id,pair,direction,open_time,open_price,stop_loss,take_profit,position_size,status) "
        "VALUES (?,?,?,?,?,?,?,?,'OPEN')",
        [trade["signal_id"], trade["pair"], trade["direction"], trade["open_time"],
         trade["open_price"], trade["stop_loss"], trade["take_profit"], trade["position_size"]]
    )
    d.commit()
    rows = d.query("SELECT id FROM paper_trades ORDER BY id DESC LIMIT 1")
    return int(rows[0]["id"]) if rows else 0


def close_paper_trade(trade_id: int, close_price: float, reason: str) -> float:
    d = db()
    rows = d.query("SELECT * FROM paper_trades WHERE id = ?", [trade_id])
    if not rows:
        return 0.0
    t = rows[0]
    pnl = (close_price - float(t["open_price"])) * float(t["position_size"]) / float(t["open_price"])
    if t["direction"] == "SELL":
        pnl = -pnl
    pnl_pct = pnl / float(t["position_size"]) * 100
    status  = "WIN" if pnl > 0 else "LOSS"
    now     = datetime.now(timezone.utc).isoformat()
    d.execute(
        "UPDATE paper_trades SET close_time=?,close_price=?,pnl=?,pnl_pct=?,status=?,close_reason=? WHERE id=?",
        [now, close_price, round(pnl, 2), round(pnl_pct, 2), status, reason, trade_id]
    )
    d.commit()
    return round(pnl, 2)


def get_open_trades() -> list:
    return db().query("SELECT * FROM paper_trades WHERE status='OPEN'")


def get_portfolio_balance() -> float:
    rows = db().query("SELECT balance FROM portfolio ORDER BY id DESC LIMIT 1")
    return float(rows[0]["balance"]) if rows else None


def update_portfolio(balance: float, equity: float, note: str = ""):
    d = db()
    d.execute(
        "INSERT INTO portfolio (timestamp,balance,equity,note) VALUES (?,?,?,?)",
        [datetime.now(timezone.utc).isoformat(), balance, equity, note]
    )
    d.commit()


def get_dashboard_data() -> dict:
    d = db()
    total  = d.query("SELECT COUNT(*) as c FROM paper_trades WHERE status != 'OPEN'")[0]["c"] or 0
    wins   = d.query("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'WIN'")[0]["c"] or 0
    losses = d.query("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'LOSS'")[0]["c"] or 0
    open_t = d.query("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'OPEN'")[0]["c"] or 0
    pnl_r  = d.query("SELECT COALESCE(SUM(pnl),0) as s FROM paper_trades WHERE status != 'OPEN'")[0]["s"] or 0
    bal_r  = d.query("SELECT balance FROM portfolio ORDER BY id DESC LIMIT 1")
    signals = d.query("SELECT pair,direction,score,price,timestamp FROM signals ORDER BY id DESC LIMIT 20")
    trades  = d.query("SELECT * FROM paper_trades ORDER BY id DESC LIMIT 30")
    bal_hist= d.query("SELECT timestamp,balance FROM portfolio ORDER BY id DESC LIMIT 60")

    balance = float(bal_r[0]["balance"]) if bal_r else 10000.0
    total, wins, losses, open_t = int(total), int(wins), int(losses), int(open_t)

    return {
        "balance":         round(balance, 2),
        "total_pnl":       round(float(pnl_r), 2),
        "total_trades":    total,
        "wins":            wins,
        "losses":          losses,
        "open_trades":     open_t,
        "win_rate":        round(wins / total * 100, 1) if total > 0 else 0.0,
        "signals":         signals,
        "trades":          trades,
        "balance_history": list(reversed(bal_hist)),
        "last_updated":    datetime.now(timezone.utc).isoformat(),
    }
