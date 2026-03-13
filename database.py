"""
db/database.py — Capa de datos con Turso (libSQL) + fallback SQLite local
Turso es SQLite distribuido en la nube con API HTTP — perfecto para GitHub Actions.
"""
import os
import json
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
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
    reasons     TEXT, executed INTEGER DEFAULT 0,
    sentiment   REAL DEFAULT 0
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
CREATE TABLE IF NOT EXISTS trade_feedback (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id       INTEGER UNIQUE,
    lesson         TEXT,
    performance_score REAL,
    timestamp      TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS hb_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT,
    status         TEXT,
    note           TEXT
);
CREATE TABLE IF NOT EXISTS system_logs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT,
    level          TEXT,
    message        TEXT
);
CREATE TABLE IF NOT EXISTS macro_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT,
    dxy_val        REAL,
    nasdaq_val     REAL,
    risk_appetite  TEXT,
    dxy_trend      TEXT,
    nasdaq_trend   TEXT
);
CREATE TABLE IF NOT EXISTS bot_memory (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT DEFAULT (datetime('now')),
    category       TEXT, -- 'REFLECTION', 'PATTERN', 'STRATEGY'
    note           TEXT,
    impact         TEXT  -- 'POSITIVE', 'NEGATIVE', 'NEUTRAL'
);
CREATE TABLE IF NOT EXISTS bot_config (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    key            TEXT UNIQUE,
    value          TEXT,
    updated_at     TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS bot_wishes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT DEFAULT (datetime('now')),
    wish           TEXT,
    status         TEXT DEFAULT 'PENDING' -- 'PENDING', 'FULFILLED', 'IGNORED', 'ACTION'
);
CREATE TABLE IF NOT EXISTS strategy_performance (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy       TEXT NOT NULL,
    pair           TEXT,
    result         TEXT,
    pnl            REAL,
    timestamp      TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS bot_improvement_requests (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT DEFAULT (datetime('now')),
    category       TEXT,   -- 'CONFIG', 'FEATURE', 'STRATEGY_INSIGHT', 'DATA_ISSUE'
    priority       TEXT,   -- 'HIGH', 'MEDIUM', 'LOW'
    title          TEXT,
    description    TEXT,
    status         TEXT DEFAULT 'PENDING'  -- 'PENDING', 'ACKNOWLEDGED', 'IMPLEMENTED'
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
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        self.session = requests.Session()
        # Reintentos a nivel de TCP (errores de conexión, no de timeout de lectura)
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
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
        """Envía todos los statements pendientes en una sola llamada HTTP con reintentos."""
        if not self._pending:
            return []
        import requests, time
        payload = {"requests": self._pending + [{"type": "close"}]}
        last_err = None
        for attempt in range(3):
            try:
                # timeout=(connect, read): falla rápido en conexión, 60s para leer
                resp = self.session.post(
                    self.base, json=payload, headers=self.headers,
                    timeout=(15, 60)
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                self._pending = []
                return results
            except requests.exceptions.Timeout as e:
                last_err = e
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"⚠️ Turso timeout (intento {attempt+1}/3), reintentando en {wait}s…")
                time.sleep(wait)
            except requests.exceptions.RequestException as e:
                last_err = e
                logger.warning(f"⚠️ Turso error de red (intento {attempt+1}/3): {e}")
                time.sleep(2 ** attempt)
        # Todos los intentos fallaron — limpiar batch y propagar
        self._pending = []
        logger.error(f"❌ Turso: todos los reintentos fallaron — {last_err}")
        raise last_err or RuntimeError("Turso: falló sin excepción registrada")

    def query(self, sql: str, params: list = None) -> list:
        """Ejecuta una consulta y devuelve lista de dicts."""
        self._pending = []  # limpiar batch
        self.execute(sql, params)
        try:
            results = self.commit()
        except Exception as e:
            logger.error(f"❌ Turso query falló: {e} | SQL: {sql[:80]}")
            return []
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


def save_macro_context(ctx: dict):
    if not ctx: return
    d = db()
    sql = "INSERT INTO macro_history (timestamp, dxy_val, nasdaq_val, risk_appetite, dxy_trend, nasdaq_trend) VALUES (?, ?, ?, ?, ?, ?)"
    params = [datetime.now(timezone.utc).isoformat(), ctx['dxy_val'], ctx['nasdaq_val'], ctx['risk_appetite'], ctx['dxy_trend'], ctx['nasdaq_trend']]
    d.execute(sql, params)
    d.commit()

def get_latest_macro():
    d = db()
    r = d.query("SELECT * FROM macro_history ORDER BY id DESC LIMIT 1")
    return r[0] if r else None

def get_daily_pnl():
    """Calcula el PnL total de los trades cerrados hoy."""
    d = db()
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    res = d.query("SELECT SUM(pnl) as total FROM paper_trades WHERE close_time LIKE ?", [f"{today}%"])
    return float(res[0]['total'] or 0.0)

def get_bot_config(key, default=None):
    """Obtiene un valor de configuración de la base de datos."""
    d = db()
    r = d.query("SELECT value FROM bot_config WHERE key = ?", [key])
    return r[0]['value'] if r else default

def set_bot_config(key, value):
    """Guarda o actualiza un valor de configuración."""
    d = db()
    d.execute(
        "INSERT INTO bot_config (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        [key, str(value), datetime.now(timezone.utc).isoformat()]
    )
    d.commit()

def log_heartbeat(status: str, note: str = ""):
    d = db()
    d.execute("INSERT INTO hb_log (timestamp, status, note) VALUES (?,?,?)",
              [datetime.now(timezone.utc).isoformat(), status, note])
    d.commit()

def get_recent_heartbeats(limit=5):
    return db().query("SELECT * FROM hb_log ORDER BY id DESC LIMIT ?", [limit])

def log_system_event(level: str, message: str):
    d = db()
    d.execute("INSERT INTO system_logs (timestamp, level, message) VALUES (?,?,?)",
              [datetime.now(timezone.utc).isoformat(), level, message])
    d.commit()

def get_recent_logs(limit=15):
    return db().query("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", [limit])

def save_signal(signal: dict) -> int:
    reasons = signal.get("reasons", [])
    if isinstance(reasons, list):
        reasons = json.dumps(reasons)
    d = db()
    d.execute(
        "INSERT INTO signals (pair,timeframe,timestamp,direction,score,price,stop_loss,take_profit,reasons,sentiment) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [signal["pair"], signal["timeframe"], signal["timestamp"],
         signal["direction"], signal["score"], signal["price"],
         signal.get("stop_loss"), signal.get("take_profit"), reasons, signal.get("sentiment", 0)]
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
        [now, close_price, round(float(pnl), 2), round(float(pnl_pct), 2), status, reason, trade_id]
    )
    d.commit()
    return round(float(pnl), 2)


def save_trade_feedback(trade_id: int, lesson: str, score: float):
    d = db()
    d.execute(
        "INSERT OR REPLACE INTO trade_feedback (trade_id, lesson, performance_score) "
        "VALUES (?,?,?)",
        [trade_id, lesson, score]
    )
    d.commit()


def get_open_trades() -> list:
    return db().query("SELECT * FROM paper_trades WHERE status='OPEN'")


def get_portfolio_balance() -> float:
    rows = db().query("SELECT balance FROM portfolio ORDER BY id DESC LIMIT 1")
    if not rows: return 10000.0
    try:
        return float(rows[0]["balance"])
    except (KeyError, TypeError, ValueError):
        return 10000.0


def update_portfolio(balance: float, equity: float, note: str = ""):
    d = db()
    d.execute(
        "INSERT INTO portfolio (timestamp,balance,equity,note) VALUES (?,?,?,?)",
        [datetime.now(timezone.utc).isoformat(), balance, equity, note]
    )
    d.commit()


def get_dashboard_data() -> dict:
    d = db()
    
    def safe_count(sql, params=None):
        r = d.query(sql, params or [])
        if not r: return 0
        return int(r[0].get("c") or 0)

    total  = safe_count("SELECT COUNT(*) as c FROM paper_trades WHERE status != 'OPEN'")
    wins   = safe_count("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'WIN'")
    losses = safe_count("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'LOSS'")
    open_t = safe_count("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'OPEN'")
    
    pnl_rows = d.query("SELECT COALESCE(SUM(pnl),0) as s FROM paper_trades WHERE status != 'OPEN'")
    pnl_r = float(pnl_rows[0].get("s") or 0) if pnl_rows else 0.0
    
    bal_r  = d.query("SELECT balance FROM portfolio ORDER BY id DESC LIMIT 1")
    signals = d.query("SELECT pair,direction,score,price,timestamp,sentiment FROM signals ORDER BY id DESC LIMIT 20")
    # Join paper_trades with trade_feedback
    trades  = d.query("SELECT t.*, f.lesson, f.performance_score FROM paper_trades t LEFT JOIN trade_feedback f ON t.id = f.trade_id ORDER BY t.id DESC LIMIT 30")
    bal_hist= d.query("SELECT timestamp,balance FROM portfolio ORDER BY id DESC LIMIT 60")
    macro   = get_latest_macro()
    memory  = d.query("SELECT * FROM bot_memory ORDER BY id DESC LIMIT 10")
    wishes  = d.query("SELECT * FROM bot_wishes WHERE status IN ('PENDING', 'ACTION') ORDER BY id DESC LIMIT 5")
    heartbeats = get_recent_heartbeats()

    # Health Metrics
    now_utc = datetime.now(timezone.utc)
    yesterday_iso = (now_utc - timedelta(days=1)).isoformat()
    
    # 1. Error count (Last 24h)
    err_24h = safe_count("SELECT COUNT(*) as c FROM system_logs WHERE level IN ('ERROR', 'CRITICAL') AND timestamp > ?", [yesterday_iso])
    
    # 2. Autonomous Actions count (Last 24h)
    act_24h = safe_count("SELECT COUNT(*) as c FROM bot_wishes WHERE status = 'ACTION' AND timestamp > ?", [yesterday_iso])
    
    # 3. Downtime Detection (Last heartbeat)
    last_hb = heartbeats[0]["timestamp"] if heartbeats else None
    is_down = False
    if last_hb:
        try:
            # Handle potential space in timestamp
            if " " in last_hb and "T" not in last_hb: last_hb = last_hb.replace(" ", "T")
            hb_dt = datetime.fromisoformat(last_hb)
            if hb_dt.tzinfo is None: hb_dt = hb_dt.replace(tzinfo=timezone.utc)
            if (now_utc - hb_dt).total_seconds() > 1800: # 30 min
                is_down = True
        except: pass

    balance_val = float(bal_r[0].get("balance") or 10000.0) if (bal_r and "balance" in bal_r[0]) else 10000.0
    total, wins, losses, open_t = int(total), int(wins), int(losses), int(open_t)

    # Nuevos datos para paneles avanzados
    improvement_requests = get_improvement_requests(8)
    strategy_perf        = get_strategy_performance()
    monthly_metrics_data = get_monthly_metrics()
    signal_only_mode     = get_bot_config("SIGNAL_ONLY_MODE", "false") == "true"

    return {
        "balance":         round(float(balance_val), 2),
        "total_pnl":       round(float(pnl_r), 2),
        "total_trades":    total,
        "wins":            wins,
        "losses":          losses,
        "open_trades":     open_t,
        "win_rate":        round(float(wins / total * 100), 1) if total > 0 else 0.0,
        "signals":         signals,
        "trades":          trades,
        "balance_history": list(reversed(bal_hist)),
        "macro":           macro,
        "heartbeats":      heartbeats,
        "system_logs":     get_recent_logs(),
        "bot_memory":      memory,
        "bot_wishes":      wishes,
        "improvement_requests": improvement_requests,
        "strategy_performance": strategy_perf,
        "monthly_metrics":      monthly_metrics_data,
        "signal_only_mode":     signal_only_mode,
        "market_monitor":       get_market_monitor(),
        "health": {
            "status": "DOWN" if is_down else ("WARNING" if err_24h > 0 else "OK"),
            "errors_24h": int(err_24h),
            "actions_24h": int(act_24h),
            "last_heartbeat": last_hb
        },
        "bot_config": {
            "strategy":      get_bot_config("ACTIVE_STRATEGY", "ALL"),
            "min_score":     get_bot_config("MIN_SCORE_TO_TRADE", "5.0"),
            "sl_atr":        get_bot_config("STOP_LOSS_ATR", "1.2"),
            "paused":        get_bot_config("TRADING_PAUSED", "false") == "true",
            "paused_pairs":  get_bot_config("PAUSED_PAIRS", ""),
            "signal_only":   signal_only_mode,
        },
        "last_updated":    now_utc.isoformat(),
    }


def get_improvement_requests(limit=10) -> list:
    """Obtiene las solicitudes de mejora más recientes para el dashboard."""
    return db().query(
        "SELECT * FROM bot_improvement_requests ORDER BY "
        "CASE priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END, "
        "id DESC LIMIT ?",
        [limit]
    )


def get_strategy_performance() -> list:
    """Obtiene el rendimiento agregado por estrategia (últimos 30 días)."""
    return db().query("""
        SELECT strategy,
               COUNT(*) as total,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) as losses,
               ROUND(SUM(CAST(pnl AS REAL)), 2) as total_pnl,
               ROUND(AVG(CAST(pnl AS REAL)), 2) as avg_pnl
        FROM strategy_performance
        WHERE timestamp > datetime('now', '-30 days')
        GROUP BY strategy
        ORDER BY total_pnl DESC
    """)


def get_market_monitor() -> list:
    """Obtiene el último estado (precio, score, sentimiento) de cada par."""
    pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "EURUSD=X", "GBPUSD=X", "USDJPY=X"]
    results = []
    
    for p in pairs:
        # Buscar última señal para este par
        rows = db().query(
            "SELECT price, score, sentiment, timestamp FROM signals WHERE pair = ? ORDER BY id DESC LIMIT 1",
            [p]
        )
        if rows:
            r = rows[0]
            results.append({
                "pair": p,
                "price": r.get("price") or 0.0,
                "score": r.get("score") or 0.0,
                "sentiment": r.get("sentiment") or 0.0,
                "timestamp": r.get("timestamp")
            })
        else:
            results.append({
                "pair": p, "price": 0.0, "score": 0.0, "sentiment": 0.0, "timestamp": None
            })
    return results


def get_monthly_metrics() -> list:
    """Obtiene las métricas mensuales históricas."""
    return db().query(
        "SELECT * FROM monthly_metrics ORDER BY month DESC LIMIT 6"
    )


def update_monthly_metrics():
    """Calcula y guarda/actualiza las métricas del mes actual."""
    d = db()
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")

    try:
        trades = d.query(
            "SELECT status, pnl, pair FROM paper_trades "
            "WHERE status != 'OPEN' AND close_time LIKE ?",
            [f"{month_key}%"]
        )
        if not trades:
            return

        total  = len(trades)
        wins   = [t for t in trades if t["status"] == "WIN"]
        losses = [t for t in trades if t["status"] == "LOSS"]
        total_pnl = sum(float(t["pnl"] or 0) for t in trades)
        win_rate  = len(wins) / total * 100 if total > 0 else 0

        pair_pnl = {}
        for t in trades:
            pair_pnl[t["pair"]] = pair_pnl.get(t["pair"], 0) + float(t["pnl"] or 0)
        best_pair  = max(pair_pnl, key=pair_pnl.get) if pair_pnl else ""
        worst_pair = min(pair_pnl, key=pair_pnl.get) if pair_pnl else ""

        bal_rows = d.query(
            "SELECT balance FROM portfolio WHERE timestamp LIKE ? ORDER BY id ASC",
            [f"{month_key}%"]
        )
        balances = [float(r["balance"]) for r in bal_rows if r.get("balance")]
        max_dd = 0.0
        if balances:
            peak = balances[0]
            for b in balances:
                peak = max(peak, b)
                dd = (peak - b) / peak * 100 if peak > 0 else 0
                max_dd = max(max_dd, dd)

        d.execute(
            "INSERT INTO monthly_metrics "
            "(month, total_trades, winning_trades, losing_trades, win_rate, "
            " total_pnl, max_drawdown, best_pair, worst_pair) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(month) DO UPDATE SET "
            "total_trades=excluded.total_trades, "
            "winning_trades=excluded.winning_trades, "
            "losing_trades=excluded.losing_trades, "
            "win_rate=excluded.win_rate, "
            "total_pnl=excluded.total_pnl, "
            "max_drawdown=excluded.max_drawdown, "
            "best_pair=excluded.best_pair, "
            "worst_pair=excluded.worst_pair",
            [month_key, total, len(wins), len(losses),
             round(win_rate, 1), round(total_pnl, 2),
             round(max_dd, 1), best_pair, worst_pair]
        )
        d.commit()
        logger.debug(f"📅 Métricas mensuales actualizadas: {month_key}")
    except Exception as e:
        logger.warning(f"update_monthly_metrics: {e}")


def get_latest_signals(limit=10):
    return db().query("SELECT * FROM signals ORDER BY id DESC LIMIT ?", [limit])


def save_portfolio_snapshot(balance: float, equity: float, note: str = ""):
    update_portfolio(balance, equity, note)


def df_to_records(df):
    """Convierte un DataFrame de pandas a lista de diccionarios para DB."""
    if df is None or df.empty:
        return []
    return df.reset_index().to_dict('records')


def get_bot_config(key: str, default=None):
    """Obtener configuración dinámica de la base de datos."""
    rows = db().query("SELECT value FROM bot_config WHERE key = ?", [key])
    if not rows: return default
    return rows[0].get("value", default)


def set_bot_config(key: str, value: str):
    """Guardar o actualizar configuración dinámica."""
    d = db()
    now = datetime.now(timezone.utc).isoformat()
    d.execute(
        "INSERT INTO bot_config (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        [key, value, now]
    )
    d.commit()

