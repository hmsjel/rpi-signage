import os
import sqlite3
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

app = Flask(__name__)

# ==========================================
# OPSÆTNING
# ==========================================

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==========================================
# DATABASE
# ==========================================

def get_db_connection():
    conn = sqlite3.connect("skaerm.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS medier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filnavn TEXT NOT NULL,
            aktiv INTEGER DEFAULT 1
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

    try:
        conn.execute('INSERT OR IGNORE INTO indstillinger (nogle, vaerdi) VALUES ("billed_sekunder", "12")')
    except Exception as e:
        pass

    conn.commit()
    conn.close()


init_db()

# ==========================================
# HJÆLPEFUNKTION:
# HENT DR NYHEDER
# ==========================================

def hent_dr_nyheder():

    nyheder = []

    # DR RSS-feed
    rss_url = "https://www.dr.dk/nyheder/service/feeds/allenyheder"

    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            rss_url,
            headers=headers,
            timeout=10
        )

        response.raise_for_status()

        feed = feedparser.parse(response.content)

        for entry in feed.entries[:5]:

            titel = entry.get("title")

            if titel:
                nyheder.append(
                    f"++ DR NYHEDER: {titel} ++"
                )

    except Exception as e:

        print("Kunne ikke hente DR RSS:", e)

    return nyheder

# ==========================================
# HJÆLPEFUNKTION:
# HENT VEJR
# ==========================================

def hent_vejr():

    # Vejr-lokation
    by = "Skovgaarde"
    latitude = 56.50941163
    longitude = 10.5417551

    temperatur = "--°C"
    beskrivelse = "Henter vejr..."
    ikon = "cloud-sun"  # Standard-ikon hvis noget driller

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

    # Matcher WMO-koderne med de rigtige ikoner fra Bootstrap Icons
    # Rettet: 'bi-' er fjernet fra navnene, da browseren tilføjer det automatisk via klassen
    weather_icons = {
        0: "sun-fill",                  # Skyfrit
        1: "cloud-sun-fill",           # Næsten skyfrit
        2: "cloud-sun",                # Delvist skyet
        3: "cloud-fill",               # Skyet
        45: "cloud-haze",              # Tåget
        48: "cloud-haze2",             # Rimtåge
        51: "cloud-drizzle",           # Let støvregn
        53: "cloud-drizzle",           # Støvregn
        55: "cloud-drizzle-fill",      # Tæt støvregn
        61: "cloud-rain",              # Let regn
        63: "cloud-rain-fill",         # Regnvejr
        65: "cloud-rain-heavy-fill",   # Kraftig regn
        71: "cloud-snow",              # Let snevejr
        73: "cloud-snow-fill",         # Snevejr
        75: "snow",                    # Tæt snevejr
        80: "cloud-lightning-rain",    # Lettere regnbyger
        81: "cloud-lightning-rain-fill", # Regnbyger
        82: "cloud-rain-heavy",        # Kraftige regnbyger
        95: "cloud-lightning-fill",    # Tordenvejr
        96: "cloud-hail",              # Tordenvejr med hagl
        99: "cloud-hail-fill"          # Kraftigt tordenvejr med hagl
    }

    try:

        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=56.50941163"
            "&longitude=10.5417551"
            "&current=temperature_2m,weather_code"
            "&timezone=Europe%2FCopenhagen"
        )

        response = requests.get(
            weather_url,
            timeout=10
        )

        response.raise_for_status()

        weather_data = response.json()

        current = weather_data.get("current", {})

        if current:

            grader = round(
                current.get("temperature_2m", 0)
            )

            temperatur = f"{grader}°C"

            code = current.get("weather_code")

            beskrivelse = weather_codes.get(
                code,
                "Skiftende vejr"
            )

            # Hent ikonet baseret på koden
            ikon = weather_icons.get(code, "cloud-sun"
            )

    except Exception as e:

        print("Vejrfejl:", e)

    # RETTELSE: Vi returnerer nu også ikonet til sidst
    return by, temperatur, beskrivelse, ikon


# ==========================================
# RUTE 1: INFOSKÆRM
# ==========================================

@app.route("/")
def skaerm():
    conn = get_db_connection()

    aktive_medier = conn.execute("""
        SELECT filnavn FROM medier WHERE aktiv = 1 ORDER BY id ASC
    """).fetchall()

    lokale_nyheder = conn.execute("""
        SELECT tekst FROM ticker ORDER BY id ASC
    """).fetchall()

    hastighed_row = conn.execute('SELECT vaerdi FROM indstillinger WHERE nogle = "billed_sekunder"').fetchone()
    billed_sekunder = int(hastighed_row['vaerdi']) if hastighed_row else 12
    conn.close()

    nyheds_liste = [nyhed["tekst"] for nyhed in lokale_nyheder]
    dr_nyheder = hent_dr_nyheder()
    nyheds_liste.extend(dr_nyheder)

    vejr_by, vejr_temp, vejr_desc, vejr_ikon = hent_vejr()

    return render_template(
        "skaerm.html",
        medier=aktive_medier,
        nyheder=nyheds_liste,
        temp=vejr_temp,
        beskrivelse=vejr_desc,
        by=vejr_by,
        sekunder=billed_sekunder,
        ikon=vejr_ikon # Her sendes ikonet afsted
    )


# ==========================================
# RUTE 2: ADMIN PANEL
# ==========================================

@app.route("/admin", methods=["GET", "POST"])
def admin():
    conn = get_db_connection()

    if request.method == "POST":
        if "nyhed_tekst" in request.form:
            tekst = request.form["nyhed_tekst"].strip()
            if tekst:
                conn.execute("INSERT INTO ticker (tekst) VALUES (?)", (tekst,))
                conn.commit()

        elif "medie_fil" in request.files:
            fil = request.files["medie_fil"]
            if fil and fil.filename:
                filnavn = fil.filename
                fil.save(os.path.join(app.config["UPLOAD_FOLDER"], filnavn))
                conn.execute("INSERT INTO medier (filnavn, aktiv) VALUES (?, 1)", (filnavn,))
                conn.commit()

        elif "billed_sekunder" in request.form:
            sekunder = request.form["billed_sekunder"].strip()
            if sekunder:
                conn.execute('UPDATE indstillinger SET vaerdi = ? WHERE nogle = "billed_sekunder"', (sekunder,))
                conn.commit()

        return redirect(url_for("admin"))

    alle_medier = conn.execute("SELECT * FROM medier ORDER BY id ASC").fetchall()
    alle_nyheder = conn.execute("SELECT * FROM ticker ORDER BY id ASC").fetchall()
    
    hastighed_row = conn.execute('SELECT vaerdi FROM indstillinger WHERE nogle = "billed_sekunder"').fetchone()
    billed_sekunder = hastighed_row['vaerdi'] if hastighed_row else "12"
    conn.close()

    return render_template(
        "admin.html",
        medier=alle_medier,
        nyheder=alle_nyheder,
        nuvaerende_sekunder=billed_sekunder
    )

# ==========================================
# SKIFT STATUS PÅ MEDIE
# ==========================================

@app.route("/skift-status/<int:id>", methods=["POST"])
def skift_status(id):
    data = request.get_json()
    if not data:
        return jsonify(success=False, error="Ingen data modtaget"), 400

    ny_status = 1 if data.get("aktiv") else 0
    conn = get_db_connection()
    conn.execute("UPDATE medier SET aktiv = ? WHERE id = ?", (ny_status, id))
    conn.commit()
    conn.close()

    return jsonify(success=True)

# ==========================================
# SLET MEDIE
# ==========================================

@app.route("/slet/<int:id>")
def slet(id):
    conn = get_db_connection()
    medie = conn.execute("SELECT filnavn FROM medier WHERE id = ?", (id,)).fetchone()

    if medie:
        filsti = os.path.join(app.config["UPLOAD_FOLDER"], medie["filnavn"])
        try:
            os.remove(filsti)
        except FileNotFoundError:
            pass

        conn.execute("DELETE FROM medier WHERE id = ?", (id,))
        conn.commit()

    conn.close()
    return redirect(url_for("admin"))

# ==========================================
# SLET NYHED
# ==========================================

@app.route("/slet-nyhed/<int:id>")
def slet_nyhed(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM ticker WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

# ==========================================
# HENT NYHEDER (JavaScript-opdatering)
# ==========================================

@app.route("/hent-nyheder")
def hent_nyheder():
    conn = get_db_connection()
    lokale_nyheder = conn.execute("""
        SELECT tekst FROM ticker ORDER BY id ASC
    """).fetchall()
    conn.close()

    nyheds_liste = [nyhed["tekst"] for nyhed in lokale_nyheder]
    dr_nyheder = hent_dr_nyheder()
    nyheds_liste.extend(dr_nyheder)

    return jsonify(nyheder=nyheds_liste)

# ==========================================
# HENT AKTIVE MEDIER & HASTIGHED
# ==========================================

@app.route("/hent-aktive-medier")
def hent_aktive_medier():
    conn = get_db_connection()
    aktive_medier = conn.execute("""
        SELECT filnavn FROM medier WHERE aktiv = 1 ORDER BY id ASC
    """).fetchall()

    hastighed_row = conn.execute('SELECT vaerdi FROM indstillinger WHERE nogle = "billed_sekunder"').fetchone()
    billed_sekunder = int(hastighed_row['vaerdi']) if hastighed_row else 12
    conn.close()

    return jsonify(
        medier=[medie["filnavn"] for medie in aktive_medier],
        sekunder=billed_sekunder
    )

# ==========================================
# HENT VEJR API
# ==========================================

@app.route("/hent-vejr")
def hent_vejr_api():
    by, temperatur, beskrivelse = hent_vejr()
    return jsonify(temp=temperatur, beskrivelse=beskrivelse)

# ==========================================
# UPLOADS
# ==========================================

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ==========================================
# START FLASK
# ==========================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
