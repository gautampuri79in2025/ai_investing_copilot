import argparse

from src.ta.indicators import get_latest_ta_summary


def print_ta_summary(summary: dict):
    ticker = summary["ticker"]
    print("\n" + "=" * 60)
    print(f"📊 TECHNICAL ANALYSIS SUMMARY: {ticker}")
    print("=" * 60)

    price = summary.get("price")
    ma50 = summary.get("ma_50")
    ma200 = summary.get("ma_200")
    trend = summary.get("trend")
    rsi = summary.get("rsi_14")
    rsi_state = summary.get("rsi_state")
    macd = summary.get("macd")
    macd_signal = summary.get("macd_signal")
    macd_state = summary.get("macd_state")
    atr = summary.get("atr")
    bb_upper = summary.get("bb_upper")
    bb_lower = summary.get("bb_lower")
    bb_position = summary.get("bb_position")

    if price is not None:
        print(f"Last Close:      {price:.2f}")
    else:
        print("Last Close:      Data not available")

    if ma50 is not None:
        print(f"50-day MA:       {ma50:.2f}")
    else:
        print("50-day MA:       Data not available")

    if ma200 is not None:
        print(f"200-day MA:      {ma200:.2f}")
    else:
        print("200-day MA:      Data not available")

    print(f"Trend (50 vs 200):   {trend or 'unknown'}")

    if rsi is not None:
        print(f"\nRSI (14):        {rsi:.2f}")
    else:
        print("\nRSI (14):        Data not available")
    print(f"RSI State:       {rsi_state or 'unknown'}")

    if macd is not None and macd_signal is not None:
        print(f"\nMACD:            {macd:.4f}")
        print(f"MACD Signal:     {macd_signal:.4f}")
        print(f"MACD State:      {macd_state or 'unknown'}")
    else:
        print("\nMACD:            Data not available")
        print("MACD Signal:     Data not available")
        print(f"MACD State:      {macd_state or 'unknown'}")

    if atr is not None:
        print(f"\nATR (14):        {atr:.4f}")
    else:
        print("\nATR (14):        Data not available")

    if bb_upper is not None and bb_lower is not None:
        print(f"\nBollinger Upper: {bb_upper:.2f}")
        print(f"Bollinger Lower: {bb_lower:.2f}")
        print(f"BB Position:     {bb_position or 'unknown'}")
    else:
        print("\nBollinger Bands: Data not available")



def main():
    parser = argparse.ArgumentParser(
        description="Technical analysis CLI for a given stock."
    )
    parser.add_argument(
        "ticker",
        help="Ticker symbol to analyse (e.g. AAPL, MSFT, TSLA)",
    )
    parser.add_argument(
        "--period",
        default="6mo",
        help="History period for analysis (e.g. 3mo, 6mo, 1y, 2y). Default: 6mo",
    )
    parser.add_argument(
        "--interval",
        default="1d",
        help="Data interval (e.g. 1d, 1h). Default: 1d",
    )

    args = parser.parse_args()
    ticker = args.ticker.upper()

    print(f"\n🔍 Fetching technicals for {ticker} (period={args.period}, interval={args.interval})...")
    summary = get_latest_ta_summary(ticker, period=args.period, interval=args.interval)
    print_ta_summary(summary)


if __name__ == "__main__":
    main()
