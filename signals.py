from datetime import datetime
from database import get_bot_config

def score_signal(vals, config_obj, sentiment_score=0.0, macro_context=None):
    """
    APEX Strategy Engine: Evaluates confluence across 3 layers.
    1. Technical (Indicators + Trend)
    2. Sentiment (VADER News)
    3. Macro (DXY + NASDAQ)
    """
    price = vals.get("price")
    ema_20 = vals.get("ema_20")
    ema_50 = vals.get("ema_50")
    ema_200 = vals.get("ema_200")
    rsi = vals.get("rsi")
    atr = vals.get("atr", 0)
    macd_hist = vals.get("macd_hist")
    volume = vals.get("volume", 0)
    
    if not all([price, rsi, ema_50]):
        return {"direction": "NEUTRAL", "score": 0, "reasons": [{"note": "Data incomplete"}]}

    # --- APEX LAYER 3: MACO CONTEXT ---
    macro_mode = "NEUTRAL"
    if macro_context:
        risk_appetite = macro_context.get("risk_appetite", "NEUTRAL")
        macro_mode = risk_appetite

    # --- APEX LAYER 2: SENTIMENT ---
    sent_signal = "NEUTRAL"
    if sentiment_score > 0.3: sent_signal = "BULLISH"
    elif sentiment_score < -0.3: sent_signal = "BEARISH"

    # --- APEX LAYER 1: TECHNICAL & STRATEGIES ---
    # Strategy B: Pullback to EMA in Trend
    primary_trend = "UP" if (ema_200 and price > ema_200) or (not ema_200 and price > ema_50) else "DOWN"
    
    confluences: list[str] = []
    
    # 1. Technical Signal (Strategy B)
    tech_dir = "NEUTRAL"
    if primary_trend == "UP":
        # Pullback to EMA20 or EMA50 (within 0.5% range)
        if (ema_20 and abs(price - ema_20)/price < 0.005) or (abs(price - ema_50)/price < 0.005):
            if rsi < 50: # Not overbought
                tech_dir = "BUY"
                confluences.append("Strategy B: Pullback to EMA in Up-Trend")
    else:
        if (ema_20 and abs(price - ema_20)/price < 0.005) or (abs(price - ema_50)/price < 0.005):
            if rsi > 50: # Not oversold
                tech_dir = "SELL"
                confluences.append("Strategy B: Pullback to EMA in Down-Trend")

    # 2. Trend Confirmation (HTF)
    if (primary_trend == "UP" and tech_dir == "BUY") or (primary_trend == "DOWN" and tech_dir == "SELL"):
        confluences.append(f"Trend confirmed ({primary_trend})")

    # 3. Sentiment Alignment
    if (tech_dir == "BUY" and sent_signal == "BULLISH") or (tech_dir == "SELL" and sent_signal == "BEARISH"):
        confluences.append(f"Sentiment aligned ({sent_signal})")
    
    # 4. Macro Compatibility
    if (tech_dir == "BUY" and macro_mode == "HIGH") or (tech_dir == "SELL" and macro_mode == "LOW"):
        confluences.append(f"Macro compatible (Risk-{macro_mode})")
    elif tech_dir != "NEUTRAL" and macro_mode == "NEUTRAL":
        confluences.append("Macro neutral (Caution)")

    # 5. Momentum/Volume
    if macd_hist:
        if (tech_dir == "BUY" and macd_hist > 0) or (tech_dir == "SELL" and macd_hist < 0):
            confluences.append("Momentum confirmed (MACD)")

    # APEX RULE 1: Mínimo 3 de 5 confluencias
    direction = "NEUTRAL"
    final_score = len(confluences) * 2 # Normalize to 10
    
    if len(confluences) >= 3 and tech_dir != "NEUTRAL":
        direction = tech_dir
    
    # Logic for SL/TP (Rule 2: R:R 1:2)
    # APEX Rule: If volatility is high, reduce position (handled in paper_broker or run)
    dyn_sl_atr = float(get_bot_config("STOP_LOSS_ATR", config_obj.STOP_LOSS_ATR))
    dyn_tp_r = max(2.0, float(get_bot_config("TAKE_PROFIT_R", config_obj.TAKE_PROFIT_R))) # Min R:R 1:2
    
    stop_loss = None
    take_profit = None
    if direction == "BUY":
        stop_loss = price - (atr * dyn_sl_atr)
        take_profit = price + (abs(price - stop_loss) * dyn_tp_r)
    elif direction == "SELL":
        stop_loss = price + (atr * dyn_sl_atr)
        take_profit = price - (abs(price - stop_loss) * dyn_tp_r)

    return {
        "direction": direction,
        "score": float(final_score),
        "reasons": [{"note": c} for c in confluences] if confluences else [{"note": "No confluences found"}],
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "sentiment": sentiment_score,
        "macro_mode": macro_mode
    }

def format_signal_summary(pair, timeframe, signal, price):
    """Formatea la señal para imprimir en consola"""
    emoji = "🟢" if signal["direction"] == "BUY" else "🔴" if signal["direction"] == "SELL" else "⚪"
    notes = " | ".join([r["note"] for r in signal["reasons"]])
    return f"{emoji} {pair} ({timeframe}) | Score: {signal['score']:.1f} | Precio: {price:.4g} | {notes}"
