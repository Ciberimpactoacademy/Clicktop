import streamlit as st
import pandas as pd
import requests
from pathlib import Path
from datetime import datetime, date
from io import BytesIO

st.set_page_config(page_title="Packs de Horas", page_icon="⏱️", layout="wide")

COLS = [
    "ID","Cliente","Data","Tipo","Solicitada por","Técnico",
    "Descrição da intervenção","Horas Pack","Horas Usadas",
    "Saldo Automático","Estado","Saldo Original","Origem",
    "Registado por","Data de registo"
]
TECNICOS = ["Clicktop", "Ivan Lopes", "Luis Lopes", "Miguel Carvalho", "Rodrigo Cândido"]
TIPOS = ["Intervenção", "Compra", "Ajuste", "Cliente criado"]

st.markdown("""
<style>
.block-container{padding-top:1.4rem}
h1{color:#061B2B}
div.stButton>button:first-child{background:#1482FF;color:white;border-radius:12px;border:0;font-weight:700}
div.stDownloadButton>button:first-child{background:#061B2B;color:white;border-radius:12px;border:0;font-weight:700}
</style>
""", unsafe_allow_html=True)

def secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

def login():
    if "ok_login" not in st.session_state:
        st.session_state.ok_login = False
    if st.session_state.ok_login:
        return

    st.title("🔐 Acesso reservado")
    with st.form("login"):
        pw = st.text_input("Palavra-passe", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        if pw == secret("APP_PASSWORD", "Click123"):
            st.session_state.ok_login = True
            st.rerun()
        else:
            st.error("Palavra-passe incorreta.")
    st.stop()

login()

def data_pt(v):
    if pd.isna(v) or v == "":
        return pd.NaT
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return pd.to_datetime(v)
    if isinstance(v, (int, float)):
        return pd.to_datetime("1899-12-30") + pd.to_timedelta(int(v), unit="D")
    return pd.to_datetime(v, errors="coerce", dayfirst=True)

def norm(df):
    df = df.copy()
    if df.empty:
        return pd.DataFrame(columns=COLS)
    df.columns = [str(c).strip() for c in df.columns]
    for c in COLS:
        if c not in df.columns:
            df[c] = None
    df = df[COLS]
    df = df[df["Cliente"].notna()]
    df = df[df["Cliente"].astype(str).str.strip() != ""]
    for c in ["Cliente","Tipo","Solicitada por","Técnico","Descrição da intervenção","Origem","Registado por"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    for c in ["Horas Pack","Horas Usadas","Saldo Automático","Saldo Original"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    df["Data"] = df["Data"].apply(data_pt)
    df["Data de registo"] = pd.to_datetime(df["Data de registo"], errors="coerce", dayfirst=True)
    return df.sort_values(["Cliente","Data","ID"], na_position="last").reset_index(drop=True)

def saldos(df):
    df = norm(df)
    if df.empty:
        return df
    df = df.sort_values(["Cliente","Data","ID"], na_position="last").reset_index(drop=True)
    df["Saldo Automático"] = df.groupby("Cliente")["Horas Pack"].cumsum() - df.groupby("Cliente")["Horas Usadas"].cumsum()
    return df

def resumo(df, critico, baixo):
    df = saldos(df)
    if df.empty:
        return pd.DataFrame(columns=["Cliente","Horas compradas","Horas usadas","Saldo","Última intervenção","N.º intervenções","Estado","Próxima ação"])
    r = df.groupby("Cliente", as_index=False).agg(
        **{"Horas compradas":("Horas Pack","sum"), "Horas usadas":("Horas Usadas","sum"), "Última intervenção":("Data","max")}
    )
    n = df[df["Tipo"].str.lower().str.contains("interven", na=False)].groupby("Cliente").size().rename("N.º intervenções").reset_index()
    r = r.merge(n, on="Cliente", how="left")
    r["N.º intervenções"] = r["N.º intervenções"].fillna(0).astype(int)
    r["Saldo"] = r["Horas compradas"] - r["Horas usadas"]

    def estado(s):
        if s <= 0: return "ESGOTADO"
        if s <= critico: return "SALDO CRÍTICO"
        if s <= baixo: return "SALDO BAIXO"
        return "OK"

    def acao(s):
        if s <= 0: return "Contactar para renovação urgente"
        if s <= critico: return "Contactar antes de nova intervenção"
        if s <= baixo: return "Sugerir reforço de pack"
        return "Sem ação imediata"

    r["Estado"] = r["Saldo"].apply(estado)
    r["Próxima ação"] = r["Saldo"].apply(acao)
    ordem = {"ESGOTADO":0, "SALDO CRÍTICO":1, "SALDO BAIXO":2, "OK":3}
    r["ordem"] = r["Estado"].map(ordem)
    return r.sort_values(["ordem","Saldo","Cliente"]).drop(columns=["ordem"]).reset_index(drop=True)

def rows_from_df(df):
    df = saldos(df).copy()
    for c in ["Data","Data de registo"]:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.strftime("%d/%m/%Y %H:%M:%S").replace("NaT","")
    return df.fillna("").to_dict(orient="records")

@st.cache_data(show_spinner=False)
def excel_inicial():
    f = Path(__file__).with_name("PACKS_DE_HORAS_AUTOMATIZADO.xlsx")
    if not f.exists():
        return pd.DataFrame(columns=COLS)
    try:
        return norm(pd.read_excel(f, sheet_name="Base_Lancamentos", header=3))
    except Exception:
        try:
            return norm(pd.read_excel(f, sheet_name="Base_Lancamentos"))
        except Exception:
            return pd.DataFrame(columns=COLS)

def backend_ok():
    return bool(secret("APPS_SCRIPT_WEBAPP_URL",""))

def call(action, **payload):
    url = secret("APPS_SCRIPT_WEBAPP_URL","")
    token = secret("APPS_SCRIPT_TOKEN","Click123")
    if not url:
        raise RuntimeError("APPS_SCRIPT_WEBAPP_URL não configurado.")
    body = {"action":action, "token":token}
    body.update(payload)
    res = requests.post(url, json=body, timeout=30)
    res.raise_for_status()
    data = res.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Erro no Apps Script."))
    return data

def ler():
    return norm(pd.DataFrame(call("read").get("rows", [])))

def append(row):
    call("append", row=row)

def replace_all(df):
    call("replace_all", rows=rows_from_df(df))

def export_excel(df, r):
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        r.to_excel(writer, sheet_name="Dashboard", index=False)
        df.to_excel(writer, sheet_name="Base_Lancamentos", index=False)
    out.seek(0)
    return out.getvalue()

st.title("⏱️ Gestão de Packs de Horas")
st.caption("Versão sem JSON: ligação à Google Sheet através de Google Apps Script.")

with st.sidebar:
    st.header("⚙️ Configuração")
    modo = backend_ok()
    if modo:
        st.success("Modo colaborativo ativo")
    else:
        st.warning("Modo demonstração")
    user = st.text_input("Nome do colaborador")
    critico = st.number_input("Limite saldo crítico", min_value=0.0, value=1.0, step=0.5)
    baixo = st.number_input("Limite saldo baixo", min_value=0.0, value=2.0, step=0.5)
    if st.button("🔄 Atualizar"):
        st.cache_data.clear()
        st.rerun()
    if st.button("Terminar sessão"):
        st.session_state.ok_login = False
        st.rerun()

try:
    if modo:
        df = ler()
    else:
        if "demo" not in st.session_state:
            st.session_state.demo = excel_inicial()
        df = st.session_state.demo
except Exception as e:
    st.error("Não foi possível carregar os dados.")
    st.exception(e)
    st.stop()

df = saldos(df)
r = resumo(df, critico, baixo)

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Clientes", r["Cliente"].nunique() if not r.empty else 0)
c2.metric("Horas compradas", f"{r['Horas compradas'].sum():.1f} h" if not r.empty else "0 h")
c3.metric("Horas usadas", f"{r['Horas usadas'].sum():.1f} h" if not r.empty else "0 h")
c4.metric("Saldo total", f"{r['Saldo'].sum():.1f} h" if not r.empty else "0 h")
c5.metric("Alertas", int((r["Estado"]!="OK").sum()) if not r.empty else 0)

tabs = st.tabs(["📊 Dashboard","👤 Cliente","👥 Clientes","➕ Registar movimento","🧾 Movimentos","📥 Importar","⬇️ Exportar"])

with tabs[0]:
    st.subheader("Resumo por cliente")
    f1,f2,f3 = st.columns([1.2,1.5,2])
    estado = f1.selectbox("Estado", ["Todos"] + sorted(r["Estado"].dropna().unique().tolist()))
    cliente = f2.selectbox("Cliente", ["Todos"] + sorted(r["Cliente"].dropna().unique().tolist()))
    pesquisa = f3.text_input("Pesquisar")
    rf = r.copy()
    if estado != "Todos": rf = rf[rf["Estado"] == estado]
    if cliente != "Todos": rf = rf[rf["Cliente"] == cliente]
    if pesquisa: rf = rf[rf["Cliente"].str.contains(pesquisa, case=False, na=False)]
    st.dataframe(rf, use_container_width=True, hide_index=True)
    if not r.empty:
        st.bar_chart(r.sort_values("Saldo").head(15).set_index("Cliente")[["Saldo"]])

with tabs[1]:
    st.subheader("Ficha do cliente")
    clientes = sorted(df["Cliente"].dropna().unique().tolist())
    if not clientes:
        st.info("Ainda não existem clientes.")
    else:
        cl = st.selectbox("Selecionar cliente", clientes)
        st.dataframe(df[df["Cliente"] == cl], use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("Gestão de clientes")
    clientes = sorted(df["Cliente"].dropna().unique().tolist())
    a,b = st.columns(2)

    with a:
        st.markdown("### Adicionar cliente")
        with st.form("add_cliente", clear_on_submit=True):
            novo = st.text_input("Nome do cliente")
            contacto = st.text_input("Contacto / solicitado por")
            horas = st.number_input("Pack inicial de horas", min_value=0.0, value=0.0, step=0.25)
            obs = st.text_area("Observações")
            ok = st.checkbox("Confirmo")
            sub = st.form_submit_button("Adicionar")
        if sub:
            if not novo.strip():
                st.error("Indique o cliente.")
            elif novo.strip().lower() in [x.lower() for x in clientes]:
                st.error("Cliente já existe.")
            elif not ok:
                st.error("Confirme.")
            else:
                max_id = pd.to_numeric(df["ID"], errors="coerce").max()
                if pd.isna(max_id): max_id = 0
                row = {
                    "ID": int(max_id)+1, "Cliente": novo.strip(), "Data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "Tipo": "Cliente criado" if horas == 0 else "Compra", "Solicitada por": contacto, "Técnico": "",
                    "Descrição da intervenção": obs or "Cliente criado na app", "Horas Pack": float(horas), "Horas Usadas": 0.0,
                    "Saldo Automático": "", "Estado": "", "Saldo Original": "", "Origem": "App",
                    "Registado por": user.strip() or "Não identificado", "Data de registo": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                }
                if modo: append(row)
                else: st.session_state.demo = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                st.success("Cliente adicionado.")
                st.rerun()

    with b:
        st.markdown("### Apagar cliente")
        if not clientes:
            st.info("Sem clientes.")
        else:
            apagar = st.selectbox("Cliente a apagar", clientes)
            st.warning(f"Vai remover {len(df[df['Cliente']==apagar])} movimento(s).")
            conf = st.text_input("Escreva o nome do cliente")
            ok2 = st.checkbox("Confirmo apagar cliente")
            if st.button("Apagar cliente"):
                if conf.strip() != apagar:
                    st.error("Nome não corresponde.")
                elif not ok2:
                    st.error("Confirme.")
                else:
                    novo_df = df[df["Cliente"] != apagar].copy()
                    if modo: replace_all(novo_df)
                    else: st.session_state.demo = novo_df
                    st.success("Cliente apagado.")
                    st.rerun()

with tabs[3]:
    st.subheader("Registar movimento")
    if not user.strip():
        st.warning("Indique o nome do colaborador na barra lateral.")
    clientes = sorted(df["Cliente"].dropna().unique().tolist())
    with st.form("movimento", clear_on_submit=True):
        c1,c2,c3 = st.columns(3)
        cliente_sel = c1.selectbox("Cliente", ["Novo cliente"] + clientes)
        novo_cliente = ""
        if cliente_sel == "Novo cliente":
            novo_cliente = st.text_input("Nome do novo cliente")
        data_mov = c2.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        tipo = c3.selectbox("Tipo", TIPOS)
        solicitada = st.text_input("Solicitada por / contacto")
        tecnico = st.selectbox("Técnico", [""] + TECNICOS)
        desc = st.text_area("Descrição")
        h1,h2 = st.columns(2)
        pack = h1.number_input("Horas Pack compradas", min_value=0.0, value=0.0, step=0.25)
        usadas = h2.number_input("Horas utilizadas", min_value=0.0, value=0.0, step=0.25)
        ok = st.checkbox("Confirmo os dados")
        sub = st.form_submit_button("Guardar movimento")
    if sub:
        cliente_final = novo_cliente.strip() if cliente_sel == "Novo cliente" else cliente_sel
        if not user.strip():
            st.error("Indique colaborador.")
        elif not cliente_final:
            st.error("Indique cliente.")
        elif pack == 0 and usadas == 0:
            st.error("Indique horas.")
        elif not ok:
            st.error("Confirme.")
        else:
            max_id = pd.to_numeric(df["ID"], errors="coerce").max()
            if pd.isna(max_id): max_id = 0
            row = {
                "ID": int(max_id)+1, "Cliente": cliente_final, "Data": pd.to_datetime(data_mov).strftime("%d/%m/%Y"),
                "Tipo": tipo, "Solicitada por": solicitada, "Técnico": tecnico, "Descrição da intervenção": desc,
                "Horas Pack": float(pack), "Horas Usadas": float(usadas), "Saldo Automático": "",
                "Estado": "", "Saldo Original": "", "Origem": "App", "Registado por": user.strip(),
                "Data de registo": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }
            if modo: append(row)
            else: st.session_state.demo = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            st.success("Movimento guardado.")
            st.rerun()

with tabs[4]:
    st.subheader("Movimentos")
    if df.empty:
        st.info("Sem movimentos.")
    else:
        st.dataframe(df.sort_values(["Data","ID"], ascending=[False,False], na_position="last"), use_container_width=True, hide_index=True)
        st.markdown("### Apagar movimento")
        ids = pd.to_numeric(df["ID"], errors="coerce").dropna().astype(int).tolist()
        id_apagar = st.selectbox("ID do movimento", ids)
        st.dataframe(df[pd.to_numeric(df["ID"], errors="coerce") == id_apagar], use_container_width=True, hide_index=True)
        conf = st.text_input("Para confirmar, escreva o ID")
        ok = st.checkbox("Confirmo apagar movimento")
        if st.button("Apagar movimento"):
            if conf.strip() != str(id_apagar):
                st.error("ID não corresponde.")
            elif not ok:
                st.error("Confirme.")
            else:
                novo_df = saldos(df[pd.to_numeric(df["ID"], errors="coerce").astype("Int64") != int(id_apagar)].copy())
                if modo: replace_all(novo_df)
                else: st.session_state.demo = novo_df
                st.success("Movimento apagado.")
                st.rerun()

with tabs[5]:
    st.subheader("Importar Excel inicial para Google Sheet")
    dados = excel_inicial()
    st.write(f"Movimentos encontrados no Excel: **{len(dados)}**")
    if not modo:
        st.warning("Configure APPS_SCRIPT_WEBAPP_URL nos Secrets.")
    else:
        if st.checkbox("Confirmo substituir os dados atuais da Google Sheet"):
            if st.button("Importar Excel"):
                replace_all(dados)
                st.success("Dados importados.")
                st.rerun()

with tabs[6]:
    st.subheader("Exportar Excel atualizado")
    st.download_button(
        "Descarregar Excel",
        data=export_excel(df, r),
        file_name="PACKS_DE_HORAS_ATUALIZADO.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.dataframe(r, use_container_width=True, hide_index=True)
