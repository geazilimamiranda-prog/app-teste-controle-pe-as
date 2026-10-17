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
st.subheader("Monitoramento de Ciclo de Vida, Emissão Automática de OCs e Simulador de Cenários")

# ----------------------------------------------------
# INICIALIZAÇÃO DO ESTADO DA SESSÃO (SESSION STATE)
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
    "Horas da Peça": [7200, 7200, 7200, 7200],  # Horas acumuladas em cada peça individual
    "Data Última Troca": ["Instalação Inicial", "Instalação Inicial", "Instalação Inicial", "Instalação Inicial"]
}

if "df_pecas" not in st.session_state:
    st.session_state["df_pecas"] = pd.DataFrame(data_exemplo)

if "historico_requisicoes" not in st.session_state:
    st.session_state["historico_requisicoes"] = []

# Sidebar - Configurações
st.sidebar.header("📁 Importação de Dados & Parâmetros")

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

# Conversões numéricas de segurança
df["MTBF"] = pd.to_numeric(df["MTBF"], errors="coerce")
df["Lead Time (semanas)"] = pd.to_numeric(df["Lead Time (semanas)"], errors="coerce")
df["Horas da Peça"] = pd.to_numeric(df["Horas da Peça"], errors="coerce")

# Parâmetros de operação do equipamento
st.sidebar.divider()
st.sidebar.header("⏱️ Parâmetros Operacionais Atuais")

regime_diario = st.sidebar.slider(
    "Regime Operacional Real (Horas por Dia):",
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
df["Gatilho Compra (Horas Peça)"] = df["MTBF"] - df["Lead Time (Horas Operacionais)"]

df["Vida Útil Restante (h)"] = df["MTBF"] - df["Horas da Peça"]
df["Horas Restantes para Compra"] = df["Gatilho Compra (Horas Peça)"] - df["Horas da Peça"]
df["Dias Restantes para Compra"] = df["Horas Restantes para Compra"] / regime_diario
df["Dias Restantes para Falha/Troca"] = df["Vida Útil Restante (h)"] / regime_diario

df["% Vida Útil Consumida"] = (df["Horas da Peça"] / df["MTBF"]) * 100
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
m1.metric("Itens Monitorados", len(df))
m2.metric("Ordens de Compra Pendentes", len(df[df["Horas Restantes para Compra"] <= 0]))
m3.metric("Peças Vencidas", len(df[df["Vida Útil Restante (h)"] <= 0]))
m4.metric("Requisições Registradas", len(st.session_state["historico_requisicoes"]))

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Status Detalhado", 
    "🛠️ Reposição & Reset", 
    "🔮 Simulador de Cenários",
    "📅 Planos & Emissão de OCs",
    "📜 Histórico de Requisições"
])

with tab1:
    st.subheader("📋 Tabela Operacional de Monitoramento")
    
    colunas_visiveis = [
        "Código SAP", "Descrição", "MTBF", "Horas da Peça", "Vida Útil Restante (h)", 
        "Lead Time (semanas)", "Data Limite Emissão Ordem Compra", 
        "Data Estimada de Troca/Parada", "Data Última Troca", "Status de Manutenção"
    ]

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
    st.subheader("🛠️ Registrar Substituição de Peça (Reset de Vida Útil)")
    st.markdown("Ao efetuar a troca de um componente, registe aqui para que as horas voltem a contar do zero e o status passe automaticamente para **🟢 Operação Normal**.")
    
    col_reg1, col_reg2 = st.columns(2)
    
    with col_reg1:
        peca_reposicao = st.selectbox("Selecione a Peça Substituída:", df["Descrição"].unique())
        data_troca = st.date_input("Data da Manutenção / Reposição:", datetime.now())
        tecnico_responsavel = st.text_input("Técnico / Responsável:", "Equipe de Manutenção")
        
    with col_reg2:
        observacoes = st.text_area("Observações:", "Substituição preventiva efetuada com sucesso.")
        horas_iniciais_nova_peca = st.number_input("Horas Iniciais da Nova Peça (h):", value=0, min_value=0)

    if st.button("🔄 Confirmar Reposição & Resetar Horas"):
        idx = df[df["Descrição"] == peca_reposicao].index[0]
        st.session_state["df_pecas"].loc[idx, "Horas da Peça"] = horas_iniciais_nova_peca
        st.session_state["df_pecas"].loc[idx, "Data Última Troca"] = data_troca.strftime("%d/%m/%Y")
        
        st.session_state["historico_requisicoes"].append({
            "Data Evento": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "Tipo": "REPOSIÇÃO / MANUTENÇÃO",
            "Código SAP": df.loc[idx, "Código SAP"],
            "Descrição": peca_reposicao,
            "Solicitante / Técnico": tecnico_responsavel,
            "Observação": f"Peça reposta. Horas resetadas para {horas_iniciais_nova_peca}h. Obs: {observacoes}"
        })
        
        st.success(f"✅ Reposição efetuada com sucesso! A vida útil do componente **{peca_reposicao}** foi reiniciada.")
        st.rerun()

with tab3:
    st.subheader("🔮 Simulador de Cenários Operacionais")
    st.markdown("Simule o comportamento do equipamento sob diferentes condições futuras (ex: aumento de turnos, aceleração de desgaste ou alteração de *Lead Time*) sem afetar os dados reais.")

    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        adicionar_horas_sim = st.number_input("Simular avanço de horas de operação (h):", min_value=0, value=1000, step=100)
        novo_regime_sim = st.slider("Simular Regime Diário (h/dia):", min_value=8, max_value=24, value=regime_diario)
    with sim_col2:
        fator_desgaste = st.slider("Fator de Carga / Severidade Operacional:", min_value=0.5, max_value=2.0, value=1.0, step=0.1)

    # Criar DataFrame simulado baseado no atual
    df_sim = df.copy()
    df_sim["Horas Simuladas"] = df_sim["Horas da Peça"] + (adicionar_horas_sim * fator_desgaste)
    df_sim["Vida Útil Restante Simulada (h)"] = df_sim["MTBF"] - df_sim["Horas Simuladas"]
    df_sim["% Consumida Simulada"] = (df_sim["Horas Simuladas"] / df_sim["MTBF"]) * 100
    df_sim["% Consumida Simulada"] = df_sim["% Consumida Simulada"].apply(lambda x: min(100.0, max(0.0, float(x))))

    def status_sim(row):
        if row["Vida Útil Restante Simulada (h)"] <= 0:
            return "🔴 VENCIDO NO CENÁRIO"
        elif row["Vida Útil Restante Simulada (h)"] <= (row["Lead Time (semanas)"] * 6 * novo_regime_sim):
            return "🟡 COMPRA NECESSÁRIA NO CENÁRIO"
        else:
            return "🟢 OK NO CENÁRIO"

    df_sim["Status Simulado"] = df_sim.apply(status_sim, axis=1)

    st.markdown("#### 📊 Resultados da Simulação")
    colunas_sim_display = [
        "Código SAP", "Descrição", "Horas da Peça", "Horas Simuladas", 
        "Vida Útil Restante Simulada (h)", "% Consumida Simulada", "Status Simulado"
    ]
    st.dataframe(df_sim[colunas_sim_display], use_container_width=True)

with tab4:
    st.subheader("📅 Plano de Paradas & Emissão Automática de Requisições")
    st.markdown("Emita ordens de compra de forma automatizada para todos os itens que atingiram o limite do *Lead Time*.")

    df_plano = df.sort_values(by="Vida Útil Restante (h)").copy()
    
    for idx, item in df_plano.iterrows():
        dias_troca = int(item["Dias Restantes para Falha/Troca"])
        
        if dias_troca <= 0:
            st.error(f"🚨 **PARADA IMEDIATA:** Substituir **{item['Descrição']}** (`{item['Código SAP']}`). Limite MTBF atingido.")
        elif dias_troca <= 15:
            st.warning(f"⚠️ **Parada Próxima (~{dias_troca} dias - {item['Data Estimada de Troca/Parada']}):** Substituir **{item['Descrição']}**.")
        else:
            st.success(f"🟢 **Parada Futura (~{dias_troca} dias - {item['Data Estimada de Troca/Parada']}):** Manutenção planeada para **{item['Descrição']}**.")

    st.divider()
    st.subheader("⚡ Painel de Ações de Suprimentos")
    
    pecas_para_compra = df[df["Horas Restantes para Compra"] <= 0]
    
    col_A, col_B = st.columns(2)
    with col_A:
        st.write(f"**Itens que exigem emissão imediata de O.C.:** {len(pecas_para_compra)}")
    with col_B:
        # Botão dedicado e destacado para emissão automática em massa
        if st.button("🚀 Emitir Requisições Automáticas em Massa (Todas as Pendentes)", type="primary"):
            if not pecas_para_compra.empty:
                count = 0
                for _, item in pecas_para_compra.iterrows():
                    st.session_state["historico_requisicoes"].append({
                        "Data Evento": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Tipo": "ORDEM DE COMPRA AUTOMÁTICA",
                        "Código SAP": item["Código SAP"],
                        "Descrição": item["Descrição"],
                        "Solicitante / Técnico": "Sistema Autônomo Indústria 4.0",
                        "Observação": f"Requisição gerada por atingir o Lead Time de {item['Lead Time (semanas)']} semanas. Horas atuais: {item['Horas da Peça']}h."
                    })
                    count += 1
                st.success(f"Sucesso! {count} requisição(ões) de compra foram emitidas automaticamente e registadas no histórico.")
                st.rerun()
            else:
                st.info("Não existem itens pendentes de emissão de O.C. no momento.")

with tab5:
    st.subheader("📜 Histórico de Requisições e Compras (Analytics)")
    st.markdown("Registo centralizado de todas as transações, ordens de compra emitidas e intervenções realizadas. Ideal para auditorias e futuras análises de inteligência de manutenção.")
    
    if len(st.session_state["historico_requisicoes"]) > 0:
        df_hist = pd.DataFrame(st.session_state["historico_requisicoes"])
        st.dataframe(df_hist, use_container_width=True)
        
        csv = df_hist.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Exportar Histórico Completo (CSV)",
            data=csv,
            file_name=f"historico_requisicoes_industria40_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("Ainda não existem requisições ou registos no histórico.")
