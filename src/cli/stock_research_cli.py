import os
import json
import argparse

from src.data.market_data import get_stock_snapshot
from src.ta.indicators import get_latest_ta_summary
from src.ai.research_agent import analyse_stock_with_ai
from src.utils.emailer import send_email


def make_logger(lines_list):
    """
    Returns a log() function that prints to console AND appends to lines_list.
    """
    def log(msg: str = ""):
        print(msg)
        lines_list.append(msg)
    return log


def print_snapshot(snapshot: dict, log):
    log("\n=== MARKET SNAPSHOT (FUNDAMENTALS) ===")
    log(f"Ticker:        {snapshot.get('ticker')}")
    price = snapshot.get('price')
    currency = snapshot.get('currency')
    if price is not None and currency:
        log(f"Price:         {price:.2f} {currency}")
    else:
        log("Price:         Data not available")

    change = snapshot.get('day_change_pct')
    if change is not None:
        log(f"Day Change %:  {change:.2f}%")
    else:
        log("Day Change %:  Data not available")

    mcap = snapshot.get('market_cap')
    if mcap is not None:
        log(f"Market Cap:    {mcap:,}")
    else:
        log("Market Cap:    Data not available")

    pe = snapshot.get('pe_ratio')
    if pe is not None:
        log(f"P/E Ratio:     {pe:.2f}")
    else:
        log("P/E Ratio:     Data not available")

    eps = snapshot.get('eps')
    if eps is not None:
        log(f"EPS (trailing): {eps:.2f}")
    else:
        log("EPS (trailing): Data not available")


def print_analysis(analysis: dict, log):
    """
    Pretty-print the AI's combined fundamental + technical analysis.
    """
    log("\n=== AI ANALYSIS (FUNDAMENTAL + TECHNICAL) ===")

    log("\nSummary:")
    log(analysis.get("summary", "No summary."))

    log("\nFundamental Valuation:")
    log(analysis.get("valuation_comment", "No valuation comment."))

    log("\nTechnical Analysis:")
    log(analysis.get("technical_comment", "No technical comment."))

    log("\nBull Case:")
    log(analysis.get("bull_case", "No bull case."))

    log("\nBear Case:")
    log(analysis.get("bear_case", "No bear case."))

    log("\nKey Risks:")
    for risk in analysis.get("risks", []):
        log(f" - {risk}")

    rating = analysis.get("final_rating", "watchlist")
    log(f"\n🔥 FINAL RATING: {rating.upper()}")


def save_analysis_to_file(ticker: str, snapshot: dict, ta_summary: dict, analysis: dict, log):
    """
    Save fundamentals, technicals, and AI analysis into outputs/{TICKER}_analysis.json
    """
    os.makedirs("outputs", exist_ok=True)
    filepath = os.path.join("outputs", f"{ticker}_analysis.json")

    data = {
        "ticker": ticker,
        "snapshot": snapshot,
        "technical": ta_summary,
        "analysis": analysis,
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    log(f"\n💾 Saved analysis to {filepath}")


def analyse_single_ticker(ticker: str, log):
    """
    Full pipeline for one ticker:
    - fundamentals
    - technicals
    - AI combined analysis
    - file save
    """
    log("\n" + "=" * 70)
    log(f"📈 ANALYSING: {ticker}")
    log("=" * 70)

    log(f"\n🔍 Fetching fundamental market data for {ticker}...")
    snapshot = get_stock_snapshot(ticker)
    if "error" in snapshot:
        log(f"❌ Error fetching stock data: {snapshot['error']}")
        return

    print_snapshot(snapshot, log)

    log(f"\n📊 Fetching technical indicators for {ticker}...")
    try:
        ta_summary = get_latest_ta_summary(ticker)
    except Exception as e:
        log(f"❌ Error fetching technical data: {e}")
        ta_summary = {}

    log("\n🤖 Running AI combined analysis (fundamentals + technicals)...")
    analysis = analyse_stock_with_ai(ticker, snapshot, ta_summary)

    if "error" in analysis:
        log(f"❌ AI Error: {analysis['error']}")
        raw = analysis.get("raw")
        if raw:
            log("\nRaw AI output:")
            log(str(raw))
        return

    print_analysis(analysis, log)
    save_analysis_to_file(ticker, snapshot, ta_summary, analysis, log)


def main():
    parser = argparse.ArgumentParser(
        description="AI-powered stock research CLI (fundamentals + technicals)."
    )
    parser.add_argument(
        "tickers",
        nargs="+",
        help="Ticker symbols to analyse (e.g. AAPL MSFT TSLA)",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Do not send email report for this run",
    )

    args = parser.parse_args()
    tickers = [t.upper() for t in args.tickers]

    email_lines = []
    log = make_logger(email_lines)

    log(f"\n🚀 Starting analysis for {len(tickers)} ticker(s): {', '.join(tickers)}")

    for ticker in tickers:
        analyse_single_ticker(ticker, log)

    log("\n✅ Done analysing all tickers.")

    if args.no_email:
        log("\n📭 Email disabled for this run (--no-email).")
        return

    subject = f"Stock Analysis Report: {', '.join(tickers)}"
    body = "\n".join(email_lines)
    send_email(subject, body)


if __name__ == "__main__":
    main()
