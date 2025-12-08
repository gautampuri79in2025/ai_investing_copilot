from dataclasses import dataclass
from typing import Optional

import yfinance as yf
from yahoo_fin import stock_info as si


@dataclass
class MarketSnapshot:
    ticker: str
    last_price: Optional[float]
    day_change_pct: Optional[float]
    pe_ratio: Optional[float]


def _safe_float(v):
    try:
        if v is None:
            return None
        if isinstance(v, str):
            v = v.replace(",", "").strip()
            # Handle things like "28.34x" or "28.34"
            v = v.replace("x", "")
        return float(v)
    except Exception:
        return None


def _get_pe_from_yahoo_fin(ticker: str) -> Optional[float]:
    """
    Primary P/E source using yahoo_fin.
    Tries to read P/E from the quote table.
    """
    try:
        qt = si.get_quote_table(ticker, dict_result=True)
    except Exception:
        return None

    if not qt:
        return None

    # Common keys yahoo_fin exposes
    candidates = [
        "PE Ratio (TTM)",
        "PE Ratio",
        "P/E Ratio",
        "P/E (TTM)",
    ]

    for key in candidates:
        if key in qt:
            pe_val = _safe_float(qt.get(key))
            if pe_val is not None and pe_val > 0:
                return round(pe_val, 2)

    return None


def _get_price_and_day_change(ticker: str):
    yt = yf.Ticker(ticker)
    hist = yt.history(period="2d", auto_adjust=False)

    if hist.empty:
        return None, None

    last_price = float(hist["Close"].iloc[-1])

    if len(hist) > 1:
        prev_close = float(hist["Close"].iloc[-2])
        if prev_close:
            day_change_pct = (last_price - prev_close) / prev_close * 100.0
        else:
            day_change_pct = None
    else:
        day_change_pct = None

    return last_price, day_change_pct


def get_market_snapshot(ticker: str) -> MarketSnapshot:
    # 1) Price + day change via yfinance (this part was already solid)
    last_price, day_change_pct = _get_price_and_day_change(ticker)

    # 2) Try to get P/E from yahoo_fin first
    pe_ratio = _get_pe_from_yahoo_fin(ticker)

    # 3) If yahoo_fin fails completely, leave as None
    # (we can add yfinance fallback later if really needed)
    return MarketSnapshot(
        ticker=ticker,
        last_price=last_price,
        day_change_pct=day_change_pct,
        pe_ratio=pe_ratio,
    )
