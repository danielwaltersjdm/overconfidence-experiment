"""
Commodities domain: predict next-day futures prices.
Ground truth: yfinance (next available trading day close).
"""
from datetime import date, timedelta

import yfinance as yf

from .base import Question

DEFAULT_COMMODITIES = [
    {"symbol": "GC=F",  "name": "Gold",              "unit": "USD/oz"},
    {"symbol": "CL=F",  "name": "Crude Oil (WTI)",   "unit": "USD/bbl"},
    {"symbol": "SI=F",  "name": "Silver",             "unit": "USD/oz"},
    {"symbol": "NG=F",  "name": "Natural Gas",        "unit": "USD/MMBtu"},
    {"symbol": "HG=F",  "name": "Copper",             "unit": "USD/lb"},
]


def generate_questions(config: dict, pred_date: date) -> list[Question]:
    items = config.get("domains", {}).get("commodities", {}).get("items", DEFAULT_COMMODITIES)
    target_date = pred_date + timedelta(days=1)
    questions = []
    for item in items:
        try:
            hist = yf.Ticker(item["symbol"]).history(period="5d")
            if hist.empty:
                continue
            price = float(hist["Close"].iloc[-1])
            qid = f"commodities_{item['symbol'].replace('=', '').replace('^', '')}"
            questions.append(Question(
                domain="commodities",
                question_id=qid,
                question_text=(
                    f"What will the price of {item['name']} be on "
                    f"{target_date.isoformat()} (or the next available trading day)?"
                ),
                context=f"The current price of {item['name']} is {price:.2f} {item['unit']}.",
                unit=item["unit"],
                current_value=price,
                target_date=target_date.isoformat(),
                metadata={"symbol": item["symbol"], "name": item["name"]},
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
