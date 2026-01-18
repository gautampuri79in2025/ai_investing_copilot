import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

def _ensure_min_period(period: str, min_days: int = 200) -> str:
    """
    Force a longer period if the requested one is too short
    """
    period_map = {
        "3mo": 63,
        "6mo": 126,
        "1y": 252,
        "2y": 504,
        "5y": 1260,
        "10y": 2520,
        "max": 10000,
    }

    days = period_map.get(period, 0)
    if days < min_days:
        return "2y"
    return period

# ---------------------------------------------------------
# RSI
# ---------------------------------------------------------
def _compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """
    Classic RSI calculation using Wilder's smoothing.
    """
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))
    return rsi


# ---------------------------------------------------------
# MACD
# ---------------------------------------------------------
def _compute_macd(close: pd.Series) -> pd.DataFrame:
    """
    MACD (12, 26, 9) with signal and histogram.
    """
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal

    return pd.DataFrame(
        {
            "macd": macd,
            "macd_signal": signal,
            "macd_hist": hist,
        }
    )


# ---------------------------------------------------------
# Classification Helpers
# ---------------------------------------------------------
def _classify_rsi(rsi: Optional[float]) -> Optional[str]:
    if rsi is None or np.isnan(rsi):
        return None
    if rsi < 30:
        return "oversold"
    if rsi > 70:
        return "overbought"
    if 45 <= rsi <= 55:
        return "neutral"
    if rsi < 45:
        return "weak"
    return "strong"


def _classify_sma_trend(close: float, sma50: float, sma200: float) -> Optional[str]:
    if any(x is None or np.isnan(x) for x in [close, sma50, sma200]):
        return None

    if close > sma50 > sma200:
        return "bullish (price above both SMAs)"
    if close < sma50 < sma200:
        return "bearish (price below both SMAs)"
    if close > sma50 and close < sma200:
        return "short-term strength vs long-term"
    if close < sma50 and close > sma200:
        return "short-term weakness vs long-term"

    return "mixed"


def _combine_overall_trend(
    close: Optional[float],
    sma50: Optional[float],
    sma200: Optional[float],
    macd: Optional[float],
    rsi: Optional[float],
) -> Optional[str]:

    if close is None or np.isnan(close):
        return None

    bullish = 0
    bearish = 0

    # SMA signals
    if sma50 is not None and sma200 is not None and not np.isnan(sma50) and not np.isnan(sma200):
        if close > sma50 > sma200:
            bullish += 2
        elif close < sma50 < sma200:
            bearish += 2

    # MACD
    if macd is not None and not np.isnan(macd):
        if macd > 0:
            bullish += 1
        elif macd < 0:
            bearish += 1

    # RSI
    if rsi is not None and not np.isnan(rsi):
        if rsi > 70:
            bearish += 1
        elif rsi < 30:
            bullish += 1

    if bullish == 0 and bearish == 0:
        return None
    if bullish - bearish >= 2:
        return "overall bullish bias"
    if bearish - bullish >= 2:
        return "overall bearish bias"

    return "neutral / mixed"


# ---------------------------------------------------------
# Main TA Summary Function
# ---------------------------------------------------------
def get_latest_ta_summary(
    ticker: str,
    period: str = "2y",
    interval: str = "1d",
) -> Optional[Dict[str, Any]]:

    yf_ticker = yf.Ticker(ticker)
    safe_period = _ensure_min_period(period, min_days=200)

    df = yf_ticker.history(period=safe_period, interval=interval)

    if safe_period != period:
        print(f"⚠️ Period '{period}' too short for SMA200. Using '{safe_period}' instead.")

    # Check if data is valid
    if df is None or df.empty:
        return None

    # Ensure enough rows for SMA200
    if len(df) < 200:
        raise ValueError("Not enough data to compute 200-day moving average")

    # Work off the Close series
    close = df["Close"].astype(float)

    # Core indicators
    rsi_series = _compute_rsi(close, window=14)
    macd_df = _compute_macd(close)
    sma50 = close.rolling(window=50, min_periods=50).mean()
    sma200 = close.rolling(window=200, min_periods=200).mean()

    # Attach indicators
    df = df.copy()
    df["rsi"] = rsi_series
    df["sma_50"] = sma50
    df["sma_200"] = sma200
    df["macd"] = macd_df["macd"]
    df["macd_signal"] = macd_df["macd_signal"]
    df["macd_hist"] = macd_df["macd_hist"]

    # Strict filter: require SMA200 too
    df_clean = df.dropna(
        subset=["rsi", "sma_50", "sma_200", "macd", "macd_signal"]
    )

    # Pick best available row
    if not df_clean.empty:
        latest = df_clean.iloc[-1]
    else:
        latest = df.iloc[-1]  # fallback

    price = float(latest["Close"])

    rsi_val = latest["rsi"] if not pd.isna(latest["rsi"]) else None
    sma50_val = latest["sma_50"] if not pd.isna(latest["sma_50"]) else None
    sma200_val = latest["sma_200"] if not pd.isna(latest["sma_200"]) else None
    macd_val = latest["macd"] if not pd.isna(latest["macd"]) else None
    macd_signal_val = latest["macd_signal"] if not pd.isna(latest["macd_signal"]) else None
    macd_hist_val = latest["macd_hist"] if not pd.isna(latest["macd_hist"]) else None

    rsi_signal = _classify_rsi(rsi_val)
    sma_trend = _classify_sma_trend(price, sma50_val, sma200_val)
    overall_trend = _combine_overall_trend(
        price, sma50_val, sma200_val, macd_val, rsi_val
    )

    return {
        "ticker": ticker,
        "price": price,
        "rsi": rsi_val,
        "rsi_signal": rsi_signal,
        "macd": macd_val,
        "macd_signal": macd_signal_val,
        "macd_hist": macd_hist_val,
        "sma_50": sma50_val,
        "sma_200": sma200_val,
        "sma_trend": sma_trend,
        "overall_trend": overall_trend,
    }

