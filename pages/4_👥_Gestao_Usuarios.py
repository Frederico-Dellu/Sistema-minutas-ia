import streamlit as st
import requests
import os
import pandas as pd
import datetime
from dotenv import load_dotenv
from config import gerar_hash_senha  # Importação da criptografia de senha

# ==========================================
# 1. TRAVA DE SEGURANÇA E ACESSO
# ==========================================
if "usuario" not in st.session_state or st.session_state["usuario"] is None:
    st.warning("⚠️ Você precisa fazer login na Tela Inicial para acessar esta página.")
    st.stop()

user = st.session_state["usuario"]

if user.get("funcao") != "Gerente":
    st.error("⛔ Acesso Restrito. Apenas Líderes de Gabinete podem gerenciar usuários.")
    st.stop()

# ==========================================
# 2. CONFIGURAÇÕES E CONEXÃO
# ==========================================
st.set_page_config(page_title="Gestão de Usuários", layout="wide")
st.title("👥 Controle de Usuários e Acesso")

load_dotenv()
URL_SUPABASE = os.getenv("SUPABASE_URL")
KEY_SUPABASE = os.getenv("SUPABASE_KEY")
HEADERS = {
    "apikey": KEY_SUPABASE,
    "Authorization": f"Bearer {KEY_SUPABASE}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}
ENDPOINT = f"{URL_SUPABASE}/rest/v1/usuarios"

# ==========================================
# FUNÇÃO DE BUSCA
# ==========================================
def buscar_todos_usuarios():
    try:
        res = requests.get(f"{ENDPOINT}?select=*", headers=HEADERS)
        if res.status_code == 200:
            return res.json()
    except:
        return []
    return []

usuarios_banco = buscar_todos_usuarios()

# ==========================================
# 3. INTERFACE - ABAS (CADASTRO E EDIÇÃO)
# ==========================================
aba_listar, aba_cadastrar, aba_editar = st.tabs(["📋 Lista de Usuários", "➕ Cadastrar Usuário", "✏️ Editar / Inativar"])

# --- ABA 1: LISTAR ---
with aba_listar:
    if not usuarios_banco:
        st.info("Nenhum usuário cadastrado.")
    else:
        df = pd.DataFrame(usuarios_banco)
        df['Status'] = df['ativo'].apply(lambda x: "🟢 Ativo" if x else "🔴 Inativo")
        
        if 'data_nascimento' in df.columns:
            df['data_nascimento'] = pd.to_datetime(df['data_nascimento']).dt.strftime('%d/%m/%Y')
        
        df_exibicao = df[['nome', 'email', 'cpf', 'funcao', 'data_nascimento', 'Status']]
        df_exibicao.columns = ['Nome', 'E-mail', 'CPF', 'Cargo/Função', 'Data de Nascimento', 'Status de Acesso']
        st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

# --- ABA 2: CADASTRAR (CREATE) ---
with aba_cadastrar:
    with st.form("form_cadastro_user"):
        st.subheader("Novo Cadastro")
        col1, col2 = st.columns(2)
        with col1:
            novo_nome = st.text_input("Nome Completo")
            novo_email = st.text_input("E-mail corporativo")
            nova_senha = st.text_input("Senha de Acesso", type="password")
        with col2:
            novo_cpf = st.text_input("CPF (com pontuação)", max_chars=14, placeholder="000.000.000-00")
            nova_funcao = st.selectbox("Cargo / Função", ["Funcionario", "Gerente"])
            
            nova_data = st.date_input(
                "Data de Nascimento", 
                value=None,
                min_value=datetime.date(1930, 1, 1),
                max_value=datetime.date.today(),
                format="DD/MM/YYYY"
            )

        btn_cadastrar = st.form_submit_button("Salvar Usuário")
        
        if btn_cadastrar:
            if not novo_nome or not novo_email or not nova_senha or not novo_cpf:
                st.error("Por favor, preencha todos os campos obrigatórios.")
            else:
                payload = {
                    "nome": novo_nome,
                    "email": novo_email,
                    "senha": gerar_hash_senha(nova_senha),
                    "cpf": novo_cpf,
                    "funcao": nova_funcao,
                    "data_nascimento": str(nova_data) if nova_data else None,
                    "ativo": True
                }
                response = requests.post(ENDPOINT, headers=HEADERS, json=payload)
                if response.status_code == 201:
                    st.success(f"🎉 {novo_nome} cadastrado com sucesso!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Erro ao cadastrar: {response.text}")

# --- ABA 3: EDITAR / INATIVAR (UPDATE) ---
with aba_editar:
    if not usuarios_banco:
        st.info("Não há usuários para editar.")
    else:
        dict_usuarios = {u['email']: u for u in usuarios_banco}
        
        # Mostra o Nome na tela, mas o sistema guarda o Email
        usuario_selecionado = st.selectbox(
            "Selecione o usuário que deseja modificar:", 
            list(dict_usuarios.keys()), 
            format_func=lambda email: dict_usuarios[email]['nome']
        )
        
        user_dados = dict_usuarios[usuario_selecionado]
        
        with st.form("form_edicao_user"):
            st.subheader(f"Editando: {user_dados['nome']}")
            col1, col2 = st.columns(2)
            with col1:
                edit_nome = st.text_input("Nome", value=user_dados['nome'])
                edit_email = st.text_input("E-mail", value=user_dados['email'])
                edit_funcao = st.selectbox("Função", ["Funcionario", "Gerente"], index=["Funcionario", "Gerente"].index(user_dados['funcao']))
            with col2:
                edit_cpf = st.text_input("CPF (com pontuação)", value=user_dados['cpf'], max_chars=14)
                
                data_atual_convertida = None
                if user_dados.get('data_nascimento'):
                    try:
                        data_atual_convertida = datetime.datetime.strptime(user_dados['data_nascimento'], "%Y-%m-%d").date()
                    except:
                        data_atual_convertida = None

                edit_data = st.date_input(
                    "Data de Nascimento",
                    value=data_atual_convertida,
                    min_value=datetime.date(1930, 1, 1),
                    max_value=datetime.date.today(),
                    format="DD/MM/YYYY"
                )
                
                edit_status = st.radio("Status de Acesso ao Sistema:", ["Ativo (Liberado)", "Inativo (Bloqueado)"], 
                                       index=0 if user_dados['ativo'] else 1)

            btn_atualizar = st.form_submit_button("Confirmar Alterações")
            
            if btn_atualizar:
                payload_update = {
                    "nome": edit_nome,
                    "email": edit_email,
                    "cpf": edit_cpf,
                    "funcao": edit_funcao,
                    "data_nascimento": str(edit_data) if edit_data else None,
                    "ativo": True if edit_status == "Ativo (Liberado)" else False
                }
                
                url_update = f"{ENDPOINT}?id=eq.{user_dados['id']}"
                response_patch = requests.patch(url_update, headers=HEADERS, json=payload_update)
                
                if response_patch.status_code in [200, 204]:
                    st.success("✅ Dados do usuário atualizados com sucesso!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Erro ao atualizar: {response_patch.text}")