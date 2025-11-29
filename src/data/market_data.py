from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
import math

import yfinance as yf


@dataclass
class MarketSnapshot:
    ticker: str
    price: Optional[float]
    day_change_pct: Optional[float]
    pe_ratio: Optional[float]
    eps: Optional[float]


def _safe_float(val) -> Optional[float]:
    """Convert value to float or return None."""
    try:
        if val is None:
            return None
        f = float(val)
        if math.isnan(f):
            return None
        return f
    except Exception:
        return None


def get_market_snapshot(ticker: str) -> Dict[str, Any]:
    """
    Fetch a clean market snapshot for a ticker using yfinance.

    - Price from last close
    - Day % change from previous close
    - EPS (trailing)
    - P/E = price / EPS if possible, otherwise from Yahoo if available
    """
    yf_ticker = yf.Ticker(ticker)

    # -------- Price + Day Change % --------
    price: Optional[float] = None
    day_change_pct: Optional[float] = None

    try:
        hist = yf_ticker.history(period="2d", interval="1d")
    except Exception:
        hist = None

    if hist is not None and not hist.empty:
        last = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else None

        price = _safe_float(last.get("Close"))

        if prev is not None:
            prev_close = _safe_float(prev.get("Close"))
            if prev_close not in (None, 0):
                day_change_pct = (price - prev_close) / prev_close * 100.0

    # -------- Fast info + full info --------
    try:
        fast = dict(yf_ticker.fast_info)
    except Exception:
        fast = {}

    try:
        info = yf_ticker.info or {}
    except Exception:
        info = {}

    # -------- EPS (trailing) --------
    eps = _safe_float(
        fast.get("eps")
        or fast.get("trailingEps")
        or info.get("trailingEps")
        or info.get("epsTrailingTwelveMonths")
    )

    # -------- P/E Ratio --------
    pe_ratio = _safe_float(
        fast.get("trailingPE")
        or fast.get("peRatio")
        or info.get("trailingPE")
        or info.get("forwardPE")
    )

    # If still missing but we have price + EPS, calculate manually
    if (pe_ratio is None) and (price is not None) and (eps not in (None, 0)):
        pe_ratio = price / eps

    snapshot = MarketSnapshot(
        ticker=ticker,
        price=price,
        day_change_pct=day_change_pct,
        pe_ratio=pe_ratio,
        eps=eps,
    )

    return asdict(snapshot)
