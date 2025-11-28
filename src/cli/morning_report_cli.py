import os
from datetime import datetime
from typing import List

import yfinance as yf
from openai import OpenAI

from src.ta.indicators import get_latest_ta_summary
from src.utils.emailer import send_email

# Default tickers for the morning report
DEFAULT_TICKERS = ["GOOG", "MSFT", "NVDA", "META"]


def build_section_for_ticker(ticker: str) -> str:
    """
    Build a text section for a single ticker:
    - Fetches basic fundamentals with yfinance
    - Fetches latest technical summary
    - Asks OpenAI to interpret the metrics and TA
    - Returns a formatted text block
    """
    t = yf.Ticker(ticker)

    # --- Fundamentals ---
    info = {}
    try:
        info = t.info or {}
    except Exception:
        info = {}

    try:
        fast = t.fast_info
    except Exception:
        fast = None

    price = None
    pe = None
    eps = None
    currency = None
    market_cap = None

    if fast is not None:
        # fast_info behaves like an object with attributes
        price = getattr(fast, "last_price", None)
        currency = getattr(fast, "currency", None)
        market_cap = getattr(fast, "market_cap", None)

    if price is None:
        price = info.get("currentPrice") or info.get("regularMarketPrice")
    pe = info.get("trailingPE") or info.get("forwardPE")
    eps = info.get("trailingEps") or info.get("forwardEps")
    currency = currency or info.get("currency")
    market_cap = market_cap or info.get("marketCap")

    # --- Technicals ---
    try:
        ta = get_latest_ta_summary(ticker, period="6mo", interval="1d")
    except Exception as e:
        ta = {"error": str(e)}

    # --- AI interpretation ---
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    metrics_block = {
        "price": price,
        "currency": currency,
        "pe": pe,
        "eps": eps,
        "market_cap": market_cap,
        "ta": ta,
    }

    prompt = f"""
You are helping a retail investor evaluate a stock.

Stock: {ticker}
Raw metrics and technical summary (as a Python-style dict):
{metrics_block}

1. Briefly summarise what kind of company this is (if known).
2. Explain what the key metrics (price, P/E, EPS, trend, RSI, MACD, moving averages) are telling us right now, in simple language.
3. Give a short bull case and bear case (2–3 bullets each).
4. Finish with a clear stance in UPPERCASE: one of BUY, SMALL_POSITION, WATCHLIST, or AVOID, and say if this is based more on valuation, momentum, or risk.

Keep it under 180–200 words.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a concise, practical investing assistant for a retail investor. "
                    "You explain things simply and avoid jargon."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    ai_text = response.choices[0].message.content.strip()

    # --- Format the section text ---
    lines: List[str] = []
    lines.append("============================================================")
    lines.append(ticker)
    lines.append("============================================================")

    if price is not None:
        try:
            lines.append(f"Price: {price:.2f} {currency or ''}".strip())
        except TypeError:
            lines.append(f"Price: {price} {currency or ''}".strip())
    if pe is not None:
        try:
            lines.append(f"P/E: {pe:.2f}")
        except TypeError:
            lines.append(f"P/E: {pe}")
    if eps is not None:
        try:
            lines.append(f"EPS: {eps:.2f}")
        except TypeError:
            lines.append(f"EPS: {eps}")
    if market_cap is not None:
        lines.append(f"Market Cap: {market_cap}")

    lines.append("")

    if isinstance(ta, dict) and "error" not in ta:
        rsi = ta.get("rsi")
        trend = ta.get("trend")
        macd_signal = ta.get("macd_signal")
        if rsi is not None:
            lines.append(f"RSI: {rsi}")
        if trend:
            lines.append(f"Trend: {trend}")
        if macd_signal:
            lines.append(f"MACD: {macd_signal}")
        lines.append("")
    elif isinstance(ta, dict) and "error" in ta:
        lines.append(f"[TA ERROR] {ta['error']}")
        lines.append("")

    lines.append("AI VIEW:")
    lines.append(ai_text)
    lines.append("")

    return "\n".join(lines)


def main(tickers: List[str] | None = None) -> None:
    """
    Entry point for the morning report CLI.

    - Uses DEFAULT_TICKERS if none are passed
    - Builds a combined report body
    - Sends a single email with all tickers
    """
    if not tickers:
        tickers = DEFAULT_TICKERS

    tickers = [t.upper() for t in tickers]
    print(f"🚀 Running morning report for: {', '.join(tickers)}")

    sections: List[str] = []

    for t in tickers:
        try:
            print(f"🔍 Analysing {t} ...")
            section = build_section_for_ticker(t)
            sections.append(section)
        except Exception as e:
            sections.append(
                "============================================================\n"
                f"{t}\n"
                "============================================================\n"
                f"ERROR while analysing: {e}\n"
            )

    body = "\n\n".join(sections)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    subject = f"Daily Stock Morning Report – {today}"

    # Preview in logs
    print("----- EMAIL BODY PREVIEW (start) -----")
    print(body[:2000])
    print("----- EMAIL BODY PREVIEW (end) -----")

    # Send the email
    try:
        send_email(subject, body)
    except Exception as e:
        print(f"❌ Failed to send email from morning_report_cli: {e}")
        raise


if __name__ == "__main__":
    main()
