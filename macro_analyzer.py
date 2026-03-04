import logging
import yfinance as yf
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DXY_TICKER = "DX-Y.NYB"
NASDAQ_TICKER = "^IXIC"

def get_macro_context():
    try:
        dxy = yf.download(DXY_TICKER, period="2d", interval="1h", progress=False)
        nasdaq = yf.download(NASDAQ_TICKER, period="2d", interval="1h", progress=False)

        if dxy.empty or nasdaq.empty:
            return None

        dxy_change = ((dxy['Close'].iloc[-1] - dxy['Close'].iloc[0]) / dxy['Close'].iloc[0]) * 100
        nas_change = ((nasdaq['Close'].iloc[-1] - nasdaq['Close'].iloc[0]) / nasdaq['Close'].iloc[0]) * 100

        context = {
            "dxy_trend": "UP" if dxy_change > 0.1 else "DOWN" if dxy_change < -0.1 else "NEUTRAL",
            "nasdaq_trend": "UP" if nas_change > 0.1 else "DOWN" if nas_change < -0.1 else "NEUTRAL",
            "dxy_val": float(dxy['Close'].iloc[-1]),
            "nasdaq_val": float(nasdaq['Close'].iloc[-1]),
            "risk_appetite": "HIGH" if nas_change > 0 and dxy_change < 0 else "LOW" if nas_change < 0 and dxy_change > 0 else "NEUTRAL"
        }
        
        logger.info(f"🌍 Macro: DXY {context['dxy_trend']} | Nasdaq {context['nasdaq_trend']} | Risk: {context['risk_appetite']}")
        return context

    except Exception as e:
        logger.error(f"❌ Error en macro_analyzer: {e}")
        return None

def is_high_impact_event_near():
    return False
