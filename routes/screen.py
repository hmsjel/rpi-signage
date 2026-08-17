from flask import (
    Blueprint,
    render_template,
)

from datetime import datetime

from database.db import get_db_connection

from database.settings import (
    get_billed_sekunder,
    get_ticker_sekunder,
    get_dr_interval_sekunder,
    get_dr_antal,
)

from services.media import (
    hent_lokale_nyheder,
)

from config import VEJR_BY


screen_bp = Blueprint(
    "screen",
    __name__
)


@screen_bp.route("/")
def skaerm():

    conn = get_db_connection()

    try:

        idag = datetime.now().strftime(
            "%Y-%m-%d"
        )

        aktive_medier = conn.execute("""
            SELECT filnavn
            FROM medier
            WHERE aktiv = 1
            AND (
                udloebs_dato IS NULL
                OR udloebs_dato = ''
                OR udloebs_dato >= ?
            )
            ORDER BY id ASC
        """, (idag,)).fetchall()

        lokale_nyheder = (
            hent_lokale_nyheder(conn)
        )

        billed_sekunder = (
            get_billed_sekunder(conn)
        )

        ticker_sekunder = (
            get_ticker_sekunder(conn)
        )

        dr_interval_sekunder = (
            get_dr_interval_sekunder(conn)
        )

        dr_antal = (
            get_dr_antal(conn)
        )

    finally:
        conn.close()

    return render_template(
        "skaerm.html",
        medier=aktive_medier,
        nyheder=lokale_nyheder,
        temp="--°C",
        beskrivelse="Henter vejr...",
        by=VEJR_BY,
        sekunder=billed_sekunder,
        ticker_sekunder=ticker_sekunder,
        dr_interval_sekunder=dr_interval_sekunder,
        dr_antal=dr_antal,
        ikon="cloud-sun"
    )