import pandas as pd
import ccxt
import yfinance as yf
import logging
from datetime import datetime
import config

logger = logging.getLogger(__name__)

def fetch_cryptocompare_data(pair, timeframe, limit=100):
    """Fallback usando la API pública de CryptoCompare"""
    try:
        import requests
        # Convertir 'BTC/USDT' -> 'BTC', 'USDT'
        fsym, tsym = pair.split("/")
        url = f"https://min-api.cryptocompare.com/data/v2/histo{'hour' if timeframe == '1h' else 'day'}?fsym={fsym}&tsym={tsym}&limit={limit}"
        res = requests.get(url, timeout=10).json()
        if res.get("Response") == "Success":
            data = res["Data"]["Data"]
            df = pd.DataFrame(data)
            df['datetime'] = pd.to_datetime(df['time'], unit='s')
            df['timestamp'] = df['time'] * 1000
            df = df.rename(columns={'volumefrom': 'volume'})
            return df[['timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume']]
    except: pass
    return None

def fetch_crypto_data(pair, timeframe, limit=200):
    """Obtiene datos de Crypto usando CCXT (Binance) con fallbacks inteligentes"""
    try:
        exchange = ccxt.binance({
            'apiKey': config.BINANCE_API_KEY,
            'secret': config.BINANCE_API_SECRET,
            'enableRateLimit': True,
        })
        ohlcv = exchange.fetch_ohlcv(pair, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        msg = str(e)
        if "451" in msg or "restricted location" in msg.lower():
            logger.info(f"ℹ️ {pair}: Región restringida para Binance. Intentando CryptoCompare...")
        else:
            logger.warning(f"⚠️ Error en Binance para {pair}: {e}. Intentando CryptoCompare...")
            
        # Fallback 1: CryptoCompare
        df_cc = fetch_cryptocompare_data(pair, timeframe, limit)
        if df_cc is not None:
             return df_cc
             
        # Fallback 2: yfinance (último recurso)
        logger.info(f"ℹ️ {pair}: Usando Yahoo Finance como último recurso...")
        yf_symbol = pair.replace("/", "-").replace("USDT", "USD")
        return fetch_forex_data(yf_symbol, timeframe, limit)

def fetch_forex_data(pair, timeframe, limit=200):
    """Obtiene datos de Forex usando yfinance"""
    try:
        # yfinance usa intervalos como '1h', '1d'
        ticker = yf.Ticker(pair)
        # Aproximamos el periodo basado en el limit y timeframe
        # Para 1h y 200 bars, '15d' es suficiente
        period = "1mo" if timeframe == "1h" else "1y"
        df = ticker.history(period=period, interval=timeframe)
        if df.empty:
            return None
        
        df = df.reset_index()
        # Estandarizar nombres de columnas
        df = df.rename(columns={
            'Datetime': 'datetime', 
            'Date': 'datetime',
            'Open': 'open', 
            'High': 'high', 
            'Low': 'low', 
            'Close': 'close', 
            'Volume': 'volume'
        })
        
        # Quedarnos con los últimos n registros
        df = df.tail(limit).copy()
        # Agregar timestamp en ms para compatibilidad
        df['timestamp'] = df['datetime'].astype('int64') // 10**6
        return df[['timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        logger.error(f"Error fetching forex {pair}: {e}")
        return None

def fetch_all_pairs(pairs, timeframe, limit=200):
    """Punto de entrada para obtener todos los pares configurados"""
    results = {}
    for pair in pairs:
        logger.info(f"📡 Cargando {pair}...")
        if "/" in pair: # Probablemente Crypto (BTC/USDT)
            df = fetch_crypto_data(pair, timeframe, limit)
        else: # Probablemente Forex o similar (EURUSD=X)
            df = fetch_forex_data(pair, timeframe, limit)
            
        if df is not None and not df.empty:
            results[pair] = df
            
    return results

def dataframe_to_db_records(df, pair, timeframe):
    """Convierte DataFrame a lista de diccionarios para la DB"""
    records = []
    for _, row in df.iterrows():
        records.append({
            "pair": pair,
            "timeframe": timeframe,
            "timestamp": row['datetime'].isoformat() if hasattr(row['datetime'], 'isoformat') else str(row['datetime']),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": float(row['volume'])
        })
    return records
