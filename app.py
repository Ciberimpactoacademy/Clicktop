
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, date
from io import BytesIO

st.set_page_config(
    page_title="Controlo de Packs de Horas",
    page_icon="⏱️",
    layout="wide",
)

# -----------------------------
# Estilo visual
# -----------------------------
st.markdown(
    """
    <style>
    :root {
        --ci-blue: #1482FF;
        --ci-dark: #061B2B;
        --ci-turquoise: #12E9CA;
        --ci-light: #F5FAFF;
    }
    .main {
        background-color: #FFFFFF;
    }
    .block-container {
        padding-top: 1.8rem;
    }
    .ci-card {
        padding: 1rem 1.2rem;
        border-radius: 18px;
        background: linear-gradient(135deg, #F5FAFF 0%, #FFFFFF 100%);
        border: 1px solid #E3EEF8;
        box-shadow: 0 8px 24px rgba(6, 27, 43, 0.06);
    }
    .ci-title {
        color: var(--ci-dark);
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    .status-ok {
        color: #047857;
        font-weight: 700;
    }
    .status-baixo {
        color: #D97706;
        font-weight: 700;
    }
    .status-critico {
        color: #B45309;
        font-weight: 700;
    }
    .status-esgotado {
        color: #B91C1C;
        font-weight: 700;
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

# -----------------------------
# Funções auxiliares
# -----------------------------
def converter_data(valor):
    """Converte datas do Excel, datas pandas e texto para datetime."""
    if pd.isna(valor):
        return pd.NaT
    if isinstance(valor, (pd.Timestamp, datetime)):
        return pd.to_datetime(valor)
    if isinstance(valor, date):
        return pd.to_datetime(valor)
    if isinstance(valor, (int, float)):
        # Sistema de datas Excel: 1899-12-30
        return pd.to_datetime("1899-12-30") + pd.to_timedelta(int(valor), unit="D")
    return pd.to_datetime(valor, errors="coerce", dayfirst=True)


def normalizar_base(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    colunas_esperadas = [
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
    ]

    # Garante que colunas essenciais existem mesmo que o Excel venha incompleto.
    for coluna in colunas_esperadas:
        if coluna not in df.columns:
            df[coluna] = None

    df = df[colunas_esperadas]
    df = df[df["Cliente"].notna()]
    df = df[df["Cliente"].astype(str).str.strip() != ""]

    df["Cliente"] = df["Cliente"].astype(str).str.strip()
    df["Tipo"] = df["Tipo"].fillna("").astype(str).str.strip()
    df["Técnico"] = df["Técnico"].fillna("").astype(str).str.strip()
    df["Descrição da intervenção"] = df["Descrição da intervenção"].fillna("").astype(str).str.strip()
    df["Solicitada por"] = df["Solicitada por"].fillna("").astype(str).str.strip()
    df["Origem"] = df["Origem"].fillna("").astype(str).str.strip()

    df["Horas Pack"] = pd.to_numeric(df["Horas Pack"], errors="coerce").fillna(0.0)
    df["Horas Usadas"] = pd.to_numeric(df["Horas Usadas"], errors="coerce").fillna(0.0)
    df["Saldo Original"] = pd.to_numeric(df["Saldo Original"], errors="coerce")
    df["Data"] = df["Data"].apply(converter_data)

    df = df.sort_values(["Cliente", "Data", "ID"], na_position="last").reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False)
def carregar_excel(ficheiro):
    return pd.read_excel(ficheiro, sheet_name="Base_Lancamentos", header=3)


def calcular_resumo(df: pd.DataFrame, limite_critico: float, limite_baixo: float) -> pd.DataFrame:
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

    def estado(saldo):
        if saldo <= 0:
            return "ESGOTADO"
        if saldo <= limite_critico:
            return "SALDO CRÍTICO"
        if saldo <= limite_baixo:
            return "SALDO BAIXO"
        return "OK"

    def acao(saldo):
        if saldo <= 0:
            return "Contactar para renovação urgente"
        if saldo <= limite_critico:
            return "Contactar antes de nova intervenção"
        if saldo <= limite_baixo:
            return "Sugerir reforço de pack"
        return "Sem ação imediata"

    resumo["Estado"] = resumo["Saldo"].apply(estado)
    resumo["Próxima ação"] = resumo["Saldo"].apply(acao)
    resumo = resumo.sort_values(["Estado", "Saldo", "Cliente"]).reset_index(drop=True)
    return resumo


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
        ok_fmt = workbook.add_format({"bg_color": "#DCFCE7", "font_color": "#166534"})
        baixo_fmt = workbook.add_format({"bg_color": "#FEF3C7", "font_color": "#92400E"})
        critico_fmt = workbook.add_format({"bg_color": "#FFEDD5", "font_color": "#9A3412"})
        esgotado_fmt = workbook.add_format({"bg_color": "#FEE2E2", "font_color": "#991B1B"})

        for sheet_name, df_sheet in {"Dashboard": df_resumo, "Base_Lancamentos": df_lancamentos}.items():
            ws = writer.sheets[sheet_name]
            for col_num, value in enumerate(df_sheet.columns):
                ws.write(0, col_num, value, header_fmt)
                largura = min(max(len(str(value)) + 3, 12), 36)
                ws.set_column(col_num, col_num, largura)
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, max(len(df_sheet), 1), max(len(df_sheet.columns) - 1, 0))

        # Formatos específicos Dashboard
        if not df_resumo.empty:
            dash = writer.sheets["Dashboard"]
            colunas_dash = list(df_resumo.columns)
            for nome_coluna in ["Horas compradas", "Horas usadas", "Saldo"]:
                if nome_coluna in colunas_dash:
                    idx = colunas_dash.index(nome_coluna)
                    dash.set_column(idx, idx, 16, number_fmt)
            if "Última intervenção" in colunas_dash:
                idx = colunas_dash.index("Última intervenção")
                dash.set_column(idx, idx, 18, date_fmt)
            if "Estado" in colunas_dash:
                idx = colunas_dash.index("Estado")
                letra = chr(ord("A") + idx)
                ultima_linha = len(df_resumo) + 1
                dash.conditional_format(f"{letra}2:{letra}{ultima_linha}", {"type": "text", "criteria": "containing", "value": "OK", "format": ok_fmt})
                dash.conditional_format(f"{letra}2:{letra}{ultima_linha}", {"type": "text", "criteria": "containing", "value": "SALDO BAIXO", "format": baixo_fmt})
                dash.conditional_format(f"{letra}2:{letra}{ultima_linha}", {"type": "text", "criteria": "containing", "value": "SALDO CRÍTICO", "format": critico_fmt})
                dash.conditional_format(f"{letra}2:{letra}{ultima_linha}", {"type": "text", "criteria": "containing", "value": "ESGOTADO", "format": esgotado_fmt})

        # Formatos Base_Lancamentos
        base = writer.sheets["Base_Lancamentos"]
        colunas_base = list(df_lancamentos.columns)
        for nome_coluna in ["Horas Pack", "Horas Usadas", "Saldo Automático", "Saldo Original"]:
            if nome_coluna in colunas_base:
                idx = colunas_base.index(nome_coluna)
                base.set_column(idx, idx, 15, number_fmt)
        if "Data" in colunas_base:
            idx = colunas_base.index("Data")
            base.set_column(idx, idx, 14, date_fmt)

    output.seek(0)
    return output.getvalue()


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


# -----------------------------
# Carregamento de dados
# -----------------------------
default_file = Path(__file__).with_name("PACKS_DE_HORAS_AUTOMATIZADO.xlsx")

st.markdown("<h1 class='ci-title'>⏱️ Controlo de Packs de Horas</h1>", unsafe_allow_html=True)
st.caption("App interna para acompanhar horas compradas, horas utilizadas, saldos e alertas por cliente.")

with st.sidebar:
    st.header("⚙️ Configuração")

    ficheiro_upload = st.file_uploader(
        "Carregar Excel dos packs de horas",
        type=["xlsx"],
        help="Pode usar o ficheiro automatizado ou outro com a folha Base_Lancamentos.",
    )

    limite_critico = st.number_input("Limite saldo crítico", min_value=0.0, value=1.0, step=0.5)
    limite_baixo = st.number_input("Limite saldo baixo", min_value=0.0, value=2.0, step=0.5)

    st.divider()
    st.caption("Dica: atualize o Excel exportado no final de cada dia para manter o histórico.")

try:
    ficheiro_origem = ficheiro_upload if ficheiro_upload is not None else default_file
    df_original = normalizar_base(carregar_excel(ficheiro_origem))
except Exception as e:
    st.error("Não foi possível carregar o ficheiro. Confirme se existe a folha 'Base_Lancamentos' com o cabeçalho na linha 4.")
    st.exception(e)
    st.stop()

if "novos_lancamentos" not in st.session_state:
    st.session_state["novos_lancamentos"] = []

df_novos = pd.DataFrame(st.session_state["novos_lancamentos"])
if not df_novos.empty:
    df_novos = normalizar_base(df_novos)
    df_base = pd.concat([df_original, df_novos], ignore_index=True)
else:
    df_base = df_original.copy()

df_base = df_base.sort_values(["Cliente", "Data", "ID"], na_position="last").reset_index(drop=True)

# Recalcula saldo acumulado por cliente
df_base["Saldo Automático"] = df_base.groupby("Cliente")["Horas Pack"].cumsum() - df_base.groupby("Cliente")["Horas Usadas"].cumsum()

df_resumo = calcular_resumo(df_base, limite_critico, limite_baixo)

# -----------------------------
# Dashboard
# -----------------------------
total_clientes = df_resumo["Cliente"].nunique()
horas_compradas = df_resumo["Horas compradas"].sum()
horas_usadas = df_resumo["Horas usadas"].sum()
saldo_total = df_resumo["Saldo"].sum()
alertas = int((df_resumo["Estado"] != "OK").sum())

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Clientes", f"{total_clientes}")
col2.metric("Horas compradas", f"{horas_compradas:.1f} h")
col3.metric("Horas usadas", f"{horas_usadas:.1f} h")
col4.metric("Saldo total", f"{saldo_total:.1f} h")
col5.metric("Alertas", f"{alertas}")

st.divider()

aba_dashboard, aba_cliente, aba_lancamento, aba_exportar = st.tabs(
    ["📊 Dashboard", "👤 Cliente", "➕ Novo lançamento", "⬇️ Exportar"]
)

with aba_dashboard:
    st.subheader("Resumo por cliente")

    c1, c2, c3 = st.columns([1.5, 1.5, 2])
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
    grafico = df_resumo.sort_values("Saldo").head(15).set_index("Cliente")[["Saldo"]]
    st.bar_chart(grafico)

with aba_cliente:
    st.subheader("Ficha do cliente")

    cliente_detalhe = st.selectbox(
        "Selecionar cliente",
        sorted(df_base["Cliente"].dropna().unique().tolist()),
        key="cliente_detalhe",
    )

    dados_cliente = df_base[df_base["Cliente"] == cliente_detalhe].copy()
    resumo_cliente = df_resumo[df_resumo["Cliente"] == cliente_detalhe].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Compradas", f"{resumo_cliente['Horas compradas']:.1f} h")
    c2.metric("Usadas", f"{resumo_cliente['Horas usadas']:.1f} h")
    c3.metric("Saldo", f"{resumo_cliente['Saldo']:.1f} h")
    c4.markdown(
        f"<div class='ci-card'>Estado<br><span class='{formatar_estado(resumo_cliente['Estado'])}'>{resumo_cliente['Estado']}</span></div>",
        unsafe_allow_html=True,
    )

    st.write("Histórico de movimentos")
    st.dataframe(
        dados_cliente[
            [
                "Data",
                "Tipo",
                "Solicitada por",
                "Técnico",
                "Descrição da intervenção",
                "Horas Pack",
                "Horas Usadas",
                "Saldo Automático",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Horas Pack": st.column_config.NumberColumn("Horas Pack", format="%.2f h"),
            "Horas Usadas": st.column_config.NumberColumn("Horas Usadas", format="%.2f h"),
            "Saldo Automático": st.column_config.NumberColumn("Saldo Automático", format="%.2f h"),
        },
    )

with aba_lancamento:
    st.subheader("Adicionar novo movimento")

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
            tipo = st.selectbox("Tipo", ["Intervenção", "Compra", "Ajuste"])

        col_d, col_e = st.columns(2)
        with col_d:
            solicitada_por = st.text_input("Solicitada por")
        with col_e:
            tecnico = st.selectbox("Técnico", [""] + tecnicos_existentes + ["Outro"])
            if tecnico == "Outro":
                tecnico = st.text_input("Indique o técnico")

        descricao = st.text_area("Descrição da intervenção / movimento")

        col_f, col_g = st.columns(2)
        with col_f:
            horas_pack = st.number_input("Horas Pack", min_value=0.0, value=0.0, step=0.25)
        with col_g:
            horas_usadas = st.number_input("Horas Usadas", min_value=0.0, value=0.0, step=0.25)

        submitted = st.form_submit_button("Adicionar lançamento")

        if submitted:
            cliente_final = novo_cliente.strip() if cliente_base == "Novo cliente" else cliente_base
            if not cliente_final:
                st.error("Indique o nome do cliente.")
            elif horas_pack == 0 and horas_usadas == 0:
                st.error("Indique horas compradas ou horas usadas.")
            else:
                proximo_id = int(pd.to_numeric(df_base["ID"], errors="coerce").max() or 0) + len(st.session_state["novos_lancamentos"]) + 1
                st.session_state["novos_lancamentos"].append(
                    {
                        "ID": proximo_id,
                        "Cliente": cliente_final,
                        "Data": pd.to_datetime(data_movimento),
                        "Tipo": tipo,
                        "Solicitada por": solicitada_por,
                        "Técnico": tecnico,
                        "Descrição da intervenção": descricao,
                        "Horas Pack": horas_pack,
                        "Horas Usadas": horas_usadas,
                        "Saldo Automático": None,
                        "Estado": "",
                        "Saldo Original": None,
                        "Origem": "App",
                    }
                )
                st.success("Lançamento adicionado à sessão. Use a aba Exportar para descarregar o Excel atualizado.")
                st.rerun()

    if st.session_state["novos_lancamentos"]:
        st.info(f"Existem {len(st.session_state['novos_lancamentos'])} lançamento(s) novo(s) ainda não gravado(s) no ficheiro original.")
        if st.button("Limpar lançamentos desta sessão"):
            st.session_state["novos_lancamentos"] = []
            st.rerun()

with aba_exportar:
    st.subheader("Exportar dados atualizados")

    ficheiro_final = exportar_excel(df_base, df_resumo)

    st.download_button(
        label="Descarregar Excel atualizado",
        data=ficheiro_final,
        file_name="PACKS_DE_HORAS_APP_ATUALIZADO.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.write("Pré-visualização dos dados que serão exportados:")
    st.dataframe(df_resumo, use_container_width=True, hide_index=True)
