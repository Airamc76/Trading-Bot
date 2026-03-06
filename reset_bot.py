"""
reset_bot.py — Utilidad para el Gran Reinicio del Bot
Wipes all history, resets balance to $10,000 and clears AI memory.
"""
import logging
import os
from database import db, initialize_database, update_portfolio, set_bot_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ResetTool")

def the_great_reset():
    logger.info("🚀 Iniciando EL GRAN REINICIO...")
    
    # 1. Asegurar que las tablas existen
    initialize_database()
    d = db()
    
    # 2. Tablas a limpiar completamente
    tables_to_wipe = [
        "prices",
        "signals",
        "paper_trades",
        "trade_feedback",
        "hb_log",
        "system_logs",
        "bot_memory",
        "bot_wishes",
        "strategy_performance",
        "portfolio"
    ]
    
    for table in tables_to_wipe:
        try:
            logger.info(f"🧹 Limpiando tabla: {table}")
            d.execute(f"DELETE FROM {table}")
            # Resetear autoincrementales
            d.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo limpiar {table}: {e}")
    
    # IMPORTANTE: También limpiar bot_config para evitar remanentes como TRADING_PAUSED
    try:
        logger.info("🧹 Limpiando tabla: bot_config")
        d.execute("DELETE FROM bot_config")
    except Exception as e:
        logger.warning(f"⚠️ No se pudo limpiar bot_config: {e}")

    d.commit()

    # 3. Restablecer balance inicial
    INITIAL_BALANCE = 10000.0
    logger.info(f"💰 Restableciendo balance a ${INITIAL_BALANCE:,.2f}")
    update_portfolio(INITIAL_BALANCE, INITIAL_BALANCE, "✨ EL GRAN REINICIO — Comienzo desde 0")
    
    # 4. Restablecer configuración predeterminada
    logger.info("⚙️ Restableciendo configuración predeterminada...")
    set_bot_config("MIN_SCORE_TO_TRADE", "5.0")
    set_bot_config("STOP_LOSS_ATR", "1.2")
    set_bot_config("ACTIVE_STRATEGY", "ALL")
    set_bot_config("PAUSED_PAIRS", "")
    set_bot_config("TRADING_PAUSED", "false") # Asegurar que no está pausado
    set_bot_config("MAX_OPEN_TRADES", "3")
    
    logger.info("✅ EL GRAN REINICIO COMPLETADO CON ÉXITO.")

if __name__ == "__main__":
    if os.getenv("FORCE_RESET") == "true":
        the_great_reset()
    else:
        confirm = input("⚠️ ¿ESTÁS SEGURO? Esto borrará TODO el historial. (s/n): ")
        if confirm.lower() == 's':
            the_great_reset()
        else:
            logger.info("❌ Reinicio cancelado.")
