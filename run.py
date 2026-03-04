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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("TradingBot")

# Imports — todos en la raíz
import config
from database import initialize_database, save_prices, save_signal
from fetcher import fetch_all_pairs, dataframe_to_db_records
from indicators import calculate_all, get_latest_values
from signals import score_signal, format_signal_summary
from paper_broker import PaperBroker
from news_scraper import get_market_sentiment


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
    start = datetime.now(timezone.utc)
    logger.info(f"{'─'*55}")
    logger.info(f"🔄 Ciclo — {start.strftime('%Y-%m-%d %H:%M UTC')}")
    logger.info(f"   Pares: {', '.join(config.ALL_PAIRS)}")
    logger.info(f"   DB:    {'Turso ☁️' if config.USE_TURSO else 'SQLite local'}")

    initialize_database()
    broker = PaperBroker()

    # ── Descargar datos ───────────────────────────────────────────
    logger.info("📡 Scrapeando noticias y sentimiento...")
    sentiments = get_market_sentiment()
    
    logger.info("📡 Descargando datos de mercado...")
    market_data = fetch_all_pairs(config.ALL_PAIRS, config.PRIMARY_TIMEFRAME, 200)

    if not market_data:
        logger.error("❌ Sin datos de mercado — abortando")
        return

    logger.info(f"✅ {len(market_data)}/{len(config.ALL_PAIRS)} pares obtenidos")

    # ── Procesar cada par ─────────────────────────────────────────
    current_prices = {}
    all_signals    = []

    for pair, df in market_data.items():
        save_prices(dataframe_to_db_records(df, pair, config.PRIMARY_TIMEFRAME))

        df_ind = calculate_all(df.copy())
        vals   = get_latest_values(df_ind)
        current_prices[pair] = vals["price"]

        # Determinar sentimiento según el tipo de par
        is_crypto = "/" in pair and any(c in pair for c in ["BTC", "ETH", "SOL", "USDT"])
        sentiment_score = sentiments["CRYPTO"] if is_crypto else sentiments["FOREX"]

        signal = score_signal(vals, config, sentiment_score=sentiment_score)
        signal.update({
            "pair":      pair,
            "timeframe": config.PRIMARY_TIMEFRAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price":     vals["price"],
        })
        all_signals.append(signal)

        if signal["score"] >= config.MIN_SCORE_ALERT:
            print(format_signal_summary(pair, config.PRIMARY_TIMEFRAME, signal, vals["price"]))

    # ── Cerrar trades que tocaron SL/TP ──────────────────────────
    closed = broker.check_and_close_trades(current_prices)
    for c in closed:
        emoji = "✅" if c["pnl"] > 0 else "❌"
        send_telegram(f"{emoji} <b>Trade cerrado</b>: {c['pair']}\n"
                      f"Razón: {c['reason']} | P&L: ${c['pnl']:+.2f}")

    # ── Abrir nuevos trades ───────────────────────────────────────
    if not dry_run:
        tradeable = sorted(
            [s for s in all_signals
             if s["score"] >= config.MIN_SCORE_TO_TRADE
             and s["direction"] != "NEUTRAL"],
            key=lambda x: x["score"], reverse=True
        )

        for signal in tradeable:
            if not broker.can_open_trade():
                break
            signal_id = save_signal({
                "pair":        signal["pair"],
                "timeframe":   signal["timeframe"],
                "timestamp":   signal["timestamp"],
                "direction":   signal["direction"],
                "score":       signal["score"],
                "price":       signal["price"],
                "stop_loss":   signal.get("stop_loss"),
                "take_profit": signal.get("take_profit"),
                "reasons":     json.dumps(signal.get("reasons", [])),
            })
            trade_id = broker.open_trade(
                signal_id   = signal_id,
                pair        = signal["pair"],
                direction   = signal["direction"],
                price       = signal["price"],
                stop_loss   = signal.get("stop_loss"),
                take_profit = signal.get("take_profit"),
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
