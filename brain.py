import logging
import json
from datetime import datetime, timezone
from database import db, log_system_event

logger = logging.getLogger(__name__)

def record_reflection(category: str, note: str, impact: str = "NEUTRAL"):
    """Guarda una reflexión de la IA en la memoria."""
    d = db()
    d.execute(
        "INSERT INTO bot_memory (category, note, impact) VALUES (?, ?, ?)",
        [category, note, impact]
    )
    d.commit()
    logger.info(f"🧠 IA Reflexión [{category}]: {note}")

def record_wish(wish: str):
    """Guarda una petición de la IA al usuario."""
    d = db()
    # Evitar duplicados recientes
    exists = d.query("SELECT id FROM bot_wishes WHERE wish = ? AND status = 'PENDING'", [wish])
    if not exists:
        d.execute("INSERT INTO bot_wishes (wish) VALUES (?)", [wish])
        d.commit()
        logger.info(f"💡 IA Petición: {wish}")

def run_brain_reflection():
    """Analiza el estado general y genera pensamientos autónomos."""
    d = db()
    
    # 1. Analizar rendimiento reciente
    recent_trades = d.query("SELECT status, pnl_pct FROM paper_trades WHERE status != 'OPEN' ORDER BY id DESC LIMIT 10")
    if recent_trades:
        losses = [t for t in recent_trades if t["status"] == "LOSS"]
        win_rate = (10 - len(losses)) / 10 * 100
        
        if win_rate < 40:
            record_reflection(
                "STRATEGY", 
                f"Mi tasa de acierto actual es baja ({win_rate}%). Estoy analizando si el mercado está demasiado volátil para mis EMAs actuales.",
                "NEGATIVE"
            )
            record_wish("¿Podríamos probar con un Stop Loss un poco más holgado? Siento que me sacan del mercado muy rápido.")
        elif win_rate > 70:
            record_reflection(
                "STRATEGY",
                f"Me siento confiado con la estrategia actual. El Win Rate es de {win_rate}%.",
                "POSITIVE"
            )
    
    # 2. Analizar sentimiento y macro
    macro = d.query("SELECT risk_appetite FROM macro_history ORDER BY id DESC LIMIT 1")
    if macro and macro[0]["risk_appetite"] == "LOW":
        record_reflection(
            "PATTERN",
            "He notado que el apetito por el riesgo es bajo. Seré más selectivo con mis entradas para proteger el capital.",
            "NEUTRAL"
        )

    # 3. Descubrimiento de patrones por par
    pairs_stats = d.query("""
        SELECT pair, COUNT(*) as total, SUM(CASE WHEN status='LOSS' THEN 1 ELSE 0 END) as losses
        FROM paper_trades 
        GROUP BY pair 
        HAVING total >= 3
    """)
    for p in pairs_stats:
        if float(p["losses"]) / float(p["total"]) > 0.7:
            record_reflection(
                "PATTERN",
                f"El par {p['pair']} me está dando problemas constantes. Quizás no se adapta bien a mi lógica de scalping actual.",
                "NEGATIVE"
            )
            record_wish(f"Sugerencia: Revisar o pausar {p['pair']} temporalmente.")

def process_bot_brain():
    """Ejecutado al final de cada ciclo."""
    try:
        run_brain_reflection()
    except Exception as e:
        logger.error(f"Error en el cerebro de la IA: {e}")
