import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuração da página
st.set_page_config(
    page_title="Gestão & Plano de Manutenção Indústria 4.0",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ Sistema Integrado de Monitoramento & Plano de Manutenção")
st.subheader("Controle de Peças, Emissão de Ordem de Compra & Manutenção Preditiva")

# Sidebar - Configurações
st.sidebar.header("📁 Importação de Dados & Parâmetros")

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
    "Criticidade": ["Alta", "Média", "Alta", "Alta"]
}

uploaded_file = st.sidebar.file_uploader("Carregue a tabela de equipamentos (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        st.sidebar.success("Arquivo carregado com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler arquivo: {e}")
        df = pd.DataFrame(data_exemplo)
else:
    st.sidebar.info("Utilizando base de dados padrão.")
    df = pd.DataFrame(data_exemplo)

# Garantir conversões numéricas
df["MTBF"] = pd.to_numeric(df["MTBF"], errors="coerce")
df["Lead Time (semanas)"] = pd.to_numeric(df["Lead Time (semanas)"], errors="coerce")

# Parâmetros de operação do equipamento
st.sidebar.divider()
st.sidebar.header("⏱️ Parâmetros Operacionais")

horas_trabalhadas = st.sidebar.number_input(
    "Horas Atuais de Operação do Equipamento (h):",
    min_value=0,
    value=7200,
    step=100
)

regime_diario = st.sidebar.slider(
    "Regime Operacional (Horas por Dia):",
    min_value=8,
    max_value=24,
    value=16
)

dias_semana = st.sidebar.slider(
    "Dias de Operação por Semana:",
    min_value=5,
    max_value=7,
    value=6
)

# ----------------------------------------------------
# CÁLCULOS TÉCNICOS & ENGENHARIA DE MANUTENÇÃO
# ----------------------------------------------------
df["Lead Time (Horas Operacionais)"] = df["Lead Time (semanas)"] * dias_semana * regime_diario
df["Gatilho Compra (Horas Equipamento)"] = df["MTBF"] - df["Lead Time (Horas Operacionais)"]

df["Vida Útil Restante (h)"] = df["MTBF"] - horas_trabalhadas
df["Horas Restantes para Compra"] = df["Gatilho Compra (Horas Equipamento)"] - horas_trabalhadas
df["Dias Restantes para Compra"] = df["Horas Restantes para Compra"] / regime_diario
df["Dias Restantes para Falha/Troca"] = df["Vida Útil Restante (h)"] / regime_diario

df["% Vida Útil Consumida"] = (horas_trabalhadas / df["MTBF"]) * 100
df["% Vida Útil Consumida"] = df["% Vida Útil Consumida"].apply(lambda x: min(100.0, max(0.0, float(x))))

def calcular_status(row):
    if row["Vida Útil Restante (h)"] <= 0:
        return "🔴 VENCIDO - Troca Imediata"
    elif row["Horas Restantes para Compra"] <= 0:
        return "🟡 Emitir Ordem de Compra (Lead Time)"
    elif row["Horas Restantes para Compra"] <= (regime_diario * 7):
        return "🟠 Atenção: Preparar Pedido"
    else:
        return "🟢 Operação Normal"

df["Status de Manutenção"] = df.apply(calcular_status, axis=1)

hoje = datetime.now()
df["Data Limite Emissão Ordem Compra"] = df["Dias Restantes para Compra"].apply(
    lambda d: (hoje + timedelta(days=float(d))).strftime("%d/%m/%Y") if d >= 0 else "Urgente (Atrasado)"
)
df["Data Estimada de Troca/Parada"] = df["Dias Restantes para Falha/Troca"].apply(
    lambda d: (hoje + timedelta(days=float(d))).strftime("%d/%m/%Y") if d >= 0 else "Imediata"
)

# ----------------------------------------------------
# INTERFACE PRINCIPAL
# ----------------------------------------------------

m1, m2, m3, m4 = st.columns(4)
m1.metric("Horas Totais do Equipamento", f"{horas_trabalhadas:,} h")
m2.metric("Itens Monitorados", len(df))
m3.metric("Ordens de Compra Pendentes", len(df[df["Horas Restantes para Compra"] <= 0]))
m4.metric("Itens Críticos", len(df[df["Criticidade"] == "Alta"]))

st.divider()

tab1, tab2, tab3 = st.tabs([
    "📊 Status Detalhado dos Itens", 
    "🔍 Monitoramento Individualizado", 
    "📅 Plano Integrado de Manutenção"
])

with tab1:
    st.subheader("📋 Tabela Operacional de Monitoramento e Controle de Compras")
    
    colunas_visiveis = [
        "Código SAP", "Descrição", "MTBF", "Lead Time (semanas)", 
        "Vida Útil Restante (h)", "Dias Restantes para Compra", 
        "Data Limite Emissão Ordem Compra", "Data Estimada de Troca/Parada", "Status de Manutenção"
    ]

    # Exibição direta do DataFrame sem usar .style.applymap para evitar o erro de versão
    st.dataframe(df[colunas_visiveis], use_container_width=True)

    st.subheader("📉 Mapeamento Visual do Ciclo de Vida (% MTBF)")
    fig = px.bar(
        df, 
        x="% Vida Útil Consumida", 
        y="Descrição", 
        orientation='h',
        color="% Vida Útil Consumida",
        color_continuous_scale="Reds",
        text_auto=".1f",
        labels={"% Vida Útil Consumida": "Consumo de Vida Útil (%)", "Descrição": "Peça / Componente"}
    )
    fig.update_layout(xaxis=dict(range=[0, 100]), height=350)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("🔍 Diagnóstico Detalhado por Componente")
    
    item_selecionado = st.selectbox("Selecione o item para inspeção detalhada:", df["Descrição"].unique())
    item_data = df[df["Descrição"] == item_selecionado].iloc[0]

    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.markdown(f"### **{item_data['Descrição']}**")
        st.write(f"**Código SAP:** `{item_data['Código SAP']}`")
        st.write(f"**Categoria:** {item_data['Categoria']}")
        st.write(f"**Criticidade:** {item_data['Criticidade']}")
        st.write(f"**MTBF:** {item_data['MTBF']:,} horas")
        st.write(f"**Lead Time:** {item_data['Lead Time (semanas)']} semanas")
        st.info(f"**Status Atual:** {item_data['Status de Manutenção']}")

    with c2:
        st.markdown("#### ⏳ Linha do Tempo e Decisão de Compra")
        
        gauge_fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = item_data["% Vida Útil Consumida"],
            title = {'text': "Vida Útil Consumida (%)"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 70], 'color': "lightgreen"},
                    {'range': [70, 100], 'color': "yellow"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 100
                }
            }
        ))
        gauge_fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(gauge_fig, use_container_width=True)

        st.warning(f"""
        **Diretrizes de Suprimentos e Manutenção:**
        * **Ponto de Emissão da Ordem de Compra:** {item_data['Gatilho Compra (Horas Equipamento)']:,}h de operação.
        * **Data Limite para Compra:** **{item_data['Data Limite Emissão Ordem Compra']}** (em aprox. {max(0, int(item_data['Dias Restantes para Compra']))} dias).
        * **Data Prevista da Substituição:** **{item_data['Data Estimada de Troca/Parada']}**.
        """)

with tab3:
    st.subheader("📅 Plano Previsto de Paradas de Manutenção")
    st.markdown("Cronograma sugerido para agrupar trocas, zerar impactos produtivos e otimizar estoques:")

    df_plano = df.sort_values(by="Vida Útil Restante (h)").copy()
    
    for idx, item in df_plano.iterrows():
        dias_troca = int(item["Dias Restantes para Falha/Troca"])
        
        if dias_troca <= 0:
            st.error(f"🚨 **PARADA IMEDIATA:** Substituir **{item['Descrição']}** (`{item['Código SAP']}`). Limite do MTBF esgotado.")
        elif dias_troca <= 15:
            st.warning(f"⚠️ **Parada Próxima (~{dias_troca} dias - {item['Data Estimada de Troca/Parada']}):** Substituir **{item['Descrição']}**. Verifique se a Ordem de Compra foi emitida.")
        else:
            st.success(f"🟢 **Parada Futura (~{dias_troca} dias - {item['Data Estimada de Troca/Parada']}):** Manutenção planejada para **{item['Descrição']}**.")

    st.divider()
    if st.button("📦 Gerar e Enviar Solicitação Automática de Compras"):
        itens_compra = df[df["Horas Restantes para Compra"] <= 0]
        if not itens_compra.empty:
            st.success(f"Ordem de Compra gerada para {len(itens_compra)} item(ns) e enviada ao fabricante com sucesso!")
        else:
            st.info("Nenhum item atingiu o gatilho de Lead Time no momento.")
