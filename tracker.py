# -*- coding: utf-8 -*-
import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "tennis_value_bot.db"

st.set_page_config(
    page_title="Tennis Bot Tracker",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS personalizado
st.markdown("""
<style>
    .main { background-color: #0f0f1a; }
    .stApp { background-color: #0f0f1a; }
    div[data-testid="metric-container"] {
        background: #1a1a2e;
        border-radius: 12px;
        padding: 16px;
        border: 1px solid #2a2a4e;
    }
    .pick-card {
        background: #1a1a2e;
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0;
        border: 1px solid #2a2a4e;
    }
    .stButton button {
        border-radius: 12px;
        font-weight: bold;
        font-size: 16px;
        padding: 12px 24px;
    }
</style>
""", unsafe_allow_html=True)

def get_bankroll():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS bankroll (fecha TEXT PRIMARY KEY, cantidad REAL)")
    cursor.execute("SELECT cantidad FROM bankroll ORDER BY fecha DESC LIMIT 1")
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return row[0] if row else 20.0

def actualizar_bankroll(nueva_cantidad):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS bankroll (fecha TEXT PRIMARY KEY, cantidad REAL)")
    conn.execute("INSERT OR REPLACE INTO bankroll VALUES (?, ?)",
                 (datetime.now().strftime("%Y-%m-%d %H:%M"), nueva_cantidad))
    conn.commit()
    conn.close()

def crear_tablas():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS picks_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT, partido TEXT, apostar_a TEXT,
            cuota REAL, prob_modelo REAL, edge REAL,
            stake REAL, apostado INTEGER DEFAULT 0,
            resultado TEXT DEFAULT 'pendiente', profit REAL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_picks_hoy():
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM value_bets_live ORDER BY prob_modelo DESC", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def get_historial():
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM picks_historial ORDER BY fecha DESC", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def guardar_apuesta(partido, apostar_a, cuota, prob, edge, stake, resultado):
    profit = round(stake * (cuota - 1), 2) if resultado == "ganado" else (-stake if resultado == "perdido" else 0)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO picks_historial
        (fecha, partido, apostar_a, cuota, prob_modelo, edge, stake, apostado, resultado, profit)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d"), partido, apostar_a, cuota, prob, edge, stake, resultado, profit))
    conn.commit()
    conn.close()
    return profit

crear_tablas()
bankroll = get_bankroll()
historial = get_historial()

# ── HEADER ──
st.markdown(f"""
<div style="text-align:center; padding: 30px 0 10px;">
    <h1 style="color:white; font-size:40px; margin:0;">🎾 Tennis Value Bot</h1>
    <p style="color:#888; font-size:16px;">Tracker de apuestas en tiempo real</p>
</div>
""", unsafe_allow_html=True)

# ── KPIs ──
apostadas = historial[historial["apostado"] == 1] if not historial.empty else pd.DataFrame()
ganadas   = apostadas[apostadas["resultado"] == "ganado"] if not apostadas.empty else pd.DataFrame()
profit_total = apostadas["profit"].sum() if not apostadas.empty else 0
winrate   = round(len(ganadas) / max(len(apostadas), 1) * 100, 1) if not apostadas.empty else 0
roi       = round(profit_total / max(apostadas["stake"].sum(), 0.01) * 100, 1) if not apostadas.empty else 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💰 Bankroll", f"{bankroll:.2f}€",
            delta=f"{profit_total:+.2f}€" if profit_total != 0 else None)
col2.metric("📈 Profit total", f"{profit_total:+.2f}€")
col3.metric("🎯 Winrate", f"{winrate}%")
col4.metric("📊 ROI", f"{roi}%")
col5.metric("🎲 Apuestas", len(apostadas) if not apostadas.empty else 0)

st.divider()

# ── TABS ──
tab1, tab2, tab3 = st.tabs(["🎯 Picks de hoy", "📊 Mi rendimiento", "📋 Historial"])

# ── TAB 1: PICKS ──
with tab1:
    picks = get_picks_hoy()

    if picks.empty:
        st.markdown("""
        <div style="text-align:center; padding:60px; background:#1a1a2e; border-radius:16px; margin:20px 0;">
            <p style="font-size:60px; margin:0;">😴</p>
            <h3 style="color:white;">Sin picks hoy</h3>
            <p style="color:#888;">El sistema solo apuesta cuando hay ventaja real.<br>
            Ejecuta <code>python run_daily.py</code> para actualizar.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"<h3 style='color:white;'>Tienes {len(picks)} pick{'s' if len(picks)!=1 else ''} hoy</h3>",
                    unsafe_allow_html=True)

        for i, (_, pick) in enumerate(picks.iterrows()):
            stake     = round(bankroll * float(pick["kelly_%"]) / 100, 2)
            prob_pct  = float(pick["prob_modelo"]) * 100
            edge_pct  = float(pick["edge"]) * 100
            cuota     = float(pick["cuota"])
            ganancia  = round(stake * (cuota - 1), 2)

            if prob_pct >= 70:
                color = "#4CAF50"
                nivel = "ALTA CONFIANZA"
                emoji = "🟢"
            elif prob_pct >= 60:
                color = "#2196F3"
                nivel = "CONFIANZA MEDIA"
                emoji = "🔵"
            else:
                color = "#FF9800"
                nivel = "CONFIANZA BAJA"
                emoji = "🟡"

            st.markdown(f"""
            <div style="background:#1a1a2e; border-radius:16px; padding:24px;
                        margin:16px 0; border-left:5px solid {color};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="background:{color}; color:white; padding:4px 12px;
                                 border-radius:20px; font-size:13px; font-weight:bold;">
                        {emoji} {nivel}
                    </span>
                    <span style="color:#888; font-size:13px;">{str(pick['hora'])}</span>
                </div>
                <h2 style="color:white; margin:16px 0 4px;">{str(pick['partido'])}</h2>
                <div style="display:flex; gap:20px; margin:16px 0;">
                    <div style="background:#0f0f1a; border-radius:12px; padding:16px; flex:1; text-align:center;">
                        <p style="color:#888; margin:0; font-size:12px;">APUESTA A</p>
                        <p style="color:white; margin:4px 0; font-size:22px; font-weight:bold;">
                            {str(pick['apostar_a'])}
                        </p>
                    </div>
                    <div style="background:#0f0f1a; border-radius:12px; padding:16px; flex:1; text-align:center;">
                        <p style="color:#888; margin:0; font-size:12px;">CUOTA BET365</p>
                        <p style="color:{color}; margin:4px 0; font-size:22px; font-weight:bold;">
                            {cuota:.2f}
                        </p>
                    </div>
                    <div style="background:#0f0f1a; border-radius:12px; padding:16px; flex:1; text-align:center;">
                        <p style="color:#888; margin:0; font-size:12px;">PROBABILIDAD</p>
                        <p style="color:white; margin:4px 0; font-size:22px; font-weight:bold;">
                            {prob_pct:.0f}%
                        </p>
                    </div>
                    <div style="background:#0f0f1a; border-radius:12px; padding:16px; flex:1; text-align:center;">
                        <p style="color:#888; margin:0; font-size:12px;">APOSTAR</p>
                        <p style="color:#4CAF50; margin:4px 0; font-size:22px; font-weight:bold;">
                            {stake}€
                        </p>
                    </div>
                </div>
                <p style="color:#4CAF50; margin:0; font-size:14px;">
                    Si ganas cobras {round(stake * cuota, 2)}€ (+{ganancia}€ de beneficio)
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Pregunta interactiva
            st.markdown(f"**¿Has apostado este pick ({str(pick['apostar_a'])})?**")
            col_si, col_no, col_esp = st.columns([1, 1, 3])

            with col_si:
                if st.button(f"✅ Sí aposté", key=f"si_{i}", use_container_width=True):
                    st.session_state[f"apostado_{i}"] = True

            with col_no:
                if st.button(f"❌ No aposté", key=f"no_{i}", use_container_width=True):
                    st.session_state[f"apostado_{i}"] = False
                    st.info("Pick ignorado. No se actualiza el bankroll.")

            if st.session_state.get(f"apostado_{i}") == True:
                st.markdown("**¿Cuál fue el resultado?**")
                col_g, col_p, col_pen = st.columns([1, 1, 1])

                with col_g:
                    if st.button(f"🏆 Ganado", key=f"gan_{i}", use_container_width=True):
                        profit = guardar_apuesta(
                            str(pick["partido"]), str(pick["apostar_a"]),
                            cuota, float(pick["prob_modelo"]),
                            float(pick["edge"]), stake, "ganado"
                        )
                        nuevo_bankroll = bankroll + profit
                        actualizar_bankroll(nuevo_bankroll)
                        st.success(f"🎉 Ganado! +{profit}€ — Nuevo bankroll: {nuevo_bankroll:.2f}€")
                        st.balloons()
                        st.rerun()

                with col_p:
                    if st.button(f"😞 Perdido", key=f"per_{i}", use_container_width=True):
                        profit = guardar_apuesta(
                            str(pick["partido"]), str(pick["apostar_a"]),
                            cuota, float(pick["prob_modelo"]),
                            float(pick["edge"]), stake, "perdido"
                        )
                        nuevo_bankroll = bankroll + profit
                        actualizar_bankroll(nuevo_bankroll)
                        st.error(f"Perdido. -{stake}€ — Nuevo bankroll: {nuevo_bankroll:.2f}€")
                        st.rerun()

                with col_pen:
                    if st.button(f"⏳ Pendiente", key=f"pend_{i}", use_container_width=True):
                        guardar_apuesta(
                            str(pick["partido"]), str(pick["apostar_a"]),
                            cuota, float(pick["prob_modelo"]),
                            float(pick["edge"]), stake, "pendiente"
                        )
                        st.info("Guardado como pendiente. Actualiza el resultado cuando termine.")
                        st.rerun()

            st.markdown("---")

# ── TAB 2: RENDIMIENTO ──
with tab2:
    if apostadas.empty:
        st.info("Aun no hay apuestas registradas.")
    else:
        st.subheader("Evolucion del bankroll")
        apostadas_sorted = apostadas.sort_values("fecha")
        apostadas_sorted["bankroll_ev"] = 20 + apostadas_sorted["profit"].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=apostadas_sorted["fecha"],
            y=apostadas_sorted["bankroll_ev"],
            mode="lines+markers",
            line=dict(color="#4CAF50", width=3),
            fill="tozeroy",
            fillcolor="rgba(76,175,80,0.1)"
        ))
        fig.add_hline(y=20, line_dash="dash", line_color="gray",
                      annotation_text="Bankroll inicial 20EUR")
        fig.update_layout(
            paper_bgcolor="#0f0f1a",
            plot_bgcolor="#0f0f1a",
            font=dict(color="white"),
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Resultados")
            res_count = apostadas.groupby("resultado").size().reset_index(name="count")
            fig2 = px.pie(res_count, values="count", names="resultado",
                          color="resultado",
                          color_discrete_map={"ganado":"#4CAF50","perdido":"#E53935","pendiente":"#FFC107"})
            fig2.update_layout(paper_bgcolor="#0f0f1a", font=dict(color="white"))
            st.plotly_chart(fig2, use_container_width=True)

        with col2:
            st.subheader("Profit por partido")
            fig3 = px.bar(apostadas.tail(10), x="apostar_a", y="profit",
                          color="resultado",
                          color_discrete_map={"ganado":"#4CAF50","perdido":"#E53935","pendiente":"#FFC107"})
            fig3.update_layout(paper_bgcolor="#0f0f1a", font=dict(color="white"))
            st.plotly_chart(fig3, use_container_width=True)

# ── TAB 3: HISTORIAL ──
with tab3:
    if historial.empty:
        st.info("No hay historial todavia.")
    else:
        st.subheader("Todas las apuestas registradas")
        cols_show = ["fecha", "partido", "apostar_a", "cuota",
                     "prob_modelo", "stake", "resultado", "profit"]
        df_show = historial[cols_show].copy()
        df_show["prob_modelo"] = (df_show["prob_modelo"] * 100).round(1).astype(str) + "%"
        df_show["profit"] = df_show["profit"].apply(lambda x: f"+{x:.2f}EUR" if x > 0 else f"{x:.2f}EUR")
        st.dataframe(df_show, use_container_width=True, height=400)