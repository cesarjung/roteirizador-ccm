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

col_in, col_out = st.columns([0.5, 0.5])
with col_in:
    ponto_partida_input = st.text_input("Ponto de partida (lat,lon):")
with col_out:
    ponto_chegada_input = st.text_input("Ponto de chegada (lat,lon) (opcional):")

arquivo = st.file_uploader("Selecione o arquivo Excel:", type=["xlsx"])

col_bt1, col_bt2, col_bt3 = st.columns([1, 1, 1])
with col_bt1:
    botao_roteirizar = st.button("Atualizar Rota")
with col_bt2:
    botao_online = st.button("BD Online")
with col_bt3:
    botao_exportar = st.button("Exportar Rota")

df = None

if botao_online:
    url_online = st.text_input("Insira o URL da planilha (formato CSV exportável):")
    if url_online:
        try:
            df = pd.read_csv(url_online, header=5)
            st.success("Base online carregada com sucesso!")
        except Exception as e:
            st.error(f"Erro ao carregar base online: {e}")

elif arquivo:
    df = pd.read_excel(arquivo, header=5)

if df is not None:
    if 'Latitude' not in df or 'Longitude' not in df:
        st.error("Colunas Latitude e Longitude não encontradas.")
        st.stop()

    df = df.dropna(subset=['Latitude', 'Longitude'])
    df['Latitude'] = df['Latitude'].astype(str).str.replace(",", ".", regex=False).astype(float)
    df['Longitude'] = df['Longitude'].astype(str).str.replace(",", ".", regex=False).astype(float)

    municipios = sorted(df['Município'].dropna().unique())
    unidades = sorted(df['Unidade'].dropna().unique())
    sel_municipios = st.multiselect("Filtrar por Município:", municipios, default=municipios)
    sel_unidades = st.multiselect("Filtrar por Unidade:", unidades, default=unidades)
    df = df[df['Município'].isin(sel_municipios) & df['Unidade'].isin(sel_unidades)]

    mapa_container = st.container()
    rota_placeholder = st.empty()

    with mapa_container:
        centro = [df['Latitude'].mean(), df['Longitude'].mean()]
        mapa = folium.Map(location=centro, zoom_start=12)
        Fullscreen().add_to(mapa)
        draw = Draw(export=True, draw_options={"polyline": False,"rectangle": True,"circle": False,"circlemarker": False,"marker": True,"polygon": True})
        draw.add_to(mapa)
        cluster = MarkerCluster().add_to(mapa)

        for _, row in df.iterrows():
            cor = cor_por_tipo.get(str(row.get("TIPO", "")).strip(), "gray")
            tooltip_text = f"{row.get('TIPO', '')} - {row.get('Projeto', '')}"
            folium.Marker(location=[row["Latitude"], row["Longitude"]], tooltip=tooltip_text, icon=folium.Icon(color=cor)).add_to(cluster)

        saida = st_folium(mapa, width=1400, height=600, returned_objects=["all_drawings"])

    if "df_preview" not in st.session_state:
        st.session_state.df_preview = None
    if "df_filtrado" not in st.session_state:
        st.session_state.df_filtrado = None
    if "rota" not in st.session_state:
        st.session_state.rota = None
    if "lat0" not in st.session_state:
        st.session_state.lat0 = None
    if "lon0" not in st.session_state:
        st.session_state.lon0 = None
    if "lat1" not in st.session_state:
        st.session_state.lat1 = None
    if "lon1" not in st.session_state:
        st.session_state.lon1 = None

    if botao_roteirizar:
        polygons = []
        if saida.get("all_drawings"):
            for feat in saida["all_drawings"]:
                if feat.get("geometry", {}).get("type") == "Polygon":
                    coords = feat["geometry"]["coordinates"][0]
                    polygons.append(Polygon([(lon, lat) for lon, lat in coords]))

        if not polygons:
            st.error("Nenhum polígono com pelo menos 3 pontos foi desenhado.")
            st.stop()

        pontos_geom = df.apply(lambda row: Point(row["Longitude"], row["Latitude"]), axis=1)
        df_filtrado = df[pontos_geom.apply(lambda p: any(poly.contains(p) for poly in polygons))].copy()

        if df_filtrado.empty:
            st.warning("Nenhum ponto dentro do polígono.")
            st.stop()

        try:
            lat0, lon0 = map(float, ponto_partida_input.split(","))
            ponto_partida = [lon0, lat0]
        except:
            st.warning("Ponto de partida inválido.")
            st.stop()

        if ponto_chegada_input:
            try:
                lat1, lon1 = map(float, ponto_chegada_input.split(","))
                ponto_chegada = [lon1, lat1]
            except:
                ponto_chegada = None
        else:
            ponto_chegada = None

        coordenadas = [[row["Longitude"], row["Latitude"]] for _, row in df_filtrado.iterrows()]
        coordenadas.insert(0, ponto_partida)
        if ponto_chegada:
            coordenadas.append(ponto_chegada)

        try:
            rota = client.directions(coordenadas, profile='driving-car', format='geojson')
        except Exception as e:
            st.error(f"Erro ao gerar rota: {e}")
            st.stop()

        legs = rota['features'][0]['properties']['segments']
        duracoes = [timedelta(seconds=s['duration']) for s in legs]

        df_preview = df_filtrado.reset_index(drop=True)
        df_preview.insert(0, "Ordem", range(1, len(df_preview) + 1))
        df_preview["Tempo Execução"] = df_preview["TEMPO"].apply(parse_tempo)
        df_preview["Tempo Deslocamento"] = duracoes[:len(df_preview)]
        df_preview["Total Acumulado"] = (df_preview["Tempo Execução"] + df_preview["Tempo Deslocamento"]).cumsum()

        df_preview["Tempo Execução"] = df_preview["Tempo Execução"].apply(format_timedelta)
        df_preview["Tempo Deslocamento"] = df_preview["Tempo Deslocamento"].apply(format_timedelta)
        df_preview["Total Acumulado"] = df_preview["Total Acumulado"].apply(format_timedelta)

        colunas = ["TIPO", "Unidade", "Projeto", "Município", "Latitude", "Longitude", "Tempo Execução", "Tempo Deslocamento", "Total Acumulado"]
        df_preview = df_preview[colunas]

        st.session_state.df_preview = df_preview
        st.session_state.df_filtrado = df_filtrado
        st.session_state.rota = rota
        st.session_state.lat0 = lat0
        st.session_state.lon0 = lon0
        st.session_state.lat1 = lat1 if ponto_chegada_input else None
        st.session_state.lon1 = lon1 if ponto_chegada_input else None

        rota_map = folium.Map(location=[lat0, lon0], zoom_start=13)
        if "features" in rota:
            folium.GeoJson(data=rota, name="Rota").add_to(rota_map)
        folium.Marker(location=[lat0, lon0], tooltip="Partida", icon=folium.Icon(color="green")).add_to(rota_map)
        if lat1 and lon1:
            folium.Marker(location=[lat1, lon1], tooltip="Chegada", icon=folium.Icon(color="red")).add_to(rota_map)
        for idx, row in df_preview.iterrows():
            tooltip_text = f"{row['TIPO']} - {row['Projeto']}"
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                tooltip=tooltip_text,
                icon=folium.DivIcon(html=f"<div style='font-size: 12pt; color: black;'><b>{idx + 1}</b></div>")
            ).add_to(rota_map)
        rota_placeholder.folium_chart(rota_map, width=1400, height=600)

    if st.session_state.df_preview is not None:
        with st.expander("📜 Ver Roteiro Gerado", expanded=True):
            st.dataframe(st.session_state.df_preview)
            total_final_str = st.session_state.df_preview["Total Acumulado"].iloc[-1]
            try:
                total_final_td = pd.to_timedelta("00:" + total_final_str) if len(total_final_str) <= 5 else pd.to_timedelta(total_final_str)
                st.success(f"⏱️ Tempo total do roteiro: {total_final_str}")
                if total_final_td > timedelta(hours=8, minutes=48):
                    st.error("⚠️ Tempo total excede o limite de um turno (8h48min).")
            except Exception as e:
                st.warning(f"Erro ao interpretar tempo total: {e}")

    if botao_exportar and st.session_state.df_preview is not None:
        output = io.BytesIO()
        st.session_state.df_preview.to_excel(output, index=False)
        st.download_button("Clique para baixar o roteiro", output.getvalue(), file_name="roteiro.xlsx")
