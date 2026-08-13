import os
import sqlite3
import time

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

from werkzeug.utils import secure_filename


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# KONFIGURATION
# ============================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DATABASE = os.path.join(BASE_DIR, "skaerm.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

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


# Vejr
VEJR_BY = "Skovgaarde"
VEJR_LATITUDE = 56.50941163
VEJR_LONGITUDE = 10.5417551


# DR RSS
DR_RSS_URL = (
    "https://www.dr.dk/nyheder/service/feeds/allenyheder"
)


# Cache-tider
VEJR_CACHE_SEKUNDER = 300       # 5 minutter
NYHED_CACHE_SEKUNDER = 300      # 5 minutter


# Opret upload-mappe
os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# ============================================================
# CACHE
# ============================================================

weather_cache = {
    "timestamp": 0,
    "data": None
}


news_cache = {
    "timestamp": 0,
    "data": []
}


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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS medier (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filnavn TEXT NOT NULL,
                aktiv INTEGER NOT NULL DEFAULT 1
            )
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

WEATHER_CODES = {

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


WEATHER_ICONS = {

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


def hent_vejr():

    global weather_cache

    now = time.time()

    # Brug cache hvis den stadig er gyldig
    if (
        weather_cache["data"] is not None
        and now - weather_cache["timestamp"]
        < VEJR_CACHE_SEKUNDER
    ):

        return weather_cache["data"]


    temperatur = "--°C"
    beskrivelse = "Henter vejr..."
    ikon = "cloud-sun"


    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={VEJR_LATITUDE}"
        f"&longitude={VEJR_LONGITUDE}"
        "&current=temperature_2m,weather_code"
        "&timezone=Europe%2FCopenhagen"
    )


    try:

        response = requests.get(
            weather_url,
            timeout=5
        )

        response.raise_for_status()

        data = response.json()

        current = data.get(
            "current",
            {}
        )

        temperature = current.get(
            "temperature_2m"
        )

        weather_code = current.get(
            "weather_code"
        )


        if temperature is not None:

            temperatur = (
                f"{round(temperature)}°C"
            )


        beskrivelse = WEATHER_CODES.get(
            weather_code,
            "Skiftende vejr"
        )


        ikon = WEATHER_ICONS.get(
            weather_code,
            "cloud-sun"
        )


    except Exception as error:

        print(
            f"Vejrfejl: {error}"
        )


        # Hvis vi har gamle data,
        # bruger vi dem
        if weather_cache["data"] is not None:

            return weather_cache["data"]


    result = (
        VEJR_BY,
        temperatur,
        beskrivelse,
        ikon
    )


    weather_cache = {
        "timestamp": now,
        "data": result
    }


    return result


# ============================================================
# DR NYHEDER
# ============================================================

def hent_dr_nyheder():

    global news_cache

    now = time.time()


    # Brug cache
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


        # Brug gamle nyheder
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

        aktive_medier = conn.execute("""
            SELECT filnavn
            FROM medier
            WHERE aktiv = 1
            ORDER BY id ASC
        """).fetchall()


        lokale_nyheder = hent_lokale_nyheder(
            conn
        )


        billed_sekunder = get_billed_sekunder(
            conn
        )

    finally:

        conn.close()


    # VIGTIGT:
    #
    # Vi henter IKKE længere DR eller vejr her.
    #
    # Browseren henter det efter siden
    # allerede er vist.


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
# ADMIN
# ============================================================

@app.route(
    "/admin",
    methods=["GET", "POST"]
)
def admin():

    conn = get_db_connection()

    try:

        if request.method == "POST":

            # ----------------------------------------
            # NYHED
            # ----------------------------------------

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


            # ----------------------------------------
            # MEDIE
            # ----------------------------------------

            elif "medie_fil" in request.files:

                fil = request.files[
                    "medie_fil"
                ]


                if fil and fil.filename:

                    if not allowed_file(
                        fil.filename
                    ):

                        return (
                            "Filtypen er ikke tilladt.",
                            400
                        )


                    filnavn = secure_filename(
                        fil.filename
                    )


                    if not filnavn:

                        return (
                            "Ugyldigt filnavn.",
                            400
                        )


                    filsti = os.path.join(
                        app.config[
                            "UPLOAD_FOLDER"
                        ],
                        filnavn
                    )


                    fil.save(
                        filsti
                    )


                    conn.execute("""
                        INSERT INTO medier
                        (filnavn, aktiv)
                        VALUES (?, 1)
                    """, (
                        filnavn,
                    ))


                    conn.commit()


            # ----------------------------------------
            # BILLEDSEKUNDER
            # ----------------------------------------

            elif "billed_sekunder" in request.form:

                try:

                    sekunder = int(
                        request.form[
                            "billed_sekunder"
                        ].strip()
                    )


                    if sekunder < 1:

                        raise ValueError


                except (
                    ValueError,
                    TypeError
                ):

                    sekunder = (
                        DEFAULT_BILLED_SEKUNDER
                    )


                conn.execute("""
                    UPDATE indstillinger
                    SET vaerdi = ?
                    WHERE nogle = ?
                """, (
                    str(sekunder),
                    "billed_sekunder"
                ))


                conn.commit()


            return redirect(
                url_for("admin")
            )


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


        billed_sekunder = get_billed_sekunder(
            conn
        )


    finally:

        conn.close()


    return render_template(
        "admin.html",

        medier=alle_medier,

        nyheder=alle_nyheder,

        nuvaerende_sekunder=str(
            billed_sekunder
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


    # DR hentes fra cache
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

    conn = get_db_connection()

    try:

        medier = conn.execute("""
            SELECT filnavn
            FROM medier
            WHERE aktiv = 1
            ORDER BY id ASC
        """).fetchall()


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
