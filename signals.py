from datetime import datetime

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
    atr = vals.get("atr", 0)

    if not all([price, rsi, ema_20, ema_200]):
        return {"direction": "NEUTRAL", "score": 0, "reasons": [{"note": "Faltan datos indicadores"}]}

    # 1. Tendencia Principal (EMA 200)
    trend = "UP" if price > ema_200 else "DOWN"
    
    # 2. Análisis para COMPRA
    buy_score = 0
    buy_reasons = []
    
    if price > ema_200:
        buy_score += 2
        buy_reasons.append({"note": "Tendencia alcista (Precio > EMA200)"})
        
    if rsi < 40:
        buy_score += 2
        buy_reasons.append({"note": f"RSI en zona de acumulación ({rsi:.1f})"})
    elif rsi < 30:
        buy_score += 3
        buy_reasons.append({"note": f"RSI Sobrevendido ({rsi:.1f})"})
        
    if macd_hist and macd_hist > 0:
        buy_score += 2
        buy_reasons.append({"note": "MACD Histograma positivo"})
        
    if bb_lower and price <= bb_lower * 1.01:
        buy_score += 3
        buy_reasons.append({"note": "Precio cerca de Banda Inferior BB"})

    # 2.5 Sentimiento del mercado
    if sentiment_score > 0.2:
        buy_score += 2
        buy_reasons.append({"note": f"Sentimiento alcista detectado ({sentiment_score:.2f})"})
    elif sentiment_score > 0.5:
        buy_score += 3
        buy_reasons.append({"note": f"Sentimiento MUY alcista detectado ({sentiment_score:.2f})"})

    # 2.6 Contexto Macro (Confluencia Global)
    if macro_context:
        if macro_context.get("risk_appetite") == "HIGH":
            buy_score += 1
            buy_reasons.append({"note": "Macro: Apetito por el riesgo ALTO (Nasdaq ▲ / DXY ▼)"})
        if macro_context.get("nasdaq_trend") == "UP":
            buy_score += 1
            buy_reasons.append({"note": "Macro: Nasdaq en tendencia alcista"})

    # 3. Análisis para VENTA
    sell_score = 0
    sell_reasons = []
    
    if price < ema_200:
        sell_score += 2
        sell_reasons.append({"note": "Tendencia bajista (Precio < EMA200)"})
        
    if rsi > 60:
        sell_score += 2
        sell_reasons.append({"note": f"RSI en zona de distribución ({rsi:.1f})"})
    elif rsi > 70:
        sell_score += 3
        sell_reasons.append({"note": f"RSI Sobrecomprado ({rsi:.1f})"})
        
    if macd_hist and macd_hist < 0:
        sell_score += 2
        sell_reasons.append({"note": "MACD Histograma negativo"})
        
    if bb_upper and price >= bb_upper * 0.99:
        sell_score += 3
        sell_reasons.append({"note": "Precio cerca de Banda Superior BB"})

    # 3.5 Sentimiento del mercado
    if sentiment_score < -0.2:
        sell_score += 2
        sell_reasons.append({"note": f"Sentimiento bajista detectado ({sentiment_score:.2f})"})
    elif sentiment_score < -0.5:
        sell_score += 3
        sell_reasons.append({"note": f"Sentimiento MUY bajista detectado ({sentiment_score:.2f})"})

    # 3.6 Contexto Macro (Confluencia Global)
    if macro_context:
        if macro_context.get("risk_appetite") == "LOW":
            sell_score += 1
            sell_reasons.append({"note": "Macro: Apetito por el riesgo BAJO (Nasdaq ▼ / DXY ▲)"})
        if macro_context.get("dxy_trend") == "UP":
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
        final_reasons = [{"note": "Sin señales claras"}]

    # Calcular niveles de SL y TP basados en ATR
    stop_loss = None
    take_profit = None
    
    if direction == "BUY":
        stop_loss = price - (atr * config.STOP_LOSS_ATR)
        take_profit = price + (atr * config.STOP_LOSS_ATR * config.TAKE_PROFIT_R)
    elif direction == "SELL":
        stop_loss = price + (atr * config.STOP_LOSS_ATR)
        take_profit = price - (atr * config.STOP_LOSS_ATR * config.TAKE_PROFIT_R)

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
