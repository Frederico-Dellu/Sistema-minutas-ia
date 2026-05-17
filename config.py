import bcrypt

CLASSES_PROCESSUAIS = [
    "Apelação Cível", "Agravo de Instrumento", "Embargos de Declaração", 
    "Habeas Corpus", "Recurso Inominado", "Mandado de Segurança",
    "Agravo Interno", "Ação Rescisória"
]

def gerar_hash_senha(senha_plana):
    """Gera um hash Bcrypt forte com Salt automático."""
    return bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_senha(senha_plana, hash_salvo):
    """Compara a senha digitada com o hash do banco."""
    return bcrypt.checkpw(senha_plana.encode('utf-8'), hash_salvo.encode('utf-8'))