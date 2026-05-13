"""
run.py — Ciclo principal: Z-Score Mean Reversion (BTC/ETH Spread)

GitHub Actions ejecuta este script cada 15 minutos.
Estrategia: detecta desviaciones estadísticas del spread log(ETH) - β×log(BTC)
y opera cuando el Z-score supera ±2σ, esperando la reversión a la media.
"""
import sys
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

Path("logs").mkdir(exist_ok=True)


class DBLogHandler(logging.Handler):
    def emit(self, record):
        try:
            from database import log_system_event
            log_system_event(record.levelname, record.getMessage())
        except Exception:
            pass


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

import config
from database import (
    initialize_database, save_prices, save_signal,
    get_latest_signals, save_macro_context,
    log_heartbeat, log_system_event,
    get_bot_config, set_bot_config, get_daily_pnl
)
from fetcher import fetch_all_pairs, dataframe_to_db_records
from indicators import calculate_spread_indicators, test_cointegration
from signals import score_zscore_signal, format_signal_summary
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


def _check_cointegration_cached(df_btc, df_eth) -> float:
    """
    Ejecuta el test Engle-Granger y cachea el resultado 24h en bot_config.
    Re-ejecuta si el p-value supera 0.10 (par en riesgo de desacople).
    """
    last_check_str = get_bot_config("COINT_LAST_CHECK", "")
    last_pvalue    = float(get_bot_config("COINT_PVALUE", "0.99"))

    should_recheck = True
    if last_check_str:
        try:
            last_check = datetime.fromisoformat(last_check_str)
            if last_check.tzinfo is None:
                last_check = last_check.replace(tzinfo=timezone.utc)
            hours_since = (datetime.now(timezone.utc) - last_check).total_seconds() / 3600
            should_recheck = hours_since > 24 or last_pvalue > 0.10
        except Exception:
            pass

    if should_recheck:
        btc_close = df_btc['close'].tail(500)
        eth_close = df_eth['close'].tail(500)
        min_len   = min(len(btc_close), len(eth_close))
        pvalue    = test_cointegration(
            btc_close.iloc[-min_len:], eth_close.iloc[-min_len:]
        )
        set_bot_config("COINT_LAST_CHECK", datetime.now(timezone.utc).isoformat())
        set_bot_config("COINT_PVALUE", str(pvalue))
        status = "✅ OK" if pvalue < config.COINT_MAX_PVALUE else "⚠️ ALTO"
        logger.info(f"🔬 Cointegración actualizada: p={pvalue:.4f} {status}")
        return pvalue

    return last_pvalue


def run_cycle(dry_run: bool = False):
    initialize_database()
    start = datetime.now(timezone.utc)
    logger.info(f"{'─'*60}")
    logger.info(f"🔄 Z-SCORE SPREAD CYCLE — {start.strftime('%Y-%m-%d %H:%M UTC')}")
    log_heartbeat("RUNNING", f"Iniciando ciclo en {start.strftime('%H:%M')}")
    broker = PaperBroker()

    # ── Sentimiento y contexto macro ──────────────────────────────────────────
    logger.info("📡 Obteniendo sentimiento y contexto macro...")
    sentiment  = get_market_sentiment()
    macro      = get_macro_context()
    event_near = is_high_impact_event_near()

    if macro:
        save_macro_context(macro)

    if event_near:
        logger.warning("⚠️ Evento macro de alto impacto cerca. Pausando nuevas entradas.")
        send_telegram("⚠️ <b>Precaución</b>: Evento macro detectado. Pausando nuevas entradas.")

    # ── Descargar datos BTC y ETH ─────────────────────────────────────────────
    logger.info(f"📡 Descargando {config.SPREAD_PAIR_A} y {config.SPREAD_PAIR_B} "
                f"({config.PRIMARY_TIMEFRAME}, {config.CANDLE_LIMIT} velas)...")
    market_data = fetch_all_pairs(
        [config.SPREAD_PAIR_A, config.SPREAD_PAIR_B],
        config.PRIMARY_TIMEFRAME,
        config.CANDLE_LIMIT
    )

    if config.SPREAD_PAIR_A not in market_data or config.SPREAD_PAIR_B not in market_data:
        msg = "❌ Sin datos de BTC o ETH — abortando ciclo"
        logger.error(msg)
        log_heartbeat("ERROR", "Falla crítica en descarga de datos")
        log_system_event("ERROR", msg)
        return

    df_btc = market_data[config.SPREAD_PAIR_A]
    df_eth = market_data[config.SPREAD_PAIR_B]
    logger.info(f"✅ BTC: {len(df_btc)} velas | ETH: {len(df_eth)} velas")

    # Guardar precios en DB
    all_prices = []
    all_prices.extend(dataframe_to_db_records(df_btc, config.SPREAD_PAIR_A, config.PRIMARY_TIMEFRAME))
    all_prices.extend(dataframe_to_db_records(df_eth, config.SPREAD_PAIR_B, config.PRIMARY_TIMEFRAME))
    if all_prices:
        save_prices(all_prices)

    # ── Calcular indicadores del spread ───────────────────────────────────────
    logger.info("📊 Calculando spread BTC/ETH (OLS + Z-Score + Hurst)...")
    spread_data = calculate_spread_indicators(df_btc, df_eth, config)

    if spread_data is None:
        msg = "❌ Error calculando spread — datos insuficientes"
        logger.error(msg)
        log_heartbeat("ERROR", msg)
        return

    z_score   = spread_data["z_score"]
    beta      = spread_data["beta"]
    hurst     = spread_data["hurst"]
    eth_price = spread_data["eth_price"]
    btc_price = spread_data["btc_price"]
    mu        = spread_data["mu"]
    sigma     = spread_data["sigma"]

    logger.info(f"📈 Z-Score: {z_score:+.3f} | β: {beta:.3f} | H: {hurst:.3f}")
    logger.info(f"   BTC: ${btc_price:>10,.2f} | ETH: ${eth_price:>8,.2f}")
    logger.info(f"   Spread μ={mu:.4f} σ={sigma:.4f} | RSI_ETH: {spread_data['eth_rsi']:.1f}")

    # ── Test de cointegración (cacheado 24h) ──────────────────────────────────
    coint_pvalue = _check_cointegration_cached(df_btc, df_eth)

    # ── Generar señal Z-Score ─────────────────────────────────────────────────
    sent_score = sentiment.get("CRYPTO", 0.0)
    signal = score_zscore_signal(spread_data, coint_pvalue, config, sent_score, macro)
    signal.update({
        "pair":      "BTC_ETH_SPREAD",
        "timeframe": config.PRIMARY_TIMEFRAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "price":     eth_price,
    })

    # Guardar señal en DB (para dashboard)
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
        "sentiment":   signal.get("sentiment", 0),
    })

    reasons_text = " | ".join(r["note"] for r in signal["reasons"])
    log_system_event("INFO", f"📊 BTC_ETH_SPREAD: Z={z_score:+.2f} | "
                             f"Score={signal['score']:.1f}/10 | {signal['direction']} | {reasons_text}")

    if signal["score"] >= config.MIN_SCORE_ALERT:
        logger.info(format_signal_summary("BTC_ETH_SPREAD", config.PRIMARY_TIMEFRAME, signal, eth_price))

    # ── Cerrar trades abiertos por Z-score ────────────────────────────────────
    closed = broker.close_spread_trade_by_zscore(z_score, eth_price)
    for c in closed:
        emoji = "✅" if c["pnl"] > 0 else "❌"
        send_telegram(
            f"{emoji} <b>Spread trade cerrado</b>\n"
            f"Razón: {c['reason']} | Z-Score: {z_score:+.2f}\n"
            f"P&L: <b>${c['pnl']:+.2f}</b> | Balance: ${broker.balance:,.2f}"
        )

    if closed:
        run_feedback_cycle()

    # ── Abrir nuevos trades ───────────────────────────────────────────────────
    if not dry_run and not event_near:
        daily_pnl      = get_daily_pnl()
        max_daily_loss = broker.balance * 0.05
        paused         = get_bot_config("TRADING_PAUSED", "false") == "true"
        signal_only    = get_bot_config("SIGNAL_ONLY_MODE", "false") == "true"
        dyn_min_score  = float(get_bot_config("MIN_SCORE_TO_TRADE", config.MIN_SCORE_TO_TRADE))

        if daily_pnl < -max_daily_loss:
            msg = f"🚨 PAUSADO: Drawdown diario máximo alcanzado (${daily_pnl:,.2f})"
            logger.warning(msg)
            process_bot_brain()
            log_heartbeat("PAUSED", msg)
            return

        if paused:
            logger.info("⏸️ Trading pausado por el cerebro — sin nuevas entradas")
        elif signal_only:
            # Modo señal: alertas para operación manual
            if signal["direction"] != "NEUTRAL" and signal["score"] >= dyn_min_score:
                r     = signal.get("reasons", [])
                notes = " | ".join(x["note"] for x in r[:2]) if r else ""
                sl    = signal.get("stop_loss")
                tp    = signal.get("take_profit")
                send_telegram(
                    f"📊 <b>SEÑAL MANUAL — BTC/ETH SPREAD</b>\n"
                    f"Dirección: <b>{signal['direction']}</b> | Z: {z_score:+.2f}\n"
                    f"Score: {signal['score']:.1f}/10 | ETH @ ${eth_price:,.2f}\n"
                    f"🛑 SL: ${sl:,.2f} | 🎯 TP: ${tp:,.2f}\n"
                    f"📌 {notes}"
                )
        else:
            # Modo autónomo
            if (signal["direction"] != "NEUTRAL"
                    and signal["score"] >= dyn_min_score
                    and broker.can_open_trade()):

                last_sigs = get_latest_signals(10)
                sig_id    = next(
                    (s["id"] for s in last_sigs if s["pair"] == "BTC_ETH_SPREAD"), 0
                )
                trade_id = broker.open_trade(
                    signal_id  = sig_id,
                    pair       = "BTC_ETH_SPREAD",
                    direction  = signal["direction"],
                    price      = eth_price,
                    stop_loss  = signal.get("stop_loss"),
                    take_profit= signal.get("take_profit"),
                )
                if trade_id:
                    r     = signal.get("reasons", [])
                    notes = " | ".join(x["note"] for x in r[:2]) if r else ""
                    dir_label = ("🟢 LONG SPREAD (BUY ETH)" if signal["direction"] == "BUY"
                                 else "🔴 SHORT SPREAD (SELL ETH)")
                    send_telegram(
                        f"🔔 <b>Spread Trade Abierto</b>\n"
                        f"{dir_label}\n"
                        f"Z-Score: {z_score:+.2f} | Score: {signal['score']:.1f}/10\n"
                        f"ETH @ ${eth_price:,.2f} | β={beta:.3f}\n"
                        f"📌 {notes}"
                    )

        process_bot_brain()

    # ── Resumen del ciclo ─────────────────────────────────────────────────────
    stats   = broker.stats()
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()

    dir_icon = {"BUY": "🟢 LONG", "SELL": "🔴 SHORT", "NEUTRAL": "⚪ NEUTRO"}.get(
        signal["direction"], "⚪"
    )
    open_count = len([t for t in broker.open_trades if t["pair"] == "BTC_ETH_SPREAD"])

    print(f"\n{'─'*60}")
    print(f"  BTC/ETH SPREAD — {dir_icon} | Score: {signal['score']:.1f}/10")
    print(f"  Z-Score: {z_score:+.3f} | H={hurst:.3f} | β={beta:.3f} | Coint p={coint_pvalue:.3f}")
    print(f"  BTC: ${btc_price:>10,.2f} | ETH: ${eth_price:>8,.2f}")
    print(f"  RSI ETH: {spread_data['eth_rsi']:.1f} | Vol ratio: "
          f"{spread_data['eth_volume']/spread_data['eth_volume_avg']:.0%}")
    print(f"{'─'*60}")
    print(f"  💼 Balance: ${stats['balance']:,.2f}  |  "
          f"Win Rate: {stats['win_rate']:.1f}%  |  "
          f"Spread abierto: {'Sí' if open_count else 'No'}")
    print(f"  ⏱  Completado en {elapsed:.1f}s\n")

    log_heartbeat("SUCCESS",
                  f"Z={z_score:+.2f} | {signal['direction']} | {elapsed:.1f}s")


def show_stats():
    initialize_database()
    from database import get_dashboard_data
    d = get_dashboard_data()
    print(f"""
╔══════════════════════════════════════╗
║  📊 Z-SCORE MEAN REVERSION — STATS  ║
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
    try:
        if   mode == "stats":   show_stats()
        elif mode == "dry-run": run_cycle(dry_run=True)
        else:                   run_cycle(dry_run=False)
    except Exception as _fatal:
        _msg = f"💥 Error fatal: {_fatal}"
        logger.error(_msg, exc_info=True)
        try:
            from database import initialize_database, log_system_event
            initialize_database()
            log_system_event("CRITICAL", _msg)
        except Exception:
            pass
        try:
            send_telegram(f"🚨 <b>Bot detenido por error crítico</b>\n<code>{_fatal}</code>")
        except Exception:
            pass
        sys.exit(0)
