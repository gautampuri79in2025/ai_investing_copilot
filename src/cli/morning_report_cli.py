import argparse
from src.ta.indicators import get_latest_ta_summary

def print_ta_summary(summary: dict):
    ticker = summary["ticker"]
    print("\n" + "=" * 60)
    print(f"📊 TECHNICAL ANALYSIS SUMMARY: {ticker}")
    print("=" * 60)

    price = summary.get("price")
    ma50 = summary.get("sma_50")
    ma200 = summary.get("sma_200")
    trend = summary.get("sma_trend")
    rsi = summary.get("rsi")
    rsi_state = summary.get("rsi_signal")
    macd = summary.get("macd")
    macd_signal = summary.get("macd_signal")
    macd_state = summary.get("overall_trend")
    vwap = summary.get("vwap")
    peg = summary.get("peg")

    print(f"Last Close:      {price:.2f}" if price is not None else "Last Close:      Data not available")
    print(f"50-day MA:       {ma50:.2f}" if ma50 is not None else "50-day MA:       Data not available")
    print(f"200-day MA:      {ma200:.2f}" if ma200 is not None else "200-day MA:      Data not available")
    print(f"Trend (50 vs 200):   {trend or 'unknown'}")

    print(f"RSI (14):        {rsi:.2f}" if rsi is not None else "RSI (14):        Data not available")
    print(f"RSI State:       {rsi_state or 'unknown'}")

    if macd is not None and macd_signal is not None:
        print(f"\nMACD:            {macd:.4f}")
        print(f"MACD Signal:     {macd_signal:.4f}")
        print(f"Overall Trend:   {macd_state or 'unknown'}")
    else:
        print("\nMACD:            Data not available")
        print("MACD Signal:     Data not available")
        print(f"Overall Trend:   {macd_state or 'unknown'}")

    print(f"\nVWAP:            {vwap:.2f}" if vwap is not None else "\nVWAP:            Data not available")
    print(f"PEG Ratio:       {peg:.2f}" if peg is not None else "PEG Ratio:       Data not available")


def main():
    parser = argparse.ArgumentParser(description="Technical analysis CLI for a given stock.")
    parser.add_argument("ticker", help="Ticker symbol to analyse (e.g. AAPL, MSFT, TSLA)")
    parser.add_argument("--period", default="6mo", help="History period (e.g. 3mo, 6mo, 1y, 2y). Default: 6mo")
    parser.add_argument("--interval", default="1d", help="Data interval (e.g. 1d, 1h). Default: 1d")

    args = parser.parse_args()
    ticker = args.ticker.upper()

    print(f"\n🔍 Fetching technicals for {ticker} (period={args.period}, interval={args.interval})...")
    summary = get_latest_ta_summary(ticker, period=args.period, interval=args.interval)
    if summary:
        print_ta_summary(summary)
    else:
        print("⚠️ Not enough data to compute TA indicators.")


if __name__ == "__main__":
    main()
