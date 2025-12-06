from dataclasses import dataclass
from typing import Optional, Dict, Any
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


def _compute_pe_from_info(info: Dict[str, Any], last_price: Optional[float]) -> Optional[float]:
    """
    Fallback: compute P/E = price / EPS using various EPS keys
    (these are what Yahoo normally exposes in the JSON).
    """
    if last_price is None or not info:
        return None

    eps_candidates = [
        info.get("trailingEps"),
        info.get("epsTrailingTwelveMonths"),
        info.get("regularMarketEps"),
        info.get("earningsPerShare"),
    ]

    for eps in eps_candidates:
        eps_val = _safe_float(eps)
        if eps_val and eps_val > 0:
            return round(last_price / eps_val, 2)

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
            day_change_pct = ((last_price - prev_close) / prev_close * 100.0) if prev_close else None
        else:
            day_change_pct = None

    # ===== P/E RATIO =====
    pe_ratio: Optional[float] = None

    # 1) Try fast_info first
    try:
        fi = yt.fast_info
        for attr in ("trailing_pe", "forward_pe", "pe_ratio"):
            if pe_ratio is None:
                pe_ratio = _safe_float(getattr(fi, attr, None))
    except Exception:
        pass

    info = None

    # 2) Try info dict: trailingPE / forwardPE
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
            info = None

    # 3) If still None, compute P/E from EPS fields in info
    if pe_ratio is None:
        if info is None:
            try:
                info = yt.get_info()
            except Exception:
                info = None

        if info is not None:
            pe_ratio = _compute_pe_from_info(info, last_price)

    # 4) Last-ditch: use get_earnings() if it really exists and looks like EPS
    if pe_ratio is None:
        try:
            earnings = yt.get_earnings()
            if earnings is not None and not earnings.empty:
                # This is very ticker-dependent; treat carefully
                eps_candidate = earnings.iloc[-1].get("Earnings", None)
                eps_val = _safe_float(eps_candidate)
                if eps_val and eps_val > 0 and last_price:
                    pe_ratio = round(last_price / eps_val, 2)
        except Exception:
            pass

    return MarketSnapshot(
        ticker=ticker,
        last_price=last_price,
        day_change_pct=day_change_pct,
        pe_ratio=pe_ratio,
    )
