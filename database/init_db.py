from database.db import get_db_connection

from config import (
    DEFAULT_BILLED_SEKUNDER,
    DEFAULT_TICKER_SEKUNDER,
    DEFAULT_DR_INTERVAL_SEKUNDER,
    DEFAULT_DR_ANTAL,
    VEJR_BY,
    VEJR_LATITUDE,
    VEJR_LONGITUDE,
)


def init_db():
    conn = get_db_connection()

    try:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS medier (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filnavn TEXT NOT NULL,
                aktiv INTEGER NOT NULL DEFAULT 1,
                udloebs_dato TEXT
            )
        """)

        columns = conn.execute(
            "PRAGMA table_info(medier)"
        ).fetchall()

        column_names = [
            column["name"]
            for column in columns
        ]

        if "udloebs_dato" not in column_names:

            conn.execute("""
                ALTER TABLE medier
                ADD COLUMN udloebs_dato TEXT
            """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tekst TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS indstillinger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nogle TEXT UNIQUE NOT NULL,
                vaerdi TEXT NOT NULL
            )
        """)

        defaults = [
            (
                "billed_sekunder",
                str(DEFAULT_BILLED_SEKUNDER)
            ),
            (
                "ticker_sekunder",
                str(DEFAULT_TICKER_SEKUNDER)
            ),
            (
                "dr_interval_sekunder",
                str(DEFAULT_DR_INTERVAL_SEKUNDER)
            ),
            (
                "dr_antal",
                str(DEFAULT_DR_ANTAL)
            ),
            (
                "vejr_by",
                VEJR_BY
            ),
            (
                "vejr_lat",
                str(VEJR_LATITUDE)
            ),
            (
                "vejr_lon",
                str(VEJR_LONGITUDE)
            ),
        ]

        for nogle, vaerdi in defaults:

            conn.execute("""
                INSERT OR IGNORE INTO indstillinger
                (nogle, vaerdi)
                VALUES (?, ?)
            """, (nogle, vaerdi))

        conn.commit()

    finally:
        conn.close()