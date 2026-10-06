import pandas as pd

def get_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average (SMA)"""
    return series.rolling(window=period).mean()

def get_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average (EMA)"""
    return series.ewm(span=period, adjust=False).mean()

def get_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """
    Bollinger Bands
    Retorna un DataFrame con columnas ['SMA', 'Upper', 'Lower']
    """
    sma = get_sma(series, period)
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return pd.DataFrame({'SMA': sma, 'Upper': upper, 'Lower': lower})

def get_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (RSI)"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))
