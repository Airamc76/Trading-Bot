"""
config.py — Configuración central
Estrategia: Z-Score Mean Reversion — BTC/ETH Spread
Lee variables de entorno (GitHub Secrets en producción, .env en local)
"""
import os
from dotenv import load_dotenv
load_dotenv()

# ── Turso (SQLite en la nube) ─────────────────────────────────────────────────
TURSO_URL        = os.getenv("TURSO_URL", "")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
USE_TURSO        = bool(TURSO_URL and TURSO_AUTH_TOKEN)

# ── Estrategia activa ─────────────────────────────────────────────────────────
STRATEGY_MODE = "ZSCORE_MEAN_REVERSION"

# ── Pares del spread (BTC / ETH cointegrados) ─────────────────────────────────
SPREAD_PAIR_A = os.getenv("SPREAD_PAIR_A", "BTC/USDT")   # Referencia
SPREAD_PAIR_B = os.getenv("SPREAD_PAIR_B", "ETH/USDT")   # Activo operado
CRYPTO_PAIRS  = [SPREAD_PAIR_A, SPREAD_PAIR_B]
FOREX_PAIRS   = []
ALL_PAIRS     = CRYPTO_PAIRS

# ── Timeframe ─────────────────────────────────────────────────────────────────
PRIMARY_TIMEFRAME = "1h"      # Velas de 1h para el Z-score
CANDLE_LIMIT      = 620       # 500 OLS + 60 Z-window + buffer

# ── Parámetros Z-Score ────────────────────────────────────────────────────────
ZSCORE_ENTRY       = float(os.getenv("ZSCORE_ENTRY",     "2.0"))   # Umbral de entrada ±σ
ZSCORE_EXIT        = float(os.getenv("ZSCORE_EXIT",      "0.5"))   # Take profit ±σ
ZSCORE_STOP        = float(os.getenv("ZSCORE_STOP",      "3.5"))   # Stop loss ±σ
ZSCORE_WINDOW_BETA = int(os.getenv("ZSCORE_WINDOW_BETA", "500"))   # Ventana OLS (velas)
ZSCORE_WINDOW_Z    = int(os.getenv("ZSCORE_WINDOW_Z",   "60"))    # Ventana Z-score (velas)

# ── Filtros obligatorios ──────────────────────────────────────────────────────
HURST_THRESHOLD   = float(os.getenv("HURST_THRESHOLD",  "0.45"))  # H < threshold → mean-reverting
VOLUME_MIN_PCT    = float(os.getenv("VOLUME_MIN_PCT",   "0.70"))  # Volumen mínimo vs avg-20
RSI_CONFIRM_BUY   = float(os.getenv("RSI_CONFIRM_BUY",  "35"))    # RSI ETH < X para LONG
RSI_CONFIRM_SELL  = float(os.getenv("RSI_CONFIRM_SELL", "65"))    # RSI ETH > X para SHORT
COINT_MAX_PVALUE  = float(os.getenv("COINT_MAX_PVALUE", "0.05"))  # p-value máximo Engle-Granger

# ── Indicadores técnicos (para RSI de ETH) ────────────────────────────────────
RSI_PERIOD     = 14
ATR_PERIOD     = 14

# ── Gestión de riesgo ─────────────────────────────────────────────────────────
PAPER_CAPITAL         = float(os.getenv("PAPER_CAPITAL",  "10000"))
RISK_PER_TRADE        = float(os.getenv("RISK_PER_TRADE", "0.015"))  # 1.5% riesgo por trade
MAX_OPEN_TRADES       = 1     # Solo 1 trade de spread a la vez
MAX_POSITION_SIZE_PCT = 0.40  # Máximo 40% del capital por trade

# ── Scoring ───────────────────────────────────────────────────────────────────
MIN_SCORE_TO_TRADE = float(os.getenv("MIN_SCORE_TO_TRADE", "5.0"))
MIN_SCORE_ALERT    = 4.0

# ── Exchange ──────────────────────────────────────────────────────────────────
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY",    "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# ── Notificaciones ────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "")
