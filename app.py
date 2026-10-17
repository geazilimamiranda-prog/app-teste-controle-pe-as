import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuração da página
st.set_page_config(
    page_title="Gestão & Simulador - Indústria 4.0",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ Sistema Integrado de Gestão, Compras & Simulação 4.0")
st.subheader("Monitoramento de Ciclo de Vida por Horas Operacionais & Lead Time")

# ----------------------------------------------------
# INICIALIZAÇÃO E SESSÃO DE DADOS
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
    "Lead Time (semanas)": [2, 4, 1, 8],
    "Criticidade": ["Alta", "Média", "Alta", "Alta"],
    "Horas da Peça": [7200, 14200, 19500, 35000],  # Horas acumuladas de cada componente
    "Data Última Troca": ["Instalação Inicial", "Instalação Inicial", "Instalação Inicial", "Instalação Inicial"]
}

if "df_pecas" not in st.session_state:
    st.session_state["df_pecas"] = pd.DataFrame(data_exemplo)

if "historico_requisicoes" not in st.session_state:
    st.session_state["historico_requisicoes"] = []

# Sidebar - Configurações
st.sidebar.header("📁 Importação de Dados")

uploaded_file = st.sidebar.file_uploader("Carregue a tabela de equipamentos (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        df_uploaded = pd.read_excel(uploaded_file)
        if "Horas da Peça" not in df_uploaded.columns:
            df_uploaded["Horas da Peça"] = 0
        if "Data Última Troca" not in df_uploaded.columns:
            df_uploaded["Data Última Troca"] = "Instalação Inicial"
        st.session_state["df_pecas"] = df_uploaded
        st.sidebar.success("Arquivo carregado com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler arquivo: {e}")

df = st.session_state["df_pecas"]

# Conversões numéricas obrigatórias
df["MTBF"] = pd.to_numeric(df["MTBF"], errors="coerce")
df["Lead Time (semanas)"] = pd.to_numeric(df["Lead Time (semanas)"], errors="coerce")
df["Horas da Peça"] = pd.to_numeric(df["Horas da Peça"], errors="coerce")

# Sidebar - Controle de Horímetro da Máquina
st.sidebar.divider()
st.sidebar.header("⏱️ Parâmetros do Equipamento")

regime_diario = st.sidebar.slider("Regime Diário (Horas/Dia):", min_value=8, max_value=24, value=16)
dias_semana = st.sidebar.slider("Dias de Operação / Semana:", min_value=5, max_value=7, value=6)

st.sidebar.subheader("🕹️ Atualizar Horímetro Geral")
incremento_horas = st.sidebar.number_input("Adicionar horas de operação a todos os itens:", min_value=0, value=0, step=50)

if st.sidebar.button("➕ Aplicar Horas Trabalhadas"):
    st.session_state["df_pecas"]["Horas da Peça"] += incremento_horas
    st.sidebar.success(f"{incremento_horas}h adicionadas com sucesso!")
    st.rerun()

# ----------------------------------------------------
# ENGENHARIA DE CÁLCULO DE VIDA ÚTIL & LEAD TIME
# ----------------------------------------------------
# 1. Converte o Lead Time (semanas) em Horas de Trabalho Efetivas
df["Lead Time (Horas)"] = df["Lead Time (semanas)"] * dias_semana * regime_diario

# 2. Ponto de gatilho para emissão da Ordem de Compra
df["Gatilho Compra (Horas)"] = df["MTBF"] - df["Lead Time (Horas)"]

# 3. Vida útil restante e margem de compra
df["Vida Útil Restante (h)"] = df["MTBF"] - df["Horas da Peça"]
df["Horas Restantes p/ Compra"] = df["Gatilho Compra (Horas)"] - df["Horas da Peça"]

df["Dias Restantes p/ Compra"] = df["Horas Restantes p/ Compra"] / regime_diario
df["Dias Restantes p/ Troca"] = df["Vida Útil Restante (h)"] / regime_diario

# 4. Porcentagem da vida útil consumida da peça
df["% Consumido"] = (df["Horas da Peça"] / df["MTBF"]) * 100
df["% Consumido"] = df["% Consumido"].apply(lambda x: min(100.0, max(0.0, float(x))))

# 5. Definição do Status de Acordo com MTBF e Lead Time
def classificar_status(row):
    if row["Vida Útil Restante (h)"] <= 0:
        return "🔴 VENCIDO (Trocar Peça Imandatamente)"
    elif row["Horas Restantes p/ Compra"] <= 0:
        return "🟡 GATILHO COMPRA (Emitir Ordem de Compra)"
    elif row["Horas Restantes p/ Compra"] <= (regime_diario * 7):
        return "🟠 ALERTA DE COMPRA (Próximo do Lead Time)"
    else:
        return "🟢 OPERAÇÃO NORMAL"

df["Status de Manutenção"] = df.apply(classificar_status, axis=1)

hoje = datetime.now()
df["Data Limite Compra"] = df["Dias Restantes p/ Compra"].apply(
    lambda d: (hoje + timedelta(days=float(d))).strftime("%d/%m/%Y") if d >= 0 else "URGENTE (Atrasado)"
)
df["Data Prevista Troca"] = df["Dias Restantes p/ Troca"].apply(
    lambda d: (hoje + timedelta(days=float(d))).strftime("%d/%m/%Y") if d >= 0 else "IMEDIATA"
)

# ----------------------------------------------------
# PAINEL E ABAS
# ----------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total de Peças Monitoradas", len(df))
m2.metric("Necessitam de Ordem de Compra", len(df[df["Horas Restantes p/ Compra"] <= 0]))
m3.metric("Peças Vencidas (Acima do MTBF)", len(df[df["Vida Útil Restante (h)"] <= 0]))
m4.metric("Histórico de Requisições", len(st.session_state["historico_requisicoes"]))

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Monitoramento por Vida Útil e Lead Time", 
    "🛠️ Reposição & Reset de Peças", 
    "🔮 Simulador de Cenários",
    "📅 Emissão Automática de Requisições",
    "📜 Histórico de Requisições"
])

with tab1:
    st.subheader("📋 Tabela Operacional de Peças - Cruzamento MTBF vs Lead Time")
    
    cols = [
        "Código SAP", "Descrição", "MTBF", "Horas da Peça", 
        "Vida Útil Restante (h)", "Lead Time (semanas)", "Lead Time (Horas)",
        "Data Limite Compra", "Data Prevista Troca", "Status de Manutenção"
    ]
    st.dataframe(df[cols], use_container_width=True)

    st.subheader("📉 Desgaste e Consumo da Vida Útil de Cada Item (% MTBF)")
    fig = px.bar(
        df, 
        x="% Consumido", 
        y="Descrição", 
        orientation='h',
        color="% Consumido",
        color_continuous_scale="Reds",
        text_auto=".1f",
        labels={"% Consumido": "% Vida Útil Consumida (MTBF)", "Descrição": "Item"}
    )
    fig.update_layout(xaxis=dict(range=[0, 100]), height=350)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("🛠️ Registrar Reposição de Peça e Resetar Horas")
    st.markdown("Assim que a peça for substituída na máquina, selecione o item abaixo para **resetar suas horas para 0** e atualizar o status para **🟢 OPERAÇÃO NORMAL**.")
    
    c_a, c_b = st.columns(2)
    with c_a:
        item_troca = st.selectbox("Selecione a peça substituída:", df["Descrição"].unique())
        dt_troca = st.date_input("Data da substituição:", datetime.now())
        tecnico = st.text_input("Técnico / Responsável:", "Manutenção Mecânica/Elétrica")
    with c_b:
        obs = st.text_area("Observações:", "Troca realizada com sucesso.")
        hrs_novas = st.number_input("Horas Iniciais do novo componente:", value=0, min_value=0)

    if st.button("🔄 Confirmar Troca e Reiniciar Contagem de Horas"):
        idx = df[df["Descrição"] == item_troca].index[0]
        st.session_state["df_pecas"].loc[idx, "Horas da Peça"] = hrs_novas
        st.session_state["df_pecas"].loc[idx, "Data Última Troca"] = dt_troca.strftime("%d/%m/%Y")
        
        st.session_state["historico_requisicoes"].append({
            "Data Evento": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "Tipo": "REPOSIÇÃO / TROCA",
            "Código SAP": df.loc[idx, "Código SAP"],
            "Descrição": item_troca,
            "Solicitante": tecnico,
            "Detalhes": f"Substituição efetuada. Vida útil resetada para {hrs_novas}h. Obs: {obs}"
        })
        st.success(f"✅ Reposição concluída! A vida útil do item **{item_troca}** foi zerada.")
        st.rerun()

with tab3:
    st.subheader("🔮 Simulador de Carga e Avanço de Horas")
    st.markdown("Projete a necessidade de peças e compras simulando a operação contínua da fábrica por semanas ou meses:")

    sc1, sc2 = st.columns(2)
    with sc1:
        sim_horas = st.number_input("Simular avanço de operação (horas):", min_value=0, value=2000, step=100)
    with sc2:
        sim_fator = st.slider("Fator de Rigidez Operacional (1.0 = Normal, 1.5 = Severo):", 0.5, 2.0, 1.0, 0.1)

    df_sim = df.copy()
    df_sim["Horas Simuladas"] = df_sim["Horas da Peça"] + (sim_horas * sim_fator)
    df_sim["Vida Restante Simulada (h)"] = df_sim["MTBF"] - df_sim["Horas Simuladas"]
    df_sim["Status Simulado"] = df_sim.apply(
        lambda r: "🔴 FALHA / VENCIDO" if r["Vida Restante Simulada (h)"] <= 0 
        else ("🟡 NECESSITA COMPRA" if r["Vida Restante Simulada (h)"] <= r["Lead Time (Horas)"] else "🟢 OK"), axis=1
    )

    st.dataframe(df_sim[["Código SAP", "Descrição", "MTBF", "Horas da Peça", "Horas Simuladas", "Vida Restante Simulada (h)", "Status Simulado"]], use_container_width=True)

with tab4:
    st.subheader("📅 Central de Emissão de Requisições de Compra")
    
    pendentes = df[df["Horas Restantes p/ Compra"] <= 0]
    
    if not pendentes.empty:
        st.warning(f"Existem **{len(pendentes)}** item(ns) atingindo ou ultrapassando o gatilho do Lead Time de compra.")
        if st.button("🚀 Emitir Requisição de Compra Automática para Itens Criticos", type="primary"):
            for _, r in pendentes.iterrows():
                st.session_state["historico_requisicoes"].append({
                    "Data Evento": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Tipo": "REQUISIÇÃO AUTOMÁTICA",
                    "Código SAP": r["Código SAP"],
                    "Descrição": r["Descrição"],
                    "Solicitante": "Sistema Preditivo Indústria 4.0",
                    "Detalhes": f"Requisição enviada ao Lead Time ({r['Lead Time (semanas)']} sem). Horas Atuais: {r['Horas da Peça']}h."
                })
            st.success("Ordens de compra emitidas e registradas no histórico com sucesso!")
            st.rerun()
    else:
        st.info("Todos os componentes estão dentro da margem de segurança de estoque/Lead Time.")

with tab5:
    st.subheader("📜 Histórico Geral de Requisições e Trocas")
    
    if len(st.session_state["historico_requisicoes"]) > 0:
        df_h = pd.DataFrame(st.session_state["historico_requisicoes"])
        st.dataframe(df_h, use_container_width=True)
        
        csv_data = df_h.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Relatório de Requisições (CSV)",
            data=csv_data,
            file_name=f"historico_requisicoes_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("Nenhuma requisição ou troca foi registrada até o momento.")
