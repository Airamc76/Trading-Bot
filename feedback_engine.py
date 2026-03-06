"""
feedback_engine.py — Motor de Post-Mortem Real

Analiza cada trade cerrado con profundidad real:
- Clasifica la causa de la pérdida (no texto genérico)
- Evalúa si el SL/TP estaba correctamente dimensionado
- Detecta patrones entre trades (no analiza cada uno en aislamiento)
- Genera lecciones específicas con datos concretos
"""

import logging
from datetime import datetime, timezone
from database import db, save_trade_feedback, get_bot_config, set_bot_config

logger = logging.getLogger(__name__)


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _classify_loss(trade: dict) -> tuple[str, str, float]:
    """
    Clasifica la causa de una pérdida y genera una lección específica.
    
    Returns:
        (classification, lesson, performance_score)
    """
    pnl        = _safe_float(trade.get("pnl"))
    pnl_pct    = _safe_float(trade.get("pnl_pct"))
    reason     = trade.get("close_reason", "UNKNOWN")
    pair       = trade.get("pair", "UNKNOWN")
    direction  = trade.get("direction", "UNKNOWN")
    open_price = _safe_float(trade.get("open_price"))
    close_price = _safe_float(trade.get("close_price"))
    sl         = _safe_float(trade.get("stop_loss"))
    tp         = _safe_float(trade.get("take_profit"))

    if pnl > 0:
        return _classify_win(trade)

    # ── Clasificación de pérdida ──────────────────────────────────────────────
    
    # Calcular distancias relativas
    sl_distance_pct = abs(open_price - sl) / open_price * 100 if open_price > 0 and sl > 0 else 0
    tp_distance_pct = abs(tp - open_price) / open_price * 100 if open_price > 0 and tp > 0 else 0
    move_pct        = abs(close_price - open_price) / open_price * 100 if open_price > 0 else 0

    # ── Caso 1: SL muy ajustado (el precio casi ni se movió) ─────────────────
    if sl_distance_pct > 0 and move_pct < sl_distance_pct * 0.5:
        classification = "FALSE_SIGNAL"
        lesson = (
            f"Pérdida en {pair} ({direction}): El precio se movió solo {move_pct:.2f}% "
            f"antes de tocar el SL ({sl_distance_pct:.2f}%). La señal técnica fue falsa — "
            f"el mercado no tenía momentum real. Necesito mayor confirmación de volumen antes de entrar."
        )
        score = 3.0

    # ── Caso 2: SL extremadamente ajustado (rango normal de vela) ────────────
    elif sl_distance_pct < 0.3:
        classification = "SL_TOO_TIGHT"
        lesson = (
            f"Pérdida en {pair}: SL a solo {sl_distance_pct:.2f}% del precio de entrada. "
            f"Este SL es más pequeño que el ruido normal de mercado (spread + volatilidad). "
            f"Con el ATR actual, el SL mínimo debería ser al menos 0.5-1% del precio."
        )
        score = 2.5

    # ── Caso 3: Trade fue en la dirección equivocada desde el inicio ─────────
    elif pnl_pct < -2.0:
        classification = "WRONG_DIRECTION"
        direction_str = "alcista" if direction == "BUY" else "bajista"
        lesson = (
            f"Pérdida significativa en {pair}: -{abs(pnl_pct):.1f}%. "
            f"El sesgo {direction_str} estaba equivocado. El precio se fue {move_pct:.2f}% "
            f"en contra desde la apertura. Revisar alineación con la tendencia mayor antes de entrar."
        )
        score = 2.0

    # ── Caso 4: Pérdida moderada — señal débil ────────────────────────────────
    elif sl_distance_pct > 0 and sl_distance_pct <= 1.0:
        classification = "WEAK_SIGNAL"
        lesson = (
            f"Pérdida moderada en {pair} ({direction}): {pnl_pct:.1f}%. "
            f"La relación SL/TP era {tp_distance_pct/sl_distance_pct:.1f}:1. "
            f"señal de score moderado que no tuvo el momentum necesario para alcanzar el TP."
        )
        score = 3.5

    else:
        classification = "MARKET_REVERSAL"
        lesson = (
            f"Pérdida en {pair} ({direction}): P&L {pnl_pct:.1f}%. "
            f"El precio se movió inicialmente a favor pero revirtió. "
            f"Posible entrada en techo/suelo o news de alto impacto no anticipada."
        )
        score = 3.0

    return classification, lesson, score


def _classify_win(trade: dict) -> tuple[str, str, float]:
    """Clasifica y genera lección para un trade ganador."""
    pnl        = _safe_float(trade.get("pnl"))
    pnl_pct    = _safe_float(trade.get("pnl_pct"))
    reason     = trade.get("close_reason", "TP_HIT")
    pair       = trade.get("pair", "UNKNOWN")
    direction  = trade.get("direction", "UNKNOWN")
    open_price = _safe_float(trade.get("open_price"))
    tp         = _safe_float(trade.get("take_profit"))
    sl         = _safe_float(trade.get("stop_loss"))

    tp_dist = abs(tp - open_price) / open_price * 100 if open_price > 0 and tp > 0 else 0
    sl_dist = abs(open_price - sl) / open_price * 100 if open_price > 0 and sl > 0 else 0
    rr_ratio = tp_dist / sl_dist if sl_dist > 0 else 0

    if reason == "TP_HIT" and pnl_pct > 1.5:
        lesson = (
            f"Éxito en {pair} ({direction}): +{pnl_pct:.1f}% (${pnl:.2f}). "
            f"TP alcanzado con ratio R:R real de {rr_ratio:.1f}:1. "
            f"La confluencia técnica funcionó como esperado."
        )
        score = 9.0
    elif reason == "TP_HIT":
        lesson = (
            f"Ganancia en {pair}: +{pnl_pct:.1f}% (${pnl:.2f}). "
            f"TP alcanzado. Señal sólida con ejecución correcta."
        )
        score = 8.0
    else:
        lesson = (
            f"Ganancia en {pair}: +{pnl_pct:.1f}% (${pnl:.2f}). "
            f"Cerrado por {reason}. El trade fue rentable aunque no tocó el TP."
        )
        score = 6.5

    return "WIN", lesson, score


def _detect_systemic_patterns():
    """
    Analiza patrones entre múltiples trades para detectar problemas sistémicos.
    Registra hallazgos en bot_memory para que el brain actúe sobre ellos.
    """
    d = db()

    # ¿Todas las pérdidas son por SL_HIT?
    recent_losses = d.query("""
        SELECT close_reason, COUNT(*) as cnt
        FROM paper_trades
        WHERE status = 'LOSS' AND close_reason IS NOT NULL
        GROUP BY close_reason
        ORDER BY cnt DESC
        LIMIT 5
    """)

    if not recent_losses:
        return

    total_losses = sum(int(r["cnt"]) for r in recent_losses)
    top_reason = recent_losses[0]

    if total_losses >= 5:
        top_pct = int(top_reason["cnt"]) / total_losses * 100
        if top_pct > 70:
            # Detectar si el SL es el problema dominante
            if top_reason["close_reason"] == "SL_HIT":
                # Analizar qué tan pronto se toca el SL
                avg_duration = d.query("""
                    SELECT AVG(
                        CAST((julianday(close_time) - julianday(open_time)) * 24 * 60 AS REAL)
                    ) as avg_minutes
                    FROM paper_trades
                    WHERE status = 'LOSS' AND close_reason = 'SL_HIT'
                    AND close_time IS NOT NULL AND open_time IS NOT NULL
                """)
                avg_min = _safe_float(avg_duration[0]["avg_minutes"] if avg_duration else None)

                # Solo escribir en bot_memory si aún no está escrito recientemente
                existing = d.query(
                    "SELECT id FROM bot_memory WHERE category = 'SYSTEMIC_SL' "
                    "AND timestamp > datetime('now', '-6 hours')"
                )
                if not existing:
                    note = (
                        f"Patrón sistémico: {top_pct:.0f}% de mis pérdidas ({int(top_reason['cnt'])}/{total_losses}) "
                        f"son por Stop Loss tocado. Duración promedio antes del SL: {avg_min:.0f} min. "
                    )
                    if avg_min < 30:
                        note += (
                            "El SL se toca en menos de 30 minutos — las entradas están en zonas de "
                            "alta volatilidad intraday. Necesito entrar en zonas de soporte/resistencia más claras."
                        )
                    else:
                        note += (
                            "El SL es eventualmente alcanzado — el tamaño del SL es adecuado "
                            "pero la dirección del trade es incorrecta. Revisar bias de tendencia."
                        )
                    d.execute(
                        "INSERT INTO bot_memory (category, note, impact) VALUES (?, ?, ?)",
                        ["SYSTEMIC_SL", note, "NEGATIVE"]
                    )
                    d.commit()


def analyze_closed_trade(trade: dict):
    """
    Analiza un trade cerrado y genera una lección aprendida real.
    """
    classification, lesson, score = _classify_loss(trade)
    save_trade_feedback(trade["id"], lesson, score)
    logger.info(
        f"🧠 Post-mortem #{trade['id']} [{classification}] "
        f"Score:{score:.1f} — {lesson[:80]}..."
    )

    # Guardar clasificación para análisis sistémico
    try:
        d = db()
        d.execute(
            "INSERT OR IGNORE INTO strategy_performance "
            "(strategy, pair, result, pnl) VALUES (?, ?, ?, ?)",
            [
                get_bot_config("ACTIVE_STRATEGY", "B_EMA_PULLBACK"),
                trade.get("pair", "UNKNOWN"),
                "WIN" if _safe_float(trade.get("pnl")) > 0 else "LOSS",
                _safe_float(trade.get("pnl"))
            ]
        )
        d.commit()
    except Exception as e:
        logger.debug(f"No se pudo guardar en strategy_performance: {e}")


def run_feedback_cycle():
    """
    Procesa todos los trades cerrados sin feedback y analiza patrones sistémicos.
    """
    d = db()
    pending = d.query(
        "SELECT t.* FROM paper_trades t "
        "LEFT JOIN trade_feedback f ON t.id = f.trade_id "
        "WHERE t.status IN ('WIN', 'LOSS') AND f.id IS NULL"
    )

    if pending:
        logger.info(f"🧠 Procesando post-mortem para {len(pending)} trade(s)...")
        for trade in pending:
            try:
                analyze_closed_trade(trade)
            except Exception as e:
                logger.error(f"Error analizando trade #{trade.get('id')}: {e}")

    # Siempre analizar patrones sistémicos (aunque no haya nuevos trades)
    try:
        _detect_systemic_patterns()
    except Exception as e:
        logger.debug(f"Error en análisis sistémico: {e}")
