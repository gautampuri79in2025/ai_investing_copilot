from dataclasses import dataclass
from typing import Optional
import os
import requests
import yfinance as yf


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
        return float(v)
    except Exception:
        return None


def _normalise_ticker_for_finnhub(ticker: str) -> str:
    """
    Map our tickers to Finnhub's expected symbols.
    """
    t = ticker.upper().strip()

    # Special cases
    if t == "BRK-B":
        return "BRK.B"   # Finnhub format for Berkshire B
    if t == "META":
        return "META"
    if t == "GOOG":
        return "GOOG"
    if t == "GOOGL":
        return "GOOGL"

    return t


def _get_pe_from_finnhub(ticker: str) -> Optional[float]:
    """
    Try to get P/E from Finnhub.
    Uses the /stock/metric endpoint and looks at several P/E fields.
    """
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        return None

    symbol = _normalise_ticker_for_finnhub(ticker)

    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/stock/metric",
            params={
                "symbol": symbol,
                "metric": "all",
                "token": api_key,
            },
            timeout=5,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        metric = data.get("metric") or {}

        # Try multiple possible P/E fields
        candidates = [
            metric.get("peTTM"),
            metric.get("peInclExtraTTM"),
            metric.get("peExclExtraTTM"),
            metric.get("peNormalizedAnnual"),
        ]

        for c in candidates:
            val = _safe_float(c)
            if val is not None and val > 0:
                return round(val, 2)

    except Exception:
        # Completely silent fail – we'll fall back to yfinance
        return None

    return None


def get_market_snapshot(ticker: str) -> MarketSnapshot:
    yt = yf.Ticker(ticker)

    # ===== PRICE & DAY CHANGE =====
    hist = yt.history(period="2d", auto_adjust=False)
    if hist.empty:
        last_price = None
        day_change_pct = None
    else:
        last_price = float(hist["Close"].iloc[-1])
        if len(hist) > 1:
            prev_close = float(hist["Close"].iloc[-2])
            day_change_pct = (
                (last_price - prev_close) / prev_close * 100.0
                if prev_close
                else None
            )
        else:
            day_change_pct = None

    # ===== P/E RATIO =====
    pe_ratio: Optional[float] = None

    # 1) Finnhub first (external API)
    pe_ratio = _get_pe_from_finnhub(ticker)

    # 2) yfinance fast_info as fallback
    if pe_ratio is None:
        try:
            fi = yt.fast_info
            pe_ratio = _safe_float(getattr(fi, "trailing_pe", None))
            if pe_ratio is None:
                pe_ratio = _safe_float(getattr(fi, "forward_pe", None))
        except Exception:
            pass

    # 3) yfinance .info dict fallback
    if pe_ratio is None:
        try:
            info = yt.get_info()
            for key in ("trailingPE", "forwardPE", "trailingPe", "forwardPe"):
                val = _safe_float(info.get(key))
                if val is not None:
                    pe_ratio = val
                    break
        except Exception:
            pass

    # 4) Round if we actually got something
    if pe_ratio is not None:
        pe_ratio = round(float(pe_ratio), 2)

    return MarketSnapshot(
        ticker=ticker,
        last_price=last_price,
        day_change_pct=day_change_pct,
        pe_ratio=pe_ratio,
    )
