import time
import requests
import feedparser

from config import (
    DR_RSS_URL,
    NYHED_CACHE_SEKUNDER,
)

from database.db import get_db_connection
from database.settings import get_dr_antal


def reset_news_cache():
    global news_cache

    news_cache = {
        "timestamp": 0,
        "data": []
    }


# ============================================================
# DR NYHEDER
# ============================================================

def hent_dr_nyheder():
    global news_cache

    now = time.time()

    conn = get_db_connection()

    try:
        antal = get_dr_antal(conn)
    finally:
        conn.close()

    # Cache skal stadig respektere det valgte interval.
    if (
        news_cache["data"]
        and now - news_cache["timestamp"] < NYHED_CACHE_SEKUNDER
        and len(news_cache["data"]) >= antal
    ):
        return news_cache["data"][:antal]

    nyheder = []

    try:
        response = requests.get(
            DR_RSS_URL,
            headers={"User-Agent": "Infoscreen/1.0"},
            timeout=5
        )
        response.raise_for_status()

        feed = feedparser.parse(response.content)

        for entry in feed.entries[:antal]:
            titel = entry.get("title")

            if titel:
                nyheder.append(
                    f"++ DR NYHEDER: {titel} ++"
                )

    except Exception as error:
        print(f"Kunne ikke hente DR RSS: {error}")

        if news_cache["data"]:
            return news_cache["data"][:antal]

    news_cache = {
        "timestamp": now,
        "data": nyheder
    }

    return nyheder
