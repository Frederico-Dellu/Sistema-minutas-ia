import streamlit as st
import requests
import os
import pandas as pd
from dotenv import load_dotenv

# ==========================================
# 1. TRAVA DE SEGURANÇA E ACESSO
# ==========================================
if "usuario" not in st.session_state or st.session_state["usuario"] is None:
    st.warning("⚠️ Você precisa fazer login no arquivo principal (app.py) para acessar esta página.")
    st.stop()

user = st.session_state["usuario"]

# Trava de Perfil (Apenas Gerente entra aqui)
if user.get("funcao") != "Gerente":
    st.error("⛔ Acesso Restrito. Apenas usuários com perfil de Gerente podem visualizar o Dashboard.")
    st.stop()

# ==========================================
# 2. CONFIGURAÇÕES
# ==========================================
st.set_page_config(page_title="Dashboard Gerencial", layout="wide")
st.title("📊 Dashboard de Gestão de Minutas")
st.write(f"Bem-vindo ao painel de controle, **{user['nome']}**.")

load_dotenv()
URL_SUPABASE = os.getenv("SUPABASE_URL")
KEY_SUPABASE = os.getenv("SUPABASE_KEY")

# ==========================================
# 3. BUSCANDO DADOS NO BANCO (API REST)
# ==========================================
@st.cache_data(ttl=60) # Faz cache dos dados por 60 segundos para o app ficar rápido
def buscar_historico():
    headers = {
        "apikey": KEY_SUPABASE,
        "Authorization": f"Bearer {KEY_SUPABASE}"
    }
    # Traz as minutas ordenadas da mais recente para a mais antiga
    url = f"{URL_SUPABASE}/rest/v1/historico_minutas?select=*&order=created_at.desc"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Erro ao buscar relatórios: {e}")
    return []

# Executa a busca
dados_minutas = buscar_historico()

# ==========================================
# 4. MONTANDO A INTERFACE (MÉTRICAS E TABELAS)
# ==========================================
if not dados_minutas:
    st.info("Nenhuma minuta foi gerada no sistema ainda.")
else:
    # Transforma o JSON do banco em um DataFrame (tabela) do Pandas
    df = pd.DataFrame(dados_minutas)
    
    # Formata a data para o padrão brasileiro
    df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
    
    # Linha de Métricas (Os "Cards" no topo da tela)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Minutas Geradas", len(df))
    with col2:
        # Pega a classe processual mais comum
        classe_comum = df['classe_processual'].mode()[0] if not df.empty else "N/A"
        st.metric("Classe Mais Frequente", classe_comum)
    with col3:
        st.metric("Usuários Ativos", df['usuario_email'].nunique())

    st.divider()

    # Tabela Interativa
    st.subheader("📋 Histórico Detalhado")
    
    # Filtro simples
    termo_busca = st.text_input("🔍 Buscar por e-mail do funcionário ou classe processual:")
    
    if termo_busca:
        # Filtra a tabela baseada no que o gerente digitou
        df_filtrado = df[
            df['usuario_email'].str.contains(termo_busca, case=False, na=False) |
            df['classe_processual'].str.contains(termo_busca, case=False, na=False)
        ]
    else:
        df_filtrado = df

    # Seleciona apenas as colunas que queremos mostrar e renomeia para ficar bonito
    df_exibicao = df_filtrado[['created_at', 'classe_processual', 'usuario_email', 'minuta_final']]
    df_exibicao.columns = ['Data/Hora', 'Classe Processual', 'Responsável', 'Texto da Minuta']

    # Mostra a tabela na tela
    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

    # Botão de Exportação
    st.caption("Você pode exportar a tabela clicando no ícone de download no canto superior direito dela.")