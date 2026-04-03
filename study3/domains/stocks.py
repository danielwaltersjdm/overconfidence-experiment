"""
Stocks domain: predict next-day closing price for a set of tickers.
Ground truth: yfinance (next available trading day close).
"""
from datetime import date, timedelta

import yfinance as yf

from .base import Question

DEFAULT_TICKERS = [
    "AAPL", "NVDA", "MSFT", "AMZN", "GOOGL",
    "META", "TSLA", "AVGO", "SPY", "QQQ",
    "BRK-B", "JPM", "V", "JNJ", "WMT",
    "XOM", "COST", "LLY", "MA", "MU",
]


def generate_questions(config: dict, pred_date: date) -> list[Question]:
    tickers = config.get("domains", {}).get("stocks", {}).get("tickers", DEFAULT_TICKERS)
    target_date = pred_date + timedelta(days=1)
    questions = []
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if hist.empty:
                continue
            price = float(hist["Close"].iloc[-1])
            questions.append(Question(
                domain="stocks",
                question_id=f"stocks_{ticker}",
                question_text=(
                    f"What will the closing price of {ticker} stock be on "
                    f"{target_date.isoformat()} (or the next available trading day)?"
                ),
                context=f"The current closing price of {ticker} is ${price:.2f}.",
                unit="USD",
                current_value=price,
                target_date=target_date.isoformat(),
                metadata={"ticker": ticker},
            ))
        except Exception:
            pass
    return questions


def fetch_actual(question: Question) -> tuple[float | None, str | None]:
    ticker = question.metadata["ticker"]
    target = date.fromisoformat(question.target_date)
    end = target + timedelta(days=6)
    hist = yf.Ticker(ticker).history(start=target.isoformat(), end=end.isoformat())
    if hist.empty:
        return None, None
    actual_date = hist.index[0].date().isoformat()
    return float(hist["Close"].iloc[0]), actual_date
