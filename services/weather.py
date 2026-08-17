import requests

from database.db import get_db_connection
from database.settings import get_indstilling

from config import (
    VEJR_BY,
    VEJR_LATITUDE,
    VEJR_LONGITUDE,
)


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