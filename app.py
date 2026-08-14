import os
import zipfile
import xml.etree.ElementTree as ET
import unicodedata
import math
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# 1. Configuração da página
st.set_page_config(
    page_title="Buscador de CTOs FTTH",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)
# Ocultar cabeçalho, menu e botões do Streamlit (Share, Edit, GitHub)
ocultar_elementos_css = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden;}
    </style>
"""
st.markdown(ocultar_elementos_css, unsafe_allow_html=True)

# Lista oficial das cidades e projetos permitidos
CIDADES_OFICIAIS = [
    "PARAISOPOLIS",
    "DISTRITO DOS COSTAS",
    "CONCEICAO DOS OUROS",
    "CACHOEIRA DE MINAS",
    "SAO BENTO DO SAPUCAI",
    "SAPUCAI MIRIM",
    "POUSO ALEGRE",
    "RIBEIRAOZINHO",
    "PONTE DE FERRO",
    "BAU DO CENTRO",
    "OSÓRIO",
    "CORREGO DA FOICE",
    "BELA VISTA",
    "RIBEIRÃO",
    "INACIOS",
    "COQUEIROS",
    "CONC. DOS OUROS"
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

def processar_bytes_kml_kmz(conteudo_bytes, nome_arquivo):
    ctos_list = []
    ext = os.path.splitext(nome_arquivo)[1].lower()
    kmls_bytes = []

    if ext == ".kml":
        kmls_bytes.append(conteudo_bytes)
    elif ext == ".kmz":
        import io
        with zipfile.ZipFile(io.BytesIO(conteudo_bytes), 'r') as z:
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

# Função matemática para calcular a distância exata em metros entre duas coordenadas
def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000  # Raio da Terra em metros
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def extrair_lat_lon(texto):
    """ Extrai latitude e longitude do texto digitado """
    try:
        partes = texto.replace(" ", "").split(",")
        if len(partes) >= 2:
            return float(partes[0]), float(partes[1])
    except ValueError:
        pass
    return None, None

# ==================== INTERFACE GRÁFICA ====================

st.title("🔍 Buscador de CTOs - FTTH")
st.caption("Consulte a localização de caixas ópticas no computador ou smartphone")

todas_ctos = []

# 1. Carrega automaticamente qualquer arquivo .kmz ou .kml da pasta da aplicação
arquivos_repositorio = [f for f in os.listdir('.') if f.lower().endswith(('.kmz', '.kml'))]

for nome_arq in arquivos_repositorio:
    with open(nome_arq, 'rb') as f:
        ctos = processar_bytes_kml_kmz(f.read(), nome_arq)
        todas_ctos.extend(ctos)

# 2. Permite uploads adicionais na barra lateral
st.sidebar.header("📁 Gerenciar Arquivos")
uploaded_files = st.sidebar.file_uploader(
    "Enviar KMZ/KML adicional",
    type=["kmz", "kml"],
    accept_multiple_files=True
)

if uploaded_files:
    for f in uploaded_files:
        ctos_extraidas = processar_bytes_kml_kmz(f.read(), f.name)
        todas_ctos.extend(ctos_extraidas)

st.sidebar.metric("Total de CTOs no Sistema", len(todas_ctos))

# Trava de segurança
if not todas_ctos:
    st.info("👈 Nenhum arquivo KMZ/KML encontrado. Adicione os arquivos no GitHub ou faça upload ao lado.")
    st.stop()

# Monta o DataFrame
df = pd.DataFrame(todas_ctos)

# Seleção do Modo de Busca
modo_busca = st.radio(
    "Escolha o modo de busca:",
    ["🔎 Buscar por Nome / Cidade", "📍 CTO Mais Próxima (Minha Localização)"],
    horizontal=True
)

st.write("---")

# MODO 1: BUSCA POR FILTROS TRADICIONAIS
if modo_busca == "🔎 Buscar por Nome / Cidade":
    # Filtros na Tela Principal
    st.subheader("🔎 Filtros de Busca")
    col1, col2 = st.columns([1, 1])

    with col1:
        cidades_presentes = list(df["Projeto / Cidade"].unique()) if "Projeto / Cidade" in df.columns else []
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

# MODO 2: CTO MAIS PRÓXIMA POR GPS
else:
    st.subheader("📍 Encontrar CTOs mais próximas da sua posição")

    # Componente HTML/JS para capturar GPS do celular/computador
    html_gps = """
    <div style="background-color:#1e1e1e; padding:15px; border-radius:10px; color:white; text-align:center;">
        <button onclick="getGPS()" style="background-color:#4CAF50; color:white; border:none; padding:12px 20px; font-size:16px; border-radius:5px; cursor:pointer; font-weight:bold;">
            📡 Obter Minha Localização Atual (GPS)
        </button>
        <p id="gps_status" style="margin-top:10px; font-size:14px; color:#aaa;">Clique no botão acima para capturar suas coordenadas.</p>
    </div>

    <script>
    function getGPS() {
        var status = document.getElementById("gps_status");
        if (navigator.geolocation) {
            status.innerHTML = "Buscando sinal de GPS...";
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    var lat = position.coords.latitude.toFixed(6);
                    var lon = position.coords.longitude.toFixed(6);
                    status.innerHTML = "<b style='color:#4CAF50;'>Sua Posição:</b> <br><span style='font-size:18px; color:white;'><b>" + lat + ", " + lon + "</b></span><br><i>Copie os números acima e cole no campo abaixo!</i>";
                },
                function(error) {
                    status.innerHTML = "<span style='color:#ff5555;'>Erro ao obter GPS. Verifique a permissão de localização no navegador/celular.</span>";
                },
                { enableHighAccuracy: true, timeout: 10000 }
            );
        } else {
            status.innerHTML = "GPS não suportado neste navegador.";
        }
    }
    </script>
    """
    components.html(html_gps, height=140)

    input_coords = st.text_input(
        "Cole aqui suas coordenadas (ex: -22.410920, -45.793186):",
        placeholder="-22.410920, -45.793186"
    )

    qtd_mostrar = st.slider("Quantidade de CTOs mais próximas a exibir:", min_value=1, max_value=20, value=5)

    if input_coords:
        user_lat, user_lon = extrair_lat_lon(input_coords)

        if user_lat is not None and user_lon is not None:
            df_prox = df.copy()

            # Cálculo da distância de cada CTO
            df_prox["dist_m"] = df_prox.apply(
                lambda row: calcular_distancia_metros(user_lat, user_lon, row["Latitude"], row["Longitude"]),
                axis=1
            )

            # Ordena da menor para a maior distância
            df_prox = df_prox.sort_values(by="dist_m").head(qtd_mostrar)

            def formatar_distancia(m):
                if m >= 1000:
                    return f"{m / 1000:.2f} km"
                return f"{int(m)} m"

            df_prox["Distância"] = df_prox["dist_m"].apply(formatar_distancia)

            st.success(f"🎯 Mostrando as {len(df_prox)} CTOs mais próximas de você:")

            st.dataframe(
                df_prox[["Distância", "Nome da CTO", "Projeto / Cidade", "Coordenadas", "Rota no GPS"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Rota no GPS": st.column_config.LinkColumn(
                        "Abrir no GPS",
                        help="Clique para traçar a rota até a CTO",
                        validate="^https://",
                        display_text="🗺️ Traçar Rota"
                    )
                }
            )

            cto_top = df_prox.iloc[0]
            st.info(f"🏆 **CTO mais próxima:** **{cto_top['Nome da CTO']}** a apenas **{cto_top['Distância']}** de distância!")

        else:
            st.error("Formato de coordenadas inválido. Exemplo correto: `-22.410920, -45.793186`")
