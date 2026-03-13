"""
improvement_engine.py — Motor de Autoconciencia y Solicitudes de Mejora

A diferencia de bot_wishes (acciones autónomas del bot), estas son peticiones
AL USUARIO: cosas que tú debes hacer para que el bot mejore.
El bot analiza sus propios puntos débiles y te los comunica aquí.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from database import db, get_bot_config

logger = logging.getLogger(__name__)


def _safe_float(v, d=0.0):
    try:
        return float(v) if v is not None else d
    except (TypeError, ValueError):
        return d


def _was_requested_recently(title_fragment: str, hours: int = 48) -> bool:
    d = db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = d.query(
        "SELECT id FROM bot_improvement_requests WHERE title LIKE ? AND timestamp > ?",
        [f"%{title_fragment}%", cutoff]
    )
    return bool(rows)


def _save_request(category: str, priority: str, title: str, description: str):
    """Guarda una solicitud de mejora si no existe una pendiente idéntica."""
    d = db()
    existing = d.query(
        "SELECT id FROM bot_improvement_requests WHERE title = ? AND status = 'PENDING'",
        [title]
    )
    if existing:
        return
    d.execute(
        "INSERT INTO bot_improvement_requests (category, priority, title, description) "
        "VALUES (?, ?, ?, ?)",
        [category, priority, title, description]
    )
    d.commit()
    logger.info(f"💡 [{priority}] Nueva solicitud de mejora: {title}")


# ── Verificaciones de configuración ──────────────────────────────────────────

def _check_llm_availability():
    """Verifica si hay APIs de LLM configuradas para el MD."""
    has_groq   = bool(os.getenv("GROQ_API_KEY", ""))
    has_gemini = bool(os.getenv("GEMINI_API_KEY", ""))
    has_openai = bool(os.getenv("OPENAI_API_KEY", ""))

    if not any([has_groq, has_gemini, has_openai]):
        if not _was_requested_recently("LLM"):
            _save_request(
                "CONFIG", "HIGH",
                "Configurar API de LLM — El MD no puede razonar",
                "El Managing Director (MD) está ciego sin LLM. "
                "Groq ofrece Llama 3.3 70B GRATIS con cuota generosa. "
                "Pasos: (1) Ve a console.groq.com, (2) Crea una API Key gratuita, "
                "(3) Agrega GROQ_API_KEY en GitHub → Settings → Secrets → Actions."
            )
    elif not has_groq and (has_openai or has_gemini):
        if not _was_requested_recently("Groq como principal"):
            _save_request(
                "CONFIG", "MEDIUM",
                "Añadir Groq como motor principal (gratuito y 10x más rápido)",
                "Tienes LLM configurado pero no Groq. Groq es gratuito, ultra-rápido "
                "y es el motor primario del MD. Agrega GROQ_API_KEY desde console.groq.com. "
                "Esto reducirá costes y mejorará los tiempos de respuesta del MD."
            )


def _check_telegram():
    """Verifica si Telegram está configurado para alertas."""
    if not os.getenv("TELEGRAM_BOT_TOKEN", ""):
        if not _was_requested_recently("Telegram"):
            _save_request(
                "FEATURE", "MEDIUM",
                "Configurar Telegram para alertas de trades en tiempo real",
                "Sin Telegram, no recibes alertas cuando el bot abre/cierra trades "
                "ni cuando hay señales de alta calidad. "
                "Pasos: (1) Habla con @BotFather en Telegram → /newbot, "
                "(2) Copia el token, (3) Obtén tu Chat ID enviando /start a tu bot, "
                "(4) Agrega TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en GitHub Secrets."
            )


# ── Análisis de rendimiento ───────────────────────────────────────────────────

def _analyze_win_rate(d):
    """Detecta problemas sistémicos de win rate y propone soluciones."""
    recent = d.query(
        "SELECT status, close_reason, pnl_pct FROM paper_trades "
        "WHERE status != 'OPEN' ORDER BY id DESC LIMIT 30"
    )
    if len(recent) < 10:
        return

    total    = len(recent)
    wins     = sum(1 for t in recent if t["status"] == "WIN")
    win_rate = wins / total * 100
    sl_hits  = sum(1 for t in recent if t.get("close_reason") == "SL_HIT")
    sl_pct   = sl_hits / total * 100

    if sl_pct > 65 and not _was_requested_recently("Stop Loss activados"):
        _save_request(
            "STRATEGY_INSIGHT", "HIGH",
            f"Alta tasa de SL activados ({sl_pct:.0f}%) — Revisar lógica de entrada",
            f"{sl_pct:.0f}% de trades terminan con Stop Loss tocado. "
            "Las entradas están en zonas de ruido de mercado. "
            "Acciones recomendadas: "
            "(1) Sube MIN_SCORE_TO_TRADE a 7.0 en bot_config (DB), "
            "(2) Activa solo B_EMA_PULLBACK (más conservador), "
            "(3) Revisa el panel de Estrategias para ver cuál falla más."
        )

    if win_rate < 35 and total >= 15 and not _was_requested_recently("Win Rate Crítico"):
        _save_request(
            "STRATEGY_INSIGHT", "HIGH",
            f"Win Rate Crítico ({win_rate:.0f}%) — Revisión de estrategia urgente",
            f"Solo {win_rate:.0f}% de {total} trades son ganadores. "
            "Necesitas al menos 40% WR con R:R 2:1 para ser rentable. "
            "Pasos: (1) Revisa qué pares tienen peor rendimiento y elimínalos de config.py, "
            "(2) Cambia ACTIVE_STRATEGY=B_EMA_PULLBACK en bot_config, "
            "(3) Sube MIN_SCORE_TO_TRADE=7.5 manualmente."
        )


def _analyze_balance_health(d):
    """Analiza la salud del balance y sugiere acciones correctivas o de escalado."""
    bal_rows = d.query("SELECT balance FROM portfolio ORDER BY id DESC LIMIT 5")
    if len(bal_rows) < 3:
        return

    current  = _safe_float(bal_rows[0]["balance"])
    drawdown = (10000.0 - current) / 10000.0 * 100

    if drawdown > 15 and not _was_requested_recently("Drawdown Elevado"):
        _save_request(
            "STRATEGY_INSIGHT", "HIGH",
            f"Drawdown Elevado ({drawdown:.1f}%) — Requiere intervención",
            f"Balance: ${current:,.2f} (pérdida del {drawdown:.1f}% desde $10,000). "
            "Opciones: "
            "(1) Reset limpio: ejecuta reset_bot.py (reinicia con $10,000 y memoria en blanco), "
            "(2) Pausa manual: establece ACTIVE_STRATEGY=PAUSE_ALL en bot_config, "
            "(3) Reduce riesgo: cambia RISK_PER_TRADE=0.01 en config.py y reinicia el bot."
        )

    # Sugerir modo señal cuando el rendimiento es sólido
    total = int(d.query("SELECT COUNT(*) as c FROM paper_trades WHERE status != 'OPEN'")[0]["c"] or 0)
    wins  = int(d.query("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'WIN'")[0]["c"] or 0)
    if total >= 30 and wins > 0:
        wr = wins / total * 100
        if wr >= 48 and drawdown < 3 and not _was_requested_recently("Modo Señal"):
            _save_request(
                "FEATURE", "LOW",
                f"Rendimiento Sólido ({wr:.0f}% WR) — ¿Activar Modo Señal Manual?",
                f"Con {wr:.0f}% WR en {total} trades y balance saludable, "
                "el bot puede operar en modo señal: te avisa por Telegram "
                "sin ejecutar trades automáticamente. Tú decides cuáles tomar. "
                "Activa con: SIGNAL_ONLY_MODE=true en bot_config (tabla de DB). "
                "Desactiva con: SIGNAL_ONLY_MODE=false para volver al modo autónomo."
            )


def _check_data_freshness(d):
    """Verifica que el bot esté recibiendo datos de mercado correctamente."""
    recent = d.query(
        "SELECT COUNT(*) as c FROM signals WHERE timestamp > datetime('now', '-3 hours')"
    )
    if recent and int(recent[0]["c"]) == 0:
        if not _was_requested_recently("Sin señales recientes"):
            _save_request(
                "DATA_ISSUE", "HIGH",
                "Sin señales en 3+ horas — Verificar estado de GitHub Actions",
                "No hay datos de mercado recientes. El bot puede estar detenido. "
                "Verifica: (1) Ve a tu repo en GitHub → Actions → bot.yml, "
                "(2) Revisa el último run para ver el error, "
                "(3) Asegúrate de que TURSO_URL y TURSO_AUTH_TOKEN estén en Secrets. "
                "Si Actions está pausado, haz click en 'Enable workflow'."
            )


def _suggest_multi_timeframe():
    """Sugiere mejoras de análisis multitemporal si hay suficientes datos."""
    d = db()
    total = int(d.query("SELECT COUNT(*) as c FROM paper_trades")[0]["c"] or 0)
    if total >= 20 and not _was_requested_recently("análisis multitemporal", hours=168):
        _save_request(
            "FEATURE", "LOW",
            "Mejora: Añadir análisis multitemporal (1H/4H como filtro macro)",
            "El bot usa solo 15min. Murphy's Principio 6: las señales de 1H/4H "
            "mandan sobre 15min. Para implementar: "
            "(1) En config.py añade SECONDARY_TIMEFRAME = '1h', "
            "(2) En signals.py añade un check: la tendencia de 1H debe alinearse "
            "con la señal de 15min antes de puntuarla. "
            "Esto reduciría señales falsas en contratendencia."
        )


# ── Motor principal ───────────────────────────────────────────────────────────

def run_improvement_engine():
    """
    Analiza el estado del bot y genera solicitudes de mejora para el usuario.
    Se ejecuta al final de cada ciclo de brain.
    """
    try:
        d = db()
        _check_llm_availability()
        _check_telegram()
        _analyze_win_rate(d)
        _analyze_balance_health(d)
        _check_data_freshness(d)
        _suggest_multi_timeframe()
        logger.debug("💡 Motor de mejora ejecutado correctamente")
    except Exception as e:
        logger.error(f"Error en improvement_engine: {e}", exc_info=True)
