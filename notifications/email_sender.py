# -*- coding: utf-8 -*-
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

EMAIL_ORIGEN  = "pedronv0607@gmail.com"
EMAIL_DESTINO = "pedronv0607@gmail.com"
APP_PASSWORD  = "zhiphgkbfcyqvfom"

def get_picks():
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("""
            SELECT * FROM value_bets_live
            ORDER BY prob_modelo DESC
        """, conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def get_bankroll():
    try:
        from sqlalchemy import create_engine
        import os
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        supabase_url = os.getenv("SUPABASE_URL")
        engine = create_engine(supabase_url)
        df = pd.read_sql("SELECT cantidad FROM bankroll ORDER BY fecha DESC LIMIT 1", engine)
        return float(df.iloc[0]["cantidad"]) if not df.empty else 20.0
    except:
        return 20.0

def nivel_confianza(edge, cuota):
    if cuota <= 2.0 and edge >= 0.06:
        return "ALTA CONFIANZA"
    elif cuota <= 3.5 and edge >= 0.05:
        return "CONFIANZA MEDIA"
    elif cuota > 6.0:
        return "ESPECULATIVA"
    else:
        return "CONFIANZA BAJA"

def construir_email_html(picks_df, bankroll):
    fecha = datetime.now().strftime("%d %B %Y")
    total_picks = len(picks_df)

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
    <div style="max-width: 600px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
        <div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">Tennis Value Bot</h1>
            <p style="color: #a0a0b0; margin: 8px 0 0;">{fecha}</p>
        </div>
        <div style="background: #f8f9ff; padding: 20px; text-align: center; border-bottom: 1px solid #e0e0e0;">
            <p style="margin: 0; color: #666; font-size: 14px;">BANKROLL ACTUAL</p>
            <p style="margin: 4px 0; font-size: 32px; font-weight: bold; color: #1a1a2e;">{bankroll:.2f}EUR</p>
        </div>
        <div style="padding: 20px;">
            <h2 style="color: #1a1a2e; border-bottom: 2px solid #4CAF50; padding-bottom: 8px;">
                {total_picks} PICK{'S' if total_picks != 1 else ''} HOY
            </h2>
    """

    if picks_df.empty:
        html += """
            <div style="text-align: center; padding: 40px; color: #888;">
                <p style="font-size: 40px;">Sin picks hoy</p>
                <p>El sistema solo apuesta cuando hay ventaja real.</p>
            </div>
        """
    else:
        for i, (_, pick) in enumerate(picks_df.iterrows(), 1):
            edge_pct    = float(pick["edge"]) * 100
            ev_pct      = float(pick["ev"]) * 100
            kelly_pct   = float(pick["kelly_%"])
            stake_euros = round(bankroll * kelly_pct / 100, 2)
            confianza   = nivel_confianza(float(pick["edge"]), float(pick["cuota"]))

            if "ALTA" in confianza:
                color = "#4CAF50"
            elif "MEDIA" in confianza:
                color = "#2196F3"
            elif "ESPECULATIVA" in confianza:
                color = "#FF9800"
            else:
                color = "#FFC107"

            html += f"""
            <div style="border-left: 5px solid {color}; background: #fafafa;
                        border-radius: 8px; padding: 20px; margin-bottom: 16px;">
                <span style="background: {color}; color: white; font-size: 12px;
                             padding: 3px 10px; border-radius: 20px; font-weight: bold;">
                    {confianza}
                </span>
                <h3 style="margin: 12px 0 4px; color: #1a1a2e; font-size: 18px;">
                    {str(pick['partido'])}
                </h3>
                <p style="margin: 0 0 12px; color: #888; font-size: 13px;">
                    {str(pick['hora'])} | {str(pick.get('superficie', 'Clay'))}
                </p>
                <div style="background: #1a1a2e; color: white; border-radius: 8px;
                            padding: 14px; margin-bottom: 12px; text-align: center;">
                    <p style="margin: 0; font-size: 13px; color: #a0a0b0;">APUESTA A</p>
                    <p style="margin: 4px 0; font-size: 24px; font-weight: bold;">
                        {str(pick['apostar_a'])}
                    </p>
                    <p style="margin: 0; font-size: 28px; font-weight: bold; color: #4CAF50;">
                        Cuota {float(pick['cuota']):.2f}
                    </p>
                    <p style="margin: 4px 0 0; font-size: 13px; color: #a0a0b0;">
                        en BET365
                    </p>
                </div>
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
                        <p style="margin: 0; font-size: 11px; color: #666;">PROB.</p>
                        <p style="margin: 0; font-size: 20px; font-weight: bold;
                                  color: #FF9800;">{float(pick['prob_modelo'])*100:.0f}%</p>
                    </div>
                </div>
                <div style="background: #1a1a2e; border-radius: 8px; padding: 14px;">
                    <p style="margin: 0; color: #a0a0b0; font-size: 13px;">CUANTO APOSTAR</p>
                    <p style="margin: 6px 0 0; color: white; font-size: 22px; font-weight: bold;">
                        {stake_euros}EUR
                        <span style="font-size: 13px; color: #a0a0b0; font-weight: normal;">
                            ({kelly_pct:.1f}% bankroll)
                        </span>
                    </p>
                    <p style="margin: 4px 0 0; color: #4CAF50; font-size: 13px;">
                        Si ganas cobras {round(stake_euros * float(pick['cuota']), 2)}EUR
                        (+{round(stake_euros * (float(pick['cuota'])-1), 2)}EUR beneficio)
                    </p>
                </div>
            </div>
            """

    html += """
        </div>
        <div style="background: #fff8e1; padding: 16px 20px; border-top: 1px solid #ffe082;">
            <p style="margin: 0; font-size: 12px; color: #856404;">
                Apuesta solo lo indicado. El value betting es rentable a largo plazo
                pero habra rachas negativas. Nunca apuestes mas de lo que puedes perder.
            </p>
        </div>
        <div style="background: #1a1a2e; padding: 16px; text-align: center;">
            <p style="margin: 0; color: #666; font-size: 12px;">
                Tennis Value Bot | Generado automaticamente<br><br>
                <a href="https://trackerpy-vekld2xfsmfmj2phrzgfvt.streamlit.app" 
                   style="background:#4CAF50; color:white; padding:12px 24px; 
                          border-radius:8px; text-decoration:none; font-weight:bold; font-size:16px;">
                    Registrar resultados
                </a>
            </p>
        </div>
    </div>
    </body>
    </html>
    """
    return html

def enviar_email():
    picks    = get_picks()
    bankroll = get_bankroll()
    fecha    = datetime.now().strftime("%d/%m/%Y")

    if picks.empty:
        asunto = f"Tennis Bot - Sin picks hoy {fecha}"
    else:
        asunto = f"{len(picks)} PICKS HOY - Tennis Value Bot {fecha}"

    html = construir_email_html(picks, bankroll)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = EMAIL_ORIGEN
    msg["To"]      = EMAIL_DESTINO
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ORIGEN, APP_PASSWORD)
            server.sendmail(EMAIL_ORIGEN, EMAIL_DESTINO, msg.as_bytes())
        logger.success(f"Email enviado: {asunto}")
        return True
    except Exception as e:
        logger.error(f"Error enviando email: {e}")
        return False

if __name__ == "__main__":
    enviar_email()