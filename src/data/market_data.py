import yfinance as yf


def get_stock_snapshot(ticker: str):
    """
    Returns a dict with price / valuation metrics for a stock.
    No news, just core fundamentals.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info  # dictionary with metrics

        return {
            "ticker": ticker.upper(),
            "price": info.get("currentPrice"),
            "day_change_pct": info.get("regularMarketChangePercent"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "eps": info.get("trailingEps"),
            "currency": info.get("currency"),
        }

    except Exception as e:
        return {"error": str(e)}
