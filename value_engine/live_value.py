import sqlite3
import pandas as pd
import numpy as np
import joblib
import os
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

BASE_DIR   = Path(__file__).parent.parent
DB_PATH    = BASE_DIR / "tennis_value_bot.db"
MODELS_DIR = BASE_DIR / "models" / "artifacts"
load_dotenv(BASE_DIR / ".env")

FEATURE_COLS = [
    "p1_elo", "p2_elo", "elo_diff_p1",
    "p1_elo_surf", "p2_elo_surf",
    "p1_form_5", "p1_form_10",
    "p2_form_5", "p2_form_10",
    "p1_rest", "p2_rest",
    "p1_fatigue", "p2_fatigue",
    "p1_winrate_surf", "p2_winrate_surf",
    "h2h_p1", "h2h_total",
    "rank_p1", "rank_p2",
]

def cargar_modelo():
    modelo, scaler = joblib.load(MODELS_DIR / "xgboost.pkl")
    logger.info("Modelo XGBoost cargado.")
    return modelo, scaler

def get_elo_actual():
    """Devuelve el Elo más reciente de cada jugador — versión rápida."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT winner_name, winner_id,
               MAX(elo_winner) as elo_winner,
               elo_winner_surf, surface
        FROM elo_history
        WHERE tourney_date >= '20250101'
        GROUP BY winner_name
    """, conn)
    conn.close()
    logger.info(f"Jugadores en Elo cache: {len(df):,}")
    return df

def buscar_jugador(nombre, df_elo):
    """Busca jugador por apellido."""
    apellido = nombre.split()[-1].lower()
    mask = df_elo["winner_name"].str.lower().str.contains(apellido, na=False)
    resultados = df_elo[mask]
    if resultados.empty:
        return None
    return resultados.iloc[0]

def fetch_odds_live():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT id, sport_key, commence_time,
               home_team, away_team,
               bookmaker, odds_home, odds_away
        FROM odds_live
        ORDER BY commence_time ASC
    """, conn)
    conn.close()
    return df

def calcular_value_live():
    logger.info("Iniciando cálculo de value en tiempo real...")

    modelo, scaler = cargar_modelo()
    df_elo  = get_elo_actual()
    df_odds = fetch_odds_live()

    if df_odds.empty:
        logger.warning("No hay cuotas. Ejecuta odds_collector.py primero.")
        return []

    partidos = df_odds.groupby(["id", "home_team", "away_team",
                                 "commence_time", "sport_key"])
    value_bets_live = []
    jugadoras_wta = ["svitolina", "rybakina", "gauff", "cirstea", "swiatek",
                  "sabalenka", "jabeur", "keys", "pegula", "collins"]

    for (pid, home, away, hora, sport), grupo in partidos:
        # Filtrar WTA
        if any(w in home.lower() or w in away.lower()
               for w in jugadoras_wta):
            continue

        if "clay" in sport.lower() or "french" in sport.lower() or "roland" in sport.lower():          superficie = "Clay"
        elif "grass" in sport.lower() or "wimbledon" in sport.lower():
            superficie = "Grass"
        else:
            superficie = "Hard"

        elo_home = buscar_jugador(home, df_elo)
        elo_away = buscar_jugador(away, df_elo)

        elo_h   = float(elo_home["elo_winner"])      if elo_home is not None else 1500
        elo_a   = float(elo_away["elo_winner"])      if elo_away is not None else 1500
        elo_h_s = float(elo_home["elo_winner_surf"]) if elo_home is not None else 1500
        elo_a_s = float(elo_away["elo_winner_surf"]) if elo_away is not None else 1500

        features = np.array([[
            elo_h, elo_a, elo_h - elo_a,
            elo_h_s, elo_a_s,
            0.6, 0.6, 0.5, 0.5,
            3, 3, 2, 2,
            0.55, 0.50,
            0.5, 5,
            50, 80,
        ]])

        prob_home = float(modelo.predict_proba(features)[:, 1][0])
        prob_away = 1 - prob_home

        for _, row in grupo.iterrows():
            bookie     = row["bookmaker"]
            cuota_home = float(row["odds_home"])
            cuota_away = float(row["odds_away"])

            p_imp_h = 1 / cuota_home
            p_imp_a = 1 / cuota_away
            total   = p_imp_h + p_imp_a
            vig     = round((total - 1) * 100, 1)
            p_fair_h = p_imp_h / total
            p_fair_a = p_imp_a / total

            edge_h = round(prob_home - p_fair_h, 4)
            edge_a = round(prob_away - p_fair_a, 4)
            ev_h   = round((prob_home * cuota_home) - 1, 4)
            ev_a   = round((prob_away * cuota_away) - 1, 4)
            kelly_h = max(round(((prob_home * cuota_home - 1) / max(cuota_home - 1, 0.01)) * 0.25, 4), 0)
            kelly_a = max(round(((prob_away * cuota_away - 1) / max(cuota_away - 1, 0.01)) * 0.25, 4), 0)

            if edge_h >= 0.10 and prob_home >= 0.65 and cuota_home <= 3.0:
                value_bets_live.append({
                    "partido":     str(f"{home} vs {away}"),
                    "hora":        str(hora[:16]).replace("T", " "),
                    "apostar_a":   str(home),
                    "bookmaker":   str(bookie),
                    "cuota":       float(cuota_home),
                    "prob_modelo": round(float(prob_home), 4),
                    "prob_fair":   round(float(p_fair_h), 4),
                    "edge":        float(edge_h),
                    "ev":          float(ev_h),
                    "kelly_%":     round(float(kelly_h) * 100, 2),
                    "vig_%":       float(vig),
                    "superficie":  str(superficie),
                })

            if edge_a >= 0.10 and prob_away >= 0.65 and cuota_away <= 3.0:
                value_bets_live.append({
                    "if edge_h":     f"{home} vs {away}",
                    "hora":        hora[:16].replace("T", " "),
                    "apostar_a":   away,
                    "bookmaker":   bookie,
                    "cuota":       cuota_away,
                    "prob_modelo": round(prob_away, 4),
                    "prob_fair":   round(p_fair_a, 4),
                    "edge":        edge_a,
                    "ev":          ev_a,
                    "kelly_%":     round(kelly_a * 100, 2),
                    "vig_%":       vig,
                    "superficie":  superficie,
                })

    if not value_bets_live:
        logger.info("Sin value bets en partidos actuales.")
    else:
        df_vb = pd.DataFrame(value_bets_live).sort_values("edge", ascending=False)
        logger.info("=" * 65)
        logger.info("VALUE BETS EN VIVO")
        logger.info("=" * 65)
        for _, r in df_vb.iterrows():
            logger.info(
                f"{str(r['partido'])[:35]:35s} | "
                f"Apostar: {r['apostar_a'][:15]:15s} | "
                f"Cuota: {r['cuota']:5.2f} | "
                f"Edge: {r['edge']*100:4.1f}% | "
                f"EV: {r['ev']*100:4.1f}% | "
                f"Kelly: {r['kelly_%']:4.1f}%"
            )
        # Quedarse solo con la mejor cuota por partido+jugador
        df_vb = df_vb.sort_values("edge", ascending=False)
        df_vb = df_vb.drop_duplicates(subset=["partido", "apostar_a"])

        conn = sqlite3.connect(DB_PATH)
        df_vb.to_sql("value_bets_live", conn, if_exists="replace", index=False)
        conn.close()
        logger.success(f"{len(df_vb)} value bets guardadas.")

    return value_bets_live

if __name__ == "__main__":
    calcular_value_live()