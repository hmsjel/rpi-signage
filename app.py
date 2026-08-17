import os
import sqlite3
from datetime import datetime
from services.weather import hent_vejr
from database.db import get_db_connection
from services.rss import hent_dr_nyheder
from database.init_db import init_db
from routes.auth import auth_bp
from routes.screen import screen_bp
from routes.api import api_bp
from routes.admin import admin_bp

from services.media import (
    allowed_file,
    hent_lokale_nyheder,
    hent_alle_nyheder_til_admin,
)
from database.settings import (
    get_indstilling,
    set_indstilling,
    get_billed_sekunder,
    get_ticker_sekunder,
    get_dr_interval_sekunder,
    get_dr_antal,
)


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
init_db()
app.register_blueprint(auth_bp)
app.register_blueprint(screen_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)


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



print(app.url_map)

# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
