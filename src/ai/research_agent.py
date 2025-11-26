import os
import json

from openai import OpenAI
from dotenv import load_dotenv

from src.ai.prompts import build_research_prompt

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def analyse_stock_with_ai(ticker: str, snapshot: dict, ta_summary: dict) -> dict:
    """
    Call the OpenAI API to generate a combined fundamental + technical analysis
    and a final BUY/SELL/WATCHLIST rating.

    Returns a dict parsed from the model's JSON response, or an error dict.
    """
    prompt = build_research_prompt(ticker, snapshot, ta_summary)

    raw_text = None
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",  # adjust if you prefer a different model
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a cautious, balanced equity research assistant. "
                        "Always follow the JSON format requested by the user. "
                        "Never output anything outside that JSON object."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        raw_text = response.choices[0].message.content
        parsed = json.loads(raw_text)
        return parsed

    except Exception as e:
        return {
            "error": f"AI call or JSON parsing failed: {e}",
            "raw": raw_text,
        }
