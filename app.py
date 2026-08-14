import os
import sqlite3
import time
from datetime import datetime

import requests
import feedparser

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    jsonify
)


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# KONFIGURATION
# ============================================================

BASE_DIR = os.path.abspath(
    os.path.dirname(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "skaerm.db"
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
    "mp4",
    "mov",
    "webm"
}


DEFAULT_BILLED_SEKUNDER = 12


# ============================================================
# VEJR
# ============================================================

VEJR_BY = "Skovgaarde"
VEJR_LATITUDE = 56.50941163
VEJR_LONGITUDE = 10.5417551


# ============================================================
# DR RSS
# ============================================================

DR_RSS_URL = (
    "https://www.dr.dk/nyheder/service/feeds/allenyheder"
)


# ============================================================
# CACHE
# ============================================================

VEJR_CACHE_SEKUNDER = 300
NYHED_CACHE_SEKUNDER = 300


weather_cache = {
    "timestamp": 0,
    "data": None
}


news_cache = {
    "timestamp": 0,
    "data": []
}


# ============================================================
# UPLOAD-MAPPE
# ============================================================

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_db_connection()

    try:

        # ----------------------------------------------------
        # MEDIER
        # ----------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS medier (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filnavn TEXT NOT NULL,
                aktiv INTEGER NOT NULL DEFAULT 1,
                udloebs_dato TEXT
            )
        """)

        # ----------------------------------------------------
        # SIKKERHED:
        # Hvis databasen allerede eksisterer fra en ældre
        # version, sørger vi for at udloebs_dato findes.
        # ----------------------------------------------------

        kolonner = conn.execute(
            "PRAGMA table_info(medier)"
        ).fetchall()

        kolonne_navne = [
            kolonne["name"]
            for kolonne in kolonner
        ]

        if "udloebs_dato" not in kolonne_navne:

            conn.execute("""
                ALTER TABLE medier
                ADD COLUMN udloebs_dato TEXT
            """)

        # ----------------------------------------------------
        # TICKER
        # ----------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tekst TEXT NOT NULL
            )
        """)

        # ----------------------------------------------------
        # INDSTILLINGER
        # ----------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS indstillinger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nogle TEXT UNIQUE NOT NULL,
                vaerdi TEXT NOT NULL
            )
        """)

        # ----------------------------------------------------
        # STANDARD BILLEDHASTIGHED
        # ----------------------------------------------------

        conn.execute("""
            INSERT OR IGNORE INTO indstillinger
            (nogle, vaerdi)
            VALUES (?, ?)
        """, (
            "billed_sekunder",
            str(DEFAULT_BILLED_SEKUNDER)
        ))

        conn.commit()

    finally:

        conn.close()


# Initialiser database
init_db()


# ============================================================
# HJÆLPEFUNKTIONER
# ============================================================

def allowed_file(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(
        ".",
        1
    )[1].lower()

    return extension in ALLOWED_EXTENSIONS


# ============================================================
# BILLEDHASTIGHED
# ============================================================

def get_billed_sekunder(conn):

    row = conn.execute("""
        SELECT vaerdi
        FROM indstillinger
        WHERE nogle = ?
    """, (
        "billed_sekunder",
    )).fetchone()

    if not row:

        return DEFAULT_BILLED_SEKUNDER

    try:

        sekunder = int(
            row["vaerdi"]
        )

        if sekunder < 1:

            return DEFAULT_BILLED_SEKUNDER

        return sekunder

    except (
        ValueError,
        TypeError
    ):

        return DEFAULT_BILLED_SEKUNDER


# ============================================================
# LOKALE NYHEDER
# ============================================================

def hent_lokale_nyheder(conn):

    rows = conn.execute("""
        SELECT tekst
        FROM ticker
        ORDER BY id ASC
    """).fetchall()

    return [
        row["tekst"]
        for row in rows
    ]


# ============================================================
# VEJR
# ============================================================

def hent_vejr():

    # Standardværdier
    by = "Skovgaarde"
    latitude = "56.50941163"
    longitude = "10.5417551"

    temperatur = "--°C"
    beskrivelse = "Henter vejr..."
    ikon = "cloud-sun"

    # --------------------------------------------------------
    # Hent valgt lokation fra databasen
    # --------------------------------------------------------

    try:

        conn = get_db_connection()

        by_row = conn.execute("""
            SELECT vaerdi
            FROM indstillinger
            WHERE nogle = "vejr_by"
        """).fetchone()

        lat_row = conn.execute("""
            SELECT vaerdi
            FROM indstillinger
            WHERE nogle = "vejr_lat"
        """).fetchone()

        lon_row = conn.execute("""
            SELECT vaerdi
            FROM indstillinger
            WHERE nogle = "vejr_lon"
        """).fetchone()

        conn.close()

        if by_row:
            by = by_row["vaerdi"]

        if lat_row:
            latitude = lat_row["vaerdi"]

        if lon_row:
            longitude = lon_row["vaerdi"]

    except Exception as error:

        print(
            "Kunne ikke hente vejr-indstillinger:",
            error
        )

    # --------------------------------------------------------
    # Vejrkoder
    # --------------------------------------------------------

    weather_codes = {

        0: "Skyfrit",
        1: "Næsten skyfrit",
        2: "Delvist skyet",
        3: "Skyet",

        45: "Tåget",
        48: "Rimtåge",

        51: "Let støvregn",
        53: "Støvregn",
        55: "Tæt støvregn",

        61: "Let regn",
        63: "Regnvejr",
        65: "Kraftig regn",

        71: "Let snevejr",
        73: "Snevejr",
        75: "Tæt snevejr",

        80: "Lettere regnbyger",
        81: "Regnbyger",
        82: "Kraftige regnbyger",

        95: "Tordenvejr",
        96: "Tordenvejr med hagl",
        99: "Kraftigt tordenvejr med hagl"
    }

    # --------------------------------------------------------
    # Vejrikoner
    # --------------------------------------------------------

    weather_icons = {

        0: "sun-fill",
        1: "cloud-sun-fill",
        2: "cloud-sun",
        3: "cloud-fill",

        45: "cloud-haze",
        48: "cloud-haze2",

        51: "cloud-drizzle",
        53: "cloud-drizzle",
        55: "cloud-drizzle-fill",

        61: "cloud-rain",
        63: "cloud-rain-fill",
        65: "cloud-rain-heavy-fill",

        71: "cloud-snow",
        73: "cloud-snow-fill",
        75: "snow",

        80: "cloud-lightning-rain",
        81: "cloud-lightning-rain-fill",
        82: "cloud-rain-heavy",

        95: "cloud-lightning-fill",
        96: "cloud-hail",
        99: "cloud-hail-fill"
    }

    # --------------------------------------------------------
    # Hent vejret fra Open-Meteo
    # --------------------------------------------------------

    try:

        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}"
            f"&longitude={longitude}"
            "&current=temperature_2m,weather_code"
            "&timezone=Europe%2FCopenhagen"
        )

        response = requests.get(
            weather_url,
            timeout=10
        )

        response.raise_for_status()

        weather_data = response.json()

        current = weather_data.get(
            "current",
            {}
        )

        if current:

            grader = round(
                current.get(
                    "temperature_2m",
                    0
                )
            )

            temperatur = f"{grader}°C"

            code = current.get(
                "weather_code"
            )

            beskrivelse = weather_codes.get(
                code,
                "Skiftende vejr"
            )

            ikon = weather_icons.get(
                code,
                "cloud-sun"
            )

    except Exception as error:

        print(
            "Vejrfejl:",
            error
        )

    return (
        by,
        temperatur,
        beskrivelse,
        ikon
    )


# ============================================================
# DR NYHEDER
# ============================================================

def hent_dr_nyheder():

    global news_cache

    now = time.time()

    # --------------------------------------------------------
    # Brug cache hvis den stadig er gyldig
    # --------------------------------------------------------

    if (
        now - news_cache["timestamp"]
        < NYHED_CACHE_SEKUNDER
    ):

        return news_cache["data"]

    nyheder = []

    headers = {
        "User-Agent": "Infoscreen/1.0"
    }

    try:

        response = requests.get(
            DR_RSS_URL,
            headers=headers,
            timeout=5
        )

        response.raise_for_status()

        feed = feedparser.parse(
            response.content
        )

        for entry in feed.entries[:5]:

            titel = entry.get(
                "title"
            )

            if titel:

                nyheder.append(
                    f"++ DR NYHEDER: {titel} ++"
                )

    except Exception as error:

        print(
            f"Kunne ikke hente DR RSS: {error}"
        )

        # Brug gamle nyheder hvis vi har dem
        if news_cache["data"]:

            return news_cache["data"]

    news_cache = {
        "timestamp": now,
        "data": nyheder
    }

    return nyheder


# ============================================================
# INFOSKÆRM
# ============================================================

@app.route("/")
def skaerm():

    conn = get_db_connection()

    try:

        idag = datetime.now().strftime(
            "%Y-%m-%d"
        )

        # ----------------------------------------------------
        # VIGTIGT:
        #
        # Hent kun aktive medier som:
        #
        # - ikke har en udløbsdato
        # ELLER
        # - har en udløbsdato i dag eller fremover
        #
        # ----------------------------------------------------

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
        """, (
            idag,
        )).fetchall()

        lokale_nyheder = hent_lokale_nyheder(
            conn
        )

        billed_sekunder = get_billed_sekunder(
            conn
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

        ikon="cloud-sun"
    )


# ============================================================
# ADMIN PANEL
# ============================================================

@app.route(
    "/admin",
    methods=["GET", "POST"]
)
def admin():

    conn = get_db_connection()

    # --------------------------------------------------------
    # Byer
    # --------------------------------------------------------

    byer_koordinater = {

        "Skovgaarde": {
            "lat": "56.50941163",
            "lon": "10.5417551"
        },

        "Aarhus": {
            "lat": "56.1567",
            "lon": "10.2108"
        },

        "Randers": {
            "lat": "56.4607",
            "lon": "10.0357"
        },

        "Grenaa": {
            "lat": "56.4158",
            "lon": "10.8783"
        },

        "Ebeltoft": {
            "lat": "56.1952",
            "lon": "10.6831"
        },

        "København": {
            "lat": "55.6761",
            "lon": "12.5683"
        },

        "Aalborg": {
            "lat": "57.0488",
            "lon": "9.9217"
        },

        "Odense": {
            "lat": "55.4038",
            "lon": "10.4024"
        }
    }

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    if request.method == "POST":

        # ====================================================
        # 1. NY TICKER-TEKST
        # ====================================================

        if "nyhed_tekst" in request.form:

            tekst = request.form[
                "nyhed_tekst"
            ].strip()

            if tekst:

                conn.execute("""
                    INSERT INTO ticker (tekst)
                    VALUES (?)
                """, (
                    tekst,
                ))

                conn.commit()

        # ====================================================
        # 2. UPLOAD MEDIE
        # ====================================================

        elif "medie_fil" in request.files:

            fil = request.files[
                "medie_fil"
            ]

            udloeb = request.form.get(
                "udloeb_dato",
                ""
            ).strip()

            if fil and fil.filename:

                filnavn = fil.filename

                if allowed_file(
                    filnavn
                ):

                    fil.save(
                        os.path.join(
                            app.config[
                                "UPLOAD_FOLDER"
                            ],
                            filnavn
                        )
                    )

                    conn.execute("""
                        INSERT INTO medier
                        (
                            filnavn,
                            aktiv,
                            udloebs_dato
                        )
                        VALUES (?, 1, ?)
                    """, (
                        filnavn,
                        udloeb
                    ))

                    conn.commit()

        # ====================================================
        # 3. BILLEDHASTIGHED
        # ====================================================

        elif "billed_sekunder" in request.form:

            sekunder = request.form[
                "billed_sekunder"
            ].strip()

            if sekunder:

                conn.execute("""
                    UPDATE indstillinger
                    SET vaerdi = ?
                    WHERE nogle = "billed_sekunder"
                """, (
                    sekunder,
                ))

                conn.commit()

        # ====================================================
        # 4. VEJR BY
        # ====================================================

        elif "valgt_by" in request.form:

            by_navn = request.form[
                "valgt_by"
            ]

            if by_navn in byer_koordinater:

                # Sørg for at vejr-indstillingerne findes

                conn.execute("""
                    INSERT OR IGNORE INTO indstillinger
                    (nogle, vaerdi)
                    VALUES ("vejr_by", "Skovgaarde")
                """)

                conn.execute("""
                    INSERT OR IGNORE INTO indstillinger
                    (nogle, vaerdi)
                    VALUES ("vejr_lat", "56.50941163")
                """)

                conn.execute("""
                    INSERT OR IGNORE INTO indstillinger
                    (nogle, vaerdi)
                    VALUES ("vejr_lon", "10.5417551")
                """)

                # Gem ny by

                conn.execute("""
                    UPDATE indstillinger
                    SET vaerdi = ?
                    WHERE nogle = "vejr_by"
                """, (
                    by_navn,
                ))

                # Gem latitude

                conn.execute("""
                    UPDATE indstillinger
                    SET vaerdi = ?
                    WHERE nogle = "vejr_lat"
                """, (
                    byer_koordinater[
                        by_navn
                    ]["lat"],
                ))

                # Gem longitude

                conn.execute("""
                    UPDATE indstillinger
                    SET vaerdi = ?
                    WHERE nogle = "vejr_lon"
                """, (
                    byer_koordinater[
                        by_navn
                    ]["lon"],
                ))

                conn.commit()

        return redirect(
            url_for("admin")
        )

    # ========================================================
    # DATA TIL ADMIN
    # ========================================================

    alle_medier = conn.execute("""
        SELECT *
        FROM medier
        ORDER BY id ASC
    """).fetchall()

    alle_nyheder = conn.execute("""
        SELECT *
        FROM ticker
        ORDER BY id ASC
    """).fetchall()

    hastighed_row = conn.execute("""
        SELECT vaerdi
        FROM indstillinger
        WHERE nogle = "billed_sekunder"
    """).fetchone()

    billed_sekunder = (
        hastighed_row["vaerdi"]
        if hastighed_row
        else "12"
    )

    by_row = conn.execute("""
        SELECT vaerdi
        FROM indstillinger
        WHERE nogle = "vejr_by"
    """).fetchone()

    nuvaerende_by = (
        by_row["vaerdi"]
        if by_row
        else "Skovgaarde"
    )

    conn.close()

    return render_template(
        "admin.html",

        medier=alle_medier,

        nyheder=alle_nyheder,

        nuvaerende_sekunder=billed_sekunder,

        nuvaerende_by=nuvaerende_by,

        byer=list(
            byer_koordinater.keys()
        )
    )


# ============================================================
# SKIFT STATUS
# ============================================================

@app.route(
    "/skift-status/<int:id>",
    methods=["POST"]
)
def skift_status(id):

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify(
            success=False,
            error="Ingen data modtaget"
        ), 400

    ny_status = (
        1
        if data.get("aktiv")
        else 0
    )

    conn = get_db_connection()

    try:

        cursor = conn.execute("""
            UPDATE medier
            SET aktiv = ?
            WHERE id = ?
        """, (
            ny_status,
            id
        ))

        conn.commit()

        if cursor.rowcount == 0:

            return jsonify(
                success=False,
                error="Medie ikke fundet"
            ), 404

    finally:

        conn.close()

    return jsonify(
        success=True
    )


# ============================================================
# SLET MEDIE
# ============================================================

@app.route(
    "/slet/<int:id>"
)
def slet(id):

    conn = get_db_connection()

    try:

        medie = conn.execute("""
            SELECT filnavn
            FROM medier
            WHERE id = ?
        """, (
            id,
        )).fetchone()

        if medie:

            filsti = os.path.join(
                app.config[
                    "UPLOAD_FOLDER"
                ],
                medie["filnavn"]
            )

            try:

                os.remove(
                    filsti
                )

            except FileNotFoundError:

                pass

            conn.execute("""
                DELETE FROM medier
                WHERE id = ?
            """, (
                id,
            ))

            conn.commit()

    finally:

        conn.close()

    return redirect(
        url_for("admin")
    )


# ============================================================
# SLET NYHED
# ============================================================

@app.route(
    "/slet-nyhed/<int:id>"
)
def slet_nyhed(id):

    conn = get_db_connection()

    try:

        conn.execute("""
            DELETE FROM ticker
            WHERE id = ?
        """, (
            id,
        ))

        conn.commit()

    finally:

        conn.close()

    return redirect(
        url_for("admin")
    )


# ============================================================
# HENT NYHEDER
# ============================================================

@app.route(
    "/hent-nyheder"
)
def hent_nyheder():

    conn = get_db_connection()

    try:

        nyheder = hent_lokale_nyheder(
            conn
        )

    finally:

        conn.close()

    nyheder.extend(
        hent_dr_nyheder()
    )

    return jsonify(
        nyheder=nyheder
    )


# ============================================================
# HENT AKTIVE MEDIER
# ============================================================

@app.route(
    "/hent-aktive-medier"
)
def hent_aktive_medier():

    idag = datetime.now().strftime(
        "%Y-%m-%d"
    )

    conn = get_db_connection()

    try:

        # ----------------------------------------------------
        # VIGTIGT:
        #
        # Her filtreres udløbne medier også fra.
        #
        # Det var denne del der manglede tidligere.
        # ----------------------------------------------------

        medier = conn.execute("""
            SELECT filnavn
            FROM medier
            WHERE aktiv = 1
            AND (
                udloebs_dato IS NULL
                OR udloebs_dato = ''
                OR udloebs_dato >= ?
            )
            ORDER BY id ASC
        """, (
            idag,
        )).fetchall()

        sekunder = get_billed_sekunder(
            conn
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


# ============================================================
# HENT VEJR
# ============================================================

@app.route(
    "/hent-vejr"
)
def hent_vejr_api():

    (
        by,
        temperatur,
        beskrivelse,
        ikon
    ) = hent_vejr()

    return jsonify(

        by=by,

        temp=temperatur,

        beskrivelse=beskrivelse,

        ikon=ikon
    )


# ============================================================
# UPLOADS
# ============================================================

@app.route(
    "/uploads/<path:filename>"
)
def uploaded_file(filename):

    return send_from_directory(
        app.config[
            "UPLOAD_FOLDER"
        ],
        filename
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )