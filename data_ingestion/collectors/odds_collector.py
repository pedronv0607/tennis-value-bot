import requests
import sqlite3
import os
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(BASE_DIR / ".env")

DB_PATH  = BASE_DIR / "tennis_value_bot.db"
API_KEY  = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"

def get_sports():
    """Lista todos los deportes disponibles."""
    url = f"{BASE_URL}/sports"
    r = requests.get(url, params={"apiKey": API_KEY})
    sports = r.json()
    tenis = [s for s in sports if "tennis_atp" in s["key"].lower()]
    logger.info(f"Deportes de tenis disponibles: {len(tenis)}")
    for s in tenis:
        logger.info(f"  {s['key']:40s} — {s['title']}")
    return tenis

def get_odds(sport_key="tennis_atp_french_open",
             regions="eu",
             markets="h2h"):
    """
    Obtiene cuotas en vivo para un torneo.
    regions: eu = cuotas europeas (decimales)
    markets: h2h = head to head (ganador del partido)
    """
    url = f"{BASE_URL}/sports/{sport_key}/odds"
    params = {
        "apiKey":  API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
    }
    r = requests.get(url, params=params)

    # Ver cuántas peticiones quedan
    remaining = r.headers.get("x-requests-remaining", "?")
    used      = r.headers.get("x-requests-used", "?")
    logger.info(f"API requests — usadas: {used} | restantes: {remaining}")

    if r.status_code != 200:
        logger.error(f"Error API: {r.status_code} — {r.text}")
        return []

    partidos = r.json()
    logger.info(f"Partidos con cuotas: {len(partidos)}")
    return partidos

def parsear_y_guardar(partidos, sport_key):
    """Guarda las cuotas en la base de datos."""
    if not partidos:
        logger.warning("No hay partidos para guardar.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS odds_live (
            id              TEXT,
            sport_key       TEXT,
            commence_time   TEXT,
            home_team       TEXT,
            away_team       TEXT,
            bookmaker       TEXT,
            odds_home       REAL,
            odds_away       REAL,
            fetched_at      TEXT,
            PRIMARY KEY (id, bookmaker)
        )
    """)

    ahora = datetime.utcnow().isoformat()
    cursor.execute("DELETE FROM odds_live")
    conn.commit()
    insertados = 0

    for partido in partidos:
        pid          = partido["id"]
        commence     = partido["commence_time"]
        home         = partido["home_team"]
        away         = partido["away_team"]

        for bookmaker in partido.get("bookmakers", []):
            bname = bookmaker["key"]
            for market in bookmaker.get("markets", []):
                if market["key"] != "h2h":
                    continue
                outcomes = {o["name"]: o["price"]
                            for o in market["outcomes"]}
                odds_home = outcomes.get(home)
                odds_away = outcomes.get(away)

                if odds_home and odds_away:
                    cursor.execute("""
                        INSERT OR REPLACE INTO odds_live
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, (pid, sport_key, commence,
                          home, away, bname,
                          odds_home, odds_away, ahora))
                    insertados += 1

    conn.commit()
    conn.close()
    logger.success(f"{insertados} cuotas guardadas en odds_live.")

def fetch_all_tennis():
    """Descarga cuotas de todos los torneos de tenis disponibles."""
    sports = get_sports()
    total  = 0
    for sport in sports:
        key = sport["key"]
        logger.info(f"Descargando cuotas: {key}")
        partidos = get_odds(sport_key=key)
        parsear_y_guardar(partidos, key)
        total += len(partidos)
    logger.success(f"Total partidos con cuotas: {total}")

if __name__ == "__main__":
    fetch_all_tennis()