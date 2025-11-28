import os
import sys
from datetime import datetime
from typing import List, Dict, Any

import yfinance as yf

from src.ta.indicators import get_latest_ta_summary
from src.ai.research_agent import analyse_stock_with_ai
from src.utils.emailer import send_email


# Default tickers for the morning report
DEFAULT_TICKERS = ["GOOG", "MSFT", "NVDA", "META"]


def get_market_snapshot(ticker: str) -> Dict[str, Any]:
    """
    Fetch a simple market snapshot for a ticker using yfinance.
    Returns a dict with fields used by both AI and email.
    """
    ticker_obj = yf.Ticker(ticker)

    # Try to use fast_info where available
    fast = getattr(ticker_obj, "fast_info", None)
    hist = ticker_obj.history(period="2d")

    price = None
    day_change_pct = None
    currency = None
    market_cap = None
    pe_ratio = None

    if fast:
        price = getattr(fast, "last_price", None)
        currency = getattr(fast, "currency", None)
        market_cap = getattr(fast, "market_cap", None)
        pe_ratio = getattr(fast, "pe_ratio", None)

    # Fallback to history if needed
    if hist is not None and not hist.empty:
        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else None

        if price is None:
            price = last_close

        if prev_close:
            day_change_pct = ((last_close - prev_close) / prev_close) * 100.0

    snapshot = {
        "ticker": ticker,
        "price": price,
        "currency": currency or "USD",
        "day_change_percent": day_change_pct,
        "market_cap": market_cap,
        "pe_ratio": pe_ratio,
    }

    return snapshot


def format_number(value: Any, decimals: int = 2, suffix: str = "") -> str:
    if isinstance(value, (int, float)):
        fmt = f"{{:.{decimals}f}}"
        return fmt.format(value) + suffix
    return str(value)


def build_email_body(
    results: List[Dict[str, Any]],
) -> str:
    """
    Build the email body with:
      1. Summary table at the top
      2. Detailed sections per ticker below (market + TA + AI)
    """
    summary_lines: List[str] = []
    detail_lines: List[str] = []

    # ---- SUMMARY TABLE ----
    summary_lines.append("DAILY STOCK SUMMARY")
    summary_lines.append("")
    summary_lines.append("| Ticker | Last Price | Day Change % | Recommendation |")
    summary_lines.append("|--------|------------|--------------|----------------|")

    for r in results:
        ticker = r["ticker"]

        snapshot = r["snapshot"]
        analysis = r["analysis"]
        ta = r["ta_summary"]

        price = snapshot.get("price")
        change = snapshot.get("day_change_percent")
        rec = analysis.get("final_stance", "watchlist")

        price_str = format_number(price, 2)
        change_str = (
            format_number(change, 2, "%") if isinstance(change, (int, float)) else str(change)
        )

        summary_lines.append(
            f"| {ticker} | {price_str} | {change_str} | {rec} |"
        )

    # ---- DETAILED PER-TICKER SECTIONS ----
    for r in results:
        ticker = r["ticker"]
        snapshot = r["snapshot"]
        analysis = r["analysis"]
        ta = r["ta_summary"]

        detail_lines.append("")
        detail_lines.append("=" * 60)
        detail_lines.append(f"{ticker}")
        detail_lines.append("=" * 60)
        detail_lines.append("")

        # MARKET SNAPSHOT
        detail_lines.append("=== MARKET SNAPSHOT ===")
        detail_lines.append(f"Price:        {format_number(snapshot.get('price'), 2)} {snapshot.get('currency')}")
        detail_lines.append(
            f"Day Change %: {format_number(snapshot.get('day_change_percent'), 2, '%')}"
        )
        detail_lines.append(f"Market Cap:   {snapshot.get('market_cap')}")
        detail_lines.append(f"P/E Ratio:    {format_number(snapshot.get('pe_ratio'), 2)}")
        detail_lines.append("")

        # TECHNICAL ANALYSIS SUMMARY
        if ta:
            detail_lines.append("=== TECHNICALS (TA SUMMARY) ===")
            price = ta.get("price")
            rsi = ta.get("rsi")
            rsi_signal = ta.get("rsi_signal")
            macd = ta.get("macd")
            macd_signal = ta.get("macd_signal")
            macd_hist = ta.get("macd_hist")
            sma50 = ta.get("sma_50")
            sma200 = ta.get("sma_200")
            sma_trend = ta.get("sma_trend")
            overall_trend = ta.get("overall_trend")

            detail_lines.append(f"Close Price:  {format_number(price, 2)}")
            detail_lines.append(f"RSI:          {format_number(rsi, 2)} ({rsi_signal})")
            detail_lines.append(
                f"MACD:         {format_number(macd, 3)} | Signal: {format_number(macd_signal, 3)} | Hist: {format_number(macd_hist, 3)}"
            )
            detail_lines.append(
                f"SMA 50 / 200: {format_number(sma50, 2)} / {format_number(sma200, 2)}  → {sma_trend}"
            )
            detail_lines.append(f"Overall Trend: {overall_trend}")
            detail_lines.append("")
        else:
            detail_lines.append("=== TECHNICALS (TA SUMMARY) ===")
            detail_lines.append("Not enough data to compute TA indicators.")
            detail_lines.append("")

        # AI ANALYSIS
        detail_lines.append("=== AI ANALYSIS ===")
        summary = analysis.get("summary")
        bull_case = analysis.get("bull_case")
        bear_case = analysis.get("bear_case")
        key_risks = analysis.get("key_risks")
        final = analysis.get("final_stance")

        if summary:
            detail_lines.append("Summary:")
            detail_lines.append(summary)
            detail_lines.append("")

        if bull_case:
            detail_lines.append("Bull Case:")
            detail_lines.append(bull_case)
            detail_lines.append("")

        if bear_case:
            detail_lines.append("Bear Case:")
            detail_lines.append(bear_case)
            detail_lines.append("")

        if key_risks:
            detail_lines.append("Key Risks:")
            # key_risks might be a list or string depending on your implementation
            if isinstance(key_risks, list):
                for risk in key_risks:
                    detail_lines.append(f" - {risk}")
            else:
                detail_lines.append(key_risks)
            detail_lines.append("")

        if final:
            detail_lines.append(f"Final Stance: {final}")
            detail_lines.append("")

    summary_block = "\n".join(summary_lines)
    details_block = "\n".join(detail_lines)

    return summary_block + "\n\n" + details_block


def main():
    # Tickers from CLI args or default list
    if len(sys.argv) > 1:
        tickers = [arg.upper() for arg in sys.argv[1:]]
    else:
        tickers = DEFAULT_TICKERS

    print(f"🚀 Running morning report for: {', '.join(tickers)}")

    results: List[Dict[str, Any]] = []

    for ticker in tickers:
        print(f"🔍 Analysing {ticker} ...")

        # Market snapshot
        snapshot = get_market_snapshot(ticker)

        # Technical analysis summary (using your TA module)
        try:
            ta_summary = get_latest_ta_summary(ticker, period="6mo", interval="1d")
        except Exception as e:
            print(f"⚠️ Failed to compute TA for {ticker}: {e}")
            ta_summary = None

        # AI analysis (reuse your existing research agent)
        try:
            try:
                # Newer version that might accept TA as third arg
                analysis = analyse_stock_with_ai(ticker, snapshot, ta_summary)
            except TypeError:
                # Backwards-compatible: older version with only (ticker, snapshot)
                analysis = analyse_stock_with_ai(ticker, snapshot)
        except Exception as e:
            print(f"⚠️ AI analysis failed for {ticker}: {e}")
            analysis = {
                "summary": "AI analysis failed.",
                "bull_case": None,
                "bear_case": None,
                "key_risks": None,
                "final_stance": "watchlist",
            }

        results.append(
            {
                "ticker": ticker,
                "snapshot": snapshot,
                "ta_summary": ta_summary,
                "analysis": analysis,
            }
        )

    # Build the email content
    email_body = build_email_body(results)

    # Subject line with date
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    subject = f"Morning Stock Report - {today_str}"

    # Send email
    try:
        send_email(subject, email_body)
        print("📧 Morning report email sent.")
    except Exception as e:
        print(f"❌ Failed to send morning report email: {e}")

    # Optional: print preview to console (truncated)
    print("\n----- EMAIL BODY PREVIEW (start) -----\n")
    print("\n".join(email_body.splitlines()[:40]))
    print("\n----- EMAIL BODY PREVIEW (end) -----\n")


if __name__ == "__main__":
    main()
