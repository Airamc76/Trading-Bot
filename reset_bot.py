"""
reset_bot.py — Gran Reinicio del Bot
Limpia todo el historial y reinicia el balance a $10,000 con la estrategia Z-Score.
"""
import logging
import os
from database import db, initialize_database, update_portfolio, set_bot_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ResetTool")


def the_great_reset():
    logger.info("🚀 Iniciando EL GRAN REINICIO — Estrategia Z-Score Mean Reversion")

    initialize_database()
    d = db()

    tables_to_wipe = [
        "prices", "signals", "paper_trades", "trade_feedback",
        "hb_log", "system_logs", "bot_memory", "bot_wishes",
        "strategy_performance", "portfolio", "macro_history",
    ]

    for table in tables_to_wipe:
        try:
            logger.info(f"🧹 Limpiando tabla: {table}")
            d.execute(f"DELETE FROM {table}")
            d.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo limpiar {table}: {e}")

    try:
        logger.info("🧹 Limpiando tabla: bot_config")
        d.execute("DELETE FROM bot_config")
    except Exception as e:
        logger.warning(f"⚠️ No se pudo limpiar bot_config: {e}")

    d.commit()

    # ── Restablecer balance ───────────────────────────────────────────────────
    INITIAL_BALANCE = 10000.0
    logger.info(f"💰 Restableciendo balance a ${INITIAL_BALANCE:,.2f}")
    update_portfolio(INITIAL_BALANCE, INITIAL_BALANCE,
                     "✨ GRAN REINICIO — Z-Score Mean Reversion Strategy")

    # ── Configuración predeterminada Z-Score ──────────────────────────────────
    logger.info("⚙️ Aplicando configuración Z-Score Mean Reversion...")
    set_bot_config("STRATEGY_MODE",     "ZSCORE_MEAN_REVERSION")
    set_bot_config("ACTIVE_STRATEGY",   "ZSCORE_MEAN_REVERSION")
    set_bot_config("ZSCORE_ENTRY",      "2.0")
    set_bot_config("ZSCORE_EXIT",       "0.5")
    set_bot_config("ZSCORE_STOP",       "3.5")
    set_bot_config("ZSCORE_WINDOW_BETA","500")
    set_bot_config("ZSCORE_WINDOW_Z",   "60")
    set_bot_config("HURST_THRESHOLD",   "0.45")
    set_bot_config("VOLUME_MIN_PCT",    "0.70")
    set_bot_config("RSI_CONFIRM_BUY",   "35")
    set_bot_config("RSI_CONFIRM_SELL",  "65")
    set_bot_config("COINT_MAX_PVALUE",  "0.05")
    set_bot_config("MIN_SCORE_TO_TRADE","5.0")
    set_bot_config("RISK_PER_TRADE",    "0.015")
    set_bot_config("MAX_OPEN_TRADES",   "1")
    set_bot_config("TRADING_PAUSED",    "false")
    set_bot_config("SIGNAL_ONLY_MODE",  "false")
    set_bot_config("PAUSED_PAIRS",      "")
    # Forzar re-test de cointegración en el próximo ciclo
    set_bot_config("COINT_LAST_CHECK",  "")
    set_bot_config("COINT_PVALUE",      "0.99")

    logger.info("✅ GRAN REINICIO COMPLETADO — Bot listo con Z-Score Mean Reversion y $10,000")


if __name__ == "__main__":
    if os.getenv("FORCE_RESET") == "true":
        the_great_reset()
    else:
        confirm = input(
            "⚠️ ¿ESTÁS SEGURO? Esto borrará TODO el historial y reiniciará a $10,000. (s/n): "
        )
        if confirm.lower() == 's':
            the_great_reset()
        else:
            logger.info("❌ Reinicio cancelado.")
