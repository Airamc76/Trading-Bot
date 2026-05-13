"""
indicators.py — Indicadores técnicos + Spread trading (Z-Score Mean Reversion)

Funciones principales:
  calculate_all()              — Indicadores clásicos (RSI, MACD, BB, EMAs, ATR)
  calculate_spread_indicators() — Spread BTC/ETH: Z-score, beta OLS, Hurst, cointegración
  test_cointegration()         — Test Engle-Granger
  calculate_hurst_exponent()   — Exponente de Hurst (R/S analysis)
"""

import numpy as np
import pandas as pd
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)


# ── Indicadores técnicos clásicos ─────────────────────────────────────────────

def calculate_all(df):
    """Calcula RSI, MACD, Bollinger Bands, EMAs y ATR sobre un DataFrame OHLCV."""
    if df is None or df.empty:
        return df

    df['rsi'] = ta.rsi(df['close'], length=14)

    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    if macd is not None:
        df = pd.concat([df, macd], axis=1)
        df = df.rename(columns={
            'MACD_12_26_9':  'macd',
            'MACDH_12_26_9': 'macd_hist',
            'MACDs_12_26_9': 'macd_signal'
        })

    bbands = ta.bbands(df['close'], length=20, std=2.0)
    if bbands is not None:
        df = pd.concat([df, bbands], axis=1)
        df = df.rename(columns={
            'BBM_20_2.0': 'bb_mid',
            'BBU_20_2.0': 'bb_upper',
            'BBL_20_2.0': 'bb_lower'
        })

    df['ema_9']   = ta.ema(df['close'], length=9)
    df['ema_20']  = ta.ema(df['close'], length=20)
    df['ema_50']  = ta.ema(df['close'], length=50)
    df['ema_200'] = ta.ema(df['close'], length=200)
    df['atr']     = ta.atr(df['high'], df['low'], df['close'], length=14)

    return df


def get_latest_values(df):
    """Devuelve el último registro como diccionario limpio."""
    if df is None or df.empty:
        return {}
    last = df.iloc[-1].to_dict()
    if 'close' in last:
        last['price'] = last['close']
    return last


# ── Spread Indicators: Z-Score Mean Reversion ─────────────────────────────────

def calculate_hurst_exponent(series: np.ndarray, max_lags: int = 50) -> float:
    """
    Hurst exponent via Rescaled Range (R/S) analysis.
    H < 0.5 → mean-reverting | H = 0.5 → random walk | H > 0.5 → trending
    """
    if len(series) < 20:
        return 0.5

    lags = range(10, min(max_lags + 1, len(series) // 2), 5)
    rs_values = []

    for lag in lags:
        chunks = len(series) // lag
        if chunks < 2:
            continue
        rs_list = []
        for i in range(chunks):
            chunk = series[i * lag:(i + 1) * lag]
            mean = np.mean(chunk)
            dev  = np.cumsum(chunk - mean)
            R = np.max(dev) - np.min(dev)
            S = np.std(chunk, ddof=1)
            if S > 0:
                rs_list.append(R / S)
        if rs_list:
            rs_values.append((lag, np.mean(rs_list)))

    if len(rs_values) < 2:
        return 0.5

    lags_arr = np.array([r[0] for r in rs_values])
    rs_arr   = np.array([r[1] for r in rs_values])
    try:
        poly = np.polyfit(np.log(lags_arr), np.log(rs_arr), 1)
        return float(np.clip(poly[0], 0.0, 1.0))
    except Exception:
        return 0.5


def test_cointegration(btc_series: pd.Series, eth_series: pd.Series) -> float:
    """
    Engle-Granger cointegration test on log prices.
    Returns p-value — operar si p < 0.05.
    """
    try:
        from statsmodels.tsa.stattools import coint
        log_btc = np.log(btc_series.values.astype(float))
        log_eth = np.log(eth_series.values.astype(float))
        _, pvalue, _ = coint(log_btc, log_eth)
        return float(pvalue)
    except Exception as e:
        logger.warning(f"Error en test de cointegración: {e}")
        return 0.99  # Conservador: asumir no cointegrado


def calculate_spread_indicators(df_btc: pd.DataFrame, df_eth: pd.DataFrame,
                                config_obj) -> dict | None:
    """
    Calcula todos los indicadores para el spread BTC/ETH.

    Spread = log(ETH) - β × log(BTC)
    donde β se calcula con OLS rolling (ventana = ZSCORE_WINDOW_BETA).
    Z-score = (spread - μ) / σ  con ventana = ZSCORE_WINDOW_Z.

    Z < -2 → ETH barato vs BTC → LONG spread (BUY ETH)
    Z > +2 → ETH caro vs BTC  → SHORT spread (SELL ETH)

    Devuelve None si hay datos insuficientes.
    """
    window_beta = getattr(config_obj, 'ZSCORE_WINDOW_BETA', 500)
    window_z    = getattr(config_obj, 'ZSCORE_WINDOW_Z',    60)

    # ── Alinear DataFrames por timestamp/datetime ────────────────────────────
    def _get_close(df):
        df = df.copy()
        if 'datetime' in df.columns:
            df = df.set_index('datetime')
        elif not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        return df['close'].dropna()

    btc_close = _get_close(df_btc)
    eth_close = _get_close(df_eth)

    common_idx = btc_close.index.intersection(eth_close.index)
    min_required = window_beta + window_z + 10
    if len(common_idx) < min_required:
        logger.warning(f"Datos insuficientes para spread: {len(common_idx)} < {min_required}")
        return None

    btc_aligned = btc_close[common_idx]
    eth_aligned = eth_close[common_idx]

    log_btc = np.log(btc_aligned)
    log_eth = np.log(eth_aligned)

    # ── OLS Rolling Beta (β = Cov(X,Y) / Var(X)) ────────────────────────────
    eff_window = min(window_beta, len(log_btc) - 1)
    cov_series  = log_btc.rolling(eff_window).cov(log_eth)
    var_series  = log_btc.rolling(eff_window).var()
    beta_series = cov_series / var_series

    # ── Spread = log(ETH) - β × log(BTC) ────────────────────────────────────
    spread_series = log_eth - beta_series * log_btc

    # ── Z-Score rolling ──────────────────────────────────────────────────────
    mu_series    = spread_series.rolling(window_z).mean()
    sigma_series = spread_series.rolling(window_z).std()
    zscore_series = (spread_series - mu_series) / sigma_series

    latest_z      = float(zscore_series.iloc[-1])
    latest_spread = float(spread_series.iloc[-1])
    latest_beta   = float(beta_series.iloc[-1])
    latest_mu     = float(mu_series.iloc[-1])
    latest_sigma  = float(sigma_series.iloc[-1])

    if any(np.isnan([latest_z, latest_beta, latest_mu, latest_sigma])):
        logger.warning("Valores NaN en spread indicators — ventana insuficiente")
        return None

    # ── RSI de ETH (1h) ──────────────────────────────────────────────────────
    eth_work = df_eth.copy()
    if 'datetime' in eth_work.columns:
        eth_work = eth_work.sort_values('datetime')
    eth_rsi_series = ta.rsi(eth_work['close'], length=14)
    eth_rsi = float(eth_rsi_series.iloc[-1]) if (
        eth_rsi_series is not None and len(eth_rsi_series) > 0
        and not np.isnan(eth_rsi_series.iloc[-1])
    ) else 50.0

    # ── Volumen ETH ──────────────────────────────────────────────────────────
    eth_volume     = float(eth_work['volume'].iloc[-1])
    eth_volume_avg = float(eth_work['volume'].tail(20).mean())

    # ── Hurst Exponent sobre el spread ───────────────────────────────────────
    spread_vals = spread_series.dropna().values[-500:]
    hurst = calculate_hurst_exponent(spread_vals)

    logger.debug(f"Spread stats — β={latest_beta:.3f} | μ={latest_mu:.4f} "
                 f"| σ={latest_sigma:.4f} | Z={latest_z:.2f} | H={hurst:.3f}")

    return {
        "z_score":        latest_z,
        "spread":         latest_spread,
        "beta":           latest_beta,
        "mu":             latest_mu,
        "sigma":          latest_sigma,
        "hurst":          hurst,
        "eth_price":      float(eth_aligned.iloc[-1]),
        "btc_price":      float(btc_aligned.iloc[-1]),
        "eth_rsi":        eth_rsi,
        "eth_volume":     eth_volume,
        "eth_volume_avg": eth_volume_avg,
        "z_series":       zscore_series,
        "spread_series":  spread_series,
    }
