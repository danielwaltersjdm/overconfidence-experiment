"""
Forex domain: predict next-day exchange rates for major currency pairs.
Ground truth: yfinance (next available trading day close).
"""
from datetime import date, timedelta

import yfinance as yf

from .base import Question

DEFAULT_PAIRS = [
    {"symbol": "EURUSD=X", "name": "EUR/USD"},
    {"symbol": "GBPUSD=X", "name": "GBP/USD"},
    {"symbol": "USDJPY=X", "name": "USD/JPY"},
    {"symbol": "AUDUSD=X", "name": "AUD/USD"},
    {"symbol": "USDCAD=X", "name": "USD/CAD"},
    {"symbol": "USDCHF=X", "name": "USD/CHF"},
    {"symbol": "NZDUSD=X", "name": "NZD/USD"},
    {"symbol": "USDMXN=X", "name": "USD/MXN"},
]


def generate_questions(config: dict, pred_date: date) -> list[Question]:
    pairs = config.get("domains", {}).get("forex", {}).get("pairs", DEFAULT_PAIRS)
    target_date = pred_date + timedelta(days=1)
    questions = []
    for pair in pairs:
        try:
            hist = yf.Ticker(pair["symbol"]).history(period="5d")
            if hist.empty:
                continue
            rate = float(hist["Close"].iloc[-1])
            questions.append(Question(
                domain="forex",
                question_id=f"forex_{pair['name'].replace('/', '_')}",
                question_text=(
                    f"What will the {pair['name']} exchange rate be on "
                    f"{target_date.isoformat()} (or the next available trading day)?"
                ),
                context=f"The current {pair['name']} rate is {rate:.4f}.",
                unit=pair["name"],
                current_value=rate,
                target_date=target_date.isoformat(),
                metadata={"symbol": pair["symbol"], "name": pair["name"]},
            ))
        except Exception:
            pass
    return questions


def fetch_actual(question: Question) -> tuple[float | None, str | None]:
    symbol = question.metadata["symbol"]
    target = date.fromisoformat(question.target_date)
    end = target + timedelta(days=6)
    hist = yf.Ticker(symbol).history(start=target.isoformat(), end=end.isoformat())
    if hist.empty:
        return None, None
    actual_date = hist.index[0].date().isoformat()
    return float(hist["Close"].iloc[0]), actual_date
