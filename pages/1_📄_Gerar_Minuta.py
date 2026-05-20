import streamlit as st
import fitz
import google.generativeai as genai
import requests
import os
import tempfile
from dotenv import load_dotenv
from fpdf import FPDF
from config import CLASSES_PROCESSUAIS
import docx
from io import BytesIO

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
    return genai.GenerativeModel('gemini-2.5-flash')

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
    
    try:
        pdf.add_font("Arial", fname="C:/Windows/Fonts/arial.ttf")
        pdf.set_font("Arial", size=12)
        texto_formatado = texto
    except Exception:
        pdf.set_font("helvetica", size=12)
        texto_formatado = texto.encode('latin-1', 'replace').decode('latin-1')
        
    pdf.multi_cell(0, 7, text=texto_formatado)
    return bytes (pdf.output())

def gerar_arquivo_word(texto):
    doc = docx.Document()
    for linha in texto.split('\n'):
        doc.add_paragraph(linha)
    
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ==========================================
# INTERFACE LATERAL
# ==========================================
with st.sidebar:
    st.write(f"👤 Operador: **{user['nome']}**")
    st.divider()
    st.header("📋 Dados da Minuta")
    opcoes_menu = ["Selecione..."] + CLASSES_PROCESSUAIS
    classe_processual = st.selectbox("Selecione a Classe Processual", opcoes_menu)
    
    if st.button("🔄 Nova Minuta"):
        st.session_state['minuta_atual'] = None
        st.session_state['id_minuta_banco'] = None
        st.rerun()

# ==========================================
# ÁREA PRINCIPAL
# ==========================================
st.subheader("1. Upload do Processo")
# CORREÇÃO: accept_multiple_files=True adicionado para aceitar vários PDFs de uma vez
arquivos_pdf = st.file_uploader("Arraste um ou mais PDFs do recurso aqui", type="pdf", accept_multiple_files=True)

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
# GERAÇÃO (Tratando Lote de Múltiplos PDFs)
# ==========================================
if st.button("🚀 Gerar Relatório/Minuta") and st.session_state['minuta_atual'] is None:
    if not arquivos_pdf:
        st.error("Por favor, suba pelo menos um PDF dos autos do processo.")
    else:
        try:
            texto_processo_completo = ""
            lista_tmp_paths = []
            lista_arquivos_gemini = []

            with st.spinner("Lendo e preparando os documentos (processos escaneados podem levar mais tempo)..."):
                # Loop para processar e criar arquivos temporários de cada PDF enviado
                for idx, arquivo_pdf in enumerate(arquivos_pdf):
                    arquivo_pdf.seek(0)
                    doc = fitz.open(stream=arquivo_pdf.read(), filetype="pdf")
                    texto_arquivo = ""
                    for pagina in doc:
                        texto_arquivo += pagina.get_text()
                    
                    texto_processo_completo += f"\n--- ARQUIVO {idx+1}: {arquivo_pdf.name} ---\n{texto_arquivo}\n"

                    # Salva cópia temporária local de cada arquivo
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        arquivo_pdf.seek(0)
                        tmp_file.write(arquivo_pdf.read())
                        lista_tmp_paths.append(tmp_file.name)

            with st.spinner("IA processando o lote de arquivos e redigindo a minuta..."):
                try:
                    # Configura a IA
                    ia = configurar_ia()
                    
                    # Faz o upload de todos os arquivos para a API de visão do Gemini
                    for path in lista_tmp_paths:
                        arq_g = genai.upload_file(path=path, mime_type="application/pdf")
                        lista_arquivos_gemini.append(arq_g)
                    
                    # Prompt estruturado para múltiplos anexos
                    prompt_completo = f"""
                    Você é um assessor de Desembargador em Câmara Cível. Sua tarefa é redigir uma minuta de relatório processual.
                    
                    REGRAS DE OURO (Siga rigorosamente):
                    1. FATOS: Extraia a narrativa e os pedidos EXCLUSIVAMENTE dos DOCUMENTOS PDF ANEXADOS. Analise o conjunto de arquivos para entender o caso por completo. Não invente ou presuma fatos.
                    2. DIREITO: Utilize a fundamentação jurídica EXCLUSIVAMENTE do 'MODELO DE FUNDAMENTAÇÃO' abaixo.
                    3. ABERTURA: Inicie sempre com: 'Em suas razões recursais, [parte] sustenta que...'.
                    4. VERBOS: Use narra, argumenta, sustenta, aduz, alega.
                    5. REQUERIMENTOS: Tutelas provisórias são sempre listadas como REQUERIMENTOS.
                    6. FECHAMENTO: Encerre o texto com: 'É o relatório.'
                    
                    CLASSE PROCESSUAL: {classe_processual}
                    
                    === MODELO DE FUNDAMENTAÇÃO (DIREITO) ===
                    {conteudo_fundamentacao}
                    """
                    
                    # Envia o Prompt de texto + a lista com todos os arquivos carregados
                    conteudo_para_ia = [prompt_completo] + lista_arquivos_gemini
                    response = ia.generate_content(conteudo_para_ia)
                    
                    st.session_state['minuta_atual'] = response.text
                    
                finally:
                    # FAXINA DE SEGURANÇA E LGPD MULTI-ARQUIVO
                    for arq_g in lista_arquivos_gemini:
                        try:
                            genai.delete_file(arq_g.name)
                        except:
                            pass
                    for path in lista_tmp_paths:
                        if os.path.exists(path):
                            os.remove(path)
            
            # Salvar Histórico Inicial no Supabase
            try:
                headers_insert = HEADERS.copy()
                headers_insert["Prefer"] = "return=representation" 
                
                dados_minuta = {
                    "classe_processual": classe_processual,
                    "texto_processo": texto_processo_completo[:5000] if texto_processo_completo.strip() else "[Lote de PDFs Escaneados]", 
                    "minuta_final": st.session_state['minuta_atual'],
                    "usuario_email": user['email']
                }
                res_db = requests.post(f"{URL_SUPABASE}/rest/v1/historico_minutas", headers=headers_insert, json=dados_minuta)
                
                if res_db.status_code == 201:
                    st.session_state['id_minuta_banco'] = res_db.json()[0]['id'] 
            except Exception:
                pass

            st.rerun() 
            
        except Exception as e:
            st.error(f"Erro técnico ao processar lote: {e}")

# ==========================================
# ÁREA DE EDIÇÃO E VERSIONAMENTO (Aparece após gerar)
# ==========================================
if st.session_state['minuta_atual']:
    st.success("✨ Minuta gerada com sucesso com base no lote de documentos!")
    
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
    
    # Botões de Exportação atualizados com suporte a TXT, PDF e o novo arquivo Word DOCX
    col_txt, col_pdf, col_word = st.columns(3)
    
    with col_txt:
        st.download_button("📥 Baixar em .TXT", data=st.session_state['minuta_atual'], file_name=f"Minuta_{classe_processual}.txt")
    
    with col_pdf:
        pdf_bytes = gerar_arquivo_pdf(st.session_state['minuta_atual'])
        st.download_button("📄 Baixar em .PDF", data=pdf_bytes, file_name=f"Minuta_{classe_processual}.pdf", mime="application/pdf")
    
    with col_word:
        word_buffer = gerar_arquivo_word(st.session_state['minuta_atual'])
        st.download_button(
            label="💙 Baixar em .DOCX",
            data=word_buffer,
            file_name=f"Minuta_{classe_processual}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )