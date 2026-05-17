import streamlit as st
import fitz  # PyMuPDF
import requests
import os
import pandas as pd
from dotenv import load_dotenv
from config import CLASSES_PROCESSUAIS

# ==========================================
# 1. TRAVA DE SEGURANÇA E ACESSO (RN001 e RN007)
# ==========================================
if "usuario" not in st.session_state or st.session_state["usuario"] is None:
    st.warning("⚠️ Você precisa fazer login na Tela Inicial para acessar esta página.")
    st.stop()

user = st.session_state["usuario"]

# Trava de Perfil: Apenas Líder/Gerente entra aqui
if user.get("funcao") != "Gerente":
    st.error("⛔ Acesso Restrito. Apenas usuários com perfil de Líder de Gabinete podem gerenciar a base de modelos.")
    st.stop()

# ==========================================
# 2. CONFIGURAÇÕES
# ==========================================
st.set_page_config(page_title="Gestão de Modelos", layout="wide")
st.title("📁 Gestão de Modelos da IA")
st.write("Faça o upload de processos que servirão como **padrão de fundamentação** para o sistema.")

load_dotenv()
URL_SUPABASE = os.getenv("SUPABASE_URL")
KEY_SUPABASE = os.getenv("SUPABASE_KEY")
HEADERS = {"apikey": KEY_SUPABASE, "Authorization": f"Bearer {KEY_SUPABASE}", "Content-Type": "application/json"}

# ==========================================
# 3. UPLOAD E CADASTRO DO NOVO MODELO
# ==========================================
with st.expander("➕ Adicionar Novo Modelo (Upload de PDF)", expanded=True):
    col1, col2 = st.columns(2)
    
    with col1:
        titulo_modelo = st.text_input("Nome/Título do Modelo (Ex: Padrão Desembargador X - Dano Moral)")
        classe_processual = st.selectbox("Vincular à Classe Processual:", CLASSES_PROCESSUAIS)
    
    with col2:
        arquivo_modelo = st.file_uploader("Suba o PDF com a fundamentação padrão", type="pdf")

    if st.button("💾 Salvar Modelo no Banco de Dados"):
        if not titulo_modelo or not arquivo_modelo:
            st.error("Por favor, preencha o título e faça o upload do PDF.")
        else:
            try:
                # Extrai o texto do PDF que o Gerente subiu
                with st.spinner("Extraindo texto do modelo..."):
                    doc = fitz.open(stream=arquivo_modelo.read(), filetype="pdf")
                    texto_modelo = ""
                    for pagina in doc:
                        if len(texto_modelo.strip()) < 50:
                            st.error("🚨 O PDF enviado está vazio ou é um documento escaneado (imagem). A Central de Modelos exige PDFs com texto pesquisável.")
                            st.stop()
                        texto_modelo += pagina.get_text()

                # Prepara os dados para salvar na tabela que criamos
                dados_modelo = {
                    "titulo": titulo_modelo,
                    "classe_processual": classe_processual,
                    "conteudo_abstrato": texto_modelo,
                    "autor_email": user['email']
                }
                
                # Salva no Supabase via API REST
                endpoint = f"{URL_SUPABASE}/rest/v1/modelos_fundamentacao"
                resposta = requests.post(endpoint, headers=HEADERS, json=dados_modelo)
                
                if resposta.status_code == 201:
                    st.success("✅ Modelo cadastrado com sucesso! Ele já pode ser usado pela IA.")
                    # Limpa o cache para atualizar a tabela abaixo automaticamente
                    st.cache_data.clear() 
                else:
                    st.warning(f"Erro ao salvar: {resposta.text}")
                    
            except Exception as e:
                st.error(f"Ocorreu um erro ao processar o PDF: {e}")

st.divider()

# ==========================================
# 4. VISUALIZAR MODELOS EXISTENTES
# ==========================================
st.subheader("📚 Modelos Ativos na Central de Dados")

@st.cache_data(ttl=60)
def buscar_modelos():
    url = f"{URL_SUPABASE}/rest/v1/modelos_fundamentacao?select=created_at,titulo,classe_processual,autor_email&order=created_at.desc"
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            return res.json()
    except:
        return []
    return []

lista_modelos = buscar_modelos()

if not lista_modelos:
    st.info("Nenhum modelo cadastrado ainda.")
else:
    df_modelos = pd.DataFrame(lista_modelos)
    df_modelos['created_at'] = pd.to_datetime(df_modelos['created_at']).dt.strftime('%d/%m/%Y')
    df_modelos.columns = ['Data de Inclusão', 'Título do Modelo', 'Classe Processual', 'Cadastrado por']
    st.dataframe(df_modelos, use_container_width=True, hide_index=True)