"""
brain.py — Motor de Conciencia Autónoma Real

El bot analiza su propia historia de trades, métricas reales, y
genera pensamientos únicos y accionables basados en datos concretos.

Principios:
  1. NUNCA generar el mismo pensamiento dos veces.
  2. Cada pensamiento debe contener números/datos reales extraídos de la DB.
  3. Las acciones deben ser medidas, con límites concretos para evitar loops.
  4. El bot puede cambiar de estrategia activa basado en rendimiento real.
"""

import logging
import json
import hashlib
import statistics
from datetime import datetime, timezone, timedelta
from database import db, get_bot_config, set_bot_config, update_monthly_metrics
from llm_brain import run_llm_brain_cycle
from improvement_engine import run_improvement_engine

logger = logging.getLogger(__name__)

# ── Constantes de seguridad ─────────────────────────────────────────────────
ATR_MIN   = 0.8   # Mínimo Stop Loss ATR
ATR_MAX   = 3.0   # Máximo Stop Loss ATR (previene el bug de 87x que existía)
ATR_DEFAULT = 1.2

STRATEGIES = ["ZSCORE_MEAN_REVERSION"]
ZSCORE_STRATEGY = "ZSCORE_MEAN_REVERSION"
COOLDOWN_HOURS = 1  # No repetir un mismo tipo de pensamiento en N horas


# ── Helpers ──────────────────────────────────────────────────────────────────

def _thought_hash(text: str) -> str:
    """Hash corto para identificar pensamientos únicos."""
    return hashlib.md5(text.encode()).hexdigest()[:12]


def _was_thought_recently(category: str, hours: int = COOLDOWN_HOURS) -> bool:
    """Verifica si ya se registró un pensamiento similar reciente."""
    d = db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = d.query(
        "SELECT id FROM bot_memory WHERE category = ? AND timestamp > ? ORDER BY id DESC LIMIT 1",
        [category, cutoff]
    )
    return bool(rows)


def _record_thought(category: str, note: str, impact: str = "NEUTRAL"):
    """Guarda un pensamiento único en la memoria del bot."""
    d = db()
    # Verificar que no sea un duplicado exacto
    existing = d.query(
        "SELECT id FROM bot_memory WHERE note = ? ORDER BY id DESC LIMIT 1",
        [note]
    )
    if existing:
        logger.debug(f"🧠 Pensamiento duplicado suprimido: {note[:60]}...")
        return False

    d.execute(
        "INSERT INTO bot_memory (category, note, impact) VALUES (?, ?, ?)",
        [category, note, impact]
    )
    d.commit()
    logger.info(f"🧠 [{category}] {note}")
    return True


def _record_action(description: str):
    """Registra una acción autónoma tomada por el bot."""
    d = db()
    exists = d.query(
        "SELECT id FROM bot_wishes WHERE wish = ? AND status = 'ACTION' "
        "AND timestamp > ?",
        [description, (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()]
    )
    if not exists:
        d.execute(
            "INSERT INTO bot_wishes (wish, status) VALUES (?, 'ACTION')",
            [description]
        )
        d.commit()
        logger.info(f"⚡ Acción autónoma: {description}")


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


# ── Módulos de análisis ──────────────────────────────────────────────────────

def _analyze_win_rate_and_strategy(d) -> dict:
    """
    Analiza el win rate real de los últimos N trades y genera reflexiones
    específicas con datos concretos. Cambia la estrategia activa si hay evidencia.
    """
    recent = d.query(
        "SELECT pair, direction, status, pnl, pnl_pct, open_time, close_time, "
        "close_reason FROM paper_trades WHERE status != 'OPEN' ORDER BY id DESC LIMIT 20"
    )
    if not recent:
        return {}

    total = len(recent)
    wins  = [t for t in recent if t["status"] == "WIN"]
    losses = [t for t in recent if t["status"] == "LOSS"]
    win_rate  = len(wins) / total * 100
    avg_pnl   = sum(_safe_float(t["pnl"]) for t in recent) / total
    avg_loss  = sum(_safe_float(t["pnl"]) for t in losses) / len(losses) if losses else 0
    avg_win   = sum(_safe_float(t["pnl"]) for t in wins)  / len(wins)  if wins  else 0

    # Detectar racha de pérdidas consecutivas
    streak = 0
    for t in recent:
        if t["status"] == "LOSS":
            streak += 1
        else:
            break

    result = {
        "total": total, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "avg_pnl": avg_pnl, "avg_loss": avg_loss,
        "avg_win": avg_win, "loss_streak": streak
    }

    # ── Racha de pérdidas ────────────────────────────────────────────────────
    if streak >= 4 and not _was_thought_recently("TILT_ALERT", hours=4):
        _record_thought(
            "TILT_ALERT",
            f"ALERTA: Llevo {streak} pérdidas consecutivas con P&L promedio de "
            f"${avg_loss:.2f} por operación. El mercado está rechazando mis entradas. "
            f"Reduciendo el score mínimo para operar y esperando confluencia más fuerte.",
            "NEGATIVE"
        )
        # Subir el umbral de score para ser más selectivo
        current_min = _safe_float(get_bot_config("MIN_SCORE_TO_TRADE", 5.0))
        new_min = min(current_min + 0.5, 8.0)
        set_bot_config("MIN_SCORE_TO_TRADE", str(round(new_min, 1)))
        _record_action(
            f"Subí el score mínimo de entrada de {current_min:.1f} a {new_min:.1f}/10 "
            f"tras {streak} pérdidas seguidas. Esperaré señales con mayor confluencia."
        )

    # ── Win rate crítico ────────────────────────────────────────────────────
    elif win_rate < 30 and total >= 5 and not _was_thought_recently("WIN_RATE_CRITICAL", hours=3):
        ratio = avg_win / abs(avg_loss) if avg_loss != 0 else 0
        _record_thought(
            "WIN_RATE_CRITICAL",
            f"Win rate: {win_rate:.1f}% en {total} trades del spread BTC/ETH. "
            f"Ganancia media: ${avg_win:.2f}, pérdida media: ${avg_loss:.2f}. "
            f"Ratio recompensa/riesgo real: {ratio:.2f}x. "
            f"El Z-Score puede estar teniendo falsos positivos — revisar cointegración y Hurst.",
            "NEGATIVE"
        )

    # ── Win rate recuperándose ──────────────────────────────────────────────
    elif win_rate >= 50 and len(wins) >= 3 and not _was_thought_recently("WIN_RATE_IMPROVING", hours=6):
        _record_thought(
            "WIN_RATE_IMPROVING",
            f"El rendimiento mejora: {win_rate:.1f}% win rate en los últimos {total} trades. "
            f"Ganancia promedio: ${avg_win:.2f}. La estrategia actual está generando resultados positivos.",
            "POSITIVE"
        )
        # Bajar el umbral si lo habíamos subido
        current_min = _safe_float(get_bot_config("MIN_SCORE_TO_TRADE", 5.0))
        if current_min > 6.0:
            new_min = max(current_min - 0.5, 5.5)
            set_bot_config("MIN_SCORE_TO_TRADE", str(round(new_min, 1)))
            _record_action(
                f"Recuperando selectividad normal: bajando score mínimo de "
                f"{current_min:.1f} a {new_min:.1f}/10 tras mejora en resultados."
            )

    return result


def _analyze_atr_and_stop_loss(d, win_rate: float):
    """
    Con Z-Score Mean Reversion, el SL se define por el umbral ZSCORE_STOP (3.5σ).
    Este módulo ajusta MIN_SCORE_TO_TRADE en función del win rate para ser
    más selectivo cuando el rendimiento es bajo.
    """
    if _was_thought_recently("SCORE_ADJUSTMENT", hours=3):
        return

    current_min = _safe_float(get_bot_config("MIN_SCORE_TO_TRADE", 5.0))

    if win_rate < 35 and current_min < 7.0:
        new_min = round(min(current_min + 0.5, 7.5), 1)
        set_bot_config("MIN_SCORE_TO_TRADE", str(new_min))
        _record_thought(
            "SCORE_ADJUSTMENT",
            f"Win rate del spread: {win_rate:.1f}%. Subiendo umbral de score "
            f"de {current_min} a {new_min}/10 para exigir más confluencia Z-Score.",
            "NEUTRAL"
        )
        _record_action(f"Score mínimo ajustado: {current_min} → {new_min}/10 (win rate bajo: {win_rate:.0f}%)")

    elif win_rate > 60 and current_min > 5.5:
        new_min = round(max(current_min - 0.5, 5.0), 1)
        set_bot_config("MIN_SCORE_TO_TRADE", str(new_min))
        _record_thought(
            "SCORE_ADJUSTMENT",
            f"Win rate del spread: {win_rate:.1f}%. Normalizando score mínimo "
            f"de {current_min} a {new_min}/10.",
            "POSITIVE"
        )


def _analyze_pair_performance(d):
    """
    Analiza el rendimiento por par de forma rigurosa.
    Solo actúa si hay suficientes trades y la evidencia es clara.
    """
    pair_stats = d.query("""
        SELECT pair,
               COUNT(*) as total,
               SUM(CASE WHEN status='WIN' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN status='LOSS' THEN 1 ELSE 0 END) as losses,
               ROUND(AVG(CASE WHEN pnl IS NOT NULL THEN CAST(pnl AS REAL) END), 2) as avg_pnl,
               ROUND(SUM(CAST(pnl AS REAL)), 2) as total_pnl
        FROM paper_trades
        WHERE status != 'OPEN'
        GROUP BY pair
        HAVING total >= 3
        ORDER BY total_pnl ASC
    """)

    paused_pairs_str = get_bot_config("PAUSED_PAIRS", "")
    paused_pairs = [p for p in paused_pairs_str.split(",") if p] if paused_pairs_str else []
    changed = False

    for p in pair_stats:
        pair     = p["pair"]
        total    = int(p["total"])
        wins     = int(p["wins"] or 0)
        losses   = int(p["losses"] or 0)
        avg_pnl  = _safe_float(p["avg_pnl"])
        total_pnl = _safe_float(p["total_pnl"])
        wr       = wins / total * 100

        # Pausar par con muy mal rendimiento
        if wr < 25 and losses >= 3 and pair not in paused_pairs:
            paused_pairs.append(pair)
            changed = True
            _record_thought(
                "PAIR_PAUSE",
                f"Pauso {pair}: {wins}W/{losses}L ({wr:.0f}% win rate), "
                f"P&L total: ${total_pnl:.2f}, promedio: ${avg_pnl:.2f}/trade. "
                f"Reanudaré en 24h o cuando el contexto macro cambie favorablemente.",
                "NEGATIVE"
            )
            _record_action(
                f"Par {pair} pausado temporalmente. "
                f"Estadísticas: {wr:.0f}% WR, ${total_pnl:.2f} P&L total en {total} trades."
            )

        # Reactivar pares pausados que mejoraron
        elif pair in paused_pairs and wr > 50 and total >= 5:
            paused_pairs.remove(pair)
            changed = True
            _record_thought(
                "PAIR_RESUME",
                f"Reactivo {pair}: ha mejorado a {wr:.0f}% win rate en los últimos {total} trades "
                f"con P&L total de ${total_pnl:.2f}. Lo incluyo de nuevo en la operativa.",
                "POSITIVE"
            )

        # Reconocer pares rentables
        elif wr > 65 and total >= 4 and not _was_thought_recently(f"PAIR_GOOD_{pair}", hours=6):
            _record_thought(
                f"PAIR_GOOD_{pair}",
                f"{pair} es mi par más rentable hoy: {wr:.0f}% win rate en {total} trades, "
                f"P&L total ${total_pnl:.2f}. Mantendré atención especial en sus señales.",
                "POSITIVE"
            )

    if changed:
        new_val = ",".join(paused_pairs)
        set_bot_config("PAUSED_PAIRS", new_val)


def _analyze_macro_alignment(d) -> str:
    """
    Analiza si el contexto macro es coherente con las operaciones actuales.
    Devuelve el régimen de mercado actual.
    """
    macro = d.query(
        "SELECT risk_appetite, dxy_trend, nasdaq_trend FROM macro_history ORDER BY id DESC LIMIT 1"
    )
    if not macro:
        return "UNKNOWN"

    m = macro[0]
    risk   = m.get("risk_appetite", "NEUTRAL")
    dxy    = m.get("dxy_trend", "NEUTRAL")
    nasdaq = m.get("nasdaq_trend", "NEUTRAL")

    # Analizar coherencia entre macro y trades abiertos
    open_trades = d.query(
        "SELECT pair, direction FROM paper_trades WHERE status='OPEN'"
    )
    crypto_buys = [t for t in open_trades if "USDT" in t["pair"] and t["direction"] == "BUY"]

    if risk == "LOW" and crypto_buys and not _was_thought_recently("MACRO_CONFLICT", hours=4):
        _record_thought(
            "MACRO_CONFLICT",
            f"Conflicto macro detectado: tengo {len(crypto_buys)} posición(es) BUY en crypto pero "
            f"el apetito por el riesgo es BAJO (DXY: {dxy}, Nasdaq: {nasdaq}). "
            f"El contexto global no apoya posiciones largas en activos de riesgo ahora mismo.",
            "NEGATIVE"
        )

    return risk


def _analyze_time_patterns(d):
    """
    Detecta si hay patrones de rendimiento por hora o sesión de mercado.
    """
    hourly = d.query("""
        SELECT
            CAST(strftime('%H', open_time) AS INTEGER) as hour,
            COUNT(*) as total,
            SUM(CASE WHEN status='WIN' THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CAST(pnl AS REAL)), 2) as avg_pnl
        FROM paper_trades
        WHERE status != 'OPEN' AND open_time IS NOT NULL
        GROUP BY hour
        HAVING total >= 2
        ORDER BY wins * 1.0 / total DESC
        LIMIT 3
    """)

    if not hourly or _was_thought_recently("TIME_PATTERN", hours=8):
        return

    best = hourly[0] if hourly else None
    worst_q = d.query("""
        SELECT CAST(strftime('%H', open_time) AS INTEGER) as hour,
               COUNT(*) as total,
               SUM(CASE WHEN status='WIN' THEN 1 ELSE 0 END) as wins,
               ROUND(AVG(CAST(pnl AS REAL)), 2) as avg_pnl
        FROM paper_trades
        WHERE status != 'OPEN' AND open_time IS NOT NULL
        GROUP BY hour HAVING total >= 2 ORDER BY wins * 1.0 / total ASC LIMIT 1
    """)
    worst = worst_q[0] if worst_q else None

    if best and worst and int(best.get("hour", -1)) != int(worst.get("hour", -1)):
        best_wr  = int(best["wins"]) / int(best["total"]) * 100
        worst_wr = int(worst["wins"]) / int(worst["total"]) * 100
        _record_thought(
            "TIME_PATTERN",
            f"Patrón temporal detectado: mi mejor rendimiento es a las {int(best['hour']):02d}h UTC "
            f"({best_wr:.0f}% WR, ${best['avg_pnl']:.2f}/trade). "
            f"Peor hora: {int(worst['hour']):02d}h UTC ({worst_wr:.0f}% WR, ${worst['avg_pnl']:.2f}/trade). "
            f"Tendré esto en cuenta para calibrar mi confianza en cada sesión.",
            "NEUTRAL"
        )


def _analyze_strategy_performance(d):
    """
    Analiza qué estrategia está funcionando mejor y activa/desactiva en consecuencia.
    Requiere la tabla strategy_performance (agregada en database.py).
    """
    try:
        strat_stats = d.query("""
            SELECT strategy,
                   COUNT(*) as total,
                   SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
                   ROUND(SUM(CAST(pnl AS REAL)), 2) as total_pnl
            FROM strategy_performance
            WHERE timestamp > datetime('now', '-3 days')
            GROUP BY strategy
            HAVING total >= 3
            ORDER BY total_pnl DESC
        """)
    except Exception:
        return  # Tabla puede no existir aún

    if not strat_stats or _was_thought_recently("STRATEGY_SWITCH", hours=6):
        return

    best = strat_stats[0]
    best_wr = int(best["wins"]) / int(best["total"]) * 100
    best_pnl = _safe_float(best["total_pnl"])

    # Proteger la estrategia Z-Score — no revertir a estrategias antiguas
    current_strategy = get_bot_config("ACTIVE_STRATEGY", ZSCORE_STRATEGY)
    if current_strategy == ZSCORE_STRATEGY:
        # Con Z-Score solo hay un "par" (el spread) — registrar rendimiento
        if best_wr > 55 and best_pnl > 0 and not _was_thought_recently("STRATEGY_PERF", hours=6):
            _record_thought(
                "STRATEGY_PERF",
                f"Z-Score Mean Reversion rinde bien: {best_wr:.0f}% WR, "
                f"${best_pnl:.2f} P&L en {best['total']} trades del spread BTC/ETH.",
                "POSITIVE"
            )
        return

    if best["strategy"] != current_strategy and best_wr > 55 and best_pnl > 0:
        set_bot_config("ACTIVE_STRATEGY", best["strategy"])
        _record_thought(
            "STRATEGY_SWITCH",
            f"Cambio de estrategia: '{best['strategy']}' supera a '{current_strategy}' "
            f"({best_wr:.0f}% WR, ${best_pnl:.2f} P&L en {best['total']} trades).",
            "POSITIVE"
        )
        _record_action(
            f"Estrategia activa: {current_strategy} → {best['strategy']} "
            f"({best_wr:.0f}% WR en últimos 3 días)."
        )


def _analyze_drawdown_velocity(d):
    """
    Mide la velocidad a la que el bot está perdiendo capital.
    Si es muy rápida, entra en modo defensivo.
    """
    history = d.query(
        "SELECT balance FROM portfolio ORDER BY id DESC LIMIT 10"
    )
    if len(history) < 5:
        return

    balances = [_safe_float(h["balance"]) for h in history]
    peak = max(balances)
    current = balances[0]
    drawdown_pct = (peak - current) / peak * 100 if peak > 0 else 0

    if drawdown_pct > 8 and not _was_thought_recently("DRAWDOWN_ALERT", hours=4):
        # Calcular velocidad: cuánto perdemos por snapshot
        drops = [balances[i] - balances[i+1] for i in range(len(balances)-1) if balances[i+1] > 0]
        avg_drop_per_cycle = sum(drops) / len(drops) if drops else 0

        _record_thought(
            "DRAWDOWN_ALERT",
            f"Drawdown actual: {drawdown_pct:.1f}% desde el pico (${peak:.0f} → ${current:.0f}). "
            f"Pérdida promedio por ciclo: ${avg_drop_per_cycle:.2f}. "
            f"Entro en modo defensivo: necesito señales de alta calidad (8+/10) para operar.",
            "NEGATIVE"
        )
        # Modo defensivo: score mínimo muy alto
        current_min = _safe_float(get_bot_config("MIN_SCORE_TO_TRADE", 5.0))
        if current_min < 7.5:
            set_bot_config("MIN_SCORE_TO_TRADE", "7.5")
            _record_action(
                f"Modo defensivo activado: drawdown de {drawdown_pct:.1f}%. "
                f"Score mínimo subido a 7.5/10. Solo operaciones de muy alta confluencia."
            )


def _generate_market_reflection(d, macro_regime: str):
    """
    Genera una reflexión de alto nivel sobre el estado actual del mercado.
    Solo una vez cada pocas horas para no ser repetitivo.
    """
    if _was_thought_recently("MARKET_REFLECTION", hours=4):
        return

    open_trades = d.query("SELECT pair, direction FROM paper_trades WHERE status='OPEN'")
    open_count = len(open_trades)

    recent_signals = d.query(
        "SELECT direction, score FROM signals ORDER BY id DESC LIMIT 20"
    )
    if not recent_signals:
        return

    bullish = sum(1 for s in recent_signals if s["direction"] == "BUY")
    bearish = sum(1 for s in recent_signals if s["direction"] == "SELL")
    neutral = sum(1 for s in recent_signals if s["direction"] == "NEUTRAL")
    avg_score = sum(_safe_float(s["score"]) for s in recent_signals) / len(recent_signals)

    bias = "ALCISTA" if bullish > bearish * 1.5 else ("BAJISTA" if bearish > bullish * 1.5 else "MIXTO")

    _record_thought(
        "MARKET_REFLECTION",
        f"Vista general del mercado: {bullish} señales alcistas, {bearish} bajistas, "
        f"{neutral} neutrales en los últimos ciclos. Sesgo técnico: {bias}. "
        f"Score promedio de señales: {avg_score:.1f}/10. Régimen macro: {macro_regime}. "
        f"Tengo {open_count} posición(es) abierta(s).",
        "NEUTRAL"
    )


def _defensive_decay(d):
    """
    Si el bot no ha operado en más de 24h, reduce gradualmente la selectividad
    y normaliza el Stop Loss para evitar el bloqueo defensivo.
    """
    last_trade = d.query("SELECT open_time FROM paper_trades ORDER BY id DESC LIMIT 1")
    if not last_trade:
        return

    try:
        # Algunos open_time pueden venir sin el formato ISO completo
        ot = last_trade[0]["open_time"]
        if " " in ot and "T" not in ot: ot = ot.replace(" ", "T")
        
        last_dt = datetime.fromisoformat(ot)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        
        hours_inactive = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        
        if hours_inactive > 24 and not _was_thought_recently("DEFENSIVE_DECAY", hours=12):
            current_min = _safe_float(get_bot_config("MIN_SCORE_TO_TRADE", 5.0))
            current_atr = _safe_float(get_bot_config("STOP_LOSS_ATR", 1.2))
            
            changed = False
            decay_msg = f"Inactividad de {hours_inactive:.1f}h detectada. "
            
            if current_min > 5.5:
                new_min = max(current_min - 0.5, 5.5)
                set_bot_config("MIN_SCORE_TO_TRADE", str(round(new_min, 1)))
                decay_msg += f"Reduciendo score min: {current_min} -> {new_min}. "
                changed = True
            
            if changed:
                _record_thought("DEFENSIVE_DECAY", decay_msg, "NEUTRAL")
                _record_action(decay_msg)
    except Exception as e:
        logger.warning(f"⚠️ Error en defensive_decay: {e}")


# ── Torneo semanal ───────────────────────────────────────────────────────────

def run_weekly_tournament():
    """
    Corre en el primer ciclo de cada lunes.
    Calcula métricas de la semana cerrada y guarda WEEKLY_VERDICT en bot_memory.
    """
    now = datetime.now(timezone.utc)
    if now.weekday() != 0:  # 0 = lunes
        return

    last_run_str = get_bot_config("WEEKLY_TOURNAMENT_LAST_RUN", "")
    if last_run_str:
        try:
            last_dt = datetime.fromisoformat(last_run_str)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            if (now - last_dt).total_seconds() < 86400 * 6:  # ya corrió esta semana
                return
        except Exception:
            pass

    d = db()
    week_ago = (now - timedelta(days=7)).isoformat()

    trades = d.query(
        "SELECT status, pnl, pnl_pct, open_time, close_time, "
        "z_score_open, hurst_open, macro_regime "
        "FROM paper_trades WHERE status != 'OPEN' AND close_time > ? ORDER BY id DESC",
        [week_ago]
    )

    if not trades:
        logger.info("🏆 Torneo semanal: sin trades cerrados esta semana")
        set_bot_config("WEEKLY_TOURNAMENT_LAST_RUN", now.isoformat())
        return

    total     = len(trades)
    wins      = [t for t in trades if t["status"] == "WIN"]
    losses    = [t for t in trades if t["status"] == "LOSS"]
    win_rate  = len(wins) / total * 100 if total > 0 else 0.0
    pnls      = [_safe_float(t["pnl"]) for t in trades]
    total_pnl = sum(pnls)
    avg_pnl   = total_pnl / total if total > 0 else 0.0
    best_pnl  = max(pnls) if pnls else 0.0
    worst_pnl = min(pnls) if pnls else 0.0

    # Sharpe semanal aproximado (anualizado × √52)
    sharpe = 0.0
    if len(pnls) > 1:
        std = statistics.stdev(pnls)
        if std > 0:
            sharpe = (statistics.mean(pnls) / std) * (52 ** 0.5)

    # Régimen macro más frecuente
    regimes = [t["macro_regime"] for t in trades if t.get("macro_regime")]
    dominant_regime = max(set(regimes), key=regimes.count) if regimes else "UNKNOWN"

    week_label = now.strftime("%Y-W%W")
    verdict = (
        f"TORNEO SEMANAL {week_label}: "
        f"{total} trades | WR {win_rate:.1f}% | P&L ${total_pnl:+.2f} | "
        f"Avg ${avg_pnl:+.2f}/trade | Sharpe {sharpe:.2f} | "
        f"Mejor ${best_pnl:+.2f} | Peor ${worst_pnl:+.2f} | "
        f"Régimen: {dominant_regime}"
    )

    _record_thought("WEEKLY_VERDICT", verdict,
                    "POSITIVE" if total_pnl > 0 else "NEGATIVE")
    set_bot_config("WEEKLY_VERDICT", verdict)
    set_bot_config("WEEKLY_TOURNAMENT_LAST_RUN", now.isoformat())
    logger.info(f"🏆 {verdict}")


# ── Motor principal ──────────────────────────────────────────────────────────

def run_brain_reflection():
    """
    Orquesta todos los módulos de análisis en orden de prioridad.
    Cada módulo genera pensamientos únicos basados en datos reales.
    """
    d = db()

    # 1. Análisis de rendimiento (necesario para win_rate real)
    perf = _analyze_win_rate_and_strategy(d)
    win_rate = perf.get("win_rate", 0.0)

    # 2. Analizar ATR con win_rate real + fix del bug de escalado
    _analyze_atr_and_stop_loss(d, win_rate)

    # 3. Análisis por par
    _analyze_pair_performance(d)

    # 4. Contexto macro
    macro_regime = _analyze_macro_alignment(d)

    # 5. Velocidad de drawdown
    _analyze_drawdown_velocity(d)

    # 6. Patrones temporales (si hay suficientes datos)
    _analyze_time_patterns(d)

    # 7. Rendimiento por estrategia
    _analyze_strategy_performance(d)

    # 8. Decaimiento defensivo (evita bloqueos por inactividad)
    _defensive_decay(d)

    # 9. Reflexión de mercado de alto nivel
    _generate_market_reflection(d, macro_regime)



def process_bot_brain():
    """Punto de entrada principal. Ejecutado al final de cada ciclo."""
    try:
        # 1. Ejecutar reflexión basada en código (rápida, determinista)
        run_brain_reflection()

        # 2. Ejecutar reflexión basada en LLM (intuitiva, estratégica)
        run_llm_brain_cycle()

        # 3. Actualizar métricas mensuales
        try:
            update_monthly_metrics()
        except Exception as e:
            logger.debug(f"update_monthly_metrics: {e}")

        # 4. Analizar el estado del bot y generar solicitudes de mejora al usuario
        run_improvement_engine()

        # 5. Torneo semanal (solo el primer ciclo de cada lunes)
        try:
            run_weekly_tournament()
        except Exception as e:
            logger.debug(f"run_weekly_tournament: {e}")

    except Exception as e:
        logger.error(f"Error en el cerebro del bot: {e}", exc_info=True)
