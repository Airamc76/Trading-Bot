"""
run.py — Ciclo principal del bot
GitHub Actions ejecuta este script cada 15 minutos.
Todos los archivos están en la raíz del proyecto.
"""
import sys
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone

# Setup
Path("logs").mkdir(exist_ok=True)
# ── Configuración de Log ──────────────────────────────────────
class DBLogHandler(logging.Handler):
    def emit(self, record):
        try:
            from database import log_system_event
            log_system_event(record.levelname, record.getMessage())
        except: pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        DBLogHandler()
    ]
)
logger = logging.getLogger("TradingBot")

# Imports — todos en la raíz
import config
from database import (
    initialize_database, save_prices, save_signal,
    get_latest_signals, get_open_trades, close_paper_trade,
    save_portfolio_snapshot, 
    save_macro_context, log_heartbeat, log_system_event
)
from fetcher import fetch_all_pairs, dataframe_to_db_records
from indicators import calculate_all, get_latest_values
from signals import score_signal, format_signal_summary
from paper_broker import PaperBroker
from news_scraper import get_market_sentiment
from feedback_engine import run_feedback_cycle
from macro_analyzer import get_macro_context, is_high_impact_event_near
from brain import process_bot_brain


def send_telegram(message: str):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=5
        )
    except Exception as e:
        logger.warning(f"Telegram error: {e}")


def run_cycle(dry_run: bool = False):
    initialize_database()
    start = datetime.now(timezone.utc)
    logger.info(f"{'─'*55}")
    logger.info(f"🔄 Ciclo — {start.strftime('%Y-%m-%d %H:%M UTC')}")
    log_heartbeat("RUNNING", f"Iniciando ciclo en {start.strftime('%H:%M')}")
    broker = PaperBroker()

    # ── Descargar datos ───────────────────────────────────────────
    # ── 3. Obtener Sentimiento y Macro ────────────────────────────
    logger.info("📡 Obteniendo sentimiento y contexto macro...")
    sentiment = get_market_sentiment()
    macro = get_macro_context()
    event_near = is_high_impact_event_near()

    if macro:
        save_macro_context(macro)

    if event_near:
        logger.warning("⚠️ EVENTO DE ALTO IMPACTO CERCA. Pausando nuevas operaciones.")
        send_telegram("⚠️ <b>Precaución</b>: Evento macro de alto impacto detectado. Pausando nuevas entradas.")
    
    logger.info("📡 Descargando datos de mercado...")
    market_data = fetch_all_pairs(config.ALL_PAIRS, config.PRIMARY_TIMEFRAME, 200)

    if not market_data:
        msg = "❌ Sin datos de mercado (todas las fuentes fallaron) — abortando ciclo"
        logger.error(msg)
        log_heartbeat("ERROR", "Falla crítica en descarga de datos")
        log_system_event("ERROR", msg)
        return

    logger.info(f"✅ {len(market_data)}/{len(config.ALL_PAIRS)} pares obtenidos")

    # ── Procesar cada par ─────────────────────────────────────────
    current_prices = {}
    all_signals    = []
    all_prices_to_save = []

    for pair, df in market_data.items():
        all_prices_to_save.extend(dataframe_to_db_records(df, pair, config.PRIMARY_TIMEFRAME))

        df_ind = calculate_all(df.copy())
        vals   = get_latest_values(df_ind)
        current_prices[pair] = vals["price"]

        # Obtener sentimiento por categoría
        sent_score = sentiment.get("CRYPTO" if pair in config.CRYPTO_PAIRS else "FOREX", 0.0)

        # Scoring avanzado (Técnico + Sentimiento + Macro)
        signal = score_signal(vals, config, sent_score, macro)
        signal.update({
            "pair":      pair,
            "timeframe": config.PRIMARY_TIMEFRAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price":     vals["price"],
            "atr":       vals.get("atr"), # Pass ATR for Rule 6
        })
        all_signals.append(signal)

    # Guardar todos los precios en un solo lote para evitar timeouts
    if all_prices_to_save:
        save_prices(all_prices_to_save)

    # Log de razonamiento y alertas + Guardar TODAS las señales para el dashboard
    for signal in all_signals:
        pair = signal["pair"]
        reasons_text = " | ".join([r["note"] for r in signal["reasons"]])
        log_system_event("INFO", f"🔍 {pair}: Score {signal['score']:.1f}/10 - {reasons_text}")

        # Guardamos la señal en la DB aunque sea NEUTRAL para que aparezca en el Dashboard
        # Pero marcamos si fue una entrada real o solo monitoreo
        save_signal({
            "pair":        signal["pair"],
            "timeframe":   signal["timeframe"],
            "timestamp":   signal["timestamp"],
            "direction":   signal["direction"],
            "score":       signal["score"],
            "price":       signal["price"],
            "stop_loss":   signal.get("stop_loss"),
            "take_profit": signal.get("take_profit"),
            "reasons":     json.dumps(signal.get("reasons", [])),
            "sentiment":   signal.get("sentiment", 0)
        })

        if signal["score"] >= config.MIN_SCORE_ALERT:
            logger.info(format_signal_summary(pair, config.PRIMARY_TIMEFRAME, signal, signal["price"]))

    # ── Cerrar trades que tocaron SL/TP ──────────────────────────
    closed = broker.check_and_close_trades(current_prices)
    for c in closed:
        emoji = "✅" if c["pnl"] > 0 else "❌"
        send_telegram(f"{emoji} <b>Trade cerrado</b>: {c['pair']}\n"
                      f"Razón: {c['reason']} | P&L: ${c['pnl']:+.2f}")

    if closed:
        run_feedback_cycle()

    # ── Abrir nuevos trades ───────────────────────────────────────
    if not dry_run and not event_near:
        from database import get_bot_config, get_daily_pnl
        
        # APEX RULE 2: Daily Drawdown Limit (5%)
        daily_pnl = get_daily_pnl()
        max_daily_loss = broker.balance * 0.05
        
        # Recuperar configuración dinámica
        dyn_min_score = float(get_bot_config("MIN_SCORE_TO_TRADE", config.MIN_SCORE_TO_TRADE))
        paused_pairs_str = get_bot_config("PAUSED_PAIRS", "")
        paused_pairs = paused_pairs_str.split(",") if paused_pairs_str else []

        if daily_pnl < -max_daily_loss:
            msg = f"🚨 PAUSADO: Límite de drawdown diario alcanzado (${daily_pnl:,.2f})."
            logger.warning(msg)
            # Aún ejecutamos el cerebro para que el MD explique por qué está pausado
            process_bot_brain()
            log_heartbeat("PAUSED", msg)
            return

        tradeable = sorted(
            [s for s in all_signals
             if s["score"] >= dyn_min_score
             and s["direction"] != "NEUTRAL"
             and s["pair"] not in paused_pairs],
            key=lambda x: x["score"], reverse=True
        )

        for signal in tradeable:
            if not broker.can_open_trade():
                break
            
            # Recuperar el ID de la señal ya guardada o buscar la última para este par
            last_sigs = get_latest_signals(10)
            signal_id = next((s["id"] for s in last_sigs if s["pair"] == signal["pair"]), 0)

            trade_id = broker.open_trade(
                signal_id   = signal_id,
                pair        = signal["pair"],
                direction   = signal["direction"],
                price       = signal["price"],
                stop_loss   = signal.get("stop_loss"),
                take_profit = signal.get("take_profit"),
                atr         = signal.get("atr"), # Rule 6 Volatility
            )
            if trade_id:
                r = signal.get("reasons", [])
                notes = " | ".join(x["note"] for x in r[:2]) if r else ""
                send_telegram(
                    f"🔔 <b>Señal detectada</b>: {signal['pair']}\n"
                    f"Dirección: <b>{signal['direction']}</b> | Score: {signal['score']:.1f}/10\n"
                    f"Precio: {signal['price']:.4g}\n"
                    f"📌 {notes}"
                )
        
        # ── IA CONSCIOUSNESS: Reflexión post-operativa ───────────────
        process_bot_brain()

    # ── Resumen del ciclo ─────────────────────────────────────────
    stats   = broker.stats()
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()

    print(f"\n{'─'*55}")
    print(f"{'Par':15s} {'Dir':6s} {'Score':8s} {'Precio':>14s}")
    print(f"{'─'*55}")
    for s in sorted(all_signals, key=lambda x: x["score"], reverse=True):
        icon = {"BUY": "🟢", "SELL": "🔴", "NEUTRAL": "⚪"}.get(s["direction"], "⚪")
        print(f"{s['pair']:15s} {icon}{s['direction']:5s} {s['score']:5.1f}/10  {s['price']:>14.4g}")

    print(f"\n💼 Balance: ${stats['balance']:,.2f}  |  "
          f"Win Rate: {stats['win_rate']:.1f}%  |  "
          f"Abiertos: {stats['open_trades']}")
    print(f"⏱  Completado en {elapsed:.1f}s\n")
    log_heartbeat("SUCCESS", f"Ciclo completado en {elapsed:.1f}s")


def show_stats():
    initialize_database()
    from database import get_dashboard_data
    d = get_dashboard_data()
    print(f"""
╔══════════════════════════════════════╗
║       📊 TRADING BOT — STATS        ║
╠══════════════════════════════════════╣
║  Balance:    ${d['balance']:>10,.2f}          ║
║  P&L total:  ${d['total_pnl']:>+10.2f}          ║
║  Win Rate:   {d['win_rate']:>9.1f}%          ║
╠══════════════════════════════════════╣
║  Trades:     {d['total_trades']:>10}          ║
║  Ganadores:  {d['wins']:>10}          ║
║  Perdedores: {d['losses']:>10}          ║
║  Abiertos:   {d['open_trades']:>10}          ║
╚══════════════════════════════════════╝
    """)


if __name__ == "__main__":
    mode = os.getenv("BOT_MODE", "cycle")
    if   mode == "stats":    show_stats()
    elif mode == "dry-run":  run_cycle(dry_run=True)
    else:                    run_cycle(dry_run=False)
