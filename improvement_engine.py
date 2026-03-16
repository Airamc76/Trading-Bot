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




def _check_data_freshness(d):
    """Verifica que el bot esté recibiendo datos de mercado correctamente."""
    recent = d.query(
        "SELECT COUNT(*) as c FROM signals WHERE timestamp > datetime('now', '-3 hours')"
    )
    if recent and int(recent[0].get("c") or 0) == 0:
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
    total_row = d.query("SELECT COUNT(*) as c FROM paper_trades")
    total = int(total_row[0].get("c") or 0) if total_row else 0
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
        _check_data_freshness(d)
        _suggest_multi_timeframe()
        logger.debug("💡 Motor de mejora ejecutado correctamente")
    except Exception as e:
        logger.error(f"Error en improvement_engine: {e}", exc_info=True)
