import os
import logging
from dataclasses import dataclass
from typing import Optional

import requests
import yfinance as yf


logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    ticker: str
    last_price: Optional[float]
    day_change_pct: Optional[float]
    pe_ratio: Optional[float]


def _safe_float(v):
    """Convert to float safely, return None on failure."""
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _fetch_finnhub_pe(ticker: str) -> Optional[float]:
    """
    Try to get P/E ratio from Finnhub.
    Returns a float or None if it fails.
    """
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        logger.info("FINNHUB_API_KEY not set; skipping Finnhub PE for %s", ticker)
        return None

    try:
        url = "https://finnhub.io/api/v1/stock/metric"
        params = {
            "symbol": ticker,
            "metric": "valuation",
            "token": api_key,
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json() or {}
        metric = data.get("metric") or {}

        # Try a few plausible Finnhub P/E keys
        for key in [
            "peTTM",
            "peNormalizedAnnual",
            "peBasicExclExtraTTM",
            "peBasicInclExtraTTM",
        ]:
            val = _safe_float(metric.get(key))
            if val is not None and val > 0:
                pe = round(float(val), 2)
                logger.info("Finnhub PE for %s from %s: %s", ticker, key, pe)
                return pe

        logger.info("Finnhub returned no usable PE for %s", ticker)
    except Exception as e:
        logger.warning("Finnhub PE fetch failed for %s: %s", ticker, e)

    return None


def get_market_snapshot(ticker: str) -> MarketSnapshot:
    """
    Fetch last price, day change %, and P/E ratio for a ticker.

    Price & day change: yfinance
    P/E priority:
      1) Finnhub valuation metrics
      2) yfinance fast_info
      3) yfinance get_info dict
      4) EPS-derived fallback
    """
    yt = yf.Ticker(ticker)

    # ===== PRICE & DAY CHANGE =====
    hist = yt.history(period="2d", auto_adjust=False)
    if hist.empty:
        last_price: Optional[float] = None
        day_change_pct: Optional[float] = None
        logger.warning("No price history for %s", ticker)
    else:
        last_price = float(hist["Close"].iloc[-1])
        if len(hist) > 1:
            prev_close = float(hist["Close"].iloc[-2])
            if prev_close:
                day_change_pct = (last_price - prev_close) / prev_close * 100.0
            else:
                day_change_pct = None
        else:
            day_change_pct = None

    # ===== P/E RATIO =====
    pe_ratio: Optional[float] = None

    # --- 1) Finnhub first ---
    pe_ratio = _fetch_finnhub_pe(ticker)

    # --- 2) fast_info from yfinance if Finnhub failed ---
    if pe_ratio is None:
        try:
            fi = yt.fast_info
            pe_ratio = _safe_float(getattr(fi, "trailing_pe", None))
            if pe_ratio is None:
                pe_ratio = _safe_float(getattr(fi, "forward_pe", None))
            if pe_ratio is not None:
                pe_ratio = round(float(pe_ratio), 2)
                logger.info("yfinance fast_info PE for %s: %s", ticker, pe_ratio)
        except Exception as e:
            logger.warning("fast_info PE fetch failed for %s: %s", ticker, e)

    # --- 3) info dict from yfinance ---
    if pe_ratio is None:
        try:
            info = yt.get_info() or {}
            pe_ratio = (
                _safe_float(info.get("trailingPE"))
                or _safe_float(info.get("forwardPE"))
                or _safe_float(info.get("trailingPe"))
                or _safe_float(info.get("forwardPe"))
            )
            if pe_ratio is not None:
                pe_ratio = round(float(pe_ratio), 2)
                logger.info("yfinance info PE for %s: %s", ticker, pe_ratio)
        except Exception as e:
            logger.warning("get_info PE fetch failed for %s: %s", ticker, e)

    # --- 4) crude EPS-based fallback from earnings ---
    if pe_ratio is None and last_price is not None:
        try:
            earnings = yt.get_earnings()
            if earnings is not None and not earnings.empty:
                eps = float(earnings["Earnings"].iloc[-1])
                if eps:
                    pe_ratio = round(last_price / eps, 2)
                    logger.info("EPS-derived PE for %s: %s", ticker, pe_ratio)
        except Exception as e:
            logger.warning("EPS-based PE calculation failed for %s: %s", ticker, e)

    # We allow pe_ratio to stay None if literally every source fails

    return MarketSnapshot(
        ticker=ticker,
        last_price=last_price,
        day_change_pct=day_change_pct,
        pe_ratio=pe_ratio,
    )
