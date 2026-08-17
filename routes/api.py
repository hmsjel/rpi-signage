from flask import (
    Blueprint,
    jsonify,
)

from datetime import datetime

from database.db import get_db_connection

from database.settings import (
    get_ticker_sekunder,
    get_billed_sekunder,
    get_dr_interval_sekunder,
    get_dr_antal,
)

from services.media import (
    hent_lokale_nyheder,
)

from services.rss import (
    hent_dr_nyheder,
)

from services.weather import (
    hent_vejr,
)

api_bp = Blueprint(
    "api",
    __name__
)

@api_bp.route("/hent-nyheder")
def hent_nyheder():

    conn = get_db_connection()

    try:
        lokale = hent_lokale_nyheder(conn)

        dr_interval = (
            get_dr_interval_sekunder(conn)
        )

        dr_antal = (
            get_dr_antal(conn)
        )

    finally:
        conn.close()

    dr = hent_dr_nyheder()

    return jsonify(
        nyheder=lokale + dr,
        dr_interval_sekunder=dr_interval,
        dr_antal=dr_antal
    )

@api_bp.route("/hent-aktive-medier")
def hent_aktive_medier():

    idag = datetime.now().strftime(
        "%Y-%m-%d"
    )

    conn = get_db_connection()

    try:

        medier = conn.execute("""
            SELECT filnavn
            FROM medier
            WHERE aktiv = 1

                AND (
                    start_dato IS NULL
                    OR start_dato = ''
                    OR start_dato <= ?
                )

                AND (
                    udloebs_dato IS NULL
                    OR udloebs_dato = ''
                    OR udloebs_dato >= ?
                )

            ORDER BY id ASC
        """, (idag, idag)).fetchall()

        sekunder = (
            get_billed_sekunder(conn)
        )

    finally:
        conn.close()

    return jsonify(
        medier=[
            medie["filnavn"]
            for medie in medier
        ],
        sekunder=sekunder
    )

@api_bp.route("/hent-ticker-indstillinger")
def hent_ticker_indstillinger():

    conn = get_db_connection()

    try:
        sekunder = (
            get_ticker_sekunder(conn)
        )

    finally:
        conn.close()

    return jsonify(
        sekunder=sekunder,
        ticker_sekunder=sekunder
    )

@api_bp.route("/hent-vejr")
def hent_vejr_api():

    by, temperatur, beskrivelse, ikon = (
        hent_vejr()
    )

    return jsonify(
        by=by,
        temp=temperatur,
        beskrivelse=beskrivelse,
        ikon=ikon
    )

