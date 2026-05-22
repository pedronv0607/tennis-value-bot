import smtplib
import sqlite3
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from loguru import logger
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
DB_PATH  = BASE_DIR / "tennis_value_bot.db"

# Configuración email
EMAIL_ORIGEN  = "pedronv0607@gmail.com"
EMAIL_DESTINO = "pedronv0607@gmail.com"
APP_PASSWORD  = "zhiphgkbfcyqvfom"

def get_picks():
    """Carga los value bets live de la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("""
            SELECT * FROM value_bets_live
            ORDER BY edge DESC
        """, conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def get_bankroll():
    """Lee el bankroll actual de la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bankroll (
            fecha TEXT PRIMARY KEY,
            cantidad REAL
        )
    """)
    cursor.execute("SELECT cantidad FROM bankroll ORDER BY fecha DESC LIMIT 1")
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return row[0] if row else 20.0

def guardar_bankroll(cantidad):
    """Guarda el bankroll actualizado."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bankroll (
            fecha TEXT PRIMARY KEY,
            cantidad REAL
        )
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO bankroll VALUES (?, ?)
    """, (datetime.now().strftime("%Y-%m-%d"), cantidad))
    conn.commit()
    conn.close()

def nivel_confianza(edge, cuota):
    # Cuotas bajas (favoritos) con edge = más fiable
    # Cuotas altas (outsiders) con edge = más especulativo
    if cuota <= 2.0 and edge >= 0.06:
        return "🔥 ALTA CONFIANZA"
    elif cuota <= 3.5 and edge >= 0.05:
        return "✅ CONFIANZA MEDIA"
    elif cuota <= 6.0 and edge >= 0.08:
        return "✅ CONFIANZA MEDIA"
    elif cuota > 6.0:
        return "🎲 ESPECULATIVA"
    else:
        return "⚠️  CONFIANZA BAJA"

def construir_email_html(picks_df, bankroll):
    """Construye el email HTML con los picks del día."""
    fecha = datetime.now().strftime("%d %B %Y")
    total_picks = len(picks_df)

    # Header
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
    <div style="max-width: 600px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">

        <!-- HEADER -->
        <div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">🎾 Tennis Value Bot</h1>
            <p style="color: #a0a0b0; margin: 8px 0 0;">{fecha}</p>
        </div>

        <!-- BANKROLL -->
        <div style="background: #f8f9ff; padding: 20px; text-align: center; border-bottom: 1px solid #e0e0e0;">
            <p style="margin: 0; color: #666; font-size: 14px;">💰 BANKROLL ACTUAL</p>
            <p style="margin: 4px 0; font-size: 32px; font-weight: bold; color: #1a1a2e;">{bankroll:.2f}€</p>
            <p style="margin: 0; color: #888; font-size: 12px;">Reinvirtiendo ganancias automáticamente</p>
        </div>

        <!-- PICKS -->
        <div style="padding: 20px;">
            <h2 style="color: #1a1a2e; border-bottom: 2px solid #4CAF50; padding-bottom: 8px;">
                📋 {total_picks} PICK{'S' if total_picks != 1 else ''} HOY
            </h2>
    """

    if picks_df.empty:
        html += """
            <div style="text-align: center; padding: 40px; color: #888;">
                <p style="font-size: 40px;">😴</p>
                <p>No hay value bets hoy.</p>
                <p style="font-size: 13px;">El sistema solo apuesta cuando hay ventaja real.</p>
            </div>
        """
    else:
        for i, (_, pick) in enumerate(picks_df.iterrows(), 1):
            edge_pct    = pick["edge"] * 100
            ev_pct      = pick["ev"] * 100
            kelly_pct   = pick["kelly_%"]
            stake_euros = round(bankroll * kelly_pct / 100, 2)
            confianza   = nivel_confianza(pick["edge"], pick["cuota"])

            # Color según confianza
            if pick["edge"] >= 0.10:
                color_borde = "#FF6B35"
                color_badge = "#FF6B35"
            elif pick["edge"] >= 0.06:
                color_borde = "#4CAF50"
                color_badge = "#4CAF50"
            else:
                color_borde = "#FFC107"
                color_badge = "#FFC107"

            html += f"""
            <div style="border-left: 5px solid {color_borde}; background: #fafafa;
                        border-radius: 8px; padding: 20px; margin-bottom: 16px;">

                <!-- Badge confianza -->
                <span style="background: {color_badge}; color: white; font-size: 12px;
                             padding: 3px 10px; border-radius: 20px; font-weight: bold;">
                    {confianza}
                </span>

                <!-- Partido -->
                <h3 style="margin: 12px 0 4px; color: #1a1a2e; font-size: 18px;">
                    {pick['partido']}
                </h3>

                <!-- Hora -->
                <p style="margin: 0 0 12px; color: #888; font-size: 13px;">
                    🕐 {pick['hora']} | 🎾 {pick.get('superficie', 'Clay')}
                </p>

                <!-- Apuesta principal -->
                <div style="background: #1a1a2e; color: white; border-radius: 8px;
                            padding: 14px; margin-bottom: 12px; text-align: center;">
                    <p style="margin: 0; font-size: 13px; color: #a0a0b0;">👉 APUESTA A</p>
                    <p style="margin: 4px 0; font-size: 24px; font-weight: bold;">
                        {pick['apostar_a']}
                    </p>
                    <p style="margin: 0; font-size: 28px; font-weight: bold; color: #4CAF50;">
                        Cuota {pick['cuota']}
                    </p>
                    <p style="margin: 4px 0 0; font-size: 13px; color: #a0a0b0;">
                        en {pick['bookmaker'].upper()}
                    </p>
                </div>

                <!-- Stats -->
                <div style="display: flex; gap: 10px; margin-bottom: 12px;">
                    <div style="flex: 1; background: #e8f5e9; border-radius: 6px;
                                padding: 10px; text-align: center;">
                        <p style="margin: 0; font-size: 11px; color: #666;">EDGE</p>
                        <p style="margin: 0; font-size: 20px; font-weight: bold;
                                  color: #4CAF50;">+{edge_pct:.1f}%</p>
                    </div>
                    <div style="flex: 1; background: #e3f2fd; border-radius: 6px;
                                padding: 10px; text-align: center;">
                        <p style="margin: 0; font-size: 11px; color: #666;">EV</p>
                        <p style="margin: 0; font-size: 20px; font-weight: bold;
                                  color: #2196F3;">+{ev_pct:.1f}%</p>
                    </div>
                    <div style="flex: 1; background: #fff3e0; border-radius: 6px;
                                padding: 10px; text-align: center;">
                        <p style="margin: 0; font-size: 11px; color: #666;">PROB. MODELO</p>
                        <p style="margin: 0; font-size: 20px; font-weight: bold;
                                  color: #FF9800;">{pick['prob_modelo']*100:.0f}%</p>
                    </div>
                </div>

                <!-- Stake -->
                <div style="background: #1a1a2e; border-radius: 8px; padding: 14px;">
                    <p style="margin: 0; color: #a0a0b0; font-size: 13px;">💰 CUÁNTO APOSTAR</p>
                    <p style="margin: 6px 0 0; color: white; font-size: 22px; font-weight: bold;">
                        {stake_euros}€
                        <span style="font-size: 13px; color: #a0a0b0; font-weight: normal;">
                            ({kelly_pct:.1f}% de tu bankroll)
                        </span>
                    </p>
                    <p style="margin: 4px 0 0; color: #4CAF50; font-size: 13px;">
                        Si ganas → cobras {round(stake_euros * pick['cuota'], 2)}€
                        (+{round(stake_euros * (pick['cuota']-1), 2)}€ de beneficio)
                    </p>
                </div>

            </div>
            """

    # Footer
    html += f"""
        </div>

        <!-- AVISO -->
        <div style="background: #fff8e1; padding: 16px 20px; border-top: 1px solid #ffe082;">
            <p style="margin: 0; font-size: 12px; color: #856404;">
                ⚠️ <strong>Recuerda:</strong> Apuesta solo lo indicado. 
                El value betting es rentable a largo plazo pero habrá rachas negativas. 
                Nunca apuestes más de lo que puedes permitirte perder.
            </p>
        </div>

        <!-- FOOTER -->
        <div style="background: #1a1a2e; padding: 16px; text-align: center;">
            <p style="margin: 0; color: #666; font-size: 12px;">
                Tennis Value Bot | Generado automáticamente
            </p>
        </div>

    </div>
    </body>
    </html>
    """
    return html

def enviar_email():
    """Envía el email con los picks del día."""
    picks   = get_picks()
    bankroll = get_bankroll()
    fecha   = datetime.now().strftime("%d/%m/%Y")

    if picks.empty:
        asunto = f"🎾 Tennis Bot — Sin picks hoy {fecha}"
    else:
        asunto = f"🎾 {len(picks)} PICK{'S' if len(picks)!=1 else ''} HOY — Tennis Value Bot {fecha}"

    html = construir_email_html(picks, bankroll)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = EMAIL_ORIGEN
    msg["To"]      = EMAIL_DESTINO
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ORIGEN, APP_PASSWORD)
            server.sendmail(EMAIL_ORIGEN, EMAIL_DESTINO, msg.as_string())
        logger.success(f"Email enviado: {asunto}")
        return True
    except Exception as e:
        logger.error(f"Error enviando email: {e}")
        return False

if __name__ == "__main__":
    enviar_email()