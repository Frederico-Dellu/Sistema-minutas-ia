import streamlit as st
import requests
import os
import fitz  # PyMuPDF
import docx
import time  # <-- MODIFICAÇÃO: Importação da biblioteca de tempo
from dotenv import load_dotenv
from config import CLASSES_PROCESSUAIS

# ==========================================
# 1. TRAVA DE SEGURANÇA E ACESSO
# ==========================================
if "usuario" not in st.session_state or st.session_state["usuario"] is None:
    st.warning("⚠️ Você precisa fazer login na Tela Inicial para acessar esta página.")
    st.stop()

user = st.session_state["usuario"]

if user.get("funcao") != "Gerente":
    st.error("⛔ Acesso Restrito. Apenas Líderes de Gabinete podem gerenciar modelos de fundamentação.")
    st.stop()

# ==========================================
# 2. CONFIGURAÇÕES E CONEXÃO
# ==========================================
st.set_page_config(page_title="Gestão de Modelos", layout="wide")
st.title("📁 Central de Modelos de Fundamentação")

load_dotenv()
URL_SUPABASE = os.getenv("SUPABASE_URL")
KEY_SUPABASE = os.getenv("SUPABASE_KEY")
HEADERS = {
    "apikey": KEY_SUPABASE,
    "Authorization": f"Bearer {KEY_SUPABASE}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}
ENDPOINT = f"{URL_SUPABASE}/rest/v1/modelos_fundamentacao"

# Função para buscar os modelos cadastrados
def buscar_todos_modelos():
    try:
        res = requests.get(f"{ENDPOINT}?select=*", headers=HEADERS)
        if res.status_code == 200:
            return res.json()
    except:
        return []
    return []

modelos_banco = buscar_todos_modelos()

# ==========================================
# 3. INTERFACE EM ABAS
# ==========================================
aba_listar, aba_cadastrar = st.tabs(["📋 Modelos Cadastrados", "➕ Adicionar Novo Modelo"])

# --- ABA 1: LISTAR MODELOS EXISTENTES ---
with aba_listar:
    if not modelos_banco:
        st.info("Nenhum modelo cadastrado na central.")
    else:
        for m in modelos_banco:
            with st.expander(f"📘 {m['classe_processual']} - {m['titulo']}"):
                st.text_area("Conteúdo da Fundamentação:", value=m['conteudo_abstrato'], height=200, disabled=True, key=f"ver_{m['id']}")
                
                if st.button("🗑️ Excluir Modelo", key=f"del_{m['id']}"):
                    res_del = requests.delete(f"{ENDPOINT}?id=eq.{m['id']}", headers=HEADERS)
                    if res_del.status_code in [200, 204]:
                        st.success("Modelo removido com sucesso!")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"Erro ao deletar do banco: {res_del.text}")

# --- ABA 2: CADASTRAR NOVO MODELO (PDF/WORD) ---
with aba_cadastrar:
    with st.form("form_cadastro_modelo", clear_on_submit=True):
        st.subheader("Cadastrar Nova Peça de Fundamentação")
        
        classe_selecionada = st.selectbox("Classe Processual do Modelo", CLASSES_PROCESSUAIS)
        titulo_modelo = st.text_input("Título do Modelo (ex: Dano Moral - Inscrição Indevida)")
        
        arquivo_modelo = st.file_uploader(
            "Suba o arquivo com a fundamentação padrão (Texto em PDF ou Word .docx)", 
            type=["pdf", "docx"]
        )
        
        btn_salvar = st.form_submit_button("💾 Salvar Modelo no Banco de Dados")
        
        if btn_salvar:
            if not titulo_modelo:
                st.error("❌ Por favor, insira um título para o modelo.")
            elif not arquivo_modelo:
                st.error("❌ Por favor, faça o upload de um arquivo PDF ou DOCX.")
            else:
                try:
                    texto_modelo = ""
                    arquivo_modelo.seek(0)
                    
                    with st.spinner("Extraindo texto do arquivo enviado..."):
                        if arquivo_modelo.name.endswith(".pdf"):
                            doc = fitz.open(stream=arquivo_modelo.read(), filetype="pdf")
                            for pagina in doc:
                                texto_modelo += pagina.get_text()
                        
                        elif arquivo_modelo.name.endswith(".docx"):
                            doc_word = docx.Document(arquivo_modelo)
                            for para in doc_word.paragraphs:
                                if para.text.strip():
                                    texto_modelo += para.text + "\n"
                    
                    if len(texto_modelo.strip()) < 50:
                        st.error("🚨 O arquivo enviado está praticamente vazio ou não possui texto extraível.")
                    else:
                        payload = {
                            "classe_processual": classe_selecionada,
                            "titulo": titulo_modelo,
                            "conteudo_abstrato": texto_modelo.strip()
                        }
                        
                        response = requests.post(ENDPOINT, headers=HEADERS, json=payload)
                        
                        if response.status_code in [200, 201]:
                            # MODIFICAÇÃO: Mensagem grande, chamativa e com pausa dramática
                            st.success(f"🎉 SUCESSO! O modelo '{titulo_modelo}' foi gravado no banco de dados!")
                            time.sleep(3)  # O sistema vai aguardar 3 segundos com a mensagem verde na tela
                            st.rerun()     # Depois de 3 segundos, recarrega a página de forma limpa
                        else:
                            st.error(f"❌ Erro na API do Banco de Dados ({response.status_code}): {response.text}")
                            
                except Exception as e:
                    st.error(f"💥 Erro técnico inesperado no processamento: {e}")