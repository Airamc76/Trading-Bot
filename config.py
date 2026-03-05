"""
config.py — Configuración central
Lee variables de entorno (GitHub Secrets en producción, .env en local)
"""
import os
from dotenv import load_dotenv
load_dotenv()

# ── Turso (SQLite en la nube) ─────────────────────────────────────────────────
TURSO_URL        = os.getenv("TURSO_URL", "")         # libsql://TUDB.turso.io
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")  # token de Turso

# Fallback: SQLite local si no hay Turso configurado
USE_TURSO = bool(TURSO_URL and TURSO_AUTH_TOKEN)

# ── Pares a monitorear ────────────────────────────────────────────────────────
CRYPTO_PAIRS = [p.strip() for p in os.getenv("CRYPTO_PAIRS", "BTC/USDT,ETH/USDT,SOL/USDT").split(",") if p.strip()]
FOREX_PAIRS  = [p.strip() for p in os.getenv("FOREX_PAIRS",  "EURUSD=X,GBPUSD=X,USDJPY=X").split(",") if p.strip()]
ALL_PAIRS    = CRYPTO_PAIRS + FOREX_PAIRS

# ── Timeframes ────────────────────────────────────────────────────────────────
PRIMARY_TIMEFRAME = "15m"

# ── Indicadores técnicos ──────────────────────────────────────────────────────
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70
MACD_FAST      = 12
MACD_SLOW      = 26
MACD_SIGNAL    = 9
BB_PERIOD      = 20
BB_STD         = 2.0
EMA_SHORT      = 20
EMA_MEDIUM     = 50
EMA_LONG       = 200
ATR_PERIOD     = 14

# ── Gestión de riesgo ─────────────────────────────────────────────────────────
PAPER_CAPITAL   = float(os.getenv("PAPER_CAPITAL",   "10000"))
RISK_PER_TRADE  = float(os.getenv("RISK_PER_TRADE",  "0.02"))
STOP_LOSS_ATR   = 1.2
TAKE_PROFIT_R   = 2.0
MAX_OPEN_TRADES        = 3  # APEX Rule 2: Máximo de operaciones simultáneas
MAX_POSITION_SIZE_PCT  = 0.50  # Máximo 50% del capital por trade

# ── Scoring ───────────────────────────────────────────────────────────────────
MIN_SCORE_TO_TRADE = float(os.getenv("MIN_SCORE_TO_TRADE", "5.0"))
MIN_SCORE_ALERT    = 5.0

# ── Exchange (Binance API) ──────────────────────────────────────────────────
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY",    "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# ── Notificaciones (Telegram opcional) ───────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "")
