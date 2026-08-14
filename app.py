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
    jsonify,
    session,
)

app = Flask(__name__)

# ============================================================
# SIKKERHED / LOGIN
# ============================================================

app.secret_key = "SKIFT-DENNE-TIL-EN-LANG-TILFÆLDIG-NØGLE"

ADMIN_BRUGERNAVN = "admin"
ADMIN_KODE = "1234"

# ============================================================
# KONFIGURATION
# ============================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DATABASE = os.path.join(BASE_DIR, "skaerm.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp",
    "mp4", "mov", "webm"
}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================================
# STANDARDINDSTILLINGER
# ============================================================

DEFAULT_BILLED_SEKUNDER = 12
DEFAULT_TICKER_SEKUNDER = 90
DEFAULT_DR_INTERVAL_SEKUNDER = 300
DEFAULT_DR_ANTAL = 5

VEJR_BY = "Skovgaarde"
VEJR_LATITUDE = 56.50941163
VEJR_LONGITUDE = 10.5417551

DR_RSS_URL = "https://www.dr.dk/nyheder/service/feeds/allenyheder"

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
# DATABASE
# ============================================================

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


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

        column_names = [column["name"] for column in columns]

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
            ("billed_sekunder", str(DEFAULT_BILLED_SEKUNDER)),
            ("ticker_sekunder", str(DEFAULT_TICKER_SEKUNDER)),
            ("dr_interval_sekunder", str(DEFAULT_DR_INTERVAL_SEKUNDER)),
            ("dr_antal", str(DEFAULT_DR_ANTAL)),
            ("vejr_by", VEJR_BY),
            ("vejr_lat", str(VEJR_LATITUDE)),
            ("vejr_lon", str(VEJR_LONGITUDE)),
        ]

        for nogle, vaerdi in defaults:
            conn.execute("""
                INSERT OR IGNORE INTO indstillinger (nogle, vaerdi)
                VALUES (?, ?)
            """, (nogle, vaerdi))

        conn.commit()

    finally:
        conn.close()


init_db()

# ============================================================
# HJÆLPEFUNKTIONER
# ============================================================

def allowed_file(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def get_indstilling(conn, nogle, default):
    row = conn.execute("""
        SELECT vaerdi
        FROM indstillinger
        WHERE nogle = ?
    """, (nogle,)).fetchone()

    return row["vaerdi"] if row else default


def set_indstilling(conn, nogle, vaerdi):
    conn.execute("""
        INSERT INTO indstillinger (nogle, vaerdi)
        VALUES (?, ?)
        ON CONFLICT(nogle)
        DO UPDATE SET vaerdi = excluded.vaerdi
    """, (nogle, str(vaerdi)))


def get_int_setting(conn, key, default, minimum=None, maximum=None):
    value = get_indstilling(conn, key, str(default))

    try:
        value = int(value)
    except (ValueError, TypeError):
        return default

    if minimum is not None and value < minimum:
        return default

    if maximum is not None and value > maximum:
        return default

    return value


def get_billed_sekunder(conn):
    return get_int_setting(
        conn,
        "billed_sekunder",
        DEFAULT_BILLED_SEKUNDER,
        1,
        120
    )


def get_ticker_sekunder(conn):
    return get_int_setting(
        conn,
        "ticker_sekunder",
        DEFAULT_TICKER_SEKUNDER,
        5,
        300
    )


def get_dr_interval_sekunder(conn):
    return get_int_setting(
        conn,
        "dr_interval_sekunder",
        DEFAULT_DR_INTERVAL_SEKUNDER,
        30,
        3600
    )


def get_dr_antal(conn):
    return get_int_setting(
        conn,
        "dr_antal",
        DEFAULT_DR_ANTAL,
        1,
        20
    )


def hent_lokale_nyheder(conn):
    rows = conn.execute("""
        SELECT tekst
        FROM ticker
        ORDER BY id ASC
    """).fetchall()

    return [row["tekst"] for row in rows]


def hent_alle_nyheder_til_admin(conn):
    rows = conn.execute("""
        SELECT id, tekst
        FROM ticker
        ORDER BY id ASC
    """).fetchall()

    return rows

# ============================================================
# VEJR
# ============================================================

def hent_vejr():
    by = VEJR_BY
    latitude = str(VEJR_LATITUDE)
    longitude = str(VEJR_LONGITUDE)

    temperatur = "--°C"
    beskrivelse = "Henter vejr..."
    ikon = "cloud-sun"

    try:
        conn = get_db_connection()

        by = get_indstilling(conn, "vejr_by", VEJR_BY)
        latitude = get_indstilling(conn, "vejr_lat", str(VEJR_LATITUDE))
        longitude = get_indstilling(conn, "vejr_lon", str(VEJR_LONGITUDE))

        conn.close()

    except Exception as error:
        print("Kunne ikke hente vejr-indstillinger:", error)

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
        99: "Kraftigt tordenvejr med hagl",
    }

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
        99: "cloud-hail-fill",
    }

    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}"
            f"&longitude={longitude}"
            "&current=temperature_2m,weather_code"
            "&timezone=Europe%2FCopenhagen"
        )

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        current = response.json().get("current", {})

        if current:
            grader = round(current.get("temperature_2m", 0))
            temperatur = f"{grader}°C"

            code = current.get("weather_code")
            beskrivelse = weather_codes.get(code, "Skiftende vejr")
            ikon = weather_icons.get(code, "cloud-sun")

    except Exception as error:
        print("Vejrfejl:", error)

    return by, temperatur, beskrivelse, ikon

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

# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        brugernavn = request.form.get("brugernavn", "").strip()
        kode = request.form.get("kode", "").strip()

        if (
            brugernavn == ADMIN_BRUGERNAVN
            and kode == ADMIN_KODE
        ):
            session["logget_ind"] = True
            return redirect(url_for("admin"))

        return render_template(
            "login.html",
            fejl="Forkert brugernavn eller kode"
        )

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logget_ind", None)
    return redirect(url_for("login"))

# ============================================================
# INFOSKÆRM
# ============================================================

@app.route("/")
def skaerm():
    conn = get_db_connection()

    try:
        idag = datetime.now().strftime("%Y-%m-%d")

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

        lokale_nyheder = hent_lokale_nyheder(conn)
        billed_sekunder = get_billed_sekunder(conn)
        ticker_sekunder = get_ticker_sekunder(conn)
        dr_interval_sekunder = get_dr_interval_sekunder(conn)
        dr_antal = get_dr_antal(conn)

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

# ============================================================
# ADMIN PANEL
# ============================================================

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("logget_ind"):
        return redirect(url_for("login"))

    byer_koordinater = {
        "Skovgaarde": {"lat": "56.50941163", "lon": "10.5417551"},
        "Aarhus": {"lat": "56.1567", "lon": "10.2108"},
        "Randers": {"lat": "56.4607", "lon": "10.0357"},
        "Grenaa": {"lat": "56.4158", "lon": "10.8783"},
        "Ebeltoft": {"lat": "56.1952", "lon": "10.6831"},
        "København": {"lat": "55.6761", "lon": "12.5683"},
        "Aalborg": {"lat": "57.0488", "lon": "9.9217"},
        "Odense": {"lat": "55.4038", "lon": "10.4024"},
    }

    conn = get_db_connection()

    try:
        if request.method == "POST":

            # -----------------------------------------------
            # NY TICKER-TEKST
            # -----------------------------------------------
            if "nyhed_tekst" in request.form:
                tekst = request.form["nyhed_tekst"].strip()

                if tekst:
                    conn.execute("""
                        INSERT INTO ticker (tekst)
                        VALUES (?)
                    """, (tekst,))
                    conn.commit()

            # -----------------------------------------------
            # UPLOAD
            # -----------------------------------------------
            elif "medie_fil" in request.files:
                fil = request.files["medie_fil"]
                udloeb = request.form.get("udloeb_dato", "").strip()

                if fil and fil.filename and allowed_file(fil.filename):
                    filnavn = os.path.basename(fil.filename)

                    fil.save(
                        os.path.join(
                            app.config["UPLOAD_FOLDER"],
                            filnavn
                        )
                    )

                    conn.execute("""
                        INSERT INTO medier
                        (filnavn, aktiv, udloebs_dato)
                        VALUES (?, 1, ?)
                    """, (filnavn, udloeb))

                    conn.commit()

            # -----------------------------------------------
            # BILLEDHASTIGHED
            # -----------------------------------------------
            elif "billed_sekunder" in request.form:
                try:
                    value = int(request.form["billed_sekunder"])

                    if 1 <= value <= 120:
                        set_indstilling(
                            conn,
                            "billed_sekunder",
                            value
                        )
                        conn.commit()

                except (ValueError, TypeError):
                    pass

            # -----------------------------------------------
            # TICKER-HASTIGHED
            # -----------------------------------------------
            elif "ticker_sekunder" in request.form:
                try:
                    value = int(request.form["ticker_sekunder"])

                    if 5 <= value <= 300:
                        set_indstilling(
                            conn,
                            "ticker_sekunder",
                            value
                        )
                        conn.commit()

                except (ValueError, TypeError):
                    pass

            # -----------------------------------------------
            # DR INTERVAL + ANTAL
            # -----------------------------------------------
            elif "dr_interval_sekunder" in request.form:
                try:
                    interval = int(
                        request.form["dr_interval_sekunder"]
                    )
                    antal = int(
                        request.form["dr_antal"]
                    )

                    if 30 <= interval <= 3600:
                        set_indstilling(
                            conn,
                            "dr_interval_sekunder",
                            interval
                        )

                    if 1 <= antal <= 20:
                        set_indstilling(
                            conn,
                            "dr_antal",
                            antal
                        )

                    conn.commit()

                    # Tving ny DR-hentning efter ændring.
                    global news_cache
                    news_cache = {
                        "timestamp": 0,
                        "data": []
                    }

                except (ValueError, TypeError, KeyError):
                    pass

            # -----------------------------------------------
            # VEJR BY
            # -----------------------------------------------
            elif "valgt_by" in request.form:
                by_navn = request.form["valgt_by"]

                if by_navn in byer_koordinater:
                    set_indstilling(
                        conn,
                        "vejr_by",
                        by_navn
                    )

                    set_indstilling(
                        conn,
                        "vejr_lat",
                        byer_koordinater[by_navn]["lat"]
                    )

                    set_indstilling(
                        conn,
                        "vejr_lon",
                        byer_koordinater[by_navn]["lon"]
                    )

                    conn.commit()

            return redirect(url_for("admin"))

        alle_medier = conn.execute("""
            SELECT *
            FROM medier
            ORDER BY id ASC
        """).fetchall()

        alle_nyheder = hent_alle_nyheder_til_admin(conn)

        billed_sekunder = get_billed_sekunder(conn)
        ticker_sekunder = get_ticker_sekunder(conn)
        dr_interval_sekunder = get_dr_interval_sekunder(conn)
        dr_antal = get_dr_antal(conn)

        nuvaerende_by = get_indstilling(
            conn,
            "vejr_by",
            VEJR_BY
        )

    finally:
        conn.close()

    # -----------------------------------------------
    # DISKPLADS
    # -----------------------------------------------
    try:
        import shutil

        total, used, free = shutil.disk_usage(BASE_DIR)

        total_gb = total / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        free_gb = free / (1024 ** 3)

        used_percent = (used / total * 100) if total else 0

    except Exception:
        total_gb = used_gb = free_gb = used_percent = 0

    current_date = datetime.now().strftime("%Y-%m-%d")

    return render_template(
        "admin.html",
        medier=alle_medier,
        nyheder=alle_nyheder,
        nuvaerende_sekunder=billed_sekunder,
        nuvaerende_ticker_sekunder=ticker_sekunder,
        dr_interval_sekunder=dr_interval_sekunder,
        dr_antal=dr_antal,
        nuvaerende_by=nuvaerende_by,
        byer=list(byer_koordinater.keys()),
        current_date=current_date,
        disk_total_gb=f"{total_gb:.1f}",
        disk_used_gb=f"{used_gb:.1f}",
        disk_free_gb=f"{free_gb:.1f}",
        disk_used_percent=round(used_percent, 1),
    )

# ============================================================
# SKIFT STATUS
# ============================================================

@app.route("/skift-status/<int:id>", methods=["POST"])
def skift_status(id):
    if not session.get("logget_ind"):
        return jsonify(
            success=False,
            error="Ikke logget ind"
        ), 401

    data = request.get_json(silent=True)

    if not data:
        return jsonify(
            success=False,
            error="Ingen data modtaget"
        ), 400

    ny_status = 1 if data.get("aktiv") else 0

    conn = get_db_connection()

    try:
        cursor = conn.execute("""
            UPDATE medier
            SET aktiv = ?
            WHERE id = ?
        """, (ny_status, id))

        conn.commit()

        if cursor.rowcount == 0:
            return jsonify(
                success=False,
                error="Medie ikke fundet"
            ), 404

    finally:
        conn.close()

    return jsonify(success=True)

# ============================================================
# ÆNDR UDLØBSDATO
# ============================================================

@app.route("/aendre-udloeb/<int:id>", methods=["POST"])
def aendre_udloeb(id):
    if not session.get("logget_ind"):
        return redirect(url_for("login"))

    udloeb = request.form.get("udloeb_dato", "").strip()
    udloeb = udloeb if udloeb else None

    conn = get_db_connection()

    try:
        cursor = conn.execute("""
            UPDATE medier
            SET udloebs_dato = ?
            WHERE id = ?
        """, (udloeb, id))

        conn.commit()

        if cursor.rowcount == 0:
            return "Medie ikke fundet", 404

    finally:
        conn.close()

    return redirect(url_for("admin"))

# ============================================================
# SLET MEDIE
# ============================================================

@app.route("/slet/<int:id>")
def slet(id):
    if not session.get("logget_ind"):
        return redirect(url_for("login"))

    conn = get_db_connection()

    try:
        medie = conn.execute("""
            SELECT filnavn
            FROM medier
            WHERE id = ?
        """, (id,)).fetchone()

        if medie:
            filsti = os.path.join(
                app.config["UPLOAD_FOLDER"],
                medie["filnavn"]
            )

            try:
                os.remove(filsti)
            except FileNotFoundError:
                pass

            conn.execute("""
                DELETE FROM medier
                WHERE id = ?
            """, (id,))

            conn.commit()

    finally:
        conn.close()

    return redirect(url_for("admin"))

# ============================================================
# SLET NYHED
# ============================================================

@app.route("/slet-nyhed/<int:id>")
def slet_nyhed(id):
    if not session.get("logget_ind"):
        return redirect(url_for("login"))

    conn = get_db_connection()

    try:
        conn.execute("""
            DELETE FROM ticker
            WHERE id = ?
        """, (id,))

        conn.commit()

    finally:
        conn.close()

    return redirect(url_for("admin"))

# ============================================================
# HENT NYHEDER
# ============================================================

@app.route("/hent-nyheder")
def hent_nyheder():
    conn = get_db_connection()

    try:
        lokale = hent_lokale_nyheder(conn)
        dr_interval = get_dr_interval_sekunder(conn)
        dr_antal = get_dr_antal(conn)
    finally:
        conn.close()

    dr = hent_dr_nyheder()

    return jsonify(
        nyheder=lokale + dr,
        dr_interval_sekunder=dr_interval,
        dr_antal=dr_antal
    )

# ============================================================
# HENT AKTIVE MEDIER
# ============================================================

@app.route("/hent-aktive-medier")
def hent_aktive_medier():
    idag = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()

    try:
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
        """, (idag,)).fetchall()

        sekunder = get_billed_sekunder(conn)

    finally:
        conn.close()

    return jsonify(
        medier=[medie["filnavn"] for medie in medier],
        sekunder=sekunder
    )

# ============================================================
# HENT TICKER-INDSTILLINGER
# ============================================================

@app.route("/hent-ticker-indstillinger")
def hent_ticker_indstillinger():
    conn = get_db_connection()

    try:
        sekunder = get_ticker_sekunder(conn)
    finally:
        conn.close()

    return jsonify(
        sekunder=sekunder,
        ticker_sekunder=sekunder
    )

# ============================================================
# HENT VEJR
# ============================================================

@app.route("/hent-vejr")
def hent_vejr_api():
    by, temperatur, beskrivelse, ikon = hent_vejr()

    return jsonify(
        by=by,
        temp=temperatur,
        beskrivelse=beskrivelse,
        ikon=ikon
    )

# ============================================================
# UPLOADS
# ============================================================

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
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
