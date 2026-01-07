from dataclasses import dataclass
from typing import Optional, Any, Dict

import logging
import re
import math

import yfinance as yf
from yahoo_fin import stock_info as si

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    ticker: str
    last_price: Optional[float]
    day_change_pct: Optional[float]
    pe_ratio: Optional[float]


# Common non-numeric placeholders we want to treat as None
_PLACEHOLDERS = {"n/a", "na", "none", "-", "--", "—", "", "nan", "n/m", "nm"}


def _safe_float(v: Any) -> Optional[float]:
    """Attempt to coerce common quote-table / info values into a float.

    This normalizes common placeholders (N/A, --, —, None), removes
    thousands separators and trailing characters like "x", and handles
    parentheses for negative numbers (eg "(12.3)"). If parsing fails
    returns None.
    """
    try:
        if v is None:
            return None

        # If it's already a numeric type
        if isinstance(v, (int, float)):
            # guard against NaN / infinities
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
            return float(v)

        s = str(v).strip()
        # normalize common unicode dashes/spaces
        s = s.replace("\u2013", "-").replace("\u2014", "-").replace("\xa0", " ")
        s = s.strip()
        if not s:
            return None

        low = s.lower()
        # direct placeholder checks
        if low in _PLACEHOLDERS:
            return None

        # Sometimes values are reported like "28.34x", "28.34 x", or "28.34 times"
        # strip common suffixes
        s = re.sub(r"(?i)\b(x|times)\b", "", s)
        s = s.replace(",", "")

        # Handle parentheses as negative numbers: (12.3) -> -12.3
        is_negative = False
        if s.startswith("(") and s.endswith(")"):
            is_negative = True
            s = s[1:-1].strip()

        # Extract first numeric token (handles things like "12.34 - Est")
        m = re.search(r"[-+]?\d+\.?\d*", s)
        if not m:
            return None

        num_str = m.group(0)
        val = float(num_str)
        if is_negative:
            val = -val

        # final sanity checks
        if math.isnan(val) or math.isinf(val):
            return None

        return val
    except Exception:
        return None


def _get_pe_from_yahoo_fin(ticker: str) -> Optional[float]:
    """
    Primary P/E source using yahoo_fin.get_quote_table (dict_result=True).
    Logs the keys returned for debugging and attempts several common key names.
    """
    try:
        qt = si.get_quote_table(ticker, dict_result=True)
    except Exception as e:
        logger.debug("yahoo_fin.get_quote_table failed for %s: %s", ticker, e)
        return None

    if not qt:
        return None

    # Log keys for debugging so we can inspect what yahoo_fin returned for a ticker
    try:
        logger.debug("yahoo_fin quote table keys for %s: %s", ticker, list(qt.keys()))
    except Exception:
        pass

    # Common keys yahoo_fin exposes (include a few variants)
    candidates = [
        "PE Ratio (TTM)",
        "PE Ratio",
        "P/E Ratio",
        "P/E (TTM)",
        "Trailing P/E",
        "Trailing P/E (TTM)",
        "PE (TTM)",
        "Price/Earnings (TTM)",
    ]

    for key in candidates:
        if key in qt:
            try:
                pe_val = _safe_float(qt.get(key))
            except Exception as e:
                logger.debug("Error parsing PE from yahoo_fin key %s for %s: %s", key, ticker, e)
                pe_val = None
            if pe_val is not None and pe_val > 0:
                return round(pe_val, 2)

    return None


def _get_pe_from_yfinance(ticker: str) -> Optional[float]:
    """
    Fallback P/E source using yfinance.Ticker.info (trailingPE) or fast_info.
    Attempts several possible field names and structures used across yfinance versions.
    """
    try:
        yt = yf.Ticker(ticker)
    except Exception as e:
        logger.debug("yfinance.Ticker() failed for %s: %s", ticker, e)
        return None

    # Try info (many yfinance versions expose info as a dict-like mapping)
    try:
        info = getattr(yt, "info", None) or {}
        if isinstance(info, dict) and info:
            for key in ("trailingPE", "trailing_pe", "trailing_pe_ratio", "trailingPe"):
                if key in info:
                    pe_val = _safe_float(info.get(key))
                    if pe_val is not None and pe_val > 0:
                        return round(pe_val, 2)
            # some builds return nested or alternate naming
            pe_val = _safe_float(info.get("trailingPE") or info.get("trailing_pe"))
            if pe_val is not None and pe_val > 0:
                return round(pe_val, 2)
    except Exception as e:
        logger.debug("Error reading yfinance.info for %s: %s", ticker, e)

    # Try fast_info if present (structure varies by yfinance version)
    try:
        fast = getattr(yt, "fast_info", None)
        if fast:
            if isinstance(fast, dict):
                pe_val = _safe_float(fast.get("pe") or fast.get("trailingPE") or fast.get("trailing_pe"))
                if pe_val is not None and pe_val > 0:
                    return round(pe_val, 2)
            else:
                # try attribute access
                pe_attr = getattr(fast, "pe", None)
                pe_val = _safe_float(pe_attr)
                if pe_val is not None and pe_val > 0:
                    return round(pe_val, 2)
    except Exception as e:
        logger.debug("Error reading yfinance.fast_info for %s: %s", ticker, e)

    return None


def _get_price_and_day_change(ticker: str):
    """Get last price and day change percentage using yfinance.history.

    This preserves the original behavior: fetch 2 days, use last Close and
    previous Close to compute percent change if available.
    """
    try:
        yt = yf.Ticker(ticker)
        hist = yt.history(period="2d", auto_adjust=False)
    except Exception as e:
        logger.debug("yfinance.history failed for %s: %s", ticker, e)
        return None, None

    if hist is None or hist.empty:
        return None, None

    try:
        last_price = float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.debug("Error reading last price for %s: %s", ticker, e)
        return None, None

    day_change_pct = None
    if len(hist) > 1:
        try:
            prev_close = float(hist["Close"].iloc[-2])
            if prev_close:
                day_change_pct = (last_price - prev_close) / prev_close * 100.0
        except Exception as e:
            logger.debug("Error computing day change for %s: %s", ticker, e)
            day_change_pct = None

    return last_price, day_change_pct


def get_market_snapshot(ticker: str) -> MarketSnapshot:
    """Return a MarketSnapshot for the given ticker.

    1) Price + day change via yfinance (preserve existing logic)
    2) Try yahoo_fin.get_quote_table first for P/E
    3) Fallback to yfinance (info.fast_info) for P/E if yahoo_fin did not return
    a usable value.
    """
    # 1) Price + day change via yfinance
    last_price, day_change_pct = _get_price_and_day_change(ticker)

    # 2) Try to get P/E from yahoo_fin first
    pe_ratio = _get_pe_from_yahoo_fin(ticker)

    # 3) Fallback to yfinance if yahoo_fin fails or returns None
    if pe_ratio is None:
        pe_ratio = _get_pe_from_yfinance(ticker)

    return MarketSnapshot(
        ticker=ticker,
        last_price=last_price,
        day_change_pct=day_change_pct,
        pe_ratio=pe_ratio,
    )
def get_stock_snapshot(ticker: str) -> dict:
    """
    Backwards-compatible wrapper used by CLI code.

    Returns a dict with keys the CLI expects (price, day_change_pct, market_cap,
    pe_ratio, eps, currency, ticker). Uses yfinance.info as a best-effort
    source for market_cap/eps/currency if available.
    """
    # 1) base snapshot (price + day change + pe)
    ms = get_market_snapshot(ticker)

    # 2) best-effort fetch of extra fields via yfinance.info (optional)
    market_cap = None
    eps = None
    currency = None
    try:
        yt = yf.Ticker(ticker)
        info = getattr(yt, "info", {}) or {}
        # common info keys
        market_cap = info.get("marketCap") or info.get("market_cap") or None
        # EPS keys vary
        eps = info.get("trailingEps") or info.get("epsTrailingTwelveMonths") or info.get("eps") or None
        # currency
        currency = info.get("currency") or info.get("financialCurrency") or None
    except Exception:
        # ignore errors; keep None
        pass

    return {
        "ticker": ticker,
        "price": ms.last_price,
        "day_change_pct": ms.day_change_pct,
        "market_cap": market_cap,
        "pe_ratio": ms.pe_ratio,
        "eps": eps,
        "currency": currency or "USD",
    }
