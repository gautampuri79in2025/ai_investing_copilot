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

    # ===== P/E RATIO (bulletproof multi-source logic) =====
    pe_ratio = None

    # ---- 1. fast_info fields (sometimes work) ----
    try:
        fi = yt.fast_info
        pe_ratio = _safe_float(getattr(fi, "trailing_pe", None))
        if pe_ratio is None:
            pe_ratio = _safe_float(getattr(fi, "forward_pe", None))
    except:
        pass

    # ---- 2. yahoo info dict (slow but more complete) ----
    if pe_ratio is None:
        try:
            info = yt.get_info()

            # Try multiple possible Yahoo keys
            pe_ratio = (
                _safe_float(info.get("trailingPE"))
                or _safe_float(info.get("forwardPE"))
                or _safe_float(info.get("trailingPe"))
                or _safe_float(info.get("forwardPe"))
            )
        except:
            pass

    # ---- 3. earnings / EPS fallback ----
    # P/E = price / EPS
    if pe_ratio is None:
        try:
            earnings = yt.get_earnings()
            if earnings is not None and not earnings.empty:
                eps = float(earnings["Earnings"].iloc[-1])
                if eps and last_price:
                    pe_ratio = last_price / eps
        except:
            pass

    # ---- 4. If everything fails -> N/A ----
    if pe_ratio is not None:
        pe_ratio = round(float(pe_ratio), 2)

    return MarketSnapshot(
        ticker=ticker,
        last_price=last_price,
        day_change_pct=day_change_pct,
        pe_ratio=pe_ratio,
    )

