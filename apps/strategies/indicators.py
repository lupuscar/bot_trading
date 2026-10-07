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

def get_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (ATR)"""
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def get_keltner_channels(df: pd.DataFrame, period: int = 20, atr_multiplier: float = 1.5) -> pd.DataFrame:
    """
    Keltner Channels
    Requiere un DataFrame con ['high', 'low', 'close']
    Retorna un DataFrame con ['EMA', 'Upper', 'Lower']
    """
    ema = get_ema(df['close'], period)
    atr = get_atr(df['high'], df['low'], df['close'], period)
    upper = ema + (atr * atr_multiplier)
    lower = ema - (atr * atr_multiplier)
    return pd.DataFrame({'EMA': ema, 'Upper': upper, 'Lower': lower})

def get_macd(series: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> pd.DataFrame:
    """
    Moving Average Convergence Divergence (MACD)
    Retorna un DataFrame con ['MACD', 'Signal', 'Histogram']
    """
    ema_fast = series.ewm(span=fast_period, adjust=False).mean()
    ema_slow = series.ewm(span=slow_period, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_period, adjust=False).mean()
    hist = macd - signal
    return pd.DataFrame({'MACD': macd, 'Signal': signal, 'Histogram': hist})
