"""
signals.py — Z-Score Mean Reversion Strategy — BTC/ETH Spread

Lógica matemática:
  spread  = log(ETH) - β × log(BTC)        β via OLS rolling (ventana 500)
  z_score = (spread - μ) / σ               μ/σ via rolling window 60

  Z < -2  → ETH barato relativo a BTC → LONG spread  (BUY  ETH + SHORT BTC)
  Z > +2  → ETH caro  relativo a BTC → SHORT spread (SELL ETH + LONG  BTC)
  |Z| < 0.5 → cerrar posición (reversión completada)
  |Z| > 3.5 → stop loss

Filtros obligatorios:
  1. Cointegración (Engle-Granger p < 0.05)
  2. Hurst Exponent (H < 0.45 → mean-reverting)
  3. Volumen mínimo (≥ 70% del avg-20)
  4. RSI de confirmación (< 35 para BUY, > 65 para SELL)
"""

import numpy as np
from database import get_bot_config


def _safe(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def score_zscore_signal(spread_data: dict, coint_pvalue: float,
                        config_obj, sentiment_score: float = 0.0,
                        macro_context: dict = None) -> dict:
    """
    Genera una señal de trading basada en Z-Score del spread BTC/ETH.

    Args:
        spread_data:    Dict con z_score, hurst, beta, mu, sigma, eth_price,
                        btc_price, eth_rsi, eth_volume, eth_volume_avg
        coint_pvalue:   P-value del test Engle-Granger (cacheado 24h)
        config_obj:     Módulo config con parámetros Z-score
        sentiment_score: Score VADER de noticias crypto (-1 a +1)
        macro_context:  Dict con risk_appetite (HIGH/NEUTRAL/LOW)

    Returns:
        Dict con direction (BUY/SELL/NEUTRAL), score 0-10, reasons, SL, TP
    """
    # ── Extraer datos del spread ─────────────────────────────────────────────
    z_score        = spread_data["z_score"]
    hurst          = spread_data["hurst"]
    eth_rsi        = spread_data["eth_rsi"]
    eth_volume     = spread_data["eth_volume"]
    eth_volume_avg = spread_data["eth_volume_avg"]
    eth_price      = spread_data["eth_price"]
    btc_price      = spread_data["btc_price"]
    mu             = spread_data["mu"]
    sigma          = spread_data["sigma"]
    beta           = spread_data["beta"]

    # ── Obtener parámetros dinámicos (el cerebro puede ajustarlos) ───────────
    entry_z      = _safe(get_bot_config("ZSCORE_ENTRY",      config_obj.ZSCORE_ENTRY))
    exit_z       = _safe(get_bot_config("ZSCORE_EXIT",       config_obj.ZSCORE_EXIT))
    stop_z       = _safe(get_bot_config("ZSCORE_STOP",       config_obj.ZSCORE_STOP))
    hurst_thresh = _safe(get_bot_config("HURST_THRESHOLD",   config_obj.HURST_THRESHOLD))
    vol_min_pct  = _safe(get_bot_config("VOLUME_MIN_PCT",    config_obj.VOLUME_MIN_PCT))
    rsi_buy      = _safe(get_bot_config("RSI_CONFIRM_BUY",   config_obj.RSI_CONFIRM_BUY))
    rsi_sell     = _safe(get_bot_config("RSI_CONFIRM_SELL",  config_obj.RSI_CONFIRM_SELL))
    coint_max_pv = _safe(get_bot_config("COINT_MAX_PVALUE",  config_obj.COINT_MAX_PVALUE))

    macro_mode = macro_context.get("risk_appetite", "NEUTRAL") if macro_context else "NEUTRAL"
    reasons    = []

    # ── FILTRO 0: Cointegración ──────────────────────────────────────────────
    if coint_pvalue > coint_max_pv:
        return _neutral(
            f"Par no cointegrado — p-value={coint_pvalue:.3f} > {coint_max_pv} "
            "(pausa obligatoria)", sentiment_score, score=0.0
        )
    reasons.append(f"Cointegración BTC/ETH confirmada (p={coint_pvalue:.4f})")

    # ── FILTRO 1: Hurst Exponent ─────────────────────────────────────────────
    if hurst >= hurst_thresh:
        return _neutral(
            f"Régimen trending — Hurst={hurst:.3f} ≥ {hurst_thresh} "
            "(requiere mercado mean-reverting)", sentiment_score, score=1.0
        )
    reasons.append(f"Régimen mean-reverting confirmado (H={hurst:.3f} < {hurst_thresh})")

    # ── FILTRO 2: Volumen mínimo ─────────────────────────────────────────────
    vol_ratio = eth_volume / eth_volume_avg if eth_volume_avg > 0 else 0.0
    if vol_ratio < vol_min_pct:
        return _neutral(
            f"Volumen ETH insuficiente ({vol_ratio:.0%} del avg-20 — mín {vol_min_pct:.0%})",
            sentiment_score, score=2.0
        )
    reasons.append(f"Volumen OK — {vol_ratio:.0%} del promedio de 20 períodos")

    # ── SEÑAL PRINCIPAL: Z-Score ─────────────────────────────────────────────
    if z_score <= -entry_z:
        direction = "BUY"   # ETH barato vs BTC → LONG spread
        reasons.append(
            f"Z-Score bajista extremo: {z_score:.2f} ≤ -{entry_z:.1f}σ "
            "— ETH barato relativo a BTC"
        )
    elif z_score >= entry_z:
        direction = "SELL"  # ETH caro vs BTC → SHORT spread
        reasons.append(
            f"Z-Score alcista extremo: {z_score:.2f} ≥ +{entry_z:.1f}σ "
            "— ETH caro relativo a BTC"
        )
    else:
        return _neutral(
            f"Z-Score en rango neutro: {z_score:.2f} (umbral ±{entry_z:.1f}σ)",
            sentiment_score, score=3.0
        )

    # ── FILTRO 3: RSI de confirmación ────────────────────────────────────────
    rsi_ok = False
    if direction == "BUY" and eth_rsi < rsi_buy:
        rsi_ok = True
        reasons.append(f"RSI ETH confirma sobrevendido: {eth_rsi:.1f} < {rsi_buy:.0f}")
    elif direction == "SELL" and eth_rsi > rsi_sell:
        rsi_ok = True
        reasons.append(f"RSI ETH confirma sobrecomprado: {eth_rsi:.1f} > {rsi_sell:.0f}")
    else:
        reasons.append(
            f"RSI ETH sin confirmar ({eth_rsi:.1f}) — señal válida pero menos convicción"
        )

    # ── Sentimiento y Macro ──────────────────────────────────────────────────
    if sentiment_score > 0.25 and direction == "BUY":
        reasons.append(f"Sentimiento crypto alcista ({sentiment_score:+.2f})")
    elif sentiment_score < -0.25 and direction == "SELL":
        reasons.append(f"Sentimiento crypto bajista ({sentiment_score:+.2f})")

    if (direction == "BUY" and macro_mode == "HIGH") or (direction == "SELL" and macro_mode == "LOW"):
        reasons.append(f"Macro acompaña la dirección ({macro_mode})")
    elif macro_mode == "NEUTRAL":
        reasons.append("Macro neutral — entrada con cautela")

    # ── Score final ──────────────────────────────────────────────────────────
    z_excess        = abs(abs(z_score) - entry_z)
    z_bonus         = min(z_excess * 0.5, 2.0)
    rsi_bonus       = 1.5 if rsi_ok else 0.0
    sentiment_bonus = 0.5 if any("entimiento" in r for r in reasons) else 0.0
    macro_bonus     = 0.5 if any("Macro" in r for r in reasons) else 0.0
    final_score     = min(5.0 + z_bonus + rsi_bonus + sentiment_bonus + macro_bonus, 10.0)

    # ── SL / TP en precio de ETH (asumiendo BTC constante para referencia) ───
    sl, tp = _calc_sl_tp(direction, z_score, entry_z, exit_z, stop_z,
                         mu, sigma, beta, eth_price, btc_price)

    return {
        "direction":        direction,
        "score":            round(final_score, 1),
        "reasons":          [{"note": r} for r in reasons],
        "stop_loss":        sl,
        "take_profit":      tp,
        "sentiment":        sentiment_score,
        "macro_mode":       macro_mode,
        "z_score":          z_score,
        "hurst":            hurst,
        "beta":             beta,
        "strategies_voted": {"ZScore": direction, "Hurst": "OK", "Coint": "OK"},
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _neutral(reason: str, sentiment: float, score: float = 0.0) -> dict:
    return {
        "direction":        "NEUTRAL",
        "score":            round(score, 1),
        "reasons":          [{"note": reason}],
        "stop_loss":        None,
        "take_profit":      None,
        "sentiment":        sentiment,
        "macro_mode":       "NEUTRAL",
        "z_score":          None,
        "hurst":            None,
        "beta":             None,
        "strategies_voted": {"ZScore": "NEUTRAL", "Hurst": "—", "Coint": "—"},
    }


def _calc_sl_tp(direction, z_score, entry_z, exit_z, stop_z,
                mu, sigma, beta, eth_price, btc_price):
    """
    Convierte los umbrales de Z-score a precios de ETH.
    Fórmula: spread_target = μ + z_target × σ
             log(ETH_target) = spread_target + β × log(BTC)
             ETH_target = exp(spread_target + β × log(BTC))
    """
    log_btc = np.log(btc_price)

    def z_to_eth(z_target):
        spread_t = mu + z_target * sigma
        return float(np.exp(spread_t + beta * log_btc))

    try:
        if direction == "BUY":
            # Spread sube desde Z ≈ -2 hasta Z = -0.5 (ETH sube)
            tp = z_to_eth(-exit_z)
            sl = z_to_eth(-stop_z)
            # Validación: TP > entry > SL
            if tp <= eth_price or sl >= eth_price:
                tp = round(eth_price * 1.04, 2)
                sl = round(eth_price * 0.96, 2)
        else:  # SELL
            # Spread baja desde Z ≈ +2 hasta Z = +0.5 (ETH baja)
            tp = z_to_eth(exit_z)
            sl = z_to_eth(stop_z)
            # Validación: TP < entry < SL
            if tp >= eth_price or sl <= eth_price:
                tp = round(eth_price * 0.96, 2)
                sl = round(eth_price * 1.04, 2)
    except Exception:
        if direction == "BUY":
            tp = round(eth_price * 1.04, 2)
            sl = round(eth_price * 0.96, 2)
        else:
            tp = round(eth_price * 0.96, 2)
            sl = round(eth_price * 1.04, 2)

    return round(sl, 2), round(tp, 2)


def format_signal_summary(pair: str, timeframe: str, signal: dict, price: float) -> str:
    icon = {"BUY": "🟢", "SELL": "🔴", "NEUTRAL": "⚪"}.get(signal["direction"], "⚪")
    z    = signal.get("z_score")
    h    = signal.get("hurst")
    z_str = f"Z={z:.2f}" if z is not None else "Z=?"
    h_str = f"H={h:.3f}" if h is not None else "H=?"
    notes = " | ".join(r["note"] for r in signal["reasons"][:2])
    return (
        f"{icon} {pair} ({timeframe}) | Score: {signal['score']:.1f}/10 "
        f"[{z_str} {h_str}] | ETH: ${price:,.2f} | {notes}"
    )
