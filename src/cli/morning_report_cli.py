import argparse
from src.reports.morning_report import generate_morning_report


def main(ticker: str | None = None):
    """
    Entry point for Morning Report.
    - If ticker is provided programmatically → use it
    - Otherwise fall back to CLI parsing
    """

    if ticker is None:
        parser = argparse.ArgumentParser(description="Generate Morning Stock Report")
        parser.add_argument(
            "ticker",
            nargs="?",
            default="GOOG",
            help="Stock ticker symbol (default: GOOG)",
        )
        parser.add_argument(
            "--period",
            default="1y",
            help="Historical data period (default: 1y)",
        )
        parser.add_argument(
            "--interval",
            default="1d",
            help="Data interval (default: 1d)",
        )

        args = parser.parse_args()
        ticker = args.ticker
        period = args.period
        interval = args.interval
    else:
        # Programmatic / workflow usage
        period = "1y"
        interval = "1d"

    print(f"📊 Generating Morning Report for {ticker}")
    generate_morning_report(
        ticker=ticker,
        period=period,
        interval=interval,
    )


if __name__ == "__main__":
    main()
