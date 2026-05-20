import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, date
from io import BytesIO
import json

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None


st.set_page_config(
    page_title="Packs de Horas | Gestão Colaborativa",
    page_icon="⏱️",
    layout="wide",
)

# ============================================================
# CONFIGURAÇÃO
# ============================================================

COLUNAS_BASE = [
    "ID",
    "Cliente",
    "Data",
    "Tipo",
    "Solicitada por",
    "Técnico",
    "Descrição da intervenção",
    "Horas Pack",
    "Horas Usadas",
    "Saldo Automático",
    "Estado",
    "Saldo Original",
    "Origem",
    "Registado por",
    "Data de registo",
]

TIPOS_MOVIMENTO = ["Intervenção", "Compra", "Ajuste"]
NOME_FOLHA = "Base_Lancamentos"

# ============================================================
# ESTILO
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --ci-blue: #1482FF;
        --ci-dark: #061B2B;
        --ci-turquoise: #12E9CA;
        --ci-light: #F5FAFF;
    }
    .block-container {
        padding-top: 1.5rem;
    }
    .ci-title {
        color: var(--ci-dark);
        font-weight: 850;
        letter-spacing: -0.03em;
    }
    .ci-card {
        padding: 1rem 1.2rem;
        border-radius: 18px;
        background: linear-gradient(135deg, #F5FAFF 0%, #FFFFFF 100%);
        border: 1px solid #E3EEF8;
        box-shadow: 0 8px 24px rgba(6, 27, 43, 0.06);
    }
    .status-ok {
        color: #047857;
        font-weight: 800;
    }
    .status-baixo {
        color: #D97706;
        font-weight: 800;
    }
    .status-critico {
        color: #B45309;
        font-weight: 800;
    }
    .status-esgotado {
        color: #B91C1C;
        font-weight: 800;
    }
    div.stButton > button:first-child {
        background-color: #1482FF;
        color: white;
        border-radius: 12px;
        border: none;
        padding: 0.55rem 1rem;
        font-weight: 700;
    }
    div.stDownloadButton > button:first-child {
        background-color: #061B2B;
        color: white;
        border-radius: 12px;
        border: none;
        padding: 0.55rem 1rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)



# ============================================================
# ACESSO À APP
# ============================================================

def obter_app_password():
    """
    Palavra-passe interna da app.
    Deve ser colocada nos Secrets do Streamlit:
    APP_PASSWORD = "a-sua-palavra-passe"
    """
    try:
        return st.secrets.get("APP_PASSWORD", "")
    except Exception:
        return ""


def verificar_acesso():
    if "acesso_autorizado" not in st.session_state:
        st.session_state["acesso_autorizado"] = False

    if st.session_state["acesso_autorizado"]:
        return True

    st.markdown("<h1 class='ci-title'>🔐 Acesso reservado</h1>", unsafe_allow_html=True)
    st.write("Introduza a palavra-passe para aceder à gestão de packs de horas.")

    password_configurada = obter_app_password()

    if not password_configurada:
        st.error(
            "A palavra-passe da app ainda não está configurada. "
            "No Streamlit, vá a Settings > Secrets e adicione APP_PASSWORD."
        )
        st.stop()

    with st.form("form_acesso"):
        password = st.text_input("Palavra-passe", type="password")
        entrar = st.form_submit_button("Entrar")

    if entrar:
        if password == password_configurada:
            st.session_state["acesso_autorizado"] = True
            st.rerun()
        else:
            st.error("Palavra-passe incorreta.")

    st.stop()


verificar_acesso()

# ============================================================
# FUNÇÕES GERAIS
# ============================================================

def converter_data(valor):
    if pd.isna(valor) or valor == "":
        return pd.NaT
    if isinstance(valor, (pd.Timestamp, datetime)):
        return pd.to_datetime(valor)
    if isinstance(valor, date):
        return pd.to_datetime(valor)
    if isinstance(valor, (int, float)):
        return pd.to_datetime("1899-12-30") + pd.to_timedelta(int(valor), unit="D")
    return pd.to_datetime(valor, errors="coerce", dayfirst=True)


def normalizar_base(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if df.empty:
        return pd.DataFrame(columns=COLUNAS_BASE)

    df.columns = [str(c).strip() for c in df.columns]

    for coluna in COLUNAS_BASE:
        if coluna not in df.columns:
            df[coluna] = None

    df = df[COLUNAS_BASE]

    df = df[df["Cliente"].notna()]
    df = df[df["Cliente"].astype(str).str.strip() != ""]

    df["Cliente"] = df["Cliente"].astype(str).str.strip()
    df["Tipo"] = df["Tipo"].fillna("").astype(str).str.strip()
    df["Técnico"] = df["Técnico"].fillna("").astype(str).str.strip()
    df["Descrição da intervenção"] = df["Descrição da intervenção"].fillna("").astype(str).str.strip()
    df["Solicitada por"] = df["Solicitada por"].fillna("").astype(str).str.strip()
    df["Origem"] = df["Origem"].fillna("").astype(str).str.strip()
    df["Registado por"] = df["Registado por"].fillna("").astype(str).str.strip()

    df["Horas Pack"] = pd.to_numeric(df["Horas Pack"], errors="coerce").fillna(0.0)
    df["Horas Usadas"] = pd.to_numeric(df["Horas Usadas"], errors="coerce").fillna(0.0)
    df["Saldo Original"] = pd.to_numeric(df["Saldo Original"], errors="coerce")
    df["Saldo Automático"] = pd.to_numeric(df["Saldo Automático"], errors="coerce")

    df["Data"] = df["Data"].apply(converter_data)
    df["Data de registo"] = pd.to_datetime(df["Data de registo"], errors="coerce", dayfirst=True)

    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    df = df.sort_values(["Cliente", "Data", "ID"], na_position="last").reset_index(drop=True)

    return df


def recalcular_saldos(df: pd.DataFrame) -> pd.DataFrame:
    df = normalizar_base(df)
    if df.empty:
        return df
    df = df.sort_values(["Cliente", "Data", "ID"], na_position="last").reset_index(drop=True)
    df["Saldo Automático"] = (
        df.groupby("Cliente")["Horas Pack"].cumsum()
        - df.groupby("Cliente")["Horas Usadas"].cumsum()
    )
    return df


def calcular_estado(saldo: float, limite_critico: float, limite_baixo: float) -> str:
    if saldo <= 0:
        return "ESGOTADO"
    if saldo <= limite_critico:
        return "SALDO CRÍTICO"
    if saldo <= limite_baixo:
        return "SALDO BAIXO"
    return "OK"


def calcular_acao(saldo: float, limite_critico: float, limite_baixo: float) -> str:
    if saldo <= 0:
        return "Contactar para renovação urgente"
    if saldo <= limite_critico:
        return "Contactar antes de nova intervenção"
    if saldo <= limite_baixo:
        return "Sugerir reforço de pack"
    return "Sem ação imediata"


def calcular_resumo(df: pd.DataFrame, limite_critico: float, limite_baixo: float) -> pd.DataFrame:
    df = recalcular_saldos(df)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "Cliente",
                "Horas compradas",
                "Horas usadas",
                "Saldo",
                "Última intervenção",
                "N.º intervenções",
                "Estado",
                "Próxima ação",
            ]
        )

    resumo = (
        df.groupby("Cliente", as_index=False)
        .agg(
            **{
                "Horas compradas": ("Horas Pack", "sum"),
                "Horas usadas": ("Horas Usadas", "sum"),
                "Última intervenção": ("Data", "max"),
            }
        )
    )

    intervencoes = (
        df[df["Tipo"].str.lower().str.contains("interven", na=False)]
        .groupby("Cliente")
        .size()
        .rename("N.º intervenções")
        .reset_index()
    )

    resumo = resumo.merge(intervencoes, on="Cliente", how="left")
    resumo["N.º intervenções"] = resumo["N.º intervenções"].fillna(0).astype(int)
    resumo["Saldo"] = resumo["Horas compradas"] - resumo["Horas usadas"]
    resumo["Estado"] = resumo["Saldo"].apply(lambda s: calcular_estado(s, limite_critico, limite_baixo))
    resumo["Próxima ação"] = resumo["Saldo"].apply(lambda s: calcular_acao(s, limite_critico, limite_baixo))

    ordem = {"ESGOTADO": 0, "SALDO CRÍTICO": 1, "SALDO BAIXO": 2, "OK": 3}
    resumo["ordem"] = resumo["Estado"].map(ordem).fillna(9)
    resumo = resumo.sort_values(["ordem", "Saldo", "Cliente"]).drop(columns=["ordem"]).reset_index(drop=True)

    return resumo


def formatar_estado(estado: str):
    if estado == "OK":
        return "status-ok"
    if estado == "SALDO BAIXO":
        return "status-baixo"
    if estado == "SALDO CRÍTICO":
        return "status-critico"
    if estado == "ESGOTADO":
        return "status-esgotado"
    return ""


def dataframe_para_linhas_google(df: pd.DataFrame):
    df = df.copy()
    for col in ["Data", "Data de registo"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y")
            df[col] = df[col].replace("NaT", "")
    df = df.fillna("")
    return [COLUNAS_BASE] + df[COLUNAS_BASE].astype(str).values.tolist()


def exportar_excel(df_lancamentos: pd.DataFrame, df_resumo: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="dd/mm/yyyy", date_format="dd/mm/yyyy") as writer:
        df_resumo.to_excel(writer, sheet_name="Dashboard", index=False)
        df_lancamentos.to_excel(writer, sheet_name="Base_Lancamentos", index=False)

        workbook = writer.book
        header_fmt = workbook.add_format(
            {
                "bold": True,
                "font_color": "white",
                "bg_color": "#061B2B",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )
        number_fmt = workbook.add_format({"num_format": "0.00"})
        date_fmt = workbook.add_format({"num_format": "dd/mm/yyyy"})

        for sheet_name, df_sheet in {"Dashboard": df_resumo, "Base_Lancamentos": df_lancamentos}.items():
            ws = writer.sheets[sheet_name]
            for col_num, value in enumerate(df_sheet.columns):
                ws.write(0, col_num, value, header_fmt)
                largura = min(max(len(str(value)) + 3, 12), 38)
                ws.set_column(col_num, col_num, largura)
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, max(len(df_sheet), 1), max(len(df_sheet.columns) - 1, 0))

        dash = writer.sheets["Dashboard"]
        colunas_dash = list(df_resumo.columns)
        for nome_coluna in ["Horas compradas", "Horas usadas", "Saldo"]:
            if nome_coluna in colunas_dash:
                idx = colunas_dash.index(nome_coluna)
                dash.set_column(idx, idx, 16, number_fmt)
        if "Última intervenção" in colunas_dash:
            idx = colunas_dash.index("Última intervenção")
            dash.set_column(idx, idx, 18, date_fmt)

        base = writer.sheets["Base_Lancamentos"]
        colunas_base = list(df_lancamentos.columns)
        for nome_coluna in ["Horas Pack", "Horas Usadas", "Saldo Automático", "Saldo Original"]:
            if nome_coluna in colunas_base:
                idx = colunas_base.index(nome_coluna)
                base.set_column(idx, idx, 15, number_fmt)
        for nome_coluna in ["Data", "Data de registo"]:
            if nome_coluna in colunas_base:
                idx = colunas_base.index(nome_coluna)
                base.set_column(idx, idx, 15, date_fmt)

    output.seek(0)
    return output.getvalue()


@st.cache_data(show_spinner=False)
def carregar_excel_demo():
    ficheiro = Path(__file__).with_name("PACKS_DE_HORAS_AUTOMATIZADO.xlsx")
    if not ficheiro.exists():
        return pd.DataFrame(columns=COLUNAS_BASE)
    try:
        # O ficheiro automatizado anterior tem o cabeçalho na linha 4.
        df = pd.read_excel(ficheiro, sheet_name="Base_Lancamentos", header=3)
    except Exception:
        try:
            df = pd.read_excel(ficheiro, sheet_name="Base_Lancamentos")
        except Exception:
            return pd.DataFrame(columns=COLUNAS_BASE)
    return normalizar_base(df)


# ============================================================
# GOOGLE SHEETS
# ============================================================

def obter_secrets():
    try:
        return st.secrets
    except Exception:
        return {}


def google_configurado():
    secrets = obter_secrets()
    try:
        tem_sheet = bool(secrets.get("GOOGLE_SHEET_ID", ""))
        tem_conta = "gcp_service_account" in secrets
        return bool(tem_sheet and tem_conta and gspread is not None and Credentials is not None)
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def obter_worksheet_google():
    secrets = obter_secrets()
    sheet_id = secrets.get("GOOGLE_SHEET_ID", "")

    service_account_info = dict(secrets["gcp_service_account"])

    # Evita erro quando a private_key é colada com \n no Streamlit.
    if "private_key" in service_account_info:
        service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(sheet_id)

    try:
        worksheet = spreadsheet.worksheet(NOME_FOLHA)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=NOME_FOLHA, rows=1000, cols=len(COLUNAS_BASE) + 5)
        worksheet.update("A1", [COLUNAS_BASE])

    valores = worksheet.get_all_values()
    if not valores:
        worksheet.update("A1", [COLUNAS_BASE])
    elif valores[0] != COLUNAS_BASE:
        # Garante que a folha tem todas as colunas necessárias sem apagar dados existentes.
        cabecalhos = valores[0]
        novas_colunas = [c for c in COLUNAS_BASE if c not in cabecalhos]
        if novas_colunas:
            novo_cabecalho = cabecalhos + novas_colunas
            worksheet.update("A1", [novo_cabecalho])

    return worksheet


def ler_google_sheets() -> pd.DataFrame:
    worksheet = obter_worksheet_google()
    valores = worksheet.get_all_values()

    if not valores or len(valores) <= 1:
        return pd.DataFrame(columns=COLUNAS_BASE)

    cabecalhos = valores[0]
    linhas = valores[1:]
    df = pd.DataFrame(linhas, columns=cabecalhos)

    return normalizar_base(df)


def gravar_dataframe_google(df: pd.DataFrame):
    worksheet = obter_worksheet_google()
    df = recalcular_saldos(df)
    linhas = dataframe_para_linhas_google(df)
    worksheet.clear()
    worksheet.update("A1", linhas)


def adicionar_lancamento_google(lancamento: dict):
    worksheet = obter_worksheet_google()
    linha = []
    for coluna in COLUNAS_BASE:
        valor = lancamento.get(coluna, "")
        if isinstance(valor, (pd.Timestamp, datetime)):
            valor = valor.strftime("%d/%m/%Y")
        elif isinstance(valor, date):
            valor = valor.strftime("%d/%m/%Y")
        elif pd.isna(valor):
            valor = ""
        linha.append(str(valor))
    worksheet.append_row(linha, value_input_option="USER_ENTERED")


# ============================================================
# INTERFACE
# ============================================================

st.markdown("<h1 class='ci-title'>⏱️ Gestão Colaborativa de Packs de Horas</h1>", unsafe_allow_html=True)
st.caption("Aplicação para colaboradores registarem clientes, compras de packs, intervenções e horas utilizadas.")

with st.sidebar:
    st.header("⚙️ Configuração")

    if st.button("Terminar sessão"):
        st.session_state["acesso_autorizado"] = False
        st.rerun()

    modo_google = google_configurado()

    if modo_google:
        st.success("Modo colaborativo ativo: Google Sheets")
    else:
        st.warning("Modo demonstração: os dados não ficam gravados permanentemente.")
        st.caption("Para colaboração real, configure o Google Sheets nos Secrets do Streamlit.")

    colaborador = st.text_input("Nome do colaborador", placeholder="Ex.: Ana, Miguel, Cátia")

    limite_critico = st.number_input("Limite saldo crítico", min_value=0.0, value=1.0, step=0.5)
    limite_baixo = st.number_input("Limite saldo baixo", min_value=0.0, value=2.0, step=0.5)

    st.divider()

    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# Carregar dados
if modo_google:
    try:
        df_base = ler_google_sheets()
    except Exception as e:
        st.error("Não foi possível ligar ao Google Sheets. Confirme os Secrets e se a folha foi partilhada com o e-mail da service account.")
        st.exception(e)
        st.stop()
else:
    if "df_demo" not in st.session_state:
        st.session_state["df_demo"] = carregar_excel_demo()
    df_base = st.session_state["df_demo"]

df_base = recalcular_saldos(df_base)
df_resumo = calcular_resumo(df_base, limite_critico, limite_baixo)

# Métricas
total_clientes = int(df_resumo["Cliente"].nunique()) if not df_resumo.empty else 0
horas_compradas = float(df_resumo["Horas compradas"].sum()) if not df_resumo.empty else 0
horas_usadas = float(df_resumo["Horas usadas"].sum()) if not df_resumo.empty else 0
saldo_total = float(df_resumo["Saldo"].sum()) if not df_resumo.empty else 0
alertas = int((df_resumo["Estado"] != "OK").sum()) if not df_resumo.empty else 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Clientes", f"{total_clientes}")
col2.metric("Horas compradas", f"{horas_compradas:.1f} h")
col3.metric("Horas usadas", f"{horas_usadas:.1f} h")
col4.metric("Saldo total", f"{saldo_total:.1f} h")
col5.metric("Alertas", f"{alertas}")

st.divider()

aba_dashboard, aba_cliente, aba_registar, aba_editar, aba_importar, aba_exportar = st.tabs(
    ["📊 Dashboard", "👤 Cliente", "➕ Registar movimento", "✏️ Gestão rápida", "📥 Importar", "⬇️ Exportar"]
)

# ============================================================
# DASHBOARD
# ============================================================

with aba_dashboard:
    st.subheader("Resumo por cliente")

    c1, c2, c3 = st.columns([1.2, 1.5, 2])
    with c1:
        estados = ["Todos"] + sorted(df_resumo["Estado"].dropna().unique().tolist())
        estado_sel = st.selectbox("Filtrar por estado", estados)
    with c2:
        clientes = ["Todos"] + sorted(df_resumo["Cliente"].dropna().unique().tolist())
        cliente_sel = st.selectbox("Filtrar por cliente", clientes)
    with c3:
        pesquisa = st.text_input("Pesquisar cliente")

    df_filtrado = df_resumo.copy()
    if estado_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Estado"] == estado_sel]
    if cliente_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Cliente"] == cliente_sel]
    if pesquisa:
        df_filtrado = df_filtrado[df_filtrado["Cliente"].str.contains(pesquisa, case=False, na=False)]

    st.dataframe(
        df_filtrado,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Saldo": st.column_config.NumberColumn("Saldo", format="%.2f h"),
            "Horas compradas": st.column_config.NumberColumn("Horas compradas", format="%.2f h"),
            "Horas usadas": st.column_config.NumberColumn("Horas usadas", format="%.2f h"),
            "Última intervenção": st.column_config.DateColumn("Última intervenção", format="DD/MM/YYYY"),
        },
    )

    st.subheader("Clientes com saldo mais baixo")
    if not df_resumo.empty:
        grafico = df_resumo.sort_values("Saldo").head(15).set_index("Cliente")[["Saldo"]]
        st.bar_chart(grafico)
    else:
        st.info("Ainda não existem movimentos registados.")

# ============================================================
# CLIENTE
# ============================================================

with aba_cliente:
    st.subheader("Ficha individual de cliente")

    lista_clientes = sorted(df_base["Cliente"].dropna().unique().tolist())
    if not lista_clientes:
        st.info("Ainda não existem clientes. Adicione o primeiro movimento no separador Registar movimento.")
    else:
        cliente_detalhe = st.selectbox("Selecionar cliente", lista_clientes, key="cliente_detalhe")

        dados_cliente = df_base[df_base["Cliente"] == cliente_detalhe].copy()
        resumo_cliente = df_resumo[df_resumo["Cliente"] == cliente_detalhe].iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Horas compradas", f"{resumo_cliente['Horas compradas']:.1f} h")
        c2.metric("Horas usadas", f"{resumo_cliente['Horas usadas']:.1f} h")
        c3.metric("Saldo", f"{resumo_cliente['Saldo']:.1f} h")
        c4.markdown(
            f"<div class='ci-card'>Estado<br><span class='{formatar_estado(resumo_cliente['Estado'])}'>{resumo_cliente['Estado']}</span></div>",
            unsafe_allow_html=True,
        )

        st.write("Histórico de movimentos")
        st.dataframe(
            dados_cliente[
                [
                    "ID",
                    "Data",
                    "Tipo",
                    "Solicitada por",
                    "Técnico",
                    "Descrição da intervenção",
                    "Horas Pack",
                    "Horas Usadas",
                    "Saldo Automático",
                    "Registado por",
                    "Data de registo",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Data de registo": st.column_config.DatetimeColumn("Data de registo", format="DD/MM/YYYY HH:mm"),
                "Horas Pack": st.column_config.NumberColumn("Horas Pack", format="%.2f h"),
                "Horas Usadas": st.column_config.NumberColumn("Horas Usadas", format="%.2f h"),
                "Saldo Automático": st.column_config.NumberColumn("Saldo Automático", format="%.2f h"),
            },
        )

# ============================================================
# REGISTAR MOVIMENTO
# ============================================================

with aba_registar:
    st.subheader("Adicionar cliente, compra de pack ou horas utilizadas")

    if not colaborador.strip():
        st.warning("Indique o nome do colaborador na barra lateral antes de registar movimentos.")

    clientes_existentes = sorted(df_base["Cliente"].dropna().unique().tolist())
    tecnicos_existentes = sorted([x for x in df_base["Técnico"].dropna().unique().tolist() if x])

    with st.form("form_novo_movimento", clear_on_submit=True):
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            cliente_base = st.selectbox("Cliente", ["Novo cliente"] + clientes_existentes)
            novo_cliente = ""
            if cliente_base == "Novo cliente":
                novo_cliente = st.text_input("Nome do novo cliente")

        with col_b:
            data_movimento = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")

        with col_c:
            tipo = st.selectbox("Tipo de movimento", TIPOS_MOVIMENTO)

        col_d, col_e = st.columns(2)
        with col_d:
            solicitada_por = st.text_input("Solicitada por / contacto")
        with col_e:
            tecnico_sel = st.selectbox("Técnico", [""] + tecnicos_existentes + ["Outro"])
            tecnico = tecnico_sel
            if tecnico_sel == "Outro":
                tecnico = st.text_input("Indique o técnico")

        descricao = st.text_area("Descrição")

        st.caption("Para compra de pack, preencher Horas Pack. Para intervenção, preencher Horas Usadas.")
        col_f, col_g = st.columns(2)

        with col_f:
            horas_pack = st.number_input("Horas Pack compradas", min_value=0.0, value=0.0, step=0.25)

        with col_g:
            horas_usadas = st.number_input("Horas utilizadas", min_value=0.0, value=0.0, step=0.25)

        confirmar = st.checkbox("Confirmo que os dados estão corretos")
        submitted = st.form_submit_button("Guardar movimento")

        if submitted:
            cliente_final = novo_cliente.strip() if cliente_base == "Novo cliente" else cliente_base
            colaborador_final = colaborador.strip()

            if not colaborador_final:
                st.error("Indique o nome do colaborador na barra lateral.")
            elif not cliente_final:
                st.error("Indique o nome do cliente.")
            elif horas_pack == 0 and horas_usadas == 0:
                st.error("Indique horas compradas ou horas utilizadas.")
            elif not confirmar:
                st.error("Confirme os dados antes de guardar.")
            else:
                max_id = pd.to_numeric(df_base["ID"], errors="coerce").max()
                if pd.isna(max_id):
                    max_id = 0

                lancamento = {
                    "ID": int(max_id) + 1,
                    "Cliente": cliente_final,
                    "Data": pd.to_datetime(data_movimento),
                    "Tipo": tipo,
                    "Solicitada por": solicitada_por,
                    "Técnico": tecnico,
                    "Descrição da intervenção": descricao,
                    "Horas Pack": float(horas_pack),
                    "Horas Usadas": float(horas_usadas),
                    "Saldo Automático": "",
                    "Estado": "",
                    "Saldo Original": "",
                    "Origem": "App colaborativa",
                    "Registado por": colaborador_final,
                    "Data de registo": datetime.now(),
                }

                if modo_google:
                    adicionar_lancamento_google(lancamento)
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    st.success("Movimento guardado no Google Sheets. Todos os colaboradores passam a ver esta atualização.")
                    st.rerun()
                else:
                    st.session_state["df_demo"] = pd.concat([df_base, pd.DataFrame([lancamento])], ignore_index=True)
                    st.success("Movimento guardado apenas nesta sessão de demonstração.")
                    st.rerun()

# ============================================================
# GESTÃO RÁPIDA
# ============================================================

with aba_editar:
    st.subheader("Gestão rápida")

    st.info(
        "Para segurança, esta área permite remover o último movimento por ID. "
        "Alterações completas linha a linha podem ser feitas diretamente no Google Sheets."
    )

    if df_base.empty:
        st.write("Não existem movimentos.")
    else:
        ultimos = df_base.sort_values("ID", ascending=False).head(20)
        st.write("Últimos movimentos registados")
        st.dataframe(
            ultimos[
                [
                    "ID",
                    "Cliente",
                    "Data",
                    "Tipo",
                    "Técnico",
                    "Descrição da intervenção",
                    "Horas Pack",
                    "Horas Usadas",
                    "Registado por",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        id_remover = st.number_input("ID do movimento a remover", min_value=0, value=0, step=1)
        confirmar_remocao = st.checkbox("Confirmo que pretendo remover este movimento")

        if st.button("Remover movimento"):
            if not confirmar_remocao:
                st.error("Confirme a remoção antes de continuar.")
            elif id_remover == 0:
                st.error("Indique um ID válido.")
            elif id_remover not in pd.to_numeric(df_base["ID"], errors="coerce").dropna().astype(int).tolist():
                st.error("ID não encontrado.")
            else:
                novo_df = df_base[pd.to_numeric(df_base["ID"], errors="coerce").astype("Int64") != int(id_remover)]
                if modo_google:
                    gravar_dataframe_google(novo_df)
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    st.success("Movimento removido no Google Sheets.")
                    st.rerun()
                else:
                    st.session_state["df_demo"] = novo_df
                    st.success("Movimento removido na sessão de demonstração.")
                    st.rerun()

# ============================================================
# IMPORTAR
# ============================================================

with aba_importar:
    st.subheader("Importar dados iniciais para Google Sheets")

    st.write(
        "Use esta opção apenas uma vez, quando quiser passar os dados do Excel para a base colaborativa."
    )

    if not modo_google:
        st.warning("Para importar para Google Sheets, configure primeiro os Secrets no Streamlit.")
    else:
        dados_demo = carregar_excel_demo()
        st.write(f"Movimentos encontrados no Excel incluído: **{len(dados_demo)}**")

        if st.checkbox("Confirmo que quero substituir os dados atuais do Google Sheets"):
            if st.button("Importar Excel para Google Sheets"):
                gravar_dataframe_google(dados_demo)
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("Dados importados para Google Sheets.")
                st.rerun()

# ============================================================
# EXPORTAR
# ============================================================

with aba_exportar:
    st.subheader("Exportar Excel atualizado")

    ficheiro_final = exportar_excel(df_base, df_resumo)

    st.download_button(
        label="Descarregar Excel atualizado",
        data=ficheiro_final,
        file_name="PACKS_DE_HORAS_COLABORATIVO_ATUALIZADO.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.write("Pré-visualização dos dados que serão exportados:")
    st.dataframe(df_resumo, use_container_width=True, hide_index=True)
