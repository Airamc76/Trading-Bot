import pandas as pd
import pandas_ta as ta

def calculate_all(df):
    """Calcula todos los indicadores técnicos necesarios"""
    if df is None or df.empty:
        return df

    # Limpiar y asegurar que el índice sea datetime si es necesario
    # pandas-ta a veces prefiere que las columnas sean minúsculas
    
    # RSI
    df['rsi'] = ta.rsi(df['close'], length=14)
    
    # MACD
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    if macd is not None:
        df = pd.concat([df, macd], axis=1)
        # Renombrar para facilitar acceso
        df = df.rename(columns={
            'MACD_12_26_9': 'macd',
            'MACDH_12_26_9': 'macd_hist',
            'MACDs_12_26_9': 'macd_signal'
        })
    
    # Bollinger Bands
    bbands = ta.bbands(df['close'], length=20, std=2.0)
    if bbands is not None:
        df = pd.concat([df, bbands], axis=1)
        df = df.rename(columns={
            'BBM_20_2.0': 'bb_mid',
            'BBU_20_2.0': 'bb_upper',
            'BBL_20_2.0': 'bb_lower'
        })
        
    # EMAs
    df['ema_9'] = ta.ema(df['close'], length=9)
    df['ema_21'] = ta.ema(df['close'], length=21)
    df['ema_20'] = ta.ema(df['close'], length=20)
    df['ema_50'] = ta.ema(df['close'], length=50)
    df['ema_200'] = ta.ema(df['close'], length=200)
    
    # ATR
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    return df

def get_latest_values(df):
    """Devuelve el último registro como un diccionario limpio"""
    if df is None or df.empty:
        return {}
    
    last = df.iloc[-1].to_dict()
    # Asegurar que el precio esté presente
    if 'close' in last:
        last['price'] = last['close']
        
    return last
