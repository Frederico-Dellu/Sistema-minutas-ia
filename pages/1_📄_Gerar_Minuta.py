import streamlit as st
import fitz
import google.generativeai as genai
import requests
import os
import tempfile
from dotenv import load_dotenv
from fpdf import FPDF
from config import CLASSES_PROCESSUAIS

# ==========================================
# 1. TRAVA DE SEGURANÇA E ACESSO
# ==========================================
if "usuario" not in st.session_state or st.session_state["usuario"] is None:
    st.warning("⚠️ Você precisa fazer login na Tela Inicial para acessar esta página.")
    st.stop()

load_dotenv()
URL_SUPABASE = os.getenv("SUPABASE_URL")
KEY_SUPABASE = os.getenv("SUPABASE_KEY")
CHAVE_GEMINI = os.getenv("GEMINI_KEY")
HEADERS = {"apikey": KEY_SUPABASE, "Authorization": f"Bearer {KEY_SUPABASE}", "Content-Type": "application/json"}

user = st.session_state["usuario"]

st.set_page_config(page_title="Gerar Minuta", layout="wide")
st.title("⚖️ Elaborador de Minutas")

# ==========================================
# INICIALIZAÇÃO DE VARIÁVEIS DE SESSÃO (Memória)
# ==========================================
if 'minuta_atual' not in st.session_state:
    st.session_state['minuta_atual'] = None
if 'id_minuta_banco' not in st.session_state:
    st.session_state['id_minuta_banco'] = None

# ==========================================
# FUNÇÕES DE APOIO
# ==========================================
def configurar_ia():
    genai.configure(api_key=CHAVE_GEMINI)
    return genai.GenerativeModel('gemini-1.5-flash')

def buscar_modelos_por_classe(classe):
    url = f"{URL_SUPABASE}/rest/v1/modelos_fundamentacao?classe_processual=eq.{classe}&select=titulo,conteudo_abstrato"
    try:
        response = requests.get(url, headers={"apikey": KEY_SUPABASE, "Authorization": f"Bearer {KEY_SUPABASE}"})
        if response.status_code == 200:
            return response.json()
    except Exception:
        return []
    return []

def gerar_arquivo_pdf(texto):
    pdf = FPDF()
    pdf.add_page()
    
    # Carrega a fonte Arial nativa do Windows para dar suporte total ao UTF-8
    # Isso evita que símbolos jurídicos como '§' ou acentos virem '?'
    try:
        pdf.add_font("Arial", fname="C:/Windows/Fonts/arial.ttf")
        pdf.set_font("Arial", size=12)
        texto_formatado = texto
    except Exception:
        # Fallback de segurança caso o sistema mude de servidor/sistema operacional
        pdf.set_font("helvetica", size=12)
        texto_formatado = texto.encode('latin-1', 'replace').decode('latin-1')
        
    # No fpdf2, usando uma fonte TTF, a quebra de linha com texto longo funciona nativamente em UTF-8
    pdf.multi_cell(0, 7, text=texto_formatado)
    return pdf.output()

# ==========================================
# INTERFACE LATERAL
# ==========================================
with st.sidebar:
    st.write(f"👤 Operador: **{user['nome']}**")
    st.divider()
    st.header("📋 Dados da Minuta")
    opcoes_menu = ["Selecione..."] + CLASSES_PROCESSUAIS
    classe_processual = st.selectbox("Selecione a Classe Processual", opcoes_menu)
    
    # Botão para limpar a tela e começar de novo
    if st.button("🔄 Nova Minuta"):
        st.session_state['minuta_atual'] = None
        st.session_state['id_minuta_banco'] = None
        st.rerun()

# ==========================================
# ÁREA PRINCIPAL
# ==========================================
st.subheader("1. Upload do Processo")
arquivo_pdf = st.file_uploader("Arraste o PDF do recurso aqui", type="pdf")

st.subheader("2. Seleção de Fundamentação")
if classe_processual == "Selecione...":
    st.info("👈 Por favor, selecione uma Classe Processual no menu lateral para carregar os modelos.")
    st.stop()
modelos_encontrados = buscar_modelos_por_classe(classe_processual)

if not modelos_encontrados:
    st.error(f"⚠️ Nenhum modelo oficial foi encontrado para a classe '{classe_processual}'.")
    st.stop()

dict_modelos = {m['titulo']: m['conteudo_abstrato'] for m in modelos_encontrados}
modelo_selecionado = st.selectbox("Selecione o modelo padrão aprovado:", list(dict_modelos.keys()))
conteudo_fundamentacao = dict_modelos[modelo_selecionado]

# ==========================================
# GERAÇÃO (Só roda se ainda não tiver minuta na memória)
# ==========================================
if st.button("🚀 Gerar Relatório/Minuta") and st.session_state['minuta_atual'] is None:
    if not arquivo_pdf:
        st.error("Por favor, suba o PDF dos autos do processo.")
    else:
        try:
            with st.spinner("Lendo documento (processos escaneados podem levar alguns segundos a mais)..."):
                # 1. Tenta extrair o texto em string (para salvar no banco depois)
                doc = fitz.open(stream=arquivo_pdf.read(), filetype="pdf")
                texto_processo = ""
                for pagina in doc:
                    texto_processo += pagina.get_text()

                # 2. Cria um arquivo temporário no servidor para enviar à IA
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    arquivo_pdf.seek(0) # Volta o ponteiro de leitura pro começo
                    tmp_file.write(arquivo_pdf.read())
                    tmp_file_path = tmp_file.name

            with st.spinner("IA processando os autos e redigindo a minuta..."):
                try:
                    # Configura a chave ANTES de fazer qualquer coisa
                    genai.configure(api_key=CHAVE_GEMINI)
                    arquivo_gemini = genai.upload_file(path=tmp_file_path, mime_type="application/pdf")
                    ia = genai.GenerativeModel('gemini-1.5-flash')
                    
                    # 4. Novo Prompt: Agora ele sabe que deve ler o arquivo anexado
                    prompt_completo = f"""
                    Você é um assessor de Desembargador em Câmara Cível. Sua tarefa é redigir uma minuta de relatório processual.
                    
                    REGRAS DE OURO (Siga rigorosamente):
                    1. FATOS: Extraia a narrativa e os pedidos EXCLUSIVAMENTE do DOCUMENTO PDF ANEXADO. Não invente ou presuma fatos.
                    2. DIREITO: Utilize a fundamentação jurídica EXCLUSIVAMENTE do 'MODELO DE FUNDAMENTAÇÃO' abaixo.
                    3. ABERTURA: Inicie sempre com: 'Em suas razões recursais, [parte] sustenta que...'.
                    4. VERBOS: Use narra, argumenta, sustenta, aduz, alega.
                    5. REQUERIMENTOS: Tutelas provisórias são sempre listadas como REQUERIMENTOS.
                    6. FECHAMENTO: Encerre o texto com: 'É o relatório.'
                    
                    CLASSE PROCESSUAL: {classe_processual}
                    
                    === MODELO DE FUNDAMENTAÇÃO (DIREITO) ===
                    {conteudo_fundamentacao}
                    """
                    
                    ia = configurar_ia()
                    
                    # 5. Passamos uma LISTA para a IA: O Prompt de texto + O Arquivo PDF
                    response = ia.generate_content([prompt_completo, arquivo_gemini])
                    st.session_state['minuta_atual'] = response.text
                    
                finally:
                    # 6. FAXINA DE SEGURANÇA E LGPD (Muito Importante!)
                    # Apaga o arquivo lá do Google
                    if 'arquivo_gemini' in locals():
                        genai.delete_file(arquivo_gemini.name)
                    # Apaga o arquivo temporário do nosso servidor
                    if os.path.exists(tmp_file_path):
                        os.remove(tmp_file_path)
            
            # Salvar Histórico Inicial e pegar o ID
            try:
                headers_insert = HEADERS.copy()
                headers_insert["Prefer"] = "return=representation" 
                
                # Se for escaneado, texto_processo será vazio, mas a IA leu a imagem perfeitamente!
                dados_minuta = {
                    "classe_processual": classe_processual,
                    "texto_processo": texto_processo[:5000] if texto_processo else "[PDF Escaneado - Lote de Imagens]", 
                    "minuta_final": st.session_state['minuta_atual'],
                    "usuario_email": user['email']
                }
                res_db = requests.post(f"{URL_SUPABASE}/rest/v1/historico_minutas", headers=headers_insert, json=dados_minuta)
                
                if res_db.status_code == 201:
                    st.session_state['id_minuta_banco'] = res_db.json()[0]['id'] 
            except Exception as e_bd:
                pass

            st.rerun() 
            
        except Exception as e:
            st.error(f"Erro técnico: {e}")

# ==========================================
# ÁREA DE EDIÇÃO E VERSIONAMENTO (Aparece após gerar)
# ==========================================
if st.session_state['minuta_atual']:
    st.success("✨ Minuta gerada! Revise e ajuste abaixo.")
    
    st.subheader("3. Revisão Final e Versionamento")
    texto_editado = st.text_area("Faça os ajustes manuais necessários antes de baixar:", 
                                 value=st.session_state['minuta_atual'], height=400)
    
    if texto_editado != st.session_state['minuta_atual']:
        st.session_state['minuta_atual'] = texto_editado

    if st.button("💾 Salvar Edição no Histórico"):
        if st.session_state['id_minuta_banco']:
            url_update = f"{URL_SUPABASE}/rest/v1/historico_minutas?id=eq.{st.session_state['id_minuta_banco']}"
            res_patch = requests.patch(url_update, headers=HEADERS, json={"minuta_final": st.session_state['minuta_atual']})
            if res_patch.status_code in [200, 204]:
                st.success("✅ A versão final editada foi salva no banco de dados!")
            else:
                st.error("Erro ao atualizar o banco.")
        else:
            st.warning("O ID da minuta não foi encontrado no banco.")

    st.divider()
    
    col_txt, col_pdf = st.columns(2)
    with col_txt:
        st.download_button("📥 Baixar em .TXT", data=st.session_state['minuta_atual'], file_name=f"Minuta_{classe_processual}.txt")
    with col_pdf:
        pdf_bytes = gerar_arquivo_pdf(st.session_state['minuta_atual'])
        st.download_button(
            "📄 Baixar em .PDF", 
            data=pdf_bytes, 
            file_name=f"Minuta_{classe_processual}.pdf", 
            mime="application/pdf"
        )