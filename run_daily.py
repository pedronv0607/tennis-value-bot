"""
Script diario que:
1. Descarga cuotas frescas de la API
2. Calcula value bets con el modelo
3. Envía el email con los picks
Se ejecuta automáticamente cada día via Programador de Tareas.
"""
import sys
import sqlite3
from pathlib import Path
from loguru import logger
from datetime import datetime

BASE_DIR = Path(__file__).parent

# Logs a archivo
logger.add(
    BASE_DIR / "logs" / "daily_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO"
)

def actualizar_bankroll_mensual():
    pass  # Bankroll solo se actualiza desde el tracker

def run():
    logger.info("=" * 50)
    logger.info(f"PIPELINE DIARIO — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 50)

    # Crear carpeta logs si no existe
    (BASE_DIR / "logs").mkdir(exist_ok=True)

    # Bankroll gestionado manualmente desde el tracker

    # Paso 2: descargar cuotas frescas
    logger.info("Descargando cuotas...")
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable,
             str(BASE_DIR / "data_ingestion" / "collectors" / "odds_collector.py")],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        if r.returncode == 0:
            logger.success("Cuotas descargadas.")
        else:
            logger.error(f"Error cuotas: {r.stderr[-300:]}")
    except Exception as e:
        logger.error(f"Error: {e}")

    # Paso 3: calcular value bets
    logger.info("Calculando value bets...")
    try:
        r = subprocess.run(
            [sys.executable,
             str(BASE_DIR / "value_engine" / "live_value.py")],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        if r.returncode == 0:
            logger.success("Value bets calculadas.")
        else:
            logger.error(f"Error value: {r.stderr[-300:]}")
    except Exception as e:
        logger.error(f"Error: {e}")

    # Paso 4: enviar email
    logger.info("Enviando email...")
    try:
        r = subprocess.run(
            [sys.executable,
             str(BASE_DIR / "notifications" / "email_sender.py")],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        if r.returncode == 0:
            logger.success("Email enviado.")
        else:
            logger.error(f"Error email: {r.stderr[-300:]}")
    except Exception as e:
        logger.error(f"Error: {e}")

    logger.success("Pipeline completado.")

if __name__ == "__main__":
    run()