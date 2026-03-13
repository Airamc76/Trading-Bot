import logging
import yfinance as yf
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

DXY_TICKER = "DX-Y.NYB"
NASDAQ_TICKER = "^IXIC"

def get_macro_context():
    try:
        dxy = yf.download(DXY_TICKER, period="2d", interval="1h", progress=False)
        nasdaq = yf.download(NASDAQ_TICKER, period="2d", interval="1h", progress=False)

        if dxy.empty or nasdaq.empty:
            return None

        # Seleccionar Close de forma robusta (yfinance puede devolver MultiIndex)
        dxy_close = dxy['Close']
        nas_close = nasdaq['Close']
        
        # Si es un DataFrame (ej. MultiIndex), tomamos la primera columna
        if hasattr(dxy_close, 'columns'): dxy_close = dxy_close.iloc[:, 0]
        if hasattr(nas_close, 'columns'): nas_close = nas_close.iloc[:, 0]

        dxy_start = float(dxy_close.iloc[0])
        dxy_end   = float(dxy_close.iloc[-1])
        nas_start = float(nas_close.iloc[0])
        nas_end   = float(nas_close.iloc[-1])

        dxy_change = ((dxy_end - dxy_start) / dxy_start) * 100
        nas_change = ((nas_end - nas_start) / nas_start) * 100

        context = {
            "dxy_trend": "UP" if dxy_change > 0.1 else "DOWN" if dxy_change < -0.1 else "NEUTRAL",
            "nasdaq_trend": "UP" if nas_change > 0.1 else "DOWN" if nas_change < -0.1 else "NEUTRAL",
            "dxy_val": dxy_end,
            "nasdaq_val": nas_end,
            "risk_appetite": "HIGH" if nas_change > 0 and dxy_change < 0 else "LOW" if nas_change < 0 and dxy_change > 0 else "NEUTRAL"
        }
        
        logger.info(f"🌍 Macro: DXY {context['dxy_trend']} | Nasdaq {context['nasdaq_trend']} | Risk: {context['risk_appetite']}")
        return context

    except Exception as e:
        logger.error(f"❌ Error en macro_analyzer: {e}")
        return None

def is_high_impact_event_near() -> bool:
    """
    Detecta si estamos cerca de un evento macro de alto impacto conocido.

    Eventos cubiertos:
    - NFP (Non-Farm Payrolls): primer viernes del mes, 13:00-14:30 UTC
    - Apertura sesión americana (volatilidad elevada): viernes 12:30-13:00 UTC

    Returns True si se debe pausar la apertura de nuevos trades.
    """
    try:
        now = datetime.now(timezone.utc)
        weekday = now.weekday()  # 0=Lunes, 4=Viernes

        # NFP: Primer viernes del mes (día 1-7), ventana 12:30-14:30 UTC
        if weekday == 4 and now.day <= 7:
            if 12 <= now.hour < 15:
                logger.warning(
                    f"⚠️ Probable NFP: primer viernes del mes {now.strftime('%Y-%m-%d')}, "
                    f"{now.hour:02d}:{now.minute:02d} UTC. Pausando nuevas entradas."
                )
                return True

        # Apertura NY cualquier viernes (alta volatilidad pre-cierre semanal)
        # Solo bloquear la primera media hora de apertura americana
        if weekday == 4 and now.hour == 13 and now.minute < 30:
            logger.info("⚠️ Apertura sesión americana (viernes). Cautela con nuevas entradas.")
            return True

        return False

    except Exception as e:
        logger.warning(f"is_high_impact_event_near error: {e}")
        return False
