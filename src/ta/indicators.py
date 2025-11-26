import yfinance as yf
import pandas as pd


def get_price_history(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV price history for a ticker using yfinance.
    """
    ticker = ticker.upper()
    data = yf.Ticker(ticker).history(period=period, interval=interval)

    if data.empty:
        raise ValueError(f"No price data returned for {ticker} with period={period}, interval={interval}")

    # Normalise column names: Open, High, Low, Close, Volume, etc.
    data = data.rename(columns=lambda c: c.lower().replace(" ", "_"))
    return data


def add_moving_averages(df: pd.DataFrame, close_col: str = "close") -> pd.DataFrame:
    df["ma_20"] = df[close_col].rolling(window=20).mean()
    df["ma_50"] = df[close_col].rolling(window=50).mean()
    df["ma_200"] = df[close_col].rolling(window=200).mean()
    return df


def add_ema(df: pd.DataFrame, close_col: str = "close") -> pd.DataFrame:
    df["ema_20"] = df[close_col].ewm(span=20, adjust=False).mean()
    return df


def add_rsi(df: pd.DataFrame, close_col: str = "close", period: int = 14) -> pd.DataFrame:
    delta = df[close_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))

    df["rsi_14"] = rsi
    return df


def add_macd(df: pd.DataFrame, close_col: str = "close") -> pd.DataFrame:
    ema12 = df[close_col].ewm(span=12, adjust=False).mean()
    ema26 = df[close_col].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal

    df["macd"] = macd
    df["macd_signal"] = signal
    df["macd_hist"] = hist
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    df["atr"] = tr.rolling(window=period).mean()
    return df


def add_bollinger_bands(df: pd.DataFrame, close_col: str = "close", window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    sma = df[close_col].rolling(window=window).mean()
    std = df[close_col].rolling(window=window).std()

    df["bb_mid"] = sma
    df["bb_upper"] = sma + num_std * std
    df["bb_lower"] = sma - num_std * std
    return df


def compute_all_indicators(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch price history and add all the standard indicators.
    Returns a DataFrame with extra columns.
    """
    df = get_price_history(ticker, period=period, interval=interval)
    df = add_moving_averages(df)
    df = add_ema(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_atr(df)
    df = add_bollinger_bands(df)
    return df


def get_latest_ta_summary(ticker: str, period: str = "6mo", interval: str = "1d") -> dict:
    """
    Returns a dict summarising the latest technical state of the stock.
    Handles NaNs gracefully instead of crashing if indicators aren't fully available.
    """
    df = compute_all_indicators(ticker, period=period, interval=interval)

    if df.empty:
        raise ValueError(f"No price data available for {ticker}.")

    latest = df.iloc[-1]  # take last row even if some indicators are NaN

    def safe_float(val):
        return float(val) if pd.notna(val) else None

    price = safe_float(latest.get("close"))
    ma50 = safe_float(latest.get("ma_50"))
    ma200 = safe_float(latest.get("ma_200"))
    rsi = safe_float(latest.get("rsi_14"))
    macd = safe_float(latest.get("macd"))
    macd_signal = safe_float(latest.get("macd_signal"))
    atr = safe_float(latest.get("atr"))
    bb_upper = safe_float(latest.get("bb_upper"))
    bb_lower = safe_float(latest.get("bb_lower"))

    # Simple interpretations
    trend = None
    if ma50 is not None and ma200 is not None and price is not None:
        if price > ma50 > ma200:
            trend = "strong_uptrend"
        elif price < ma50 < ma200:
            trend = "strong_downtrend"
        elif ma50 > ma200:
            trend = "medium_term_bullish"
        else:
            trend = "medium_term_bearish"

    rsi_state = None
    if rsi is not None:
        if rsi >= 70:
            rsi_state = "overbought"
        elif rsi <= 30:
            rsi_state = "oversold"
        elif 40 <= rsi <= 60:
            rsi_state = "neutral"
        else:
            rsi_state = "mixed"

    macd_state = None
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            macd_state = "bullish_cross_or_above_signal"
        elif macd < macd_signal:
            macd_state = "bearish_cross_or_below_signal"

    bb_position = None
    if bb_upper is not None and bb_lower is not None and price is not None:
        if price >= bb_upper:
            bb_position = "near_or_above_upper_band"
        elif price <= bb_lower:
            bb_position = "near_or_below_lower_band"
        else:
            bb_position = "inside_bands"

    return {
        "ticker": ticker.upper(),
        "price": price,
        "ma_50": ma50,
        "ma_200": ma200,
        "trend": trend,
        "rsi_14": rsi,
        "rsi_state": rsi_state,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_state": macd_state,
        "atr": atr,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "bb_position": bb_position,
    }
