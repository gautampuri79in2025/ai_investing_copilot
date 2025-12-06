from dataclasses import dataclass
from typing import Optional
import time

import yfinance as yf


@dataclass
class MarketSnapshot:
    """
    Simple container for the top-of-email snapshot.

    NOTE: No market_cap here on purpose – we only care about:
      - last_price
      - day_change_pct
      - pe_ratio
    """
    ticker: str
    last_price: Optional[float]
    day_change_pct: Optional[float]
    pe_ratio: Optional[float]


# --- Simple throttle + per-run cache to avoid Yahoo throttling ---

_LAST_YF_CALL_TS = None          # type: Optional[float]
_REQUEST_GAP_SECONDS = 0.5       # 500 ms between calls
_MARKET_SNAPSHOT_CACHE = {}      # ticker -> MarketSnapshot


def _safe_float(v):
    """Convert to float or return None."""
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _throttled_ticker(ticker: str):
    """
    Wrap yf.Ticker with a global 0.5s gap between calls to avoid
    hammering Yahoo from GitHub Actions / Cloud Shell IPs.
    """
    global _LAST_YF_CALL_TS

    now = time.time()
    if _LAST_YF_CALL_TS is not None:
        delta = now - _LAST_YF_CALL_TS
        if delta < _REQUEST_GAP_SECONDS:
            time.sleep(_REQUEST_GAP_SECONDS - delta)

    _LAST_YF_CALL_TS = time.time()
    return yf.Ticker(ticker)


def get_market_snapshot(ticker: str) -> MarketSnapshot:
    """
    Fetch:
      - last close price
      - day change %
      - P/E ratio (from multiple possible Yahoo sources)

    Also:
      - throttles Yahoo requests
      - caches per run
    """
    # --- per-run cache: don't refetch the same ticker twice in one run ---
    if ticker in _MARKET_SNAPSHOT_CACHE:
        return _MARKET_SNAPSHOT_CACHE[ticker]

    yt = _throttled_ticker(ticker)

    # ===== PRICE & DAY CHANGE =====
    hist = yt.history(period="2d", auto_adjust=False)
    if hist.empty:
        last_price: Optional[float] = None
        day_change_pct: Optional[float] = None
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

    # ===== P/E RATIO (multi-source, throttle-friendly) =====
    pe_ratio: Optional[float] = None

    # ---- 1. fast_info (JSON-like, lightweight) ----
    try:
        fi = yt.fast_info

        # Try mapping-style access first (newer yfinance)
        if hasattr(fi, "get"):
            pe_ratio = (
                _safe_float(fi.get("trailingPE"))
                or _safe_float(fi.get("forwardPE"))
            )
        else:
            # Attribute-style (older yfinance) – try both camel + snake just in case
            for attr in ("trailingPE", "forwardPE", "trailing_pe", "forward_pe"):
                val = getattr(fi, attr, None)
                pe_ratio = _safe_float(val)
                if pe_ratio is not None:
                    break
    except Exception:
        pass

    # ---- 2. info dict (heavier; only if still None) ----
    if pe_ratio is None:
        try:
            info = yt.get_info()
            pe_ratio = (
                _safe_float(info.get("trailingPE"))
                or _safe_float(info.get("forwardPE"))
                or _safe_float(info.get("trailingPe"))
                or _safe_float(info.get("forwardPe"))
            )
        except Exception:
            pass

    # ---- 3. earnings / EPS fallback (last resort) ----
    # P/E = price / EPS
    if pe_ratio is None:
        try:
            earnings = yt.get_earnings()
            if earnings is not None and not earnings.empty and last_price:
                # Take last reported annual EPS
                eps = float(earnings["Earnings"].iloc[-1])
                if eps:
                    pe_ratio = last_price / eps
        except Exception:
            pass

    # ---- 4. Final formatting ----
    if pe_ratio is not None:
        pe_ratio = round(float(pe_ratio), 2)

    snapshot = MarketSnapshot(
        ticker=ticker,
        last_price=last_price,
        day_change_pct=day_change_pct,
        pe_ratio=pe_ratio,
    )

    # cache it for this run
    _MARKET_SNAPSHOT_CACHE[ticker] = snapshot
    return snapshot
