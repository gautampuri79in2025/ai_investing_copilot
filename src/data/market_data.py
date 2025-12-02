import os
import logging

import requests
import yfinance as yf

def _safe_float(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
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

    # ===== P/E RATIO (more robust multi-source logic) =====
    pe_ratio = None

    # ---- 1. fast_info fields (sometimes present) ----
    try:
        fi = yt.fast_info
        fast_candidates = [
            getattr(fi, "trailing_pe", None),
            getattr(fi, "forward_pe", None),
        ]
        for c in fast_candidates:
            pe_ratio = _safe_float(c)
            if pe_ratio is not None:
                break
    except Exception:
        pass

    # ---- 2. info / get_info dict (more complete, sometimes slow) ----
    if pe_ratio is None:
        info = {}
        try:
            # yfinance versions differ: try .info first, then .get_info()
            try:
                info = yt.info or {}
            except Exception:
                info = yt.get_info() or {}
        except Exception:
            info = {}

        try:
            # Try multiple common P/E keys
            pe_candidates = [
                info.get("trailingPE"),
                info.get("forwardPE"),
                info.get("trailingPe"),
                info.get("forwardPe"),
                info.get("peRatio"),
                info.get("PERatio"),
            ]
            for c in pe_candidates:
                pe_ratio = _safe_float(c)
                if pe_ratio is not None:
                    break

            # If still None, derive from EPS if available: P/E = price / EPS
            if pe_ratio is None:
                eps_candidates = [
                    info.get("trailingEps"),
                    info.get("epsTrailing12Months"),
                    info.get("epsForward"),
                ]
                eps = None
                for e in eps_candidates:
                    eps = _safe_float(e)
                    if eps not in (None, 0.0):
                        break

                if eps not in (None, 0.0) and last_price:
                    pe_ratio = last_price / eps
        except Exception:
            pass

    # ---- 3. Final clean-up ----
    if pe_ratio is not None:
        pe_ratio = round(float(pe_ratio), 2)

    return MarketSnapshot(
        ticker=ticker,
        last_price=last_price,
        day_change_pct=day_change_pct,
        pe_ratio=pe_ratio,
    )
