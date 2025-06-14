import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, Fullscreen, Draw
from shapely.geometry import Point, Polygon
from datetime import datetime, timedelta
import openrouteservice
import io
import streamlit.components.v1 as components

st.set_page_config(layout="wide")
col1, col2 = st.columns([0.15, 0.85])
with col1:
    st.image("logo_sirtec.png", width=120)
with col2:
    st.markdown(
        """
        <h1 style='font-size:32px; margin-top:5px;'>CCM - Roteirizador de Vistorias</h1>
        """,
        unsafe_allow_html=True
    )

ORS_API_KEY = "5b3ce3597851110001cf6248cc2568a203694c3580ce90fb1175c1fb"
client = openrouteservice.Client(key=ORS_API_KEY)

def format_timedelta(td):
    try:
        total_seconds = int(td.total_seconds())
        h, r = divmod(total_seconds, 3600)
        m, _ = divmod(r, 60)
        return f"{h:02}:{m:02}"
    except:
        return "00:00"

def parse_tempo(valor):
    try:
        if pd.isna(valor):
            return timedelta(0)
        valor = str(valor).strip()
        if ":" in valor:
            return pd.to_timedelta(valor)
        if valor.replace(',', '').replace('.', '').isdigit():
            return pd.to_timedelta(float(valor), unit="m")
    except:
        pass
    return timedelta(0)

cor_por_tipo = {
    "OBRA": "green",
    "PLANO MANUT.": "blue",
    "ASSIN. LPT": "orange",
    "ASSIN. VIP's": "purple",
    "PARECER 023": "red",
    "AS BUILT": "darkred"
}
...
