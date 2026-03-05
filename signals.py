from datetime import datetime
from database import get_bot_config

def score_signal(vals, config, sentiment_score=0.0, macro_context=None):
    """
    Evalúa los indicadores y devuelve un score de 0 a 10 y una dirección.
    sentiment_score: float entre -1 (muy negativo) y 1 (muy positivo).
    macro_context: dict con tendencias de DXY y Nasdaq.
    """
    score = 0
    reasons = []
    
    price = vals.get("price")
    rsi = vals.get("rsi")
    ema_20 = vals.get("ema_20")
    ema_50 = vals.get("ema_50")
    ema_200 = vals.get("ema_200")
    macd_hist = vals.get("macd_hist")
    bb_upper = vals.get("bb_upper")
    bb_lower = vals.get("bb_lower")
    ema_9 = vals.get("ema_9")
    ema_21 = vals.get("ema_21")
    atr = vals.get("atr", 0)

    # REGLA FLEXIBLE: Si falta EMA200, usamos EMA50 como tendencia base
    primary_trend_ma = ema_200 if ema_200 else ema_50
    
    if not all([price, rsi, primary_trend_ma]):
        return {"direction": "NEUTRAL", "score": 0, "reasons": [{"note": "Faltan datos básicos de análisis"}]}

    # 1. Análisis para COMPRA
    buy_score = 0
    buy_reasons = []
    
    # Tendencia
    if price > primary_trend_ma:
        buy_score += 2
        note = "Tendencia alcista (EMA200)" if ema_200 else "Tendencia alcista (EMA50 fallback)"
        buy_reasons.append({"note": note})
        
    # Scalping: EMA Cross
    if ema_9 and ema_21 and ema_9 > ema_21:
        buy_score += 1
        buy_reasons.append({"note": "Scalping: EMA9 > EMA21"})

    # RSI
    if rsi < 45:
        buy_score += 2
        buy_reasons.append({"note": f"RSI en zona baja ({rsi:.1f})"})
    if rsi < 35:
        buy_score += 1
        buy_reasons.append({"note": f"RSI Sobrevendido ({rsi:.1f})"})
        
    # Impulso (Vela actual con fuerza)
    prev_close = vals.get("open") # Aproximación de cambio en vela actual
    if prev_close and price > prev_close * 1.002: # +0.2% en 15m es fuerza
        buy_score += 1
        buy_reasons.append({"note": "Fuerza alcista detectada"})

    if macd_hist and macd_hist > 0:
        buy_score += 1
        buy_reasons.append({"note": "MACD Histograma positivo"})
        
    if bb_lower and price <= bb_lower * 1.01:
        buy_score += 2
        buy_reasons.append({"note": "Precio cerca de Banda Inferior BB"})

    # Sentimiento y Macro (ya sensibles antes)
    if sentiment_score > 0.1:
        buy_score += 2
        buy_reasons.append({"note": f"Sentimiento alcista ({sentiment_score:.2f})"})
    
    if macro_context and macro_context.get("nasdaq_trend") == "UP":
        buy_score += 1
        buy_reasons.append({"note": "Macro: Nasdaq alcista"})

    # 2. Análisis para VENTA
    sell_score = 0
    sell_reasons = []
    
    if price < primary_trend_ma:
        sell_score += 2
        note = "Tendencia bajista (EMA200)" if ema_200 else "Tendencia bajista (EMA50 fallback)"
        sell_reasons.append({"note": note})

    if ema_9 and ema_21 and ema_9 < ema_21:
        sell_score += 1
        sell_reasons.append({"note": "Scalping: EMA9 < EMA21"})
        
    if rsi > 55:
        sell_score += 2
        sell_reasons.append({"note": f"RSI en zona alta ({rsi:.1f})"})
    if rsi > 70:
        sell_score += 1
        sell_reasons.append({"note": f"RSI Sobrecomprado ({rsi:.1f})"})

    if prev_close and price < prev_close * 0.998:
        sell_score += 1
        sell_reasons.append({"note": "Fuerza bajista detectada"})
        
    if macd_hist and macd_hist < 0:
        sell_score += 1
        sell_reasons.append({"note": "MACD Histograma negativo"})
        
    if bb_upper and price >= bb_upper * 0.99:
        sell_score += 2
        sell_reasons.append({"note": "Precio cerca de Banda Superior BB"})

    if sentiment_score < -0.1:
        sell_score += 2
        sell_reasons.append({"note": f"Sentimiento bajista ({sentiment_score:.2f})"})

    if macro_context and macro_context.get("dxy_trend") == "UP":
        sell_score += 1
        sell_reasons.append({"note": "Macro: Dólar fuerte (DXY ▲)"})

    # Determinar dirección final
    if buy_score >= sell_score and buy_score >= 5:
        direction = "BUY"
        final_score = min(buy_score, 10)
        final_reasons = buy_reasons
    elif sell_score > buy_score and sell_score >= 5:
        direction = "SELL"
        final_score = min(sell_score, 10)
        final_reasons = sell_reasons
    else:
        direction = "NEUTRAL"
        final_score = max(buy_score, sell_score)
        # Transparencia: Mostrar qué está viendo el bot aunque no opere
        dominant_reasons = buy_reasons if buy_score >= sell_score else sell_reasons
        if dominant_reasons:
            final_reasons = [{"note": "(Neutral) " + r["note"]} for r in dominant_reasons]
        else:
            final_reasons = [{"note": "Sin señales claras"}]

    # Calcular niveles de SL y TP basados en ATR dinámico
    stop_loss = None
    take_profit = None
    
    # Obtener configuración dinámica o usar por defecto de config
    dyn_sl_atr = float(get_bot_config("STOP_LOSS_ATR", config.STOP_LOSS_ATR))
    dyn_tp_r = float(get_bot_config("TAKE_PROFIT_R", config.TAKE_PROFIT_R))
    
    if direction == "BUY":
        stop_loss = price - (atr * dyn_sl_atr)
        take_profit = price + (atr * dyn_sl_atr * dyn_tp_r)
    elif direction == "SELL":
        stop_loss = price + (atr * dyn_sl_atr)
        take_profit = price - (atr * dyn_sl_atr * dyn_tp_r)

    return {
        "direction": direction,
        "score": float(final_score),
        "reasons": final_reasons,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "sentiment": sentiment_score
    }

def format_signal_summary(pair, timeframe, signal, price):
    """Formatea la señal para imprimir en consola"""
    emoji = "🟢" if signal["direction"] == "BUY" else "🔴" if signal["direction"] == "SELL" else "⚪"
    notes = " | ".join([r["note"] for r in signal["reasons"]])
    return f"{emoji} {pair} ({timeframe}) | Score: {signal['score']:.1f} | Precio: {price:.4g} | {notes}"
