import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import urllib.parse

# Configuração da página
st.set_page_config(
    page_title="Gestão Integrada de Peças & Fornecedores 4.0",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ Gestão de Peças, Monitoramento de Horas & Fornecedores (Indústria 4.0)")
st.markdown("Sistema integrado para controle de vida útil (MTBF), cadastro de fornecedores e cotação automática.")

# ----------------------------------------------------
# 1. BASE DE DADOS INICIAL / SESSION STATE
# ----------------------------------------------------
data_exemplo = {
    "Código SAP": ["301-260-01", "301-260-02", "301-260-03", "301-260-05"],
    "Descrição": [
        "Correia de Acionamento Principal", 
        "Rolamento do Eixo Principal", 
        "Sensor de Proximidade Indutivo", 
        "Motor Elétrico 2HP"
    ],
    "Categoria": ["Desgaste", "Recomendada", "Eletrônica", "Crítica"],
    "MTBF": [8000, 15000, 20000, 40000],
    "Horas Trabalhadas": [7200, 14200, 19500, 35000],
    "Lead Time (semanas)": [2, 4, 1, 8],
    "Criticidade": ["Alta", "Média", "Alta", "Alta"],
    "Fornecedor": ["Correias Industrial S.A.", "Rolamentos & Cia", "Sensors & Automation", "Motores Industriais Ltda"],
    "E-mail Fornecedor": ["vendas@correiasindustrial.com", "contato@rolamentoscia.com", "comercial@sensorsauto.com", "vendas@motoresind.com"],
    "Data Última Troca": ["Instalação Inicial", "Instalação Inicial", "Instalação Inicial", "Instalação Inicial"]
}

if "df_pecas" not in st.session_state:
    st.session_state["df_pecas"] = pd.DataFrame(data_exemplo)

if "historico_requisicoes" not in st.session_state:
    st.session_state["historico_requisicoes"] = []

# Sidebar - Configurações Gerais
st.sidebar.header("📁 Importação & Operação")

uploaded_file = st.sidebar.file_uploader("Carregar Tabela Excel (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        df_up = pd.read_excel(uploaded_file)
        st.session_state["df_pecas"] = df_up
        st.sidebar.success("Excel carregado com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler arquivo: {e}")

# Processamento e padronização dos nomes das colunas
df = st.session_state["df_pecas"].copy()

# Mapear e renomear variações de nomes de colunas
renomear_colunas = {}
for col in df.columns:
    col_clean = str(col).strip()
    if col_clean.lower() in ["mtbf", "mtbf (horas)", "mtbf(h)"]:
        renomear_colunas[col] = "MTBF"
    elif col_clean.lower() in ["horas trabalhadas", "horas da peça", "horas peca", "horas acumuladas"]:
        renomear_colunas[col] = "Horas Trabalhadas"

df = df.rename(columns=renomear_colunas)

# Garantir a criação das colunas caso não existam no arquivo importado
if "MTBF" not in df.columns:
    df["MTBF"] = 10000

if "Horas Trabalhadas" not in df.columns:
    df["Horas Trabalhadas"] = 0

if "Fornecedor" not in df.columns:
    df["Fornecedor"] = "Não Cadastrado"

if "E-mail Fornecedor" not in df.columns:
    df["E-mail Fornecedor"] = "fornecedor@email.com"

if "Data Última Troca" not in df.columns:
    df["Data Última Troca"] = "Instalação Inicial"

# Atualizar o session_state com o dataframe padronizado
st.session_state["df_pecas"] = df

# Parâmetros da Fábrica
st.sidebar.divider()
st.sidebar.header("⏱️ Regime da Máquina")
regime_diario = st.sidebar.slider("Horas de Trabalho / Dia:", min_value=8, max_value=24, value=16)
dias_semana = st.sidebar.slider("Dias de Operação / Semana:", min_value=5, max_value=7, value=6)

# Horímetro Geral
st.sidebar.divider()
st.sidebar.subheader("🕹️ Avançar Horímetro Geral")
inc_horas = st.sidebar.number_input("Adicionar Horas a Todos os Itens:", min_value=0, value=0, step=50)
if st.sidebar.button("➕ Aplicar Horas na Máquina"):
    st.session_state["df_pecas"]["Horas Trabalhadas"] += inc_horas
    st.sidebar.success(f"{inc_horas}h adicionadas!")
    st.rerun()

# ----------------------------------------------------
# 2. ENGENHARIA DE CÁLCULO
# ----------------------------------------------------
df["MTBF"] = pd.to_numeric(df["MTBF"], errors="coerce").fillna(0)
df["Horas Trabalhadas"] = pd.to_numeric(df["Horas Trabalhadas"], errors="coerce").fillna(0)
df["Lead Time (semanas)"] = pd.to_numeric(df["Lead Time (semanas)"], errors="coerce").fillna(1)

# Conversão do Lead Time em Horas de Trabalho Efetivas
df["Lead Time (Horas)"] = df["Lead Time (semanas)"] * dias_semana * regime_diario
df["Gatilho Compra (Horas)"] = df["MTBF"] - df["Lead Time (Horas)"]

df["Vida Útil Restante (h)"] = df["MTBF"] - df["Horas Trabalhadas"]
df["Horas Restantes p/ Compra"] = df["Gatilho Compra (Horas)"] - df["Horas Trabalhadas"]

df["Dias Restantes p/ Compra"] = df["Horas Restantes p/ Compra"] / regime_diario
df["Dias Restantes p/ Troca"] = df["Vida Útil Restante (h)"] / regime_diario

df["% Consumido"] = (df["Horas Trabalhadas"] / df["MTBF"]) * 100
df["% Consumido"] = df["% Consumido"].apply(lambda x: min(100.0, max(0.0, float(x))) if pd.notnull(x) else 0.0)

def classificar_status(row):
    if row["Vida Útil Restante (h)"] <= 0:
        return "🔴 VENCIDO (Troca Imediata)"
    elif row["Horas Restantes p/ Compra"] <= 0:
        return "🟡 GATILHO COMPRA (Emitir Pedido)"
    elif row["Horas Restantes p/ Compra"] <= (regime_diario * 7):
        return "🟠 ALERTA DE COMPRA (Próximo do LT)"
    else:
        return "🟢 OPERAÇÃO NORMAL"

df["Status de Manutenção"] = df.apply(classificar_status, axis=1)

hoje = datetime.now()
df["Data Limite Compra"] = df["Dias Restantes p/ Compra"].apply(
    lambda d: (hoje + timedelta(days=float(d))).strftime("%d/%m/%Y") if d >= 0 else "URGENTE"
)
df["Data Prevista Troca"] = df["Dias Restantes p/ Troca"].apply(
    lambda d: (hoje + timedelta(days=float(d))).strftime("%d/%m/%Y") if d >= 0 else "IMEDIATA"
)

# ----------------------------------------------------
# 3. INTERFACE PRINCIPAL - ABAS
# ----------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("Itens Monitorados", len(df))
m2.metric("Pendentes de Ordem de Compra", len(df[df["Horas Restantes p/ Compra"] <= 0]))
m3.metric("Peças Vencidas (Horas > MTBF)", len(df[df["Vida Útil Restante (h)"] <= 0]))
m4.metric("Requisições / Histórico", len(st.session_state["historico_requisicoes"]))

st.divider()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 1. Monitoramento de Horas por Item", 
    "🏷️ 2. Cadastro de Fornecedores",
    "📩 3. Solicitação de Cotação", 
    "🛠️ 4. Reposição & Reset de Peça", 
    "🔮 5. Simulador de Horas",
    "📜 6. Histórico de Requisições"
])

# TAB 1: MONITORAMENTO
with tab1:
    st.subheader("📊 Painel de Monitoramento Individual de Horas Trabalhadas")
    st.markdown("Altere abaixo as **Horas Trabalhadas** de qualquer item para atualizar o status em tempo real:")

    df_edit_horas = st.data_editor(
        df[["Código SAP", "Descrição", "Horas Trabalhadas", "MTBF", "Vida Útil Restante (h)", "Status de Manutenção"]],
        disabled=["Código SAP", "Descrição", "MTBF", "Vida Útil Restante (h)", "Status de Manutenção"],
        use_container_width=True,
        key="editor_horas_trabalhadas"
    )

    if st.button("💾 Atualizar Horas Trabalhadas"):
        for idx, row in df_edit_horas.iterrows():
            st.session_state["df_pecas"].loc[idx, "Horas Trabalhadas"] = row["Horas Trabalhadas"]
        st.success("Horas atualizadas com sucesso!")
        st.rerun()

    st.divider()
    st.subheader("📉 Consumo da Vida Útil das Peças (% MTBF)")
    fig = px.bar(
        df, 
        x="% Consumido", 
        y="Descrição", 
        orientation='h',
        color="% Consumido",
        color_continuous_scale="Reds",
        text_auto=".1f"
    )
    fig.update_layout(xaxis=dict(range=[0, 100]), height=300)
    st.plotly_chart(fig, use_container_width=True)

# TAB 2: FORNECEDORES
with tab2:
    st.subheader("🏷️ Cadastro e Edição de Fornecedores por Peça")
    st.markdown("Preencha ou altere o **Nome do Fornecedor** e o **E-mail de Contato** de cada componente:")

    df_forn_edit = st.data_editor(
        df[["Código SAP", "Descrição", "Fornecedor", "E-mail Fornecedor"]],
        disabled=["Código SAP", "Descrição"],
        use_container_width=True,
        key="editor_fornecedores_tab"
    )

    if st.button("💾 Salvar Fornecedores e E-mails"):
        for idx, row in df_forn_edit.iterrows():
            st.session_state["df_pecas"].loc[idx, "Fornecedor"] = row["Fornecedor"]
            st.session_state["df_pecas"].loc[idx, "E-mail Fornecedor"] = row["E-mail Fornecedor"]
        st.success("Cadastro de Fornecedores salvo com sucesso!")
        st.rerun()

# TAB 3: SOLICITAÇÃO DE COTAÇÃO
with tab3:
    st.subheader("📩 Selecionar Peças e Enviar Solicitação de Orçamento")
    st.markdown("Marque os itens que deseja cotar abaixo:")

    df_selecao = df.copy()
    df_selecao.insert(0, "Selecionar", False)
    df_selecao.loc[df_selecao["Horas Restantes p/ Compra"] <= 0, "Selecionar"] = True

    df_editado = st.data_editor(
        df_selecao[[
            "Selecionar", "Código SAP", "Descrição", "Horas Trabalhadas", 
            "Vida Útil Restante (h)", "Lead Time (semanas)", "Data Limite Compra",
            "Fornecedor", "E-mail Fornecedor", "Status de Manutenção"
        ]],
        disabled=[
            "Código SAP", "Descrição", "Horas Trabalhadas", 
            "Vida Útil Restante (h)", "Lead Time (semanas)", "Data Limite Compra",
            "Fornecedor", "E-mail Fornecedor", "Status de Manutenção"
        ],
        use_container_width=True,
        key="editor_cotacao_tab"
    )

    itens_cotar = df_editado[df_editado["Selecionar"] == True]

    if not itens_cotar.empty:
        st.divider()
        st.subheader(f"📦 Solicitando Orçamento para {len(itens_cotar)} item(ns)")

        for fornecedor, grupo in itens_cotar.groupby("Fornecedor"):
            email_f = grupo["E-mail Fornecedor"].iloc[0]
            st.markdown(f"### 🏢 Fornecedor: **{fornecedor}** (`{email_f}`)")
            
            corpo_msg = f"Prezado time da {fornecedor},\n\nGostaríamos de solicitar cotação urgente para os itens:\n\n"
            for _, item in grupo.iterrows():
                corpo_msg += f"• Item: {item['Descrição']} (SAP: {item['Código SAP']}) - Lead Time: {item['Lead Time (semanas)']} sem.\n"
            corpo_msg += "\nAtenciosamente,\nDepartamento de Suprimentos / Manutenção"

            assunto = f"Solicitação de Orçamento - {fornecedor}"
            mailto_url = f"mailto:{email_f}?subject={urllib.parse.quote(assunto)}&body={urllib.parse.quote(corpo_msg)}"

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f'''
                <a href="{mailto_url}" target="_blank">
                    <button style="background-color: #008CBA; color: white; border: none; padding: 10px 18px; border-radius: 5px; font-weight: bold; cursor: pointer;">
                        ✉️ Abrir E-mail e Enviar para {fornecedor}
                    </button>
                </a>
                ''', unsafe_allow_html=True)
            with col_b:
                if st.button(f"📌 Registrar Solicitação de {fornecedor}", key=f"hist_{fornecedor}"):
                    for _, item in grupo.iterrows():
                        st.session_state["historico_requisicoes"].append({
                            "Data Evento": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "Tipo": "SOLICITAÇÃO DE COTAÇÃO",
                            "Código SAP": item["Código SAP"],
                            "Descrição": item["Descrição"],
                            "Fornecedor": fornecedor,
                            "E-mail": email_f,
                            "Detalhes": f"Cotação solicitada. Status: {item['Status de Manutenção']}"
                        })
                    st.success(f"Registrado com sucesso no Histórico!")
                    st.rerun()

# TAB 4: REPOSIÇÃO / RESET
with tab4:
    st.subheader("🛠️ Registrar Reposição de Peça e Zerar Horas Trabalhadas")
    
    col_a, col_b = st.columns(2)
    with col_a:
        item_troca = st.selectbox("Selecione a peça trocada:", df["Descrição"].unique())
        dt_troca = st.date_input("Data da troca:", datetime.now())
        tecnico = st.text_input("Técnico Responsável:", "Manutenção")
    with col_b:
        obs = st.text_area("Observações:", "Troca de peça realizada.")
        hrs_novas = st.number_input("Horas Iniciais do Componente Novo:", value=0, min_value=0)

    if st.button("🔄 Confirmar Substituição & Resetar Horas"):
        idx = df[df["Descrição"] == item_troca].index[0]
        st.session_state["df_pecas"].loc[idx, "Horas Trabalhadas"] = hrs_novas
        st.session_state["df_pecas"].loc[idx, "Data Última Troca"] = dt_troca.strftime("%d/%m/%Y")
        
        st.session_state["historico_requisicoes"].append({
            "Data Evento": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "Tipo": "REPOSIÇÃO / TROCA",
            "Código SAP": df.loc[idx, "Código SAP"],
            "Descrição": item_troca,
            "Fornecedor": df.loc[idx, "Fornecedor"],
            "E-mail": df.loc[idx, "E-mail Fornecedor"],
            "Detalhes": f"Peça trocada por {tecnico}. Horas zeradas para {hrs_novas}h."
        })
        st.success(f"✅ Horas do item {item_troca} resetadas com sucesso!")
        st.rerun()

# TAB 5: SIMULADOR
with tab5:
    st.subheader("🔮 Simulador de Carga de Trabalho")
    sim_h = st.number_input("Simular avanço de operação (Horas):", min_value=0, value=1000, step=100)
    
    df_s = df.copy()
    df_s["Horas Simuladas"] = df_s["Horas Trabalhadas"] + sim_h
    df_s["Vida Útil Restante Simulada"] = df_s["MTBF"] - df_s["Horas Simuladas"]
    df_s["Status Simulado"] = df_s.apply(
        lambda r: "🔴 VENCIDO" if r["Vida Útil Restante Simulada"] <= 0 
        else ("🟡 COMPRAR" if r["Vida Útil Restante Simulada"] <= r["Lead Time (Horas)"] else "🟢 OK"), axis=1
    )
    st.dataframe(df_s[["Código SAP", "Descrição", "Horas Trabalhadas", "Horas Simuladas", "Vida Útil Restante Simulada", "Status Simulado"]], use_container_width=True)

# TAB 6: HISTÓRICO
with tab6:
    st.subheader("📜 Histórico Geral de Transações")
    if len(st.session_state["historico_requisicoes"]) > 0:
        df_h = pd.DataFrame(st.session_state["historico_requisicoes"])
        st.dataframe(df_h, use_container_width=True)
        csv_data = df_h.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Histórico (CSV)",
            data=csv_data,
            file_name=f"historico_pecas_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("Nenhuma requisição ou reposição registrada até o momento.")
