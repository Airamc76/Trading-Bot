import logging
import json
from datetime import datetime, timezone
import config
from database import db, log_system_event, get_bot_config, set_bot_config

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

def record_wish(wish: str, status: str = "PENDING"):
    """Guarda una petición de la IA al usuario, o una acción tomada."""
    d = db()
    # Evitar duplicados recientes
    exists = d.query("SELECT id FROM bot_wishes WHERE wish = ? AND status = ?", [wish, status])
    if not exists:
        d.execute("INSERT INTO bot_wishes (wish, status) VALUES (?, ?)", [wish, status])
        d.commit()
        if status == "ACTION":
            logger.info(f"⚡ IA Acción Automática: {wish}")
        else:
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
                f"Mi tasa de acierto actual es baja ({win_rate}%). Aumentando automáticamente el Stop Loss para adaptarme a la volatilidad.",
                "NEGATIVE"
            )
            current_atr = float(get_bot_config("STOP_LOSS_ATR", config.STOP_LOSS_ATR))
            new_atr = round(current_atr * 1.1, 2)
            set_bot_config("STOP_LOSS_ATR", str(new_atr))
            record_wish(f"He ampliado automáticamente el Stop Loss a {new_atr}x ATR para evitar salir anticipadamente del mercado.", "ACTION")
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
                f"El par {p['pair']} me está dando problemas constantes. Pausando el par temporalmente.",
                "NEGATIVE"
            )
            paused_pairs_str = get_bot_config("PAUSED_PAIRS", "")
            paused_pairs = paused_pairs_str.split(",") if paused_pairs_str else []
            if p['pair'] not in paused_pairs:
                paused_pairs.append(p['pair'])
                set_bot_config("PAUSED_PAIRS", ",".join(paused_pairs))
            record_wish(f"He pausado temporalmente la operativa en {p['pair']} debido a bajo rendimiento continuado.", "ACTION")

def process_bot_brain():
    """Ejecutado al final de cada ciclo."""
    try:
        run_brain_reflection()
    except Exception as e:
        logger.error(f"Error en el cerebro de la IA: {e}")
