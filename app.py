import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuração da página no Streamlit
st.set_page_config(
    page_title="Gestão Integrada de Peças - Indústria 4.0",
    page_icon="⚙️",
    layout="wide"
)

# Título e Introdução
st.title("⚙️ Sistema Integrado de Gestão de Peças Recomendadas")
st.subheader("Manutenção Preditiva & Monitoramento Remoto (Indústria 4.0)")

st.markdown("""
Este aplicativo visa **otimizar a manutenção**, **reduzir custos operacionais** e **melhorar o planejamento de paradas de máquinas**. 
Acompanhe o ciclo de vida útil dos componentes industriais com base em horas trabalhadas e lead time de reposição.
""")

st.sidebar.header("📁 Importação de Dados & Configurações")

# Exemplo de dados padrão baseados na imagem fornecida
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

# Upload do arquivo XLSX
uploaded_file = st.sidebar.file_uploader("Carregue a tabela de equipamentos (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        st.sidebar.success("Arquivo carregado com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler arquivo: {e}")
        df = pd.DataFrame(data_exemplo)
else:
    st.sidebar.info("Usando dados de demonstração (imagem do equipamento).")
    df = pd.DataFrame(data_exemplo)

# Garantir tipos numéricos corretos
df["MTBF"] = pd.to_numeric(df["MTBF"], errors="coerce")
df["Lead Time (semanas)"] = pd.to_numeric(df["Lead Time (semanas)"], errors="coerce")

st.sidebar.divider()
st.sidebar.header("🕹️ Simulação de Operação Remota")
horas_trabalhadas = st.sidebar.number_input(
    "Horas Atuais de Operação do Equipamento (h):",
    min_value=0,
    value=7200,
    step=100
)

regime_trabalho = st.sidebar.slider(
    "Regime de Operação Diário (Horas/Dia):",
    min_value=8,
    max_value=24,
    value=16
)

# Cálculos de Indicadores
df["Horas Acumuladas"] = horas_trabalhadas
df["Vida Útil Restante (h)"] = df["MTBF"] - df["Horas Acumuladas"]
df["% Vida Útil Consumida"] = (df["Horas Acumuladas"] / df["MTBF"]) * 100
df["% Vida Útil Consumida"] = df["% Vida Útil Consumida"].apply(lambda x: min(x, 100.0))

# Cálculo do Ponto de Pedido (Lead Time convertido em horas de trabalho)
df["Horas Lead Time"] = df["Lead Time (semanas)"] * 7 * regime_trabalho
df["Dias Restantes"] = df["Vida Útil Restante (h)"] / regime_trabalho

# Definir Status do Item
def calcular_status(row):
    if row["Vida Útil Restante (h)"] <= 0:
        return "🔴 Troca Imediata (Excedido)"
    elif row["Vida Útil Restante (h)"] <= row["Horas Lead Time"]:
        return "🟡 Pedido de Compra Requerido (Lead Time)"
    else:
        return "🟢 Operação Normal"

df["Status de Manutenção"] = df.apply(calcular_status, axis=1)

# Dashboard - Métricas Principais
st.header("📊 Painel de Monitoramento do Equipamento")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Horas Totais do Equipamento", f"{horas_trabalhadas:,} h")
col2.metric("Itens Críticos Cadastrados", len(df[df["Criticidade"] == "Alta"]))
col3.metric("Pedidos de Compra/Ação", len(df[df["Status de Manutenção"] != "🟢 Operação Normal"]))
col4.metric("Regime de Trabalho", f"{regime_trabalho} h/dia")

st.divider()

# Tabela Interativa
st.subheader("📋 Status Detalhado dos Componentes Monitorados")

# Estilização da Tabela
def highlight_status(val):
    if "🔴" in str(val):
        return "background-color: #ffcccc; color: black; font-weight: bold;"
    elif "🟡" in str(val):
        return "background-color: #fff2cc; color: black; font-weight: bold;"
    elif "🟢" in str(val):
        return "background-color: #d9ead3; color: black;"
    return ""

col_display = [
    "Código SAP", "Descrição", "Categoria", "MTBF", 
    "Vida Útil Restante (h)", "Dias Restantes", 
    "Lead Time (semanas)", "Criticidade", "Status de Manutenção"
]

st.dataframe(
    df[col_display].style.applymap(highlight_status, subset=["Status de Manutenção"]),
    use_container_width=True
)

# Gráfico Visual do Consumo da Vida Útil
st.subheader("📉 Consumo da Vida Útil das Peças (% MTBF)")

fig = go.Figure()

for idx, row in df.iterrows():
    fig.add_trace(go.Bar(
        y=[row["Descrição"]],
        x=[row["% Vida Útil Consumida"]],
        name=row["Descrição"],
        orientation='h',
        text=f"{row['% Vida Útil Consumida']:.1f}% ({row['Vida Útil Restante (h)']}h restantes)",
        textposition='inside'
    ))

fig.update_layout(
    xaxis=dict(range=[0, 100], title="Porcentagem de Vida Útil Consumida (%)"),
    yaxis=dict(title="Componentes"),
    height=350,
    showlegend=False,
    margin=dict(l=20, r=20, t=30, b=20)
)

st.plotly_chart(fig, use_container_width=True)

# Seção de Comunicação Cliente x Fabricante & Planejamento de Parada
st.divider()
st.header("🤝 Módulo de Integração Cliente-Fabricante & Compras")

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📦 Recomendação de Pedidos Automáticos")
    pedidos_necessarios = df[df["Status de Manutenção"] != "🟢 Operação Normal"]
    
    if not pedidos_necessarios.empty:
        st.warning("Atenção! Os seguintes itens necessitam de ação imediata ou emissão de Pedido de Compra devido ao Lead Time:")
        for idx, item in pedidos_necessarios.iterrows():
            st.write(f"- **{item['Descrição']}** (Código SAP: `{item['Código SAP']}`): {item['Status de Manutenção']} | Lead Time: {item['Lead Time (semanas)']} sem.")
            
        if st.button("🚀 Enviar Proposta/Solicitação ao Fabricante"):
            st.success("Solicitação enviada com sucesso para a equipe de suprimentos e fabricante integrados!")
    else:
        st.success("Todos os componentes estão operando dentro das margens de segurança!")

with col_right:
    st.subheader("📅 Planejamento de Parada Programada")
    menor_dias = df["Dias Restantes"].min()
    item_proximo = df.loc[df["Dias Restantes"].idxmin()]
    
    st.info(f"""
    **Próxima parada recomendada em aproximadamente:**  
    🗓️ **{max(0, int(menor_dias))} dias** de operação contínua.
    
    **Componente limitante:** {item_proximo['Descrição']} (Código SAP: {item_proximo['Código SAP']}).
    """)
