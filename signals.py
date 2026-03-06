"""
signals.py — Motor Multi-Estrategia

Tres estrategias independientes evaluadas por par:
  B_EMA_PULLBACK  — Pullback a EMA en tendencia (original, mejorada)
  R_RSI_EXTREME   — Rebote/rechazo desde extremos de RSI con confirmación
  M_MACD_MOMENTUM — Cruce de histograma MACD con volumen

El cerebro (brain.py) puede activar/desactivar estrategias según rendimiento.
El score final refleja qué tan alineados están todos los factores.
"""

from datetime import datetime
from database import get_bot_config


def _safe(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


# ── Strategy B: EMA Pullback ──────────────────────────────────────────────────

def _strategy_B(vals: dict) -> tuple[str, list[str], float]:
    """
    Pullback a la EMA en contexto de tendencia definida.
    Requiere: tendencia clara en EMA200/EMA50, precio que toca EMA20 o EMA50,
              RSI no sobrecomprado/sobrevendido en exceso.
    """
    price    = _safe(vals.get("price"))
    ema_20   = _safe(vals.get("ema_20"))
    ema_50   = _safe(vals.get("ema_50"))
    ema_200  = _safe(vals.get("ema_200"))
    rsi      = _safe(vals.get("rsi"), 50)
    macd_h   = _safe(vals.get("macd_hist"))
    bb_lower = _safe(vals.get("bb_lower"))
    bb_upper = _safe(vals.get("bb_upper"))
    bb_mid   = _safe(vals.get("bb_mid"))

    if not all([price, ema_50, rsi]):
        return "NEUTRAL", [], 0.0

    confluences = []
    direction = "NEUTRAL"

    # Determinar tendencia principal (usando EMA200 si disponible, sino EMA50)
    if ema_200 and ema_200 > 0:
        trend_up = price > ema_200 and ema_50 > ema_200
        trend_dn = price < ema_200 and ema_50 < ema_200
    else:
        trend_up = price > ema_50 and (ema_20 > ema_50 if ema_20 else True)
        trend_dn = price < ema_50 and (ema_20 < ema_50 if ema_20 else True)

    # Zona de pullback: precio tocando EMA20 o EMA50 (dentro de 0.3%)
    near_ema20 = ema_20 > 0 and abs(price - ema_20) / price < 0.003
    near_ema50 = ema_50 > 0 and abs(price - ema_50) / price < 0.004

    if trend_up and (near_ema20 or near_ema50):
        if 25 < rsi < 55:  # RSI vendido o neutro, no sobrecomprado
            direction = "BUY"
            confluences.append(f"B: Pullback a {'EMA20' if near_ema20 else 'EMA50'} en tendencia alcista")
            if ema_200 and price > ema_200:
                confluences.append("B: EMA200 confirma tendencia alcista mayor")
            if macd_h > 0:
                confluences.append("B: MACD apoya el impulso alcista")
            if bb_lower and price < bb_mid:
                confluences.append("B: Precio en zona baja de Bollinger — soporte potencial")

    elif trend_dn and (near_ema20 or near_ema50):
        if 45 < rsi < 75:  # RSI comprado o neutro, no sobrevendido
            direction = "SELL"
            confluences.append(f"B: Pullback a {'EMA20' if near_ema20 else 'EMA50'} en tendencia bajista")
            if ema_200 and price < ema_200:
                confluences.append("B: EMA200 confirma tendencia bajista mayor")
            if macd_h < 0:
                confluences.append("B: MACD apoya el impulso bajista")
            if bb_upper and price > bb_mid:
                confluences.append("B: Precio en zona alta de Bollinger — resistencia potencial")

    quality = len(confluences) / 4.0  # 4 máx confluencias
    return direction, confluences, quality


# ── Strategy R: RSI Extreme Reversal ─────────────────────────────────────────

def _strategy_R(vals: dict) -> tuple[str, list[str], float]:
    """
    Rebote desde extremos de RSI con confirmación de precio.
    RSI < 30 → posible rebote alcista / RSI > 70 → posible rechazo bajista.
    Requiere confirmación adicional (Bollinger Bands + MACD).
    """
    price    = _safe(vals.get("price"))
    rsi      = _safe(vals.get("rsi"), 50)
    macd_h   = _safe(vals.get("macd_hist"))
    bb_lower = _safe(vals.get("bb_lower"))
    bb_upper = _safe(vals.get("bb_upper"))
    ema_50   = _safe(vals.get("ema_50"))

    if not all([price, rsi]):
        return "NEUTRAL", [], 0.0

    confluences = []
    direction = "NEUTRAL"

    # RSI sobrevendido → buscar rebote alcista
    if rsi < 28:
        direction = "BUY"
        confluences.append(f"R: RSI sobrevendido ({rsi:.1f}) — potencial rebote")
        if bb_lower and price <= bb_lower * 1.002:
            confluences.append("R: Precio en o debajo de Bollinger inferior — soporte estadístico")
        if macd_h > 0 or macd_h > -0.0001:  # MACD virando o positivo
            confluences.append("R: MACD virando positivo — confirmación de momentum")
        if ema_50 and price > ema_50 * 0.98:  # No demasiado lejos de EMA50
            confluences.append("R: Precio cerca de soporte EMA50")

    # RSI sobrecomprado → buscar rechazo bajista
    elif rsi > 72:
        direction = "SELL"
        confluences.append(f"R: RSI sobrecomprado ({rsi:.1f}) — potencial rechazo")
        if bb_upper and price >= bb_upper * 0.998:
            confluences.append("R: Precio en o encima de Bollinger superior — resistencia estadística")
        if macd_h < 0 or macd_h < 0.0001:  # MACD virando o negativo
            confluences.append("R: MACD virando negativo — confirmación de debilidad")
        if ema_50 and price < ema_50 * 1.02:
            confluences.append("R: Precio cerca de resistencia EMA50")

    quality = len(confluences) / 4.0
    return direction, confluences, quality


# ── Strategy M: MACD Momentum ─────────────────────────────────────────────────

def _strategy_M(vals: dict) -> tuple[str, list[str], float]:
    """
    Cruce de histograma MACD con confirmación de tendencia y volumen.
    Busca el cambio de signo del histograma con el precio bien posicionado.
    """
    price   = _safe(vals.get("price"))
    macd    = _safe(vals.get("macd"))
    macd_h  = _safe(vals.get("macd_hist"))
    macd_s  = _safe(vals.get("macd_signal"))
    rsi     = _safe(vals.get("rsi"), 50)
    ema_20  = _safe(vals.get("ema_20"))
    ema_50  = _safe(vals.get("ema_50"))
    volume  = _safe(vals.get("volume"))

    if not all([price, macd, macd_s]):
        return "NEUTRAL", [], 0.0

    confluences = []
    direction = "NEUTRAL"

    # Cruce alcista: MACD cruza por encima de señal (histograma positivo y creciendo)
    if macd > macd_s and macd_h > 0:
        if 35 < rsi < 65:  # RSI en zona media — momentum sin exceso
            direction = "BUY"
            confluences.append(f"M: MACD cruzó al alza (hist: {macd_h:.5f})")
            if ema_20 and price > ema_20:
                confluences.append("M: Precio sobre EMA20 confirma momentum")
            if ema_50 and price > ema_50:
                confluences.append("M: Precio sobre EMA50 — tendencia de fondo alcista")
            if volume and volume > 0:
                confluences.append("M: Volumen presente en el movimiento")

    # Cruce bajista: MACD cruza por debajo de señal (histograma negativo)
    elif macd < macd_s and macd_h < 0:
        if 35 < rsi < 65:
            direction = "SELL"
            confluences.append(f"M: MACD cruzó a la baja (hist: {macd_h:.5f})")
            if ema_20 and price < ema_20:
                confluences.append("M: Precio bajo EMA20 confirma debilidad")
            if ema_50 and price < ema_50:
                confluences.append("M: Precio bajo EMA50 — tendencia de fondo bajista")
            if volume and volume > 0:
                confluences.append("M: Volumen en la caída")

    quality = len(confluences) / 4.0
    return direction, confluences, quality


# ── Motor de señal integrado ─────────────────────────────────────────────────

def score_signal(vals: dict, config_obj, sentiment_score: float = 0.0,
                 macro_context: dict = None) -> dict:
    """
    Evalúa las 3 estrategias y construye el score final por confluencia global.
    
    El cerebro puede deshabilitar una estrategia escribiendo en bot_config.
    El score final = weighted sum de estrategias activas + sentiment + macro.
    """
    price = _safe(vals.get("price"))
    atr   = _safe(vals.get("atr"), 0.001)

    if not price:
        return {"direction": "NEUTRAL", "score": 0, "reasons": [{"note": "Sin datos de precio"}]}

    # ── Obtener configuración dinámica del cerebro ───────────────────────────
    dyn_sl_atr = _safe(get_bot_config("STOP_LOSS_ATR", config_obj.STOP_LOSS_ATR))
    # Aplicar límites de seguridad siempre
    dyn_sl_atr = max(0.8, min(dyn_sl_atr, 3.0))

    dyn_tp_r   = _safe(get_bot_config("TAKE_PROFIT_R", config_obj.TAKE_PROFIT_R))
    dyn_tp_r   = max(2.0, dyn_tp_r)

    active_strategy = get_bot_config("ACTIVE_STRATEGY", "ALL")

    # ── Evaluar cada estrategia ──────────────────────────────────────────────
    b_dir, b_conf, b_qual = _strategy_B(vals)
    r_dir, r_conf, r_qual = _strategy_R(vals)
    m_dir, m_conf, m_qual = _strategy_M(vals)

    # Filtrar por estrategia activa si el cerebro forzó una
    if active_strategy != "ALL":
        if active_strategy == "B_EMA_PULLBACK":
            r_dir, r_conf, r_qual = "NEUTRAL", [], 0.0
            m_dir, m_conf, m_qual = "NEUTRAL", [], 0.0
        elif active_strategy == "R_RSI_EXTREME":
            b_dir, b_conf, b_qual = "NEUTRAL", [], 0.0
            m_dir, m_conf, m_qual = "NEUTRAL", [], 0.0
        elif active_strategy == "M_MACD_MOMENTUM":
            b_dir, b_conf, b_qual = "NEUTRAL", [], 0.0
            r_dir, r_conf, r_qual = "NEUTRAL", [], 0.0

    # ── Consenso de estrategias ──────────────────────────────────────────────
    directions = [d for d in [b_dir, r_dir, m_dir] if d != "NEUTRAL"]
    all_confluences = b_conf + r_conf + m_conf

    if not directions:
        direction = "NEUTRAL"
    else:
        buy_count  = directions.count("BUY")
        sell_count = directions.count("SELL")
        # Consenso: mayoría de estrategias activas deben estar de acuerdo
        if buy_count > sell_count:
            direction = "BUY"
        elif sell_count > buy_count:
            direction = "SELL"
        else:
            # Empate 1-1 en direcciones contrarias → neutralizar
            direction = "NEUTRAL"
            all_confluences = []

    # Excluir confluencias de la dirección contraria
    if direction == "BUY":
        all_confluences = [c for c in all_confluences if "bajist" not in c.lower() and "baja" not in c.lower()]
    elif direction == "SELL":
        all_confluences = [c for c in all_confluences if "alcist" not in c.lower() and "alza" not in c.lower()]

    # ── Sentimiento ──────────────────────────────────────────────────────────
    macro_mode = "NEUTRAL"
    if macro_context:
        macro_mode = macro_context.get("risk_appetite", "NEUTRAL")

    if sentiment_score > 0.25 and direction == "BUY":
        all_confluences.append(f"Sentimiento alcista ({sentiment_score:+.2f})")
    elif sentiment_score < -0.25 and direction == "SELL":
        all_confluences.append(f"Sentimiento bajista ({sentiment_score:+.2f})")

    if (direction == "BUY" and macro_mode == "HIGH") or (direction == "SELL" and macro_mode == "LOW"):
        all_confluences.append(f"Macro acompaña ({macro_mode})")
    elif direction != "NEUTRAL" and macro_mode == "NEUTRAL":
        all_confluences.append("Macro neutral (entrada con cautela)")

    # ── Score final ──────────────────────────────────────────────────────────
    # Mínimo 3 confluencias para generar señal, score máximo 10
    if direction == "NEUTRAL" or len(all_confluences) < 3:
        direction = "NEUTRAL"
        final_score = float(len(all_confluences)) * 1.5  # Score parcial informativo
    else:
        # Base: 2 pts por confluencia, cap 10
        base = min(len(all_confluences) * 2.0, 8.0)
        # Bonus por consenso múltiple de estrategias
        strategy_bonus = min((len(directions) - 1) * 1.0, 2.0)
        final_score = min(base + strategy_bonus, 10.0)

    # ── SL / TP ──────────────────────────────────────────────────────────────
    stop_loss = take_profit = None
    if direction == "BUY":
        stop_loss   = price - (atr * dyn_sl_atr)
        take_profit = price + (abs(price - stop_loss) * dyn_tp_r)
    elif direction == "SELL":
        stop_loss   = price + (atr * dyn_sl_atr)
        take_profit = price - (abs(price - stop_loss) * dyn_tp_r)

    return {
        "direction":   direction,
        "score":       round(final_score, 1),
        "reasons":     [{"note": c} for c in all_confluences] if all_confluences
                       else [{"note": "Sin confluencias suficientes"}],
        "stop_loss":   stop_loss,
        "take_profit": take_profit,
        "sentiment":   sentiment_score,
        "macro_mode":  macro_mode,
        "strategies_voted": {
            "B": b_dir, "R": r_dir, "M": m_dir
        }
    }


def format_signal_summary(pair: str, timeframe: str, signal: dict, price: float) -> str:
    emoji = {"BUY": "🟢", "SELL": "🔴", "NEUTRAL": "⚪"}.get(signal["direction"], "⚪")
    votes = signal.get("strategies_voted", {})
    vote_str = f"[B:{votes.get('B','?')} R:{votes.get('R','?')} M:{votes.get('M','?')}]"
    notes = " | ".join(r["note"] for r in signal["reasons"][:2])
    return (
        f"{emoji} {pair} ({timeframe}) | Score: {signal['score']:.1f}/10 "
        f"{vote_str} | Precio: {price:.4g} | {notes}"
    )
