"""
Crypto domain: predict 24-hour-ahead prices for major cryptocurrencies.
Ground truth: CoinGecko historical price API.

Free tier: no API key needed for basic endpoints, but rate-limited (~10-30 req/min).
Set COINGECKO_API_KEY in .env to use a Demo key and bypass rate limits.
"""
import os
import time
from datetime import date, timedelta

import requests

from .base import Question

BASE_URL = "https://api.coingecko.com/api/v3"

DEFAULT_COINS = [
    {"id": "bitcoin",        "symbol": "BTC"},
    {"id": "ethereum",       "symbol": "ETH"},
    {"id": "solana",         "symbol": "SOL"},
    {"id": "ripple",         "symbol": "XRP"},
    {"id": "binancecoin",    "symbol": "BNB"},
    {"id": "dogecoin",       "symbol": "DOGE"},
    {"id": "cardano",        "symbol": "ADA"},
    {"id": "avalanche-2",    "symbol": "AVAX"},
    {"id": "chainlink",      "symbol": "LINK"},
    {"id": "polkadot",       "symbol": "DOT"},
]


def _headers() -> dict:
    key = os.environ.get("COINGECKO_API_KEY")
    return {"x-cg-demo-api-key": key} if key else {}


def _get_current_prices(coin_ids: list[str]) -> dict:
    resp = requests.get(
        f"{BASE_URL}/simple/price",
        params={"ids": ",".join(coin_ids), "vs_currencies": "usd", "include_24hr_change": "true"},
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def generate_questions(config: dict, pred_date: date) -> list[Question]:
    coins = config.get("domains", {}).get("crypto", {}).get("coins", DEFAULT_COINS)
    target_date = pred_date + timedelta(days=1)

    coin_ids = [c["id"] for c in coins]
    try:
        prices = _get_current_prices(coin_ids)
    except Exception:
        return []

    questions = []
    for coin in coins:
        cid = coin["id"]
        sym = coin["symbol"]
        data = prices.get(cid)
        if not data:
            continue
        price = float(data["usd"])
        change = data.get("usd_24h_change")
        change_str = f" (24h change: {change:+.1f}%)" if change is not None else ""

        questions.append(Question(
            domain="crypto",
            question_id=f"crypto_{sym}",
            question_text=f"What will the price of {sym} (in USD) be in 24 hours ({target_date.isoformat()})?",
            context=f"The current price of {sym} is ${price:,.2f}{change_str}.",
            unit="USD",
            current_value=price,
            target_date=target_date.isoformat(),
            metadata={"coin_id": cid, "symbol": sym},
        ))
        time.sleep(0.15)  # stay well under free-tier rate limit

    return questions


def fetch_actual(question: Question) -> tuple[float | None, str | None]:
    coin_id = question.metadata["coin_id"]
    target = date.fromisoformat(question.target_date)
    date_str = target.strftime("%d-%m-%Y")  # CoinGecko format
    try:
        resp = requests.get(
            f"{BASE_URL}/coins/{coin_id}/history",
            params={"date": date_str, "localization": "false"},
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        price = resp.json()["market_data"]["current_price"]["usd"]
        return float(price), target.isoformat()
    except Exception:
        return None, None
