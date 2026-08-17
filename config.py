import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DATABASE = os.path.join(
    BASE_DIR,
    "skaerm.db"
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

SECRET_KEY = (
    "SKIFT-DENNE-TIL-EN-LANG-TILFÆLDIG-NØGLE"
)

ADMIN_BRUGERNAVN = "admin"
ADMIN_KODE = "1234"

ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
    "mp4",
    "mov",
    "webm",
}

DEFAULT_BILLED_SEKUNDER = 12
DEFAULT_TICKER_SEKUNDER = 90
DEFAULT_DR_INTERVAL_SEKUNDER = 300
DEFAULT_DR_ANTAL = 5

VEJR_BY = "Skovgaarde"
VEJR_LATITUDE = 56.50941163
VEJR_LONGITUDE = 10.5417551

DR_RSS_URL = (
    "https://www.dr.dk/nyheder/service/feeds/allenyheder"
)

VEJR_CACHE_SEKUNDER = 300
NYHED_CACHE_SEKUNDER = 300
