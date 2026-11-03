import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg2


def fetch_currency_rate(api_url, timeout=10):
    # A. Fetch and validate the provider response
    request = Request(api_url, headers={"User-Agent": "AutaxEstimator/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Currency provider could not be reached.") from exc

    rate = payload.get("rate")
    if rate is None:
        rate = payload.get("rates", {}).get("UGX")
    if rate is None or float(rate) <= 0:
        raise RuntimeError("Currency provider returned an invalid USD to UGX rate.")

    return float(rate)


def save_currency_rate(connection, rate, source):
    # B. Store the latest successful rate with its source and timestamp
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO currency_rates (
                base_currency, quote_currency, rate, source, fetched_at
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            ("USD", "UGX", rate, source, datetime.now(timezone.utc)),
        )
    connection.commit()


def sync_currency_rate(api_url, database_url):
    rate = fetch_currency_rate(api_url)
    connection = None

    # C. Connect only after the external rate has passed validation
    try:
        connection = psycopg2.connect(database_url)
        save_currency_rate(connection, rate, api_url)
    finally:
        if connection:
            connection.close()
    return rate


if __name__ == "__main__":
    provider_url = os.environ.get("CURRENCY_API_URL")
    database_url = os.environ.get("DATABASE_URL")
    if not provider_url or not database_url:
        raise SystemExit("CURRENCY_API_URL and DATABASE_URL are required.")
    synced_rate = sync_currency_rate(provider_url, database_url)
    print(f"USD to UGX rate synced: {synced_rate}")
