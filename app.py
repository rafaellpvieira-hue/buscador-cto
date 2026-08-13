import os
import zipfile
import xml.etree.ElementTree as ET
import unicodedata
import pandas as pd
import streamlit as st

# 1. Configuração da página
st.set_page_config(
    page_title="Buscador de CTOs FTTH",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Lista oficial das cidades e projetos permitidos
CIDADES_OFICIAIS = [
    "PROJETO PARAISOPOLIS",
    "REDE FTTH DISTRITO DOS COSTAS_V1.kmz",
    "PROJETO_FTTH_CONC. DOS OUROS.kmz",
    "PROJETO_FTTH CACHOEIRA DE MINAS.kmz",
    "PROJETO SAO BENTO DO SAPUCAI.kmz",
    "PROJETO SAPUCAÍ MIRIM.kmz",
    "POUSO ALEGRE CIDADE JARDIM",
    "POUSO ALEGRE JARDIM AEROPORTO"
]

def normalizar(texto):
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFD', texto)
    sem_acento = ''.join([c for c in nfkd if unicodedata.category(c) != 'Mn'])
    return sem_acento.lower().strip()

def identificar_cidade_oficial(stack):
    for folder_name in stack:
        norm_folder = normalizar(folder_name)
        for cidade_oficial in CIDADES_OFICIAIS:
            norm_oficial = normalizar(cidade_oficial)
            if norm_oficial == norm_folder or norm_oficial in norm_folder or norm_folder in norm_oficial:
                return cidade_oficial
    return "OUTROS / NÃO IDENTIFICADO"

def parse_element(element, container_stack=None):
    if container_stack is None:
        container_stack = []

    tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
    new_stack = list(container_stack)

    if tag in ("Folder", "Document"):
        name_elem = element.find('{*}name')
        if name_elem is not None and name_elem.text:
            new_stack.append(name_elem.text.strip())

    results = []
    if tag == "Placemark":
        name_elem = element.find('{*}name')
        coords_elem = element.find('.//{*}coordinates')
        if name_elem is not None and name_elem.text and coords_elem is not None and coords_elem.text:
            cto_name = name_elem.text.strip()
            coords = coords_elem.text.strip().split(',')
            if len(coords) >= 2:
                try:
                    lon = float(coords[0].strip())
                    lat = float(coords[1].strip())
                    results.append((cto_name, lat, lon, list(new_stack)))
                except ValueError:
                    pass

    for child in element:
        results.extend(parse_element(child, new_stack))

    return results

def processar_arquivo_uploaded(uploaded_file):
    ctos_list = []
    nome_arq = uploaded_file.name
    ext = os.path.splitext(nome_arq)[1].lower()

    kmls_bytes = []

    if ext == ".kml":
        kmls_bytes.append(uploaded_file.read())
    elif ext == ".kmz":
        with zipfile.ZipFile(uploaded_file, 'r') as z:
            kmls = [f for f in z.namelist() if f.lower().endswith('.kml')]
            for kml_filename in kmls:
                kmls_bytes.append(z.read(kml_filename))

    for kml_byte in kmls_bytes:
        root = ET.fromstring(kml_byte)
        placemarks = parse_element(root)

        for cto_name, lat, lon, stack in placemarks:
            cidade_nome = identificar_cidade_oficial(stack)
            maps_url = f"https://www.google.com/maps?q={lat},{lon}"
            
            ctos_list.append({
                "Projeto / Cidade": cidade_nome,
                "Nome da CTO": cto_name,
                "Latitude": lat,
                "Longitude": lon,
                "Coordenadas": f"{lat:.6f}, {lon:.6f}",
                "Rota no GPS": maps_url
            })

    return ctos_list

# ==================== INTERFACE GRÁFICA ====================

st.title("🔍 Buscador de CTOs - FTTH")
st.caption("Consulte a localização de caixas ópticas no computador ou smartphone")

# Menu Lateral para Upload
st.sidebar.header("📁 Arquivos do Projeto")
uploaded_files = st.sidebar.file_uploader(
    "Carregue um ou vários arquivos KMZ / KML",
    type=["kmz", "kml"],
    accept_multiple_files=True
)

todas_ctos = []
if uploaded_files:
    for f in uploaded_files:
        ctos_extraidas = processar_arquivo_uploaded(f)
        todas_ctos.extend(ctos_extraidas)

    st.sidebar.success(f"🟢 {len(uploaded_files)} arquivo(s) carregado(s)")
    st.sidebar.metric("Total de CTOs no Sistema", len(todas_ctos))

# Trava de segurança: se não houver CTOs carregadas, exibe instrução e para a execução aqui
if not todas_ctos:
    st.info("👈 Por favor, carregue os arquivos **KMZ/KML** no menu lateral à esquerda para começar.")
    st.stop()

# Monta o DataFrame garantindo as colunas
df = pd.DataFrame(todas_ctos)

# Filtros na Tela Principal
st.subheader("🔎 Filtros de Busca")
col1, col2 = st.columns([1, 1])

with col1:
    cidades_presentes = list(df["Projeto / Cidade"].unique())
    cidades_ordenadas = [c for c in CIDADES_OFICIAIS if c in cidades_presentes]
    outras_cidades = [c for c in cidades_presentes if c not in CIDADES_OFICIAIS]
    
    opcoes_cidades = ["ALL - Todas as Cidades"] + cidades_ordenadas + outras_cidades
    cidade_selecionada = st.selectbox("Selecione a Cidade / Projeto:", opcoes_cidades)

with col2:
    termo_cto = st.text_input("Digite o Nome da CTO (ex: CTO 122):")

# Aplicação dos Filtros
df_filtrado = df.copy()

if cidade_selecionada != "ALL - Todas as Cidades":
    df_filtrado = df_filtrado[df_filtrado["Projeto / Cidade"] == cidade_selecionada]

if termo_cto:
    termo_norm = normalizar(termo_cto)
    df_filtrado = df_filtrado[
        df_filtrado["Nome da CTO"].apply(lambda x: termo_norm in normalizar(str(x)))
    ]

# Exibição dos Resultados
st.subheader(f"📍 Resultados ({len(df_filtrado)} CTOs encontradas)")

if not df_filtrado.empty:
    st.dataframe(
        df_filtrado[["Projeto / Cidade", "Nome da CTO", "Coordenadas", "Rota no GPS"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Rota no GPS": st.column_config.LinkColumn(
                "Abrir no GPS",
                help="Clique para abrir a localização direto no Google Maps/Waze",
                validate="^https://",
                display_text="🗺️ Abrir no Mapa"
            )
        }
    )
else:
    st.warning("Nenhuma CTO encontrada com os filtros selecionados.")