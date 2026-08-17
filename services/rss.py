import time
import requests
import feedparser

from config import (
    DR_RSS_URL,
)

from database.db import get_db_connection
from database.settings import (
    get_dr_antal,
    get_dr_interval_sekunder,
)


news_cache = {
    "timestamp": 0,
    "data": []
}


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
        interval = get_dr_interval_sekunder(conn)
    finally:
        conn.close()

    # Brug det interval, der er valgt i admin.
    #
    # Eksempel:
    # 60 sekunder  -> hent nye nyheder efter 60 sekunder
    # 300 sekunder -> hent nye nyheder efter 5 minutter
    # 3600 sekunder -> hent nye nyheder efter 1 time
    if (
        news_cache["data"]
        and now - news_cache["timestamp"] < interval
        and len(news_cache["data"]) >= antal
    ):
        return news_cache["data"][:antal]

    nyheder = []

    try:
        response = requests.get(
            DR_RSS_URL,
            headers={
                "User-Agent": "Infoscreen/1.0"
            },
            timeout=5
        )

        response.raise_for_status()

        feed = feedparser.parse(
            response.content
        )

        for entry in feed.entries[:antal]:
            titel = entry.get("title")

            if titel:
                nyheder.append(
                    f"++ DR NYHEDER: {titel} ++"
                )

    except Exception as error:
        print(
            f"Kunne ikke hente DR RSS: {error}"
        )

        # Hvis DR ikke kan kontaktes,
        # brug de seneste nyheder fra cachen.
        if news_cache["data"]:
            return news_cache["data"][:antal]

    news_cache = {
        "timestamp": now,
        "data": nyheder
    }

    return nyheder