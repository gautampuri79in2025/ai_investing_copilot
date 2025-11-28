import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any


def _compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """
    Classic RSI calculation using Wilder's smoothing.
    """
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()

    # Avoid division by zero
    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))
    return rsi


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


def _classify_sma_trend(
    close: Optional[float],
    sma50: Optional[float],
    sma200: Optional[float],
) -> Optional[str]:
    if any(
        x is None or np.isnan(x)
        for x in [close, sma50, sma200]
    ):
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
    """
    Very simple overall trend classifier using SMA, MACD, RSI.
    This is NOT trading advice, just a structured summary.
    """
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

    # MACD signals
    if macd is not None and not np.isnan(macd):
        if macd > 0:
            bullish += 1
        elif macd < 0:
            bearish += 1

    # RSI signals
    if rsi is not None and not np.isnan(rsi):
        if rsi > 70:
            bearish += 1  # overbought → risk of pullback
        elif rsi < 30:
            bullish += 1  # oversold → potential bounce

    if bullish == 0 and bearish == 0:
        return None
    if bullish - bearish >= 2:
        return "overall bullish bias"
    if bearish - bullish >= 2:
        return "overall bearish bias"
    return "neutral / mixed"


def get_latest_ta_summary(
    ticker: str,
    period: str = "2y",
    interval: str = "1d",
) -> Optional[Dict[str, Any]]:
    """
    Fetch OHLCV history for `ticker` from yfinance and compute a handful of
    technical indicators. Returns a dict summarising the *latest* bar.

    Returns None if there isn't enough data.
    """
    yf_ticker = yf.Ticker(ticker)
    df = yf_ticker.history(period=period, interval=interval)

    if df is None or df.empty:
        return None

    # Work off the Close series
    close = df["Close"].astype(float)

    # Core indicators
    rsi_series = _compute_rsi(close, window=14)
    macd_df = _compute_macd(close)
    sma50 = close.rolling(window=50, min_periods=50).mean()
    sma200 = close.rolling(window=200, min_periods=200).mean()

    # Attach indicators to main df
    df = df.copy()
    df["rsi"] = rsi_series
    df["sma_50"] = sma50
    df["sma_200"] = sma200
    df["macd"] = macd_df["macd"]
    df["macd_signal"] = macd_df["macd_signal"]
    df["macd_hist"] = macd_df["macd_hist"]

    # Drop early rows that don't have enough data for long windows
    df_clean = df.dropna(subset=["rsi", "sma_50", "macd", "macd_signal"])

    if df_clean.empty:
        # not enough data for full TA set, but we can still try with partial
        latest = df.iloc[-1]
    else:
        latest = df_clean.iloc[-1]

    price = float(latest["Close"])

    rsi_val = float(latest.get("rsi")) if not pd.isna(latest.get("rsi")) else None
    sma50_val = float(latest.get("sma_50")) if not pd.isna(latest.get("sma_50")) else None
    sma200_val = float(latest.get("sma_200")) if not pd.isna(latest.get("sma_200")) else None
    macd_val = float(latest.get("macd")) if not pd.isna(latest.get("macd")) else None
    macd_signal_val = (
        float(latest.get("macd_signal")) if not pd.isna(latest.get("macd_signal")) else None
    )
    macd_hist_val = (
        float(latest.get("macd_hist")) if not pd.isna(latest.get("macd_hist")) else None
    )

    rsi_signal = _classify_rsi(rsi_val)
    sma_trend = _classify_sma_trend(price, sma50_val, sma200_val)
    overall_trend = _combine_overall_trend(
        price,
        sma50_val,
        sma200_val,
        macd_val,
        rsi_val,
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
