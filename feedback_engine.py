import logging
from database import save_trade_feedback, db

logger = logging.getLogger(__name__)

def analyze_closed_trade(trade):
    \"\"\"
    Analiza un trade cerrado y genera una lección aprendida.
    \"\"\"
    pnl = float(trade["pnl"])
    reason = trade["close_reason"]
    pair = trade["pair"]
    
    lesson = ""
    performance_score = 0.0
    
    if pnl > 0:
        performance_score = 10.0
        if reason == "TP_HIT":
            lesson = f"Éxito en {pair}. La estrategia de TP funcionó perfectamente."
        else:
            lesson = f"Ganancia en {pair}. Trade cerrado por {reason}."
    else:
        # Analizar pérdida
        performance_score = 2.0
        if reason == "SL_HIT":
            lesson = f"Pérdida en {pair}. El Stop Loss protegió el capital. Considerar si el SL era muy ajustado."
        else:
            lesson = f"Pérdida en {pair}. Cerrado prematuramente por {reason}."
            
    save_trade_feedback(trade["id"], lesson, performance_score)
    logger.info(f"🧠 Feedback generado para #{trade['id']}: {lesson}")

def run_feedback_cycle():
    \"\"\"
    Busca trades recién cerrados sin feedback y los procesa.
    \"\"\"
    d = db()
    # Buscamos trades cerrados que no estén en la tabla de feedback
    query = "SELECT t.* FROM paper_trades t LEFT JOIN trade_feedback f ON t.id = f.trade_id WHERE t.status IN ('WIN', 'LOSS') AND f.id IS NULL"
    pending = d.query(query)
    
    if not pending:
        return
        
    logger.info(f"🧠 Procesando feedback para {len(pending)} trades...")
    for trade in pending:
        analyze_closed_trade(trade)
