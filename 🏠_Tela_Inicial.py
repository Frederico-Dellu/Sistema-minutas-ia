import streamlit as st
import requests
import os
from dotenv import load_dotenv
from config import gerar_hash_senha, verificar_senha

# Configuração da página (deve ser o primeiro comando)
st.set_page_config(page_title="Login - Sistema de Minutas", layout="centered")

# Carrega variáveis de ambiente
load_dotenv()
URL_SUPABASE = os.getenv("SUPABASE_URL")
KEY_SUPABASE = os.getenv("SUPABASE_KEY")

# ==========================================
# VERIFICAÇÃO DO .ENV
# ==========================================
if not URL_SUPABASE or not KEY_SUPABASE:
    st.error("🚨 ERRO CRÍTICO: O arquivo .env não foi encontrado ou está formatado incorretamente. Verifique se o nome do arquivo não ficou como '.env.txt'.")
    st.stop() # Para o sistema aqui para não dar aquele erro feio de 'None'

# ==========================================
# FUNÇÃO DE LOGIN
# ==========================================
def validar_login(email, senha_plana):
    headers = {"apikey": KEY_SUPABASE, "Authorization": f"Bearer {KEY_SUPABASE}"}
    
    # 1. LGPD: Traz apenas o estritamente necessário. Não transita CPF ou Data de Nascimento aqui.
    # 2. Segurança: Busca só pelo e-mail ativo. Não coloca senha na URL.
    url = f"{URL_SUPABASE}/rest/v1/usuarios?select=id,nome,email,funcao,senha,ativo&email=eq.{email}&ativo=eq.true"
    
    try:
        response = requests.get(url, headers=headers)
        dados = response.json()
        
        # 3. Se achou o e-mail, verifica se a senha bate com o Hash seguro (Bcrypt)
        if response.status_code == 200 and len(dados) > 0:
            usuario = dados[0]
            hash_do_banco = usuario.pop('senha') # Tira a senha da memória por segurança
            
            if verificar_senha(senha_plana, hash_do_banco):
                return usuario # Retorna o usuário limpo, sem a senha
    except Exception:
        pass
    return None

# Gerenciamento de Estado
if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

# ==========================================
# TELA DE LOGIN (Sem barra lateral)
# ==========================================
if st.session_state["usuario"] is None:
    # --- CÓDIGO MÁGICO PARA ESCONDER A BARRA LATERAL ---
    st.markdown("""
        <style>
            [data-testid="collapsedControl"] {display: none;}
            [data-testid="stSidebar"] {display: none;}
        </style>
    """, unsafe_allow_html=True)
    
    st.title("⚖️ Sistema de Minutas - Gabinete")
    st.subheader("Acesso Restrito")
    
    with st.form("login_form"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")
        
        if entrar:
            user_data = validar_login(email, senha)
            if user_data:
                st.session_state["usuario"] = user_data
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")

# ==========================================
# TELA DE BOAS VINDAS (Pós-Login - Barra lateral volta a aparecer)
# ==========================================
else:
    user = st.session_state["usuario"]
    
    # --- TRAVA DE FRONTEND (Esconde o Dashboard no menu) ---
    if user['funcao'] != 'Gerente':
        st.markdown("""
            <style>
                /* Busca o link do Dashboard no menu lateral e esconde */
                [data-testid="stSidebarNav"] a[href*="Dashboard"] {
                    display: none !important;
                }
            </style>
        """, unsafe_allow_html=True)

    st.sidebar.success("Logado com sucesso!")
    st.sidebar.write(f"👤 **{user['nome']}**")
    st.sidebar.write(f"🎖️ {user['funcao']}")
    
    if st.sidebar.button("Sair (Logout)"):
        st.session_state["usuario"] = None
        st.rerun()

    st.title(f"Bem-vindo(a), {user['nome']}! 👋")
    st.write("Utilize o menu lateral para acessar as funcionalidades do sistema.")
    
    if user['funcao'] == 'Gerente':
        st.info("💡 Como Líder, você também tem acesso ao Dashboard de Gestão.")