import os
import zipfile
import xml.etree.ElementTree as ET
import unicodedata
import math
import urllib.parse
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

# Ocultar menus e ajustar estilo CSS
ocultar_elementos_css = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    div[class*="stAppViewerToolbar"] {display: none !important;}
    
    /* Ocultar badges de status */
    [data-testid="stStatusWidget"] {display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    a[class*="viewerBadge"] {display: none !important;}
    [data-testid="stActionButton"] {display: none !important;}

    /* Oculta/desativa o menu flutuante das colunas da tabela */
    div[role="menu"],
    [data-baseweb="popover"]:has([role="menu"]) {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
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
    nfkd = unicodedata.normalize('NFD', str(texto))
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

def gerar_link_whatsapp(nome_cto, cidade, coordenadas, maps_url):
    """ Gera link formatado para envio direto via WhatsApp """
    mensagem = (
        f"📍 *Bater CTO:* {nome_cto}\n"
        f"   *Cidade:*:            \n"
    
    )
    mensagem_enc = urllib.parse.quote(mensagem)
    return f"https://api.whatsapp.com/send?text={mensagem_enc}"

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

    try:
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
                coords_str = f"{lat:.6f}, {lon:.6f}"
                maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                wsp_url = gerar_link_whatsapp(cto_name, cidade_nome, coords_str, maps_url)
                
                ctos_list.append({
                    "Projeto / Cidade": cidade_nome,
                    "Nome da CTO": cto_name,
                    "Latitude": lat,
                    "Longitude": lon,
                    "Coordenadas": coords_str,
                    "Rota no GPS": maps_url,
                    "WhatsApp": wsp_url
                })
    except Exception as e:
        st.error(f"Erro ao processar o arquivo {nome_arquivo}: {e}")

    return ctos_list

def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def extrair_lat_lon(texto):
    try:
        partes = texto.replace(" ", "").split(",")
        if len(partes) >= 2:
            return float(partes[0]), float(partes[1])
    except ValueError:
        pass
    return None, None

# ==================== INTERFACE GRÁFICA ====================

st.title("🔍 Buscador de CTOs - FTTH")
st.caption("Consulte e compartilhe a localização de caixas ópticas com a equipe")

todas_ctos = []

# 1. Carrega arquivos do repositório
arquivos_repositorio = [f for f in os.listdir('.') if f.lower().endswith(('.kmz', '.kml'))]
for nome_arq in arquivos_repositorio:
    try:
        with open(nome_arq, 'rb') as f:
            ctos = processar_bytes_kml_kmz(f.read(), nome_arq)
            todas_ctos.extend(ctos)
    except Exception as e:
        st.warning(f"Não foi possível carregar {nome_arq}: {e}")

# 2. Uploads manuais adicionais
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

if not todas_ctos:
    st.info("👈 Nenhum arquivo KMZ/KML encontrado. Adicione os arquivos no GitHub ou faça upload ao lado.")
    st.stop()

df = pd.DataFrame(todas_ctos)

modo_busca = st.radio(
    "Escolha o modo de busca:",
    ["🔎 Buscar por Nome / Cidade", "📍 CTO Mais Próxima (Minha Localização)"],
    horizontal=True
)

st.write("---")

# MODO 1: BUSCA POR FILTROS
if modo_busca == "🔎 Buscar por Nome / Cidade":
    st.subheader("🔎 Filtros de Busca")
    col1, col2 = st.columns([1, 1])

    with col1:
        cidades_presentes = list(df["Projeto / Cidade"].unique()) if "Projeto / Cidade" in df.columns else []
        cidades_ordenadas = [c for c in CIDADES_OFICIAIS if c in cidades_presentes]
        outras_cidades = [c for c in cidades_presentes if c not in CIDADES_OFICIAIS]
        
        opcoes_cidades = ["Todas as Cidades/Bairro Rural"] + cidades_ordenadas + outras_cidades
        cidade_selecionada = st.selectbox("Selecione a Cidade / Projeto:", opcoes_cidades)

    with col2:
        termo_cto = st.text_input("Digite o Nome da CTO (ex: CTO 122):")

    df_filtrado = df.copy()

    if cidade_selecionada != "Todas as Cidades/Bairro Rural":
        df_filtrado = df_filtrado[df_filtrado["Projeto / Cidade"] == cidade_selecionada]

    if termo_cto:
        termo_norm = normalizar(termo_cto)
        df_filtrado = df_filtrado[
            df_filtrado["Nome da CTO"].apply(lambda x: termo_norm in normalizar(str(x)))
        ]

    st.subheader(f"📍 Resultados ({len(df_filtrado)} CTOs encontradas)")

    if not df_filtrado.empty:
        st.dataframe(
            df_filtrado[["Projeto / Cidade", "Nome da CTO", "Coordenadas", "Rota no GPS", "WhatsApp"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Rota no GPS": st.column_config.LinkColumn(
                    "Abrir no GPS",
                    help="Clique para abrir a localização direto no Google Maps",
                    validate="^https://",
                    display_text="🗺️ Abrir no Mapa"
                ),
                "WhatsApp": st.column_config.LinkColumn(
                    "WhatsApp",
                    help="Enviar dados desta CTO pelo WhatsApp",
                    validate="^https://",
                    display_text="📲 Compartilhar"
                )
            }
        )
        
        # Bloco de ação rápida se houver apenas 1 CTO encontrada
        if len(df_filtrado) == 1:
            cto_nome = df_filtrado.iloc[0]["Nome da CTO"]
            coords_texto = df_filtrado.iloc[0]["Coordenadas"]
            wsp_link = df_filtrado.iloc[0]["WhatsApp"]
            
            st.write("---")
            col_c1, col_c2 = st.columns([1, 1])
            with col_c1:
                st.markdown(f"📋 **Copiar coordenadas da {cto_nome}:**")
                st.code(coords_texto, language=None)
            with col_c2:
                st.markdown(f"📲 **Enviar para o WhatsApp:**")
                st.link_button("🟢 Compartilhar no WhatsApp", wsp_link)
    else:
        st.warning("Nenhuma CTO encontrada com os filtros selecionados.")

# MODO 2: CTO MAIS PRÓXIMA POR GPS
else:
    st.subheader("📍 Encontrar CTOs mais próximas da sua posição")

    # Captura GPS no navegador
    html_gps = """
    <div style="background-color:#1e1e1e; padding:15px; border-radius:10px; color:white; text-align:center; font-family:sans-serif;">
        <button onclick="getGPS()" style="background-color:#4CAF50; color:white; border:none; padding:12px 20px; font-size:16px; border-radius:5px; cursor:pointer; font-weight:bold; width:100%; max-width:320px;">
            📡 Obter Minha Localização Atual (GPS)
        </button>
        <div id="gps_status" style="margin-top:12px; font-size:14px; color:#aaa;">Clique no botão acima para capturar suas coordenadas.</div>
    </div>

    <script>
    function copyToClipboard(text) {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(function() {
                document.getElementById("copy_status").innerText = "✅ Coordenada copiada! Agora cole no campo abaixo.";
            }).catch(function() { fallbackCopy(text); });
        } else { fallbackCopy(text); }
    }

    function fallbackCopy(text) {
        var textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
            document.getElementById("copy_status").innerText = "✅ Coordenada copiada! Agora cole no campo abaixo.";
        } catch (err) {
            document.getElementById("copy_status").innerText = "❌ Selecione e copie manualmente.";
        }
        document.body.removeChild(textArea);
    }

    function getGPS() {
        var status = document.getElementById("gps_status");
        if (navigator.geolocation) {
            status.innerHTML = "Buscando sinal de GPS...";
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    var lat = position.coords.latitude.toFixed(6);
                    var lon = position.coords.longitude.toFixed(6);
                    var coords = lat + ", " + lon;
                    
                    status.innerHTML = `
                        <b style='color:#4CAF50;'>Sua Posição:</b><br>
                        <span style='font-size:20px; color:white; font-weight:bold;'>${coords}</span><br><br>
                        <button onclick="copyToClipboard('${coords}')" style="background-color:#2196F3; color:white; border:none; padding:10px 18px; font-size:14px; border-radius:5px; cursor:pointer; font-weight:bold;">
                            📋 Copiar Coordenadas
                        </button>
                        <div id="copy_status" style="margin-top:8px; font-size:13px; color:#ffeb3b; font-weight:bold;"></div>
                    `;
                },
                function(error) {
                    status.innerHTML = "<span style='color:#ff5555;'>Erro ao obter GPS. Verifique a permissão de localização no celular.</span>";
                },
                { enableHighAccuracy: true, timeout: 10000 }
            );
        } else {
            status.innerHTML = "GPS não suportado neste navegador.";
        }
    }
    </script>
    """
    components.html(html_gps, height=190)

    input_coords = st.text_input(
        "Cole aqui suas coordenadas (ex: -22.410920, -45.793186):",
        placeholder="-22.410920, -45.793186"
    )

    qtd_mostrar = st.slider("Quantidade de CTOs mais próximas a exibir:", min_value=1, max_value=20, value=5)

    if input_coords:
        user_lat, user_lon = extrair_lat_lon(input_coords)

        if user_lat is not None and user_lon is not None:
            df_prox = df.copy()

            df_prox["dist_m"] = df_prox.apply(
                lambda row: calcular_distancia_metros(user_lat, user_lon, row["Latitude"], row["Longitude"]),
                axis=1
            )

            df_prox = df_prox.sort_values(by="dist_m").head(qtd_mostrar)

            def formatar_distancia(m):
                if m >= 1000:
                    return f"{m / 1000:.2f} km"
                return f"{int(m)} m"

            df_prox["Distância"] = df_prox["dist_m"].apply(formatar_distancia)

            st.success(f"🎯 Mostrando as {len(df_prox)} CTOs mais próximas de você:")

            st.dataframe(
                df_prox[["Distância", "Nome da CTO", "Projeto / Cidade", "Coordenadas", "Rota no GPS", "WhatsApp"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Rota no GPS": st.column_config.LinkColumn(
                        "Abrir no GPS",
                        help="Clique para traçar a rota até a CTO",
                        validate="^https://",
                        display_text="🗺️ Traçar Rota"
                    ),
                    "WhatsApp": st.column_config.LinkColumn(
                        "WhatsApp",
                        help="Enviar dados desta CTO pelo WhatsApp",
                        validate="^https://",
                        display_text="📲 Compartilhar"
                    )
                }
            )

            cto_top = df_prox.iloc[0]
            st.info(f"🏆 **CTO mais próxima:** **{cto_top['Nome da CTO']}** a apenas **{cto_top['Distância']}** de distância!")

            col_p1, col_p2 = st.columns([1, 1])
            with col_p1:
                st.markdown(f"📋 **Copiar coordenadas da CTO mais próxima ({cto_top['Nome da CTO']}):**")
                st.code(cto_top["Coordenadas"], language=None)
            with col_p2:
                st.markdown(f"📲 **Enviar para o WhatsApp:**")
                st.link_button("🟢 Compartilhar no WhatsApp", cto_top["WhatsApp"])

        else:
            st.error("Formato de coordenadas inválido. Exemplo correto: `-22.410920, -45.793186`")
