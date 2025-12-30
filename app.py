from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, flash, session, send_file, Response
import os
import logging
from logging.handlers import RotatingFileHandler
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import database
from datetime import datetime
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import functools
import pandas as pd
import unicodedata
import io
import shutil
import tempfile

app = Flask(__name__)

# Sinaliza execução em modo debug
DEBUG_MODE = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

# Configuração sensível via variáveis de ambiente para uso em produção
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'mude-esta-chave')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'static/uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_MB', '16')) * 1024 * 1024  # MB → bytes

# Cookies de sessão: por padrão seguros em produção
_session_secure_env = os.getenv('SESSION_COOKIE_SECURE')
app.config['SESSION_COOKIE_SECURE'] = (_session_secure_env.lower() == 'true') if _session_secure_env else (not DEBUG_MODE)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
app.config['PREFERRED_URL_SCHEME'] = 'https' if not DEBUG_MODE else 'http'

# Abort early if running in production with weak secret
if not DEBUG_MODE and app.config['SECRET_KEY'] == 'mude-esta-chave':
    raise RuntimeError('SECRET_KEY precisa ser definido por variável de ambiente em produção.')

# Respeitar cabeçalhos de proxy (ex.: Nginx) quando habilitado
if os.getenv('TRUST_PROXY_HEADERS', 'true').lower() == 'true':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)


def configure_logging():
    """Configura logging com rotação para ambiente de produção."""
    if DEBUG_MODE:
        return
    os.makedirs('logs', exist_ok=True)
    handler = RotatingFileHandler('logs/app.log', maxBytes=2 * 1024 * 1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Evita duplicar handlers se já configurado
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)


configure_logging()

# Rate limiting (usar memória por padrão; configure RATELIMIT_STORAGE_URI para redis/memcached)
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.getenv('RATELIMIT_STORAGE_URI', 'memory://'),
    default_limits=[os.getenv('DEFAULT_RATE_LIMIT', '200 per hour')],
    headers_enabled=True,
)

# Criar pastas de upload se não existirem
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
for folder in ['instalacoes', 'equipamentos', 'areas_edificaveis', 'sistemas_seguranca', 
               'equipamentos_unitizacao', 'viaturas', 'geradores', 'empilhadeiras', 
               'pessoal']:
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], folder), exist_ok=True)

# Extensões permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Middleware de autenticação
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('nivel_acesso') != 'admin':
            flash('Acesso negado. Somente administradores podem acessar esta funcionalidade.', 'error')
            return redirect(url_for('index'))
        return view(**kwargs)
    return wrapped_view

@app.teardown_appcontext
def close_connection(exception):
    database.close_db()


@app.route('/foto/<int:foto_id>/delete', methods=['POST'])
@login_required
def delete_foto(foto_id):
    db = database.get_db()
    try:
        row = db.execute('SELECT caminho_arquivo FROM fotos WHERE id = ?', (foto_id,)).fetchone()
        if not row:
            return jsonify(success=False, message='Foto não encontrada'), 404
        caminho = row['caminho_arquivo']
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], caminho.replace('/', os.sep))
        db.execute('DELETE FROM fotos WHERE id = ?', (foto_id,))
        db.commit()
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                print('[DEBUG delete_foto] removido do disco', full_path)
            except Exception as err_rm:
                print('[WARN delete_foto] falha ao remover do disco', full_path, err_rm)
        return jsonify(success=True)
    except Exception as e:
        db.rollback()
        print('[ERROR delete_foto]', e)
        return jsonify(success=False, message=str(e)), 500

# Lista de órgãos provedores permitidos
ORGÃOS_PROVEDORES = {
    "1º DEPÓSITO DE SUPRIMENTO": "1º D SUP",
    "2º BATALHÃO DE SUPRIMENTO": "2º B SUP",
    "3º BATALHÃO DE SUPRIMENTO": "3º B SUP",
    "4º DEPÓSITO DE SUPRIMENTO": "4º D SUP",
    "5º BATALHÃO DE SUPRIMENTO": "5º B SUP",
    "6º DEPÓSITO DE SUPRIMENTO": "6º D SUP",
    "7º DEPÓSITO DE SUPRIMENTO": "7º D SUP",
    "8º BATALHÃO DE SUPRIMENTO DE SELVA": "8º B SUP SL",
    "9º BATALHÃO DE SUPRIMENTO": "9º B SUP",
    "10º DEPÓSITO DE SUPRIMENTO": "10º D SUP",
    "11º DEPÓSITO DE SUPRIMENTO": "11º D SUP",
    "12º BATALHÃO DE SUPRIMENTO": "12º B SUP",
    "1º BATALHÃO LOGÍSTICO DE SELVA": "1º B LOG SL",
    "17º BATALHÃO LOGÍSTICO DE SELVA": "17º B LOG SL",
    "16ª BASE LOGÍSTICA": "16ª BA LOG",
    "DEPÓSITO DE SUBSISTÊNCIA DE SANTA MARIA": "DSSM",
    "DEPÓSITO DE SUBSISTÊNCIA DE SANTO ÂNGELO": "DSSA",
    "DEPÓSITO CENTRAL DE MUNIÇÃO": "DC MUN",
    "13ª COMPANHIA DEPÓSITO DE ARMAMENTO E MUNIÇÃO": "13ª CIA DAM",
    "CENTRO LOGÍSTICO DE MÍSSEIS E FOGUETES": "C LOG MSL FGT",
    "BATALHÃO DE DOBRAGEM, MANUTENÇÃO DE PÁRA-QUEDAS E SUPRIMENTO PELO AR": "B DOMPSA"
}

# Mapa normalizado (sem acentos/caixa) para comparações tolerantes
def _normalize_orgao_nome(valor: str) -> str:
    if valor is None:
        return ''
    texto = ''.join(c for c in unicodedata.normalize('NFKD', str(valor)) if not unicodedata.combining(c))
    texto = texto.upper().replace('º', '').replace('ª', '')
    texto = ' '.join(texto.split())
    return texto

ORGAOS_PROVEDORES_NORM = {_normalize_orgao_nome(k): v for k, v in ORGÃOS_PROVEDORES.items()}

# Listas canônicas usadas no cadastro de pessoal
ARMA_QUADROS = [
    'Infantaria', 'Cavalaria', 'Artilharia', 'Engenharia', 'Comunicações',
    'Material Bélico', 'Saúde', 'Administração', 'Intendência', 'Técnico',
    'QCO', 'QAO', 'QEM', 'Aviação', 'Manutenção de Comunicações', 'Topografia'
]

ESPECIALIDADES = [
    'Transporte', 'Mecânica', 'Eletricidade', 'Manutenção de Veículos', 'Eletrônica',
    'Enfermagem', 'Medicina', 'Veterinária', 'Comunicações', 'Municiamento', 'Culinária',
    'Administrativo', 'Saneamento', 'Suprimento', 'Contabilidade', 'Informática', 'Direito', 'Farmácia', 'Dentista', 'Mecânica Automotiva', 'Mecânica de Armamento', 'Mecânico Operador', 'Outro'
]

# Carregar dados do CODOM.xlsx
def carregar_dados_codom():
    """Carrega os dados do arquivo CODOM.xlsx"""
    try:
        # Lê o arquivo Excel
        df = pd.read_excel('CODOM.xlsx', engine='openpyxl')
        
        # Criar dicionário de mapeamento para OMs
        dados_oms = {}
        # Criar dicionário de mapeamento para UG/CODOM por sigla
        dados_ug_codom = {}
        # Criar dicionário de mapeamento CODOM -> Subordinação (se presente na planilha)
        dados_subordinacao = {}
        
        for _, row in df.iterrows():
            sigla = str(row.get('SIGLA', '')).strip()
            codom = str(row.get('CODOM', '')).strip()
            ug = str(row.get('UG', '')).strip()
            subordinacao = ''
            # Tentar ler coluna 'SUBORDINACAO' ou 'SUBORDINAÇÃO' (variações na planilha)
            if 'SUBORDINACAO' in row.index:
                subordinacao = str(row.get('SUBORDINACAO', '')).strip()
            elif 'SUBORDINAÇÃO' in row.index:
                subordinacao = str(row.get('SUBORDINAÇÃO', '')).strip()
            
            # Adicionar à lista de OMs para seleção
            if sigla and sigla != 'nan' and sigla not in dados_oms:
                dados_oms[sigla] = {
                    'CODOM': codom,
                    'UG': ug,
                    'SUBORDINACAO': subordinacao
                }
            
            # Mapear UG/CODOM/Subordinação por sigla (último valor encontrado)
            if sigla and sigla != 'nan':
                dados_ug_codom[sigla] = {
                    'CODOM': codom,
                    'UG': ug,
                    'SUBORDINACAO': subordinacao
                }
            
            # Mapear CODOM -> Subordinação para buscas diretas
            if codom and codom != 'nan' and subordinacao:
                dados_subordinacao[codom] = subordinacao
        
        return dados_oms, dados_ug_codom, dados_subordinacao
    except Exception as e:
        print(f"Erro ao carregar CODOM.xlsx: {e}")
        return {}, {}, {}


def normalizar_sigla_chave(valor):
    """Normaliza siglas para comparações tolerantes."""
    if valor is None:
        return ''
    texto = ''.join(c for c in unicodedata.normalize('NFKD', str(valor)) if not unicodedata.combining(c))
    texto = texto.upper().replace('º', '').replace('ª', '')
    texto = ' '.join(texto.split())
    return texto


def carregar_dados_vinculo_efetivo():
    """Carrega vínculos (Vinculo_OM) e efetivos (Efetivo) do arquivo Dados.xlsx."""
    try:
        xl = pd.ExcelFile('Dados.xlsx', engine='openpyxl')
        df_vinculo = xl.parse('Vinculo_OM')
        df_efetivo = xl.parse('Efetivo')
    except Exception as e:
        print(f"Erro ao carregar Dados.xlsx: {e}")
        return {}, {}, {}

    vinculo_por_op = {}
    efetivo_por_om = {}
    rm_por_op = {}

    # Mapeia OMs apoiadas por OP (usando chave normalizada)
    for _, row in df_vinculo.iterrows():
        om_sigla = str(row.get('SIGLA OM', '')).strip()
        op_sigla = str(row.get('SIGLA OM VINC OP', '')).strip()
        cod_om = str(row.get('COD OM', '')).strip()
        ug_om = str(row.get('COD UG', '')).strip()
        codom_op = str(row.get('COD OM VINC OP', '')).strip()
        ug_op = str(row.get('COD UG VINC OP', '')).strip()
        rm = str(row.get('RM', '')).strip()

        chave_op = normalizar_sigla_chave(op_sigla)
        if chave_op and om_sigla:
            vinculo_por_op.setdefault(chave_op, []).append({
                'sigla': om_sigla,
                'codom': cod_om,
                'ug': ug_om,
                'codom_op': codom_op,
                'ug_op': ug_op
            })

        if chave_op and rm:
            rm_por_op[chave_op] = rm

    # Mapeia efetivo médio por OM (chave normalizada)
    for _, row in df_efetivo.iterrows():
        om_sigla = str(row.get('SIGLA OM', '')).strip()
        chave_om = normalizar_sigla_chave(om_sigla)
        efetivo = row.get('MEDIA EFETIVO ATIVA')
        if chave_om and pd.notna(efetivo):
            try:
                efetivo_por_om[chave_om] = int(float(efetivo))
            except Exception:
                continue

    return vinculo_por_op, efetivo_por_om, rm_por_op

# Carregar dados ao iniciar
DADOS_OMS, DADOS_UG_CODOM, DADOS_SUBORDINACAO = carregar_dados_codom()
LISTA_OMS = sorted(DADOS_OMS.keys())
DADOS_VINCULO_OP, DADOS_EFETIVO_OM, DADOS_RM_OP = carregar_dados_vinculo_efetivo()

# Mapa canônico de postos/graduações para exibição ordenada
POSTO_MAP = {
    'general_exercito': 'General de Exército',
    'general_divisao': 'General de Divisão',
    'general_brigada': 'General de Brigada',
    'coronel': 'Cel',
    'tenente_coronel': 'TC',
    'major': 'Major',
    'capitao': 'Capitão',
    'primeiro_tenente': '1º Tenente',
    'segundo_tenente': '2º Tenente',
    'aspirante': 'Aspirante',
    'subtenente': 'Subtenente',
    'primeiro_sargento': '1º Sargento',
    'segundo_sargento': '2º Sargento',
    'terceiro_sargento': '3º Sargento',
    'cabo': 'Cabo',
    'soldado': 'Sd',
    'taifeiro': 'Taifeiro',
    'civil_superior': 'Servidor Superior',
    'civil_tecnico': 'Servidor Técnico',
    'civil_administrativo': 'Servidor Administrativo',
    'outro': 'Outro'
}
POSTO_KEYS = list(POSTO_MAP.keys())

# Função para obter nome do posto
def get_posto_display(posto_key):
    return POSTO_MAP.get(posto_key, posto_key)

def get_sigla_orgao(nome):
    if not nome:
        return ''
    return ORGÃOS_PROVEDORES.get(nome, '') or ORGAOS_PROVEDORES_NORM.get(_normalize_orgao_nome(nome), '')


def find_orgao_existente(nome, sigla):
    """Busca um órgão existente por nome ou sigla, de forma tolerante."""
    db = database.get_db()
    nome_norm = _normalize_orgao_nome(nome)
    sigla_norm = (sigla or '').strip().upper()

    row = db.execute('SELECT * FROM orgao_provedor WHERE nome = ? OR sigla = ? LIMIT 1', (nome, sigla)).fetchone()
    if row:
        return row

    rows = db.execute('SELECT * FROM orgao_provedor').fetchall()
    for r in rows:
        if _normalize_orgao_nome(r['nome']) == nome_norm:
            return r
        if (r['sigla'] or '').strip().upper() == sigla_norm:
            return r
    return None


def get_oms_apoiadas_por_op(sigla_op):
    chave = normalizar_sigla_chave(sigla_op)
    return DADOS_VINCULO_OP.get(chave, [])


def get_dados_automaticos_op(sigla_op):
    alvo_sigla = normalizar_sigla_chave(sigla_op)
    if not alvo_sigla:
        return {
            'oms_apoiadas': [],
            'oms_detalhes': [],
            'efetivo_total': 0,
            'efetivos_por_om': {},
            'subordinacao': ''
        }

    oms = get_oms_apoiadas_por_op(sigla_op)
    efetivo_total = 0
    efetivos_por_om = {}
    oms_detalhes = []

    for om in oms:
        sigla_om = (om.get('sigla') or '').strip()
        if not sigla_om:
            continue

        chave_om = normalizar_sigla_chave(sigla_om)
        efetivo_val = DADOS_EFETIVO_OM.get(chave_om)
        if efetivo_val is not None:
            try:
                efetivo_val = int(efetivo_val)
            except Exception:
                efetivo_val = 0
            efetivos_por_om[sigla_om] = efetivo_val
            efetivo_total += efetivo_val

        detalhes = dict(om)
        detalhes['sigla'] = sigla_om
        dados_codom = DADOS_UG_CODOM.get(sigla_om) or DADOS_UG_CODOM.get(chave_om) or {}
        detalhes.update(dados_codom)
        oms_detalhes.append(detalhes)

    subordinacao = ''
    dados_op = DADOS_UG_CODOM.get(sigla_op) or DADOS_UG_CODOM.get(alvo_sigla) or {}
    subordinacao = dados_op.get('SUBORDINACAO') or dados_op.get('SUBORDINAÇÃO') or ''
    if not subordinacao:
        subordinacao = DADOS_RM_OP.get(alvo_sigla, '')

    return {
        'oms_apoiadas': [om.get('sigla') for om in oms if om.get('sigla')],
        'oms_detalhes': oms_detalhes,
        'efetivo_total': efetivo_total,
        'efetivos_por_om': efetivos_por_om,
        'subordinacao': subordinacao
    }

# Função para obter UG e CODOM baseado na sigla (MELHORADA)
def get_ug_codom(sigla):
    # Normaliza usando helper que remove acentos e espaços duplicados
    sigla_normalizada = normalizar_sigla_chave(sigla)

    for key, value in DADOS_UG_CODOM.items():
        key_normalizada = normalizar_sigla_chave(key)
        if sigla_normalizada == key_normalizada:
            return value
        if sigla_normalizada in key_normalizada or key_normalizada in sigla_normalizada:
            return value

    return {'UG': '', 'CODOM': ''}

# Adicione ao contexto do template
@app.context_processor
def utility_processor():
    return dict(
        get_posto_display=get_posto_display,
        get_sigla_orgao=get_sigla_orgao,
        get_ug_codom=get_ug_codom,
        ORGÃOS_PROVEDORES=ORGÃOS_PROVEDORES,
        DADOS_OMS=DADOS_OMS,
        DADOS_UG_CODOM=DADOS_UG_CODOM,
        DADOS_SUBORDINACAO=DADOS_SUBORDINACAO,
        LISTA_OMS=LISTA_OMS,
        POSTO_MAP=POSTO_MAP,
        POSTO_KEYS=POSTO_KEYS,
        ARMA_QUADROS=ARMA_QUADROS,
        ESPECIALIDADES=ESPECIALIDADES,
        now=datetime.now()
    )

# Rota para buscar UG/CODOM via AJAX
@app.route('/api/buscar_ug_codom')
def api_buscar_ug_codom():
    sigla = request.args.get('sigla', '')
    resultado = get_ug_codom(sigla)
    return jsonify(resultado)

# Helper para obter subordinação por CODOM
def get_subordinacao_by_codom(codom):
    return DADOS_SUBORDINACAO.get(str(codom).strip()) if codom else None

# Rota para buscar Subordinação via CODOM
@app.route('/api/buscar_subordinacao')
def api_buscar_subordinacao():
    codom = request.args.get('codom', '')
    subordinacao = get_subordinacao_by_codom(codom)
    return jsonify({'subordinacao': subordinacao or ''})


@app.route('/api/op/dados_automaticos')
def api_op_dados_automaticos():
    sigla_op = request.args.get('sigla_op', '')
    if not sigla_op:
        return jsonify({'oms_apoiadas': [], 'oms_detalhes': [], 'efetivo_total': 0, 'efetivos_por_om': {}, 'subordinacao': ''})

    dados = get_dados_automaticos_op(sigla_op)
    return jsonify(dados)

# Rota de login
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit(os.getenv('LOGIN_RATE_LIMIT', '5 per minute'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = database.get_db()
        user = db.execute('SELECT * FROM usuarios WHERE username = ?', (username,)).fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            if not user['ativo']:
                flash('Usuário inativo. Entre em contato com o administrador.', 'error')
                return redirect(url_for('login'))
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['nome_completo'] = user['nome_completo']
            session['nome_guerra'] = user['nome_guerra']
            session['nivel_acesso'] = user['nivel_acesso']
            session['orgao_provedor'] = user['orgao_provedor']
            
            # Atualizar último acesso
            db.execute('UPDATE usuarios SET ultimo_acesso = ? WHERE id = ?', 
                      (datetime.now(), user['id']))
            db.commit()
            
            flash(f'Login realizado com sucesso! Bem-vindo, {user["nome_guerra"] or user["nome_completo"]}', 'success')
            return redirect(url_for('index'))
        
        flash('Usuário ou senha inválidos', 'error')
    
    return render_template('login.html')

# Rota de logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema', 'info')
    return redirect(url_for('login'))


@app.route('/orgao/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def excluir_orgao(id):
    """Exclui um órgão provedor e todos os registros dependentes (apenas admin)."""
    db = database.get_db()

    def delete_with_ids(query_base, ids):
        if not ids:
            return
        placeholders = ','.join(['?'] * len(ids))
        db.execute(f"{query_base} ({placeholders})", ids)

    try:
        orgao = db.execute('SELECT id, nome FROM orgao_provedor WHERE id = ?', (id,)).fetchone()
        if not orgao:
            flash('Órgão Provedor não encontrado.', 'error')
            return redirect(url_for('index'))

        # Instalacoes e subitens
        inst_ids = [r['id'] for r in db.execute('SELECT id FROM instalacoes WHERE orgao_provedor_id = ?', (id,)).fetchall()]
        if inst_ids:
            ph_inst = ','.join(['?'] * len(inst_ids))
            emp_ids = [r['id'] for r in db.execute(f'SELECT id FROM empilhadeiras WHERE instalacao_id IN ({ph_inst})', inst_ids).fetchall()]
            sis_ids = [r['id'] for r in db.execute(f'SELECT id FROM sistemas_seguranca WHERE instalacao_id IN ({ph_inst})', inst_ids).fetchall()]
            eq_ids = [r['id'] for r in db.execute(f'SELECT id FROM equipamentos_unitizacao WHERE instalacao_id IN ({ph_inst})', inst_ids).fetchall()]

            delete_with_ids("DELETE FROM fotos WHERE tabela_origem = 'empilhadeira' AND registro_id IN", emp_ids)
            delete_with_ids("DELETE FROM fotos WHERE tabela_origem = 'sistema_seguranca' AND registro_id IN", sis_ids)
            delete_with_ids("DELETE FROM fotos WHERE tabela_origem = 'equipamento_unitizacao' AND registro_id IN", eq_ids)
            delete_with_ids("DELETE FROM fotos WHERE tabela_origem = 'instalacao' AND registro_id IN", inst_ids)

            delete_with_ids('DELETE FROM empilhadeiras WHERE instalacao_id IN', inst_ids)
            delete_with_ids('DELETE FROM sistemas_seguranca WHERE instalacao_id IN', inst_ids)
            delete_with_ids('DELETE FROM equipamentos_unitizacao WHERE instalacao_id IN', inst_ids)
            delete_with_ids('DELETE FROM instalacoes WHERE id IN', inst_ids)

        # Geradores
        ger_ids = [r['id'] for r in db.execute('SELECT id FROM geradores WHERE orgao_provedor_id = ?', (id,)).fetchall()]
        delete_with_ids("DELETE FROM fotos WHERE tabela_origem = 'gerador' AND registro_id IN", ger_ids)
        db.execute('DELETE FROM geradores WHERE orgao_provedor_id = ?', (id,))

        # Viaturas
        via_ids = [r['id'] for r in db.execute('SELECT id FROM viaturas WHERE orgao_provedor_id = ?', (id,)).fetchall()]
        delete_with_ids("DELETE FROM fotos WHERE tabela_origem = 'viatura' AND registro_id IN", via_ids)
        db.execute('DELETE FROM viaturas WHERE orgao_provedor_id = ?', (id,))

        # Fotos da área edificável
        db.execute("DELETE FROM fotos WHERE tabela_origem = 'area_edificavel' AND registro_id = ?", (id,))

        # Energia e pessoal
        db.execute('DELETE FROM energia_eletrica WHERE orgao_provedor_id = ?', (id,))
        db.execute('DELETE FROM pessoal WHERE orgao_provedor_id = ?', (id,))

        # Orgao
        db.execute('DELETE FROM orgao_provedor WHERE id = ?', (id,))
        db.commit()
        flash(f"Órgão Provedor '{orgao['nome']}' excluído com sucesso.", 'success')
    except Exception as e:
        db.rollback()
        flash(f'Erro ao excluir cadastro: {e}', 'error')

    return redirect(url_for('index'))

# Rota para corrigir o perfil do admin
@app.route('/corrigir_admin')
def corrigir_admin():
    db = database.get_db()
    
    # Verificar e atualizar o usuário admin
    admin = db.execute('SELECT * FROM usuarios WHERE username = ?', ('admin',)).fetchone()
    
    if admin:
        # Atualizar perfil para admin
        db.execute('UPDATE usuarios SET nivel_acesso = ? WHERE username = ?', ('admin', 'admin'))
        db.commit()
        flash('Perfil do admin corrigido para Administrador!', 'success')
    else:
        # Criar usuário admin com perfil correto
        senha_hash = generate_password_hash('admin123')
        db.execute('''
            INSERT INTO usuarios (username, password_hash, nome_completo, nome_guerra, 
                                 posto_graduacao, email, nivel_acesso, ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('admin', senha_hash, 'Administrador do Sistema', 'Admin', 
              'Administrador', 'admin@sistema.com', 'admin', 1))
        db.commit()
        flash('Usuário admin criado com perfil de Administrador!', 'success')
    
    return redirect(url_for('index'))

# Criar usuário administrador inicial
def criar_usuario_admin():
    db = database.get_db()
    admin = db.execute('SELECT * FROM usuarios WHERE username = ?', ('admin',)).fetchone()
    if not admin:
        senha_hash = generate_password_hash('admin123')
        db.execute('''
            INSERT INTO usuarios (username, password_hash, nome_completo, nome_guerra, 
                                 posto_graduacao, email, nivel_acesso, ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('admin', senha_hash, 'Administrador do Sistema', 'Admin', 
              'Administrador', 'admin@sistema.com', 'admin', 1))
        db.commit()
        print("✓ Usuário admin criado. Login: admin / Senha: admin123 (Perfil: Administrador)")

@app.route('/')
@login_required
def index():
    db = database.get_db()
    try:
        user_id = session['user_id']
        nivel_acesso = session['nivel_acesso']
        
        if nivel_acesso == 'admin':
            # Admin vê todos os órgãos
            try:
                orgaos_rows = db.execute('''
                    SELECT o.*, u.username as criado_por_nome 
                    FROM orgao_provedor o
                    LEFT JOIN usuarios u ON o.criado_por = u.id
                    ORDER BY o.data_cadastro DESC
                ''').fetchall()
            except Exception as e:
                print(f"Erro na consulta: {e}")
                # Fallback se houver erro
                orgaos_rows = db.execute('SELECT * FROM orgao_provedor ORDER BY data_cadastro DESC').fetchall()

            # Converter sqlite3.Row para dict e enriquecer com contagem de OMs
            orgaos = []
            for r in orgaos_rows:
                d = dict(r)
                historico_txt = (d.get('historico') or '').replace('\n', ',')
                oms_list = [s.strip() for s in historico_txt.split(',') if s.strip()]
                d['oms_count'] = len(oms_list)
                d['efetivo_atendimento'] = d.get('efetivo_atendimento') or 0

                # Se não há histórico ou efetivo salvo, tenta preencher com dados automáticos por sigla
                if (d['oms_count'] == 0 or d['efetivo_atendimento'] == 0) and (d.get('sigla') or d.get('nome')):
                    auto = get_dados_automaticos_op(d.get('sigla') or d.get('nome'))
                    if d['oms_count'] == 0:
                        d['oms_count'] = len(auto.get('oms_apoiadas') or [])
                    if d['efetivo_atendimento'] == 0:
                        d['efetivo_atendimento'] = auto.get('efetivo_total', 0) or 0

                orgaos.append(d)

            # Contar total de órgãos
            total_orgaos = db.execute('SELECT COUNT(*) as total FROM orgao_provedor').fetchone()['total']

            # Agregados para análises
            analiticos = {}
            try:
                emp_rows = db.execute('''
                    SELECT i.orgao_provedor_id as op_id,
                           COUNT(e.id) as total_emp,
                           SUM(COALESCE(i.capacidade_toneladas, 0)) as cap_estoque
                    FROM instalacoes i
                    LEFT JOIN empilhadeiras e ON e.instalacao_id = i.id
                    GROUP BY i.orgao_provedor_id
                ''').fetchall()
                analiticos['empilhadeiras'] = {r['op_id']: {'total': r['total_emp'], 'cap_estoque': r['cap_estoque'] or 0} for r in emp_rows}
            except Exception as e:
                print('Erro agregando empilhadeiras:', e)
                analiticos['empilhadeiras'] = {}

            try:
                sis_rows = db.execute('''
                    SELECT i.orgao_provedor_id as op_id, COUNT(s.id) as total
                    FROM sistemas_seguranca s
                    JOIN instalacoes i ON s.instalacao_id = i.id
                    GROUP BY i.orgao_provedor_id
                ''').fetchall()
                analiticos['sistemas'] = {r['op_id']: r['total'] for r in sis_rows}
            except Exception as e:
                print('Erro agregando sistemas:', e)
                analiticos['sistemas'] = {}

            try:
                eq_rows = db.execute('''
                    SELECT i.orgao_provedor_id as op_id, COUNT(eq.id) as total
                    FROM equipamentos_unitizacao eq
                    JOIN instalacoes i ON eq.instalacao_id = i.id
                    GROUP BY i.orgao_provedor_id
                ''').fetchall()
                analiticos['equipamentos'] = {r['op_id']: r['total'] for r in eq_rows}
            except Exception as e:
                print('Erro agregando equipamentos:', e)
                analiticos['equipamentos'] = {}

            try:
                via_rows = db.execute('''
                    SELECT orgao_provedor_id as op_id,
                           COUNT(*) as total,
                           COALESCE(SUM(capacidade_carga_kg),0) as cap_total,
                           COALESCE(SUM(CASE WHEN LOWER(especializacao) LIKE '%frigo%' THEN capacidade_carga_kg ELSE 0 END),0) as cap_frigo,
                           COALESCE(SUM(CASE WHEN LOWER(especializacao) LIKE '%frigo%' THEN 0 ELSE capacidade_carga_kg END),0) as cap_seco
                    FROM viaturas
                    GROUP BY orgao_provedor_id
                ''').fetchall()
                analiticos['viaturas'] = {
                    r['op_id']: {
                        'total': r['total'],
                        'cap_total': r['cap_total'],
                        'cap_frigo': r['cap_frigo'],
                        'cap_seco': r['cap_seco']
                    } for r in via_rows
                }
            except Exception as e:
                print('Erro agregando viaturas:', e)
                analiticos['viaturas'] = {}

            try:
                bau_rows = db.execute('''
                    SELECT orgao_provedor_id as op_id,
                           SUM(CASE WHEN LOWER(especializacao) LIKE '%bau%' AND LOWER(especializacao) NOT LIKE '%frigo%' THEN 1 ELSE 0 END) as bau_seco_total,
                           SUM(CASE WHEN LOWER(especializacao) LIKE '%bau%' AND LOWER(especializacao) NOT LIKE '%frigo%' AND situacao = 'operacional' THEN 1 ELSE 0 END) as bau_seco_operacional,
                           SUM(CASE WHEN LOWER(especializacao) LIKE '%bau%' AND LOWER(especializacao) NOT LIKE '%frigo%' AND situacao = 'em_manutencao' THEN 1 ELSE 0 END) as bau_seco_manutencao,
                           SUM(CASE WHEN LOWER(especializacao) LIKE '%bau%' AND LOWER(especializacao) NOT LIKE '%frigo%' AND situacao IN ('inoperante','baixada') THEN 1 ELSE 0 END) as bau_seco_inoperante,
                           SUM(CASE WHEN LOWER(especializacao) LIKE '%bau%' AND LOWER(especializacao) LIKE '%frigo%' THEN 1 ELSE 0 END) as bau_frigo_total,
                           SUM(CASE WHEN LOWER(especializacao) LIKE '%bau%' AND LOWER(especializacao) LIKE '%frigo%' AND situacao = 'operacional' THEN 1 ELSE 0 END) as bau_frigo_operacional,
                           SUM(CASE WHEN LOWER(especializacao) LIKE '%bau%' AND LOWER(especializacao) LIKE '%frigo%' AND situacao = 'em_manutencao' THEN 1 ELSE 0 END) as bau_frigo_manutencao,
                           SUM(CASE WHEN LOWER(especializacao) LIKE '%bau%' AND LOWER(especializacao) LIKE '%frigo%' AND situacao IN ('inoperante','baixada') THEN 1 ELSE 0 END) as bau_frigo_inoperante
                    FROM viaturas
                    WHERE LOWER(tipo_veiculo) LIKE 'vte%'
                    GROUP BY orgao_provedor_id
                ''').fetchall()
                analiticos['viaturas_bau'] = {
                    r['op_id']: {
                        'bau_seco': {
                            'total': r['bau_seco_total'] or 0,
                            'operacional': r['bau_seco_operacional'] or 0,
                            'manutencao': r['bau_seco_manutencao'] or 0,
                            'inoperante': r['bau_seco_inoperante'] or 0
                        },
                        'bau_frigo': {
                            'total': r['bau_frigo_total'] or 0,
                            'operacional': r['bau_frigo_operacional'] or 0,
                            'manutencao': r['bau_frigo_manutencao'] or 0,
                            'inoperante': r['bau_frigo_inoperante'] or 0
                        }
                    } for r in bau_rows
                }
            except Exception as e:
                print('Erro agregando VTE baus:', e)
                analiticos['viaturas_bau'] = {}

            try:
                pes_rows = db.execute('''
                    SELECT orgao_provedor_id as op_id, COALESCE(SUM(quantidade),0) as total
                    FROM pessoal
                    GROUP BY orgao_provedor_id
                ''').fetchall()
                analiticos['pessoal'] = {r['op_id']: r['total'] for r in pes_rows}
            except Exception as e:
                print('Erro agregando pessoal:', e)
                analiticos['pessoal'] = {}

            try:
                pes_posto_rows = db.execute('''
                    SELECT orgao_provedor_id as op_id, posto_graduacao, COALESCE(SUM(quantidade),0) as total
                    FROM pessoal
                    GROUP BY orgao_provedor_id, posto_graduacao
                ''').fetchall()
                pessoal_por_posto = {}
                for r in pes_posto_rows:
                    op_id = r['op_id']
                    posto_key = r['posto_graduacao'] or 'outro'
                    pessoal_por_posto.setdefault(op_id, {})[posto_key] = r['total'] or 0
                analiticos['pessoal_por_posto'] = pessoal_por_posto
            except Exception as e:
                print('Erro agregando pessoal por posto:', e)
                analiticos['pessoal_por_posto'] = {}

            try:
                ger_rows = db.execute('''
                    SELECT orgao_provedor_id as op_id, COUNT(*) as total
                    FROM geradores
                    GROUP BY orgao_provedor_id
                ''').fetchall()
                analiticos['geradores'] = {r['op_id']: r['total'] for r in ger_rows}
            except Exception as e:
                print('Erro agregando geradores:', e)
                analiticos['geradores'] = {}

            try:
                ger_detalhe_rows = db.execute('''
                    SELECT orgao_provedor_id as op_id,
                           COUNT(*) as total,
                           COALESCE(SUM(capacidade_kva),0) as cap_kva,
                           SUM(CASE WHEN situacao = 'operacional' THEN 1 ELSE 0 END) as operacional,
                           SUM(CASE WHEN situacao = 'em_manutencao' THEN 1 ELSE 0 END) as manutencao,
                           SUM(CASE WHEN situacao = 'baixada' THEN 1 ELSE 0 END) as baixada
                    FROM geradores
                    GROUP BY orgao_provedor_id
                ''').fetchall()
                analiticos['geradores_resumo'] = {
                    r['op_id']: {
                        'total': r['total'] or 0,
                        'cap_kva': r['cap_kva'] or 0,
                        'operacional': r['operacional'] or 0,
                        'manutencao': r['manutencao'] or 0,
                        'baixada': r['baixada'] or 0
                    } for r in ger_detalhe_rows
                }
            except Exception as e:
                print('Erro agregando geradores (detalhe):', e)
                analiticos['geradores_resumo'] = {}

            try:
                ins_rows = db.execute('''
                    SELECT orgao_provedor_id as op_id, COUNT(*) as total
                    FROM instalacoes
                    GROUP BY orgao_provedor_id
                ''').fetchall()
                analiticos['instalacoes'] = {r['op_id']: r['total'] for r in ins_rows}
            except Exception as e:
                print('Erro agregando instalacoes:', e)
                analiticos['instalacoes'] = {}

            try:
                energia_rows = db.execute('''
                    SELECT orgao_provedor_id as op_id, dimensionamento_adequado, capacidade_total_kva
                    FROM energia_eletrica
                    GROUP BY orgao_provedor_id
                ''').fetchall()
                analiticos['energia'] = {r['op_id']: {'dimensionamento': r['dimensionamento_adequado'], 'capacidade_kva': r['capacidade_total_kva']} for r in energia_rows}
            except Exception as e:
                print('Erro agregando energia:', e)
                analiticos['energia'] = {}

            try:
                sis_dep_rows = db.execute('''
                    SELECT i.orgao_provedor_id as op_id,
                           COUNT(DISTINCT i.id) as depositos_total,
                           COUNT(DISTINCT CASE WHEN s.id IS NOT NULL THEN i.id END) as depositos_com_sis,
                           COUNT(s.id) as sistemas_total,
                           SUM(CASE WHEN LOWER(COALESCE(s.situacao,'')) = 'operacional' THEN 1 ELSE 0 END) as sis_operacional,
                           SUM(CASE WHEN LOWER(COALESCE(s.situacao,'')) = 'em_manutencao' THEN 1 ELSE 0 END) as sis_manutencao,
                           SUM(CASE WHEN LOWER(COALESCE(s.situacao,'')) = 'inoperante' THEN 1 ELSE 0 END) as sis_inoperante
                    FROM instalacoes i
                    LEFT JOIN sistemas_seguranca s ON s.instalacao_id = i.id
                    WHERE LOWER(i.tipo_instalacao) LIKE '%deposit%'
                    GROUP BY i.orgao_provedor_id
                ''').fetchall()
                analiticos['sistemas_depositos'] = {}
                for r in sis_dep_rows:
                    dep_total = r['depositos_total'] or 0
                    dep_com = r['depositos_com_sis'] or 0
                    analiticos['sistemas_depositos'][r['op_id']] = {
                        'depositos_total': dep_total,
                        'depositos_com_sistema': dep_com,
                        'depositos_sem_sistema': max(dep_total - dep_com, 0),
                        'sistemas_total': r['sistemas_total'] or 0,
                        'operacional': r['sis_operacional'] or 0,
                        'manutencao': r['sis_manutencao'] or 0,
                        'inoperante': r['sis_inoperante'] or 0
                    }
            except Exception as e:
                print('Erro agregando sistemas de seguranca por deposito:', e)
                analiticos['sistemas_depositos'] = {}

            try:
                vert_rows = db.execute('''
                    SELECT i.orgao_provedor_id as op_id,
                           LOWER(COALESCE(i.tipo_instalacao, '')) as tipo_instalacao,
                           LOWER(COALESCE(i.verticalizacao, '')) as verticalizacao
                    FROM instalacoes i
                    WHERE LOWER(i.tipo_instalacao) LIKE 'deposito_cl%'
                ''').fetchall()

                def map_cl(tipo_val: str) -> str:
                    tipo = tipo_val or ''
                    for num in ['10','9','8','7','6','5','4','3','2','1']:
                        if f"cl{num}" in tipo:
                            return f"CL{num}"
                    return ''

                vert_map = {}
                vert_list = []
                for r in vert_rows:
                    cl_key = map_cl(r['tipo_instalacao'])
                    if not cl_key:
                        continue
                    vert_flag = (r['verticalizacao'] or '').startswith('vertical')
                    entry = vert_map.setdefault(r['op_id'], {}).setdefault(cl_key, {
                        'verticalizado': 0,
                        'nao_verticalizado': 0,
                        'total': 0
                    })
                    if vert_flag:
                        entry['verticalizado'] += 1
                    else:
                        entry['nao_verticalizado'] += 1
                    entry['total'] += 1

                for op_id, data in vert_map.items():
                    for cl_key, entry in data.items():
                        total = entry.get('total', 0) or 0
                        vert = entry.get('verticalizado', 0) or 0
                        nao = entry.get('nao_verticalizado', 0) or 0
                        perc = (vert * 100 / total) if total else 0
                        vert_list.append({
                            'op_id': op_id,
                            'cl': cl_key,
                            'total': total,
                            'verticalizado': vert,
                            'nao_verticalizado': nao,
                            'perc': perc
                        })

                analiticos['verticalizacao_depositos'] = vert_map
                analiticos['verticalizacao_lista'] = vert_list
            except Exception as e:
                print('Erro agregando verticalizacao de depositos:', e)
                analiticos['verticalizacao_depositos'] = {}
                analiticos['verticalizacao_lista'] = []

            try:
                frigo_deficit = []
                for org in orgaos:
                    cap_frigo = (org.get('capacidade_total_toneladas_seco') or 0)
                    cons_frigo = (org.get('consumo_frigorificados_mensal') or 0)
                    area_disp = (org.get('area_edificavel_disponivel') or 0)
                    cobertura = (cap_frigo / cons_frigo) if cons_frigo else 0

                    # Considera déficit apenas quando existe consumo declarado e cobertura < 4 FC
                    if cons_frigo and cobertura < 4:
                        frigo_deficit.append({
                            'id': org.get('id'),
                            'sigla': org.get('sigla') or org.get('nome'),
                            'cap_frigo': cap_frigo,
                            'cons_frigo': cons_frigo,
                            'cobertura': cobertura,
                            'area_disp': area_disp,
                            'tem_area': area_disp > 0
                        })

                # Ordena do pior atendimento para o melhor
                analiticos['frigo_deficit'] = sorted(frigo_deficit, key=lambda x: x['cobertura'])
            except Exception as e:
                print('Erro agregando déficit de frigorificados:', e)
                analiticos['frigo_deficit'] = []

            try:
                emp_sit_rows = db.execute('''
                    SELECT i.orgao_provedor_id as op_id,
                           LOWER(COALESCE(e.situacao,'')) as situacao,
                           COALESCE(SUM(COALESCE(e.quantidade,1)),0) as total
                    FROM empilhadeiras e
                    JOIN instalacoes i ON i.id = e.instalacao_id
                    GROUP BY i.orgao_provedor_id, LOWER(COALESCE(e.situacao,''))
                ''').fetchall()
                emp_por_situacao = {}
                for r in emp_sit_rows:
                    op_id = r['op_id']
                    emp_por_situacao.setdefault(op_id, {})[r['situacao'] or 'indefinida'] = r['total'] or 0

                dep_rows = db.execute('''
                    SELECT orgao_provedor_id as op_id, COUNT(*) as total
                    FROM instalacoes
                    WHERE LOWER(tipo_instalacao) LIKE '%deposit%'
                    GROUP BY orgao_provedor_id
                ''').fetchall()
                dep_por_op = {r['op_id']: r['total'] or 0 for r in dep_rows}

                analiticos['empilhadeiras_situacao'] = {
                    op_id: {
                        'situacoes': emp_por_situacao.get(op_id, {}),
                        'depositos': dep_por_op.get(op_id, 0)
                    } for op_id in set(list(emp_por_situacao.keys()) + list(dep_por_op.keys()))
                }
            except Exception as e:
                print('Erro agregando empilhadeiras por situacao:', e)
                analiticos['empilhadeiras_situacao'] = {}
            
            return render_template('index.html', orgaos=orgaos, total_orgaos=total_orgaos, nivel_acesso=nivel_acesso, analiticos=analiticos)
        
        else:  # Cadastrador ou Visualizador
            # Buscar o órgão do usuário
            usuario = db.execute('SELECT orgao_provedor FROM usuarios WHERE id = ?', (user_id,)).fetchone()
            
            if not usuario or not usuario['orgao_provedor']:
                flash('Você não está vinculado a um órgão provedor.', 'error')
                return render_template('index.html', orgaos=[], nivel_acesso=nivel_acesso)
            
            # Buscar apenas o órgão do usuário
            orgao = db.execute('''
                SELECT * FROM orgao_provedor 
                WHERE nome = ?
            ''', (usuario['orgao_provedor'],)).fetchone()
            
            orgaos = []
            if orgao:
                d = dict(orgao)
                historico_txt = (d.get('historico') or '').replace('\n', ',')
                oms_list = [s.strip() for s in historico_txt.split(',') if s.strip()]
                d['oms_count'] = len(oms_list)
                d['efetivo_atendimento'] = d.get('efetivo_atendimento') or 0

                if (d['oms_count'] == 0 or d['efetivo_atendimento'] == 0) and (d.get('sigla') or d.get('nome')):
                    auto = get_dados_automaticos_op(d.get('sigla') or d.get('nome'))
                    if d['oms_count'] == 0:
                        d['oms_count'] = len(auto.get('oms_apoiadas') or [])
                    if d['efetivo_atendimento'] == 0:
                        d['efetivo_atendimento'] = auto.get('efetivo_total', 0) or 0

                orgaos = [d]
            return render_template('index.html', orgaos=orgaos, nivel_acesso=nivel_acesso)
            
    except Exception as e:
        flash(f'Erro ao carregar dados: {str(e)}', 'error')
        return render_template('index.html', orgaos=[], nivel_acesso=session.get('nivel_acesso', 'visualizador'))

# Rota para o painel administrativo
@app.route('/admin')
@login_required
@admin_required
def admin():
    """Painel administrativo"""
    db = database.get_db()
    
    # Estatísticas
    total_usuarios = db.execute('SELECT COUNT(*) as total FROM usuarios').fetchone()['total']
    total_orgaos = db.execute('SELECT COUNT(*) as total FROM orgao_provedor').fetchone()['total']
    usuarios_ativos = db.execute('SELECT COUNT(*) as total FROM usuarios WHERE ativo = 1').fetchone()['total']
    
    # Últimos cadastros
    ultimos_orgaos = db.execute('''
        SELECT o.*, u.username as criado_por 
        FROM orgao_provedor o 
        LEFT JOIN usuarios u ON o.criado_por = u.id 
        ORDER BY o.data_cadastro DESC 
        LIMIT 10
    ''').fetchall()
    
    # Últimos usuários
    ultimos_usuarios = db.execute('''
        SELECT * FROM usuarios 
        ORDER BY data_criacao DESC 
        LIMIT 10
    ''').fetchall()
    
    return render_template('admin.html', 
                          total_usuarios=total_usuarios,
                          total_orgaos=total_orgaos,
                          usuarios_ativos=usuarios_ativos,
                          ultimos_orgaos=ultimos_orgaos,
                          ultimos_usuarios=ultimos_usuarios)


# Página de gestão de usuários (interface)
@app.route('/usuarios')
@login_required
@admin_required
def usuarios():
    db = database.get_db()
    try:
        usuarios_rows = db.execute('''
            SELECT id, username, nome_completo, nome_guerra, posto_graduacao,
                   orgao_provedor, email, nivel_acesso, ativo, data_criacao
            FROM usuarios
            ORDER BY data_criacao DESC
        ''').fetchall()
        usuarios_list = [dict(row) for row in usuarios_rows]
    except Exception as e:
        flash(f'Erro ao carregar usuários: {e}', 'error')
        usuarios_list = []

    return render_template('usuarios.html', usuarios=usuarios_list)


@app.route('/admin/backup', methods=['GET'])
@login_required
@admin_required
def admin_backup():
    """Gera backup do banco SQLite e envia como download."""
    try:
        db_path = database.DATABASE
        if not os.path.exists(db_path):
            flash('Arquivo de banco de dados não encontrado.', 'error')
            return redirect(url_for('admin'))

        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            shutil.copy2(db_path, tmp.name)
            tmp.flush()
            backup_name = f"backup_op_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            return send_file(tmp.name, as_attachment=True, download_name=backup_name)
    except Exception as e:
        flash(f'Erro ao gerar backup: {e}', 'error')
        return redirect(url_for('admin'))


@app.route('/admin/relatorios', methods=['GET'])
@login_required
@admin_required
def admin_relatorios():
    """Exporta relatório CSV com dados gerenciais dos OP."""
    db = database.get_db()
    try:
        rows = db.execute('''
            SELECT o.id, o.nome, o.sigla, o.subordinacao, o.unidade_gestora, o.codom,
                   o.efetivo_atendimento, o.capacidade_total_toneladas, o.capacidade_total_toneladas_seco,
                   o.consumo_secos_mensal, o.consumo_frigorificados_mensal,
                   COALESCE(v.cap_total,0) as viaturas_cap_kg,
                   COALESCE(v.qtd,0) as viaturas_qtd,
                   COALESCE(p.total,0) as pessoal_total,
                   COALESCE(e.emp_total,0) as empilhadeiras_qtd,
                   o.data_cadastro
            FROM orgao_provedor o
            LEFT JOIN (
                SELECT orgao_provedor_id, COUNT(*) as qtd, COALESCE(SUM(capacidade_carga_kg),0) as cap_total
                FROM viaturas GROUP BY orgao_provedor_id
            ) v ON v.orgao_provedor_id = o.id
            LEFT JOIN (
                SELECT orgao_provedor_id, COALESCE(SUM(quantidade),0) as total
                FROM pessoal GROUP BY orgao_provedor_id
            ) p ON p.orgao_provedor_id = o.id
            LEFT JOIN (
                SELECT i.orgao_provedor_id, COUNT(e.id) as emp_total
                FROM empilhadeiras e
                JOIN instalacoes i ON i.id = e.instalacao_id
                GROUP BY i.orgao_provedor_id
            ) e ON e.orgao_provedor_id = o.id
            ORDER BY o.nome
        ''').fetchall()

        output = io.StringIO()
        header = [
            'id','nome','sigla','subordinacao','unidade_gestora','codom','efetivo_atendimento',
            'capacidade_total_toneladas','capacidade_total_toneladas_seco',
            'consumo_secos_mensal','consumo_frigorificados_mensal',
            'viaturas_capacidade_kg','viaturas_qtd','pessoal_total','empilhadeiras_qtd','data_cadastro'
        ]
        output.write(','.join(header) + '\n')
        for r in rows:
            line = [
                r['id'], r['nome'], r['sigla'], r['subordinacao'], r['unidade_gestora'] or '', r['codom'] or '',
                r['efetivo_atendimento'] or 0,
                r['capacidade_total_toneladas'] or 0,
                r['capacidade_total_toneladas_seco'] or 0,
                r['consumo_secos_mensal'] or 0,
                r['consumo_frigorificados_mensal'] or 0,
                r['viaturas_cap_kg'] or 0,
                r['viaturas_qtd'] or 0,
                r['pessoal_total'] or 0,
                r['empilhadeiras_qtd'] or 0,
                r['data_cadastro'] or ''
            ]
            output.write(','.join([str(x).replace(',', ' ') for x in line]) + '\n')

        resp = Response(output.getvalue(), mimetype='text/csv')
        resp.headers['Content-Disposition'] = f"attachment; filename=relatorio_op_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return resp
    except Exception as e:
        flash(f'Erro ao gerar relatório: {e}', 'error')
        return redirect(url_for('admin'))


@app.route('/admin/relatorios_viaturas_excel', methods=['GET'])
@login_required
@admin_required
def admin_relatorios_viaturas_excel():
    """Exporta Excel com dados principais das viaturas."""
    db = database.get_db()
    try:
        rows = db.execute('''
            SELECT v.id, o.nome AS orgao_nome, o.sigla AS orgao_sigla,
                   v.categoria, v.tipo_veiculo, v.especializacao, v.placa,
                   v.marca, v.modelo, v.ano_fabricacao, v.capacidade_carga_kg,
                   v.lotacao_pessoas, v.tipo_refrigeracao, v.temperatura_min, v.temperatura_max,
                   v.situacao, v.km_atual, v.ultima_manutencao, v.proxima_manutencao,
                   v.valor_recuperacao, v.patrimonio, v.numero_inventario, v.observacoes
            FROM viaturas v
            JOIN orgao_provedor o ON o.id = v.orgao_provedor_id
            ORDER BY o.nome, v.tipo_veiculo, v.placa
        ''').fetchall()

        df = pd.DataFrame([dict(r) for r in rows])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Viaturas')
        output.seek(0)

        filename = f"relatorio_viaturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(output, as_attachment=True,
                         download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Erro ao gerar relatório de viaturas (Excel): {e}', 'error')
        return redirect(url_for('admin'))


@app.route('/admin/relatorios_empilhadeiras_excel', methods=['GET'])
@login_required
@admin_required
def admin_relatorios_empilhadeiras_excel():
    """Exporta Excel com dados principais das empilhadeiras."""
    db = database.get_db()
    try:
        rows = db.execute('''
            SELECT e.id, o.nome AS orgao_nome, o.sigla AS orgao_sigla,
                   i.tipo_instalacao, i.descricao AS instalacao_descricao,
                   e.tipo, e.capacidade, e.quantidade, e.ano_fabricacao,
                   e.situacao, e.valor_recuperacao
            FROM empilhadeiras e
            JOIN instalacoes i ON i.id = e.instalacao_id
            JOIN orgao_provedor o ON o.id = i.orgao_provedor_id
            ORDER BY o.nome, i.tipo_instalacao, e.tipo
        ''').fetchall()

        df = pd.DataFrame([dict(r) for r in rows])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Empilhadeiras')
        output.seek(0)

        filename = f"relatorio_empilhadeiras_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(output, as_attachment=True,
                         download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Erro ao gerar relatório de empilhadeiras (Excel): {e}', 'error')
        return redirect(url_for('admin'))

# Rota para cadastrar/editar usuário (ATUALIZADA)
@app.route('/cadastrar_usuario', methods=['POST'])
@login_required
@admin_required
def cadastrar_usuario():
    try:
        db = database.get_db()
        
        user_id = request.form.get('user_id')
        nome_completo = request.form.get('nome_completo')
        nome_guerra = request.form.get('nome_guerra')
        posto_graduacao = request.form.get('posto_graduacao')
        orgao_provedor = request.form.get('orgao_provedor')
        email = request.form.get('email')
        username = request.form.get('username')
        nivel_acesso = request.form.get('nivel_acesso')
        password = request.form.get('password')
        ativo = 1 if request.form.get('ativo') else 0
        
        # Validar dados obrigatórios
        if not all([nome_completo, nome_guerra, posto_graduacao, email, username, nivel_acesso, orgao_provedor]):
            flash('Preencha todos os campos obrigatórios', 'error')
            return redirect(url_for('usuarios'))
        
        # Validar se o órgão é válido (tolerante a acentos/caixa)
        if _normalize_orgao_nome(orgao_provedor) not in ORGAOS_PROVEDORES_NORM:
            flash('Órgão Provedor inválido. Selecione uma opção válida.', 'error')
            return redirect(url_for('usuarios'))
        
        # Verificar se username já existe
        existing_user = db.execute(
            'SELECT id FROM usuarios WHERE username = ? AND id != ?',
            (username, user_id or 0)
        ).fetchone()
        
        if existing_user:
            flash('Nome de usuário já está em uso', 'error')
            return redirect(url_for('usuarios'))
        
        # Verificar se já existe usuário para este órgão (se não for admin)
        if nivel_acesso != 'admin' and orgao_provedor:
            usuario_existente = db.execute(
                'SELECT id FROM usuarios WHERE orgao_provedor = ? AND id != ?',
                (orgao_provedor, user_id or 0)
            ).fetchone()
            
            if usuario_existente:
                flash('Já existe um usuário cadastrado para este órgão provedor.', 'error')
                return redirect(url_for('usuarios'))
        
        if user_id:  # Edição
            if password:
                if len(password) < 8:
                    flash('A senha deve ter no mínimo 8 caracteres', 'error')
                    return redirect(url_for('usuarios'))
                
                senha_hash = generate_password_hash(password)
                db.execute('''
                    UPDATE usuarios 
                    SET nome_completo = ?, nome_guerra = ?, posto_graduacao = ?,
                        orgao_provedor = ?, email = ?, username = ?, 
                        nivel_acesso = ?, password_hash = ?, ativo = ?
                    WHERE id = ?
                ''', (nome_completo, nome_guerra, posto_graduacao, orgao_provedor, 
                      email, username, nivel_acesso, senha_hash, ativo, user_id))
            else:
                db.execute('''
                    UPDATE usuarios 
                    SET nome_completo = ?, nome_guerra = ?, posto_graduacao = ?,
                        orgao_provedor = ?, email = ?, username = ?, 
                        nivel_acesso = ?, ativo = ?
                    WHERE id = ?
                ''', (nome_completo, nome_guerra, posto_graduacao, orgao_provedor, 
                      email, username, nivel_acesso, ativo, user_id))
            flash('Usuário atualizado com sucesso!', 'success')
        else:  # Novo usuário
            if not password:
                flash('Senha é obrigatória para novo usuário', 'error')
                return redirect(url_for('usuarios'))
            
            if len(password) < 8:
                flash('A senha deve ter no mínimo 8 caracteres', 'error')
                return redirect(url_for('usuarios'))
            
            senha_hash = generate_password_hash(password)
            db.execute('''
                INSERT INTO usuarios 
                (username, password_hash, nome_completo, nome_guerra, posto_graduacao,
                 orgao_provedor, email, nivel_acesso, ativo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, senha_hash, nome_completo, nome_guerra, posto_graduacao,
                  orgao_provedor, email, nivel_acesso, ativo))
            flash('Usuário cadastrado com sucesso!', 'success')
        
        db.commit()
        return redirect(url_for('usuarios'))
        
    except Exception as e:
        db.rollback()
        flash(f'Erro ao salvar usuário: {str(e)}', 'error')
        return redirect(url_for('usuarios'))

# API para buscar dados do usuário
@app.route('/api/usuario/<int:user_id>')
@login_required
@admin_required
def api_usuario(user_id):
    db = database.get_db()
    usuario = db.execute('''
        SELECT id, username, nome_completo, nome_guerra, posto_graduacao,
               orgao_provedor, email, nivel_acesso, ativo
        FROM usuarios WHERE id = ?
    ''', (user_id,)).fetchone()
    
    if usuario:
        return jsonify(dict(usuario))
    return jsonify({'error': 'Usuário não encontrado'}), 404

# API para alterar status do usuário
@app.route('/api/usuario/<int:user_id>/status', methods=['PUT'])
@login_required
@admin_required
def api_toggle_usuario_status(user_id):
    if user_id == session['user_id']:
        return jsonify({'error': 'Não é possível alterar seu próprio status'}), 400
    
    try:
        data = request.get_json()
        ativo = data.get('ativo', 0)
        
        db = database.get_db()
        db.execute('UPDATE usuarios SET ativo = ? WHERE id = ?', (ativo, user_id))
        db.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API para excluir usuário
@app.route('/api/usuario/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_usuario(user_id):
    if user_id == session['user_id']:
        return jsonify({'error': 'Não é possível excluir seu próprio usuário'}), 400
    
    try:
        db = database.get_db()
        db.execute('DELETE FROM usuarios WHERE id = ?', (user_id,))
        db.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Rota para visualizar perfil do usuário
@app.route('/perfil')
@login_required
def perfil():
    db = database.get_db()
    usuario = db.execute('''
        SELECT u.*
        FROM usuarios u
        WHERE u.id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not usuario:
        flash('Usuário não encontrado', 'error')
        return redirect(url_for('index'))
    
    return render_template('perfil.html', usuario=usuario)

# Rota para editar perfil
@app.route('/editar_perfil', methods=['POST'])
@login_required
def editar_perfil():
    try:
        db = database.get_db()
        
        nome_completo = request.form.get('nome_completo')
        nome_guerra = request.form.get('nome_guerra')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validar senha se for alterada
        if password:
            if len(password) < 8:
                flash('A senha deve ter no mínimo 8 caracteres', 'error')
                return redirect(url_for('perfil'))
            
            if password != confirm_password:
                flash('As senhas não conferem', 'error')
                return redirect(url_for('perfil'))
            
            senha_hash = generate_password_hash(password)
            db.execute('''
                UPDATE usuarios 
                SET nome_completo = ?, nome_guerra = ?, email = ?, password_hash = ?
                WHERE id = ?
            ''', (nome_completo, nome_guerra, email, senha_hash, session['user_id']))
        else:
            db.execute('''
                UPDATE usuarios 
                SET nome_completo = ?, nome_guerra = ?, email = ?
                WHERE id = ?
            ''', (nome_completo, nome_guerra, email, session['user_id']))
        
        db.commit()
        
        # Atualizar sessão
        session['nome_completo'] = nome_completo
        session['nome_guerra'] = nome_guerra
        
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('perfil'))
        
    except Exception as e:
        db.rollback()
        flash(f'Erro ao atualizar perfil: {str(e)}', 'error')
        return redirect(url_for('perfil'))

# Rota para cadastro de órgãos provedores (ATUALIZADA)
# Decorador da rota principal definido mais abaixo; a rota AJAX '/cadastro/salvar' está definida abaixo.
# Endpoint AJAX para salvar rascunho / Dados Gerais via POST JSON
@app.route('/cadastro/salvar', methods=['POST'])
@login_required
def salvar_cadastro():
    try:
        data = request.get_json() or {}
        nome = (data.get('nome') or '').strip()
        sigla = (data.get('sigla') or '').strip()
        # normalização consistente para evitar duplicidade por espaços/letras
        nome_norm = ' '.join(nome.split()).upper()
        nome_norm_map = _normalize_orgao_nome(nome)
        sigla_expected = ORGÃOS_PROVEDORES.get(nome) or ORGAOS_PROVEDORES_NORM.get(nome_norm_map)
        sigla_norm = (sigla or sigla_expected or '').strip().upper()
        nome_db = ' '.join(nome.split())
        sigla_db = sigla_norm
        subordinacao = data.get('subordinacao')
        unidade_gestora = data.get('unidade_gestora')
        codom = data.get('codom')
        om_licitacao_qs = data.get('om_licitacao_qs')
        om_licitacao_qr = data.get('om_licitacao_qr')
        data_criacao = data.get('data_criacao')
        missao = data.get('missao')
        classes_provedor_list = data.get('classes_provedor') or []
        if isinstance(classes_provedor_list, str):
            classes_provedor_list = [c.strip() for c in classes_provedor_list.split(',') if c.strip()]
        classes_provedor = ', '.join(classes_provedor_list)
        apoia_classe_i = any('classe i' in c.lower() or c.strip().upper() == 'I' for c in classes_provedor_list)
        oms = data.get('oms_que_apoia') or []
        historico = ', '.join(oms) if oms else ''

        def to_num(val):
            if val is None:
                return None
            text = str(val).strip().replace('.', '').replace(',', '.')
            if text == '':
                return None
            try:
                return float(text)
            except Exception:
                return None

        efetivo = to_num(data.get('efetivo')) or 0
        consumo_secos = to_num(data.get('consumo_secos')) or 0
        consumo_frigorificados = to_num(data.get('consumo_frigorificados')) or 0
        suprimento_secos = to_num(data.get('suprimento_secos')) or 0
        suprimento_frigorificados = to_num(data.get('suprimento_frigorificados')) or 0
        area_edificavel = to_num(data.get('area_edificavel')) or 0
        capacidade_total_toneladas = to_num(data.get('capacidade_total_toneladas')) or 0
        capacidade_total_toneladas_seco = to_num(data.get('capacidade_total_toneladas_seco')) or 0

        if not apoia_classe_i:
            efetivo = 0
            consumo_secos = 0
            consumo_frigorificados = 0
            suprimento_secos = 0
            suprimento_frigorificados = 0

        energia_payload = data.get('energia') or {}
        geradores_payload = data.get('geradores') or []

        if not nome or not subordinacao:
            return jsonify(success=False, message='Campos obrigatórios ausentes (Nome ou Subordinação).'), 400

        if nome_norm_map not in ORGAOS_PROVEDORES_NORM:
            return jsonify(success=False, message='Órgão Provedor inválido.'), 400

        # Restrições de permissão
        if session.get('nivel_acesso') != 'admin':
            user_org = session.get('orgao_provedor')
            if not user_org:
                return jsonify(success=False, message='Seu usuário não está vinculado a um Órgão Provedor.'), 403
            if _normalize_orgao_nome(user_org) != nome_norm_map:
                return jsonify(success=False, message='Você só pode salvar cadastro para o seu Órgão Provedor.'), 403

        db = database.get_db()
        existente = find_orgao_existente(nome_db, sigla_db)

        if existente:
            # Permissão para editar
            if session.get('nivel_acesso') == 'cadastrador':
                usuario = db.execute('SELECT orgao_provedor FROM usuarios WHERE id = ?', (session['user_id'],)).fetchone()
                if not usuario or usuario['orgao_provedor'] != nome:
                    return jsonify(success=False, message='Você não tem permissão para editar este cadastro.'), 403

            db.execute('''UPDATE orgao_provedor SET
                          unidade_gestora = ?, codom = ?, om_licitacao_qs = ?, om_licitacao_qr = ?,
                          subordinacao = ?, efetivo_atendimento = ?, data_criacao = ?, missao = ?, historico = ?,
                          consumo_secos_mensal = ?, consumo_frigorificados_mensal = ?, suprimento_secos_mensal = ?,
                                                    suprimento_frigorificados_mensal = ?, area_edificavel_disponivel = ?,
                                                    classes_provedor = ?, capacidade_total_toneladas = ?, capacidade_total_toneladas_seco = ?
                          WHERE id = ?''', (unidade_gestora, codom, om_licitacao_qs, om_licitacao_qr,
                                                                                        subordinacao, efetivo, data_criacao, missao, historico,
                                                                                        consumo_secos, consumo_frigorificados, suprimento_secos,
                                                                                        suprimento_frigorificados, area_edificavel, classes_provedor,
                                                                                        capacidade_total_toneladas, capacidade_total_toneladas_seco, existente['id']))
            orgao_id = existente['id']
            action_msg = 'Cadastro já existia e foi atualizado.'
        else:
            # Criar novo com valores mínimos; efetivo_atendimento definido como 0 para obedecer NOT NULL
            cursor = db.execute('''INSERT INTO orgao_provedor (nome, sigla, unidade_gestora, codom, om_licitacao_qs, om_licitacao_qr,
                                                                     subordinacao, efetivo_atendimento, data_criacao, historico, missao,
                                                                     consumo_secos_mensal, consumo_frigorificados_mensal,
                                                                     suprimento_secos_mensal, suprimento_frigorificados_mensal,
                                                                     area_edificavel_disponivel, classes_provedor, capacidade_total_toneladas, capacidade_total_toneladas_seco, criado_por)
                                                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (nome_db, sigla_db, unidade_gestora, codom, om_licitacao_qs, om_licitacao_qr,
                                 subordinacao, efetivo, data_criacao, historico, missao,
                                                                 consumo_secos, consumo_frigorificados, suprimento_secos, suprimento_frigorificados,
                                                                 area_edificavel, classes_provedor, capacidade_total_toneladas, capacidade_total_toneladas_seco, session['user_id']))
            orgao_id = cursor.lastrowid
            action_msg = 'Cadastro criado com sucesso.'

        # Persistir energia elétrica (substitui registros anteriores)
        dimensionamento_energia = (energia_payload.get('dimensionamento') or '').strip()
        capacidade_total_kva = to_num(energia_payload.get('capacidade_total_kva')) or 0
        observacoes_energia = energia_payload.get('observacoes')

        db.execute('DELETE FROM energia_eletrica WHERE orgao_provedor_id = ?', (orgao_id,))
        if dimensionamento_energia or capacidade_total_kva or (observacoes_energia and observacoes_energia.strip()):
            db.execute(
                '''INSERT INTO energia_eletrica (orgao_provedor_id, dimensionamento_adequado, capacidade_total_kva, observacoes_energia)
                   VALUES (?, ?, ?, ?)''',
                (orgao_id, dimensionamento_energia, capacidade_total_kva, observacoes_energia)
            )

        # Persistir geradores (remoção total + regravação)
        geradores = geradores_payload if isinstance(geradores_payload, list) else []
        existing_g_ids = db.execute('SELECT id FROM geradores WHERE orgao_provedor_id = ?', (orgao_id,)).fetchall()
        if existing_g_ids:
            ids = [row['id'] for row in existing_g_ids]
            placeholders = ','.join(['?'] * len(ids))
            db.execute(f"DELETE FROM fotos WHERE tabela_origem='gerador' AND registro_id IN ({placeholders})", ids)
        db.execute('DELETE FROM geradores WHERE orgao_provedor_id = ?', (orgao_id,))

        allowed_situacoes = {'operacional', 'em_manutencao', 'baixada'}

        for g in geradores:
            capacidade_kva = to_num(g.get('capacidade')) or 0
            marca_modelo = g.get('marca')
            ano_fabricacao = to_num(g.get('ano'))
            situacao_raw = (g.get('situacao') or '').strip()
            situacao = situacao_raw if situacao_raw in allowed_situacoes else 'operacional'
            valor_recuperacao = to_num(g.get('valor_recuperacao'))
            pode_24h = 1 if g.get('pode_24h') else 0
            horas_operacao = to_num(g.get('horas'))
            ultima_manutencao = g.get('ultima_manutencao')
            proxima_manutencao = g.get('proxima_manutencao')
            observacoes = g.get('observacoes')

            # Ignorar cartões vazios para evitar violar CHECK de situação
            if not any([
                capacidade_kva, marca_modelo, ano_fabricacao, situacao_raw, valor_recuperacao,
                pode_24h, horas_operacao, ultima_manutencao, proxima_manutencao, observacoes
            ]):
                continue

            db.execute(
                '''INSERT INTO geradores (orgao_provedor_id, capacidade_kva, marca_modelo, ano_fabricacao, situacao, valor_recuperacao,
                                           pode_operar_24h, horas_operacao_continuas, ultima_manutencao, proxima_manutencao, observacoes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (orgao_id, capacidade_kva, marca_modelo, ano_fabricacao, situacao, valor_recuperacao,
                 pode_24h, horas_operacao, ultima_manutencao, proxima_manutencao, observacoes)
            )

        db.commit()

        return jsonify(success=True, id=orgao_id, message=action_msg, redirect=url_for('editar_orgao', id=orgao_id))
    except Exception as e:
        print('Erro ao salvar cadastro (AJAX):', e)
        return jsonify(success=False, message=str(e)), 500


# Endpoint AJAX para salvar apenas Energia/Geradores (modo edição)
@app.route('/geradores/salvar', methods=['POST'])
@login_required
def salvar_geradores():
    try:
        data = request.get_json() or {}
        orgao_id = data.get('orgao_id')
        if not orgao_id:
            return jsonify(success=False, message='ID do órgão não informado. Salve os dados gerais primeiro.'), 400

        db = database.get_db()
        orgao = db.execute('SELECT id, nome FROM orgao_provedor WHERE id = ?', (orgao_id,)).fetchone()
        if not orgao:
            return jsonify(success=False, message='Órgão Provedor não encontrado.'), 404

        # Permissão: não-admin só salva o próprio órgão
        if session.get('nivel_acesso') != 'admin':
            usuario = db.execute('SELECT orgao_provedor FROM usuarios WHERE id = ?', (session['user_id'],)).fetchone()
            if not usuario or usuario['orgao_provedor'] != orgao['nome']:
                return jsonify(success=False, message='Você não tem permissão para editar este órgão.'), 403

        def to_num(val):
            if val is None:
                return None
            text = str(val).strip().replace('.', '').replace(',', '.')
            if text == '':
                return None
            try:
                return float(text)
            except Exception:
                return None

        energia_payload = data.get('energia') or {}
        geradores_payload = data.get('geradores') or []

        # Atualizar energia elétrica
        dimensionamento_energia = (energia_payload.get('dimensionamento') or '').strip()
        capacidade_total_kva = to_num(energia_payload.get('capacidade_total_kva')) or 0
        observacoes_energia = energia_payload.get('observacoes')

        db.execute('DELETE FROM energia_eletrica WHERE orgao_provedor_id = ?', (orgao_id,))
        if dimensionamento_energia or capacidade_total_kva or (observacoes_energia and observacoes_energia.strip()):
            db.execute(
                '''INSERT INTO energia_eletrica (orgao_provedor_id, dimensionamento_adequado, capacidade_total_kva, observacoes_energia)
                   VALUES (?, ?, ?, ?)''',
                (orgao_id, dimensionamento_energia, capacidade_total_kva, observacoes_energia)
            )

        # Atualizar geradores
        existing_g_ids = db.execute('SELECT id FROM geradores WHERE orgao_provedor_id = ?', (orgao_id,)).fetchall()
        if existing_g_ids:
            ids = [row['id'] for row in existing_g_ids]
            placeholders = ','.join(['?'] * len(ids))
            db.execute(f"DELETE FROM fotos WHERE tabela_origem='gerador' AND registro_id IN ({placeholders})", ids)
        db.execute('DELETE FROM geradores WHERE orgao_provedor_id = ?', (orgao_id,))

        allowed_situacoes = {'operacional', 'em_manutencao', 'baixada'}
        geradores = geradores_payload if isinstance(geradores_payload, list) else []

        for g in geradores:
            capacidade_kva = to_num(g.get('capacidade')) or 0
            marca_modelo = g.get('marca')
            ano_fabricacao = to_num(g.get('ano'))
            situacao_raw = (g.get('situacao') or '').strip()
            situacao = situacao_raw if situacao_raw in allowed_situacoes else 'operacional'
            valor_recuperacao = to_num(g.get('valor_recuperacao'))
            pode_24h = 1 if g.get('pode_24h') else 0
            horas_operacao = to_num(g.get('horas'))
            ultima_manutencao = g.get('ultima_manutencao')
            proxima_manutencao = g.get('proxima_manutencao')
            observacoes = g.get('observacoes')

            # Ignorar cartões vazios
            if not any([
                capacidade_kva, marca_modelo, ano_fabricacao, situacao_raw, valor_recuperacao,
                pode_24h, horas_operacao, ultima_manutencao, proxima_manutencao, observacoes
            ]):
                continue

            db.execute(
                '''INSERT INTO geradores (orgao_provedor_id, capacidade_kva, marca_modelo, ano_fabricacao, situacao, valor_recuperacao,
                                           pode_operar_24h, horas_operacao_continuas, ultima_manutencao, proxima_manutencao, observacoes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (orgao_id, capacidade_kva, marca_modelo, ano_fabricacao, situacao, valor_recuperacao,
                 pode_24h, horas_operacao, ultima_manutencao, proxima_manutencao, observacoes)
            )

        db.commit()
        return jsonify(success=True, message='Energia e geradores salvos com sucesso.')

    except Exception as e:
        db.rollback()
        print('Erro ao salvar geradores (AJAX):', e)
        return jsonify(success=False, message=str(e)), 500


@app.route('/cadastro', methods=['GET', 'POST'])
@login_required
def cadastro():
    if session.get('nivel_acesso') == 'visualizador':
        flash('Acesso negado. Visualizadores não podem criar cadastros.', 'error')
        return redirect(url_for('index'))
    
    # Se o usuário não for admin e estiver vinculado a um Órgão Provedor,
    # verificar se já existe um cadastro para o seu órgão e redirecionar para edição.
    if session.get('nivel_acesso') != 'admin':
        user_org = session.get('orgao_provedor')
        if not user_org:
            flash('Seu usuário não está vinculado a um Órgão Provedor. Contate o administrador para vinculação.', 'error')
            return redirect(url_for('index'))
        db = database.get_db()
        existente = db.execute('SELECT id FROM orgao_provedor WHERE nome = ?', (user_org,)).fetchone()
        if existente:
            flash('Seu Órgão Provedor já possui cadastro; você pode editá-lo.', 'info')
            return redirect(url_for('editar_orgao', id=existente['id']))

    if request.method == 'POST':
        try:
            try:
                print('[DEBUG cadastro] request.files keys:', list(request.files.keys()))
            except Exception:
                pass
            db = database.get_db()

            # Utilitários de parsing seguro para formulários dinâmicos
            def collect_indices(prefix):
                indices = set()
                for key in request.form.keys():
                    if key.startswith(prefix):
                        parts = key.split('_')
                        for part in parts[::-1]:
                            if part.isdigit():
                                indices.add(int(part))
                                break
                return sorted(indices)

            def to_int(val):
                if val is None:
                    return None
                text = str(val).strip().replace('.', '').replace(',', '.')
                if text == '':
                    return None
                try:
                    return int(float(text))
                except Exception:
                    return None

            def to_float(val):
                if val is None:
                    return None
                text = str(val).strip().replace('.', '').replace(',', '.')
                if text == '':
                    return None
                try:
                    return float(text)
                except Exception:
                    return None
            
            # Dados do Órgão Provedor
            nome = request.form.get('nome')
            sigla = request.form.get('sigla')
            
            nome = nome.strip() if nome else ''
            nome_norm = ' '.join(nome.split()).upper()
            nome_db = ' '.join(nome.split())
            sigla = sigla.strip() if sigla else ''
            sigla_norm = (sigla or ORGÃOS_PROVEDORES.get(nome, '')).strip().upper()
            sigla_db = sigla_norm

            # Validar se o órgão é válido (tolerante a acentos/caixa)
            nome_norm_map = _normalize_orgao_nome(nome)
            if nome_norm_map not in ORGAOS_PROVEDORES_NORM:
                flash('Órgão Provedor inválido. Selecione uma opção válida.', 'error')
                return redirect(url_for('cadastro'))
            
            # Restringir criação para usuários que não sejam administradores
            if session.get('nivel_acesso') != 'admin':
                user_org = session.get('orgao_provedor')
                if not user_org:
                    flash('Somente administradores podem criar cadastros. Solicite que um administrador vincule seu usuário a um órgão provedor.', 'error')
                    return redirect(url_for('cadastro'))
                if nome != user_org:
                    flash('Você só pode criar o cadastro do seu órgão provedor.', 'error')
                    return redirect(url_for('cadastro'))

            # Validar se a sigla corresponde ao órgão (tolerante)
            sigla_esperada = ORGÃOS_PROVEDORES.get(nome) or ORGAOS_PROVEDORES_NORM.get(nome_norm_map)
            if sigla != sigla_esperada:
                flash('Sigla inválida para o órgão selecionado.', 'error')
                return redirect(url_for('cadastro'))
            
            # Verificar se já existe cadastro para este órgão
            orgao_existente = find_orgao_existente(nome_db, sigla_db)
            
            if orgao_existente:
                flash('Este órgão já possui cadastro. Você pode editá-lo.', 'info')
                return redirect(url_for('editar_orgao', id=orgao_existente['id']))
            
            # Coletar outros dados do formulário
            unidade_gestora = request.form.get('unidade_gestora')
            codom = request.form.get('codom')
            om_licitacao_qs = request.form.get('om_licitacao_qs')
            om_licitacao_qr = request.form.get('om_licitacao_qr')
            subordinacao = request.form.get('subordinacao')
            efetivo = request.form.get('efetivo')
            data_criacao = request.form.get('data_criacao')
            classes_list = request.form.getlist('classes_provedor')
            classes_provedor = ', '.join([c for c in classes_list if c]) if classes_list else ''
            apoia_classe_i = any('classe i' in (c or '').lower() or (c or '').strip().upper() == 'I' for c in classes_list)
            # Obter OMs que apoiam (seleção múltipla)
            oms_que_apoia = request.form.getlist('oms_que_apoia[]')
            if len(oms_que_apoia) == 1 and ',' in (oms_que_apoia[0] or ''):
                oms_que_apoia = [s.strip() for s in oms_que_apoia[0].split(',') if s.strip()]
            historico = ', '.join(oms_que_apoia) if oms_que_apoia else ''
            missao = request.form.get('missao')
            consumo_secos = request.form.get('consumo_secos') or 0
            consumo_frigorificados = request.form.get('consumo_frigorificados') or 0
            suprimento_secos = request.form.get('suprimento_secos') or 0
            suprimento_frigorificados = request.form.get('suprimento_frigorificados') or 0
            area_edificavel = request.form.get('area_edificavel') or 0
            capacidade_total_toneladas = request.form.get('capacidade_total_toneladas') or 0
            capacidade_total_toneladas_seco = request.form.get('capacidade_total_toneladas_seco') or 0

            if not apoia_classe_i:
                efetivo = 0
                consumo_secos = 0
                consumo_frigorificados = 0
                suprimento_secos = 0
                suprimento_frigorificados = 0
            
            # Upload das fotos da área edificável
            fotos_area = []
            area_keys = [k for k in request.files.keys() if k.startswith('foto_area_edificavel')]
            if area_keys:
                print('[DEBUG cadastro] area_edificavel file keys:', area_keys)
            else:
                print('[DEBUG cadastro] nenhuma foto_area_edificavel no payload')
            for key in area_keys:
                files = request.files.getlist(key)
                for file in files:
                    if file and file.filename != '' and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4().hex}_{filename}"
                        filepath = f"areas_edificaveis/{unique_filename}"  # usar path com '/'
                        full_path = os.path.join(app.config['UPLOAD_FOLDER'], 'areas_edificaveis', unique_filename)
                        try:
                            os.makedirs(os.path.dirname(full_path), exist_ok=True)
                            file.save(full_path)
                            print('[DEBUG cadastro] area_edificavel saved', full_path)
                        except Exception as save_err:
                            print('[ERROR cadastro] ao salvar area_edificavel', full_path, save_err)
                            continue
                        fotos_area.append(filepath)
            print('[DEBUG cadastro] area_edificavel fotos count:', len(fotos_area), fotos_area)
            
            # Inserir Órgão Provedor
            cursor = db.execute(
                '''INSERT INTO orgao_provedor 
                (nome, sigla, unidade_gestora, codom, om_licitacao_qs, om_licitacao_qr,
                  subordinacao, efetivo_atendimento, data_criacao,
                 historico, missao, consumo_secos_mensal, consumo_frigorificados_mensal,
                  suprimento_secos_mensal, suprimento_frigorificados_mensal,
                  area_edificavel_disponivel, classes_provedor, capacidade_total_toneladas, capacidade_total_toneladas_seco, criado_por) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (nome_db, sigla_db, unidade_gestora, codom, om_licitacao_qs, om_licitacao_qr,
                  subordinacao, efetivo, data_criacao, historico, missao,
                  consumo_secos, consumo_frigorificados, 
                  suprimento_secos, suprimento_frigorificados,
                  area_edificavel, classes_provedor, capacidade_total_toneladas, capacidade_total_toneladas_seco, session['user_id'])
            )
            orgao_id = cursor.lastrowid

            # Persistir fotos da área edificável (se houver)
            if fotos_area:
                for idx, filepath in enumerate(fotos_area):
                    db.execute(
                        '''INSERT INTO fotos (tabela_origem, registro_id, caminho_arquivo, tipo_foto)
                           VALUES (?, ?, ?, ?)''',
                        ('area_edificavel', orgao_id, filepath, 'area_edificavel')
                    )
            
            # Processar energia elétrica
            dimensionamento_energia = request.form.get('dimensionamento_energia')
            capacidade_total_kva = request.form.get('capacidade_total_kva') or 0
            observacoes_energia = request.form.get('observacoes_energia')
            
            if dimensionamento_energia:
                db.execute(
                    '''INSERT INTO energia_eletrica 
                    (orgao_provedor_id, dimensionamento_adequado, capacidade_total_kva, observacoes_energia) 
                    VALUES (?, ?, ?, ?)''',
                    (orgao_id, dimensionamento_energia, capacidade_total_kva, observacoes_energia)
                )
            
            # Processar geradores
            geradores_count = to_int(request.form.get('geradores_count')) or 0
            allowed_situacoes = {'operacional', 'em_manutencao', 'baixada', 'disponivel', 'indisponivel_recuperavel', 'indisponivel'}

            if geradores_count == 0:
                geradores_indices = collect_indices('gerador_capacidade')
            else:
                geradores_indices = list(range(geradores_count))

            if geradores_indices:
                print('[DEBUG geradores] count declarada:', geradores_count, 'indices:', geradores_indices)
                try:
                    db.execute('SAVEPOINT sp_geradores_create')
                    for g in geradores_indices:
                        capacidade = to_float(request.form.get(f'gerador_capacidade_{g}'))
                        marca = request.form.get(f'gerador_marca_{g}')
                        ano_fabricacao = to_int(request.form.get(f'gerador_ano_{g}'))
                        situacao_raw = (request.form.get(f'gerador_situacao_{g}') or '').strip().lower()
                        if situacao_raw in ['operacional', 'disponivel', 'disponível']:
                            situacao = 'disponivel'
                        elif situacao_raw in ['em_manutencao', 'em manutencao', 'manutencao', 'manutenção']:
                            situacao = 'indisponivel_recuperavel'
                        elif situacao_raw in ['baixada', 'inoperante']:
                            situacao = 'indisponivel'
                        elif situacao_raw in allowed_situacoes:
                            situacao = situacao_raw
                        else:
                            situacao = 'disponivel'
                        valor_recuperacao = to_float(request.form.get(f'gerador_valor_recuperacao_{g}'))
                        pode_24h = to_int(request.form.get(f'gerador_24h_{g}', 0)) or 0
                        horas_operacao = to_float(request.form.get(f'gerador_horas_{g}'))
                        ultima_manutencao = request.form.get(f'gerador_ultima_manutencao_{g}')
                        proxima_manutencao = request.form.get(f'gerador_proxima_manutencao_{g}')
                        observacoes = request.form.get(f'gerador_observacoes_{g}')

                        print('[DEBUG gerador card]', g, {
                            'capacidade': capacidade, 'marca': marca, 'ano': ano_fabricacao,
                            'situacao_raw': situacao_raw, 'situacao_final': situacao,
                            'valor': valor_recuperacao, 'pode_24h': pode_24h, 'horas': horas_operacao
                        })

                        # Ignorar cartões vazios para não violar o CHECK de situação e NOT NULL de capacidade
                        if not any([
                            capacidade, marca, ano_fabricacao, situacao_raw, valor_recuperacao,
                            pode_24h, horas_operacao, ultima_manutencao, proxima_manutencao, observacoes
                        ]):
                            print('[DEBUG gerador card skip vazio]', g)
                            continue

                        capacidade_final = capacidade if capacidade is not None else 0

                        try:
                            cursor = db.execute(
                                '''INSERT INTO geradores 
                                (orgao_provedor_id, capacidade_kva, marca_modelo, ano_fabricacao, situacao, valor_recuperacao, 
                                 pode_operar_24h, horas_operacao_continuas, ultima_manutencao, 
                                 proxima_manutencao, observacoes) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (orgao_id, capacidade_final, marca, ano_fabricacao, situacao, valor_recuperacao, 
                                 pode_24h, horas_operacao, ultima_manutencao, proxima_manutencao, observacoes)
                            )
                        except Exception as err:
                            print('[WARN cadastro gerador] skip insert por erro:', err, 'dados=', {
                                'capacidade': capacidade_final, 'marca': marca, 'ano': ano_fabricacao,
                                'situacao': situacao, 'valor': valor_recuperacao, 'pode_24h': pode_24h,
                                'horas': horas_operacao, 'ultima': ultima_manutencao, 'proxima': proxima_manutencao
                            })
                            db.execute('ROLLBACK TO sp_geradores_create')
                            continue

                        gerador_id = cursor.lastrowid

                        # Upload múltiplas fotos do gerador
                        if f'gerador_fotos_{g}[]' in request.files:
                            files = request.files.getlist(f'gerador_fotos_{g}[]')
                            for i, file in enumerate(files):
                                if file and file.filename != '' and allowed_file(file.filename):
                                    filename = secure_filename(file.filename)
                                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                                    filepath = os.path.join('geradores', f'{orgao_id}_{g}_{i}_{unique_filename}')
                                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                                    file.save(full_path)
                                    
                                    # Inserir foto na tabela de fotos
                                    db.execute(
                                        '''INSERT INTO fotos 
                                        (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                        VALUES (?, ?, ?, ?)''',
                                        ('gerador', gerador_id, filepath, 'gerador')
                                    )
                    db.execute('RELEASE sp_geradores_create')
                except Exception as outer_err:
                    print('[WARN cadastro gerador bloco] erro inesperado:', outer_err)
                    try:
                        db.execute('ROLLBACK TO sp_geradores_create')
                        db.execute('RELEASE sp_geradores_create')
                    except Exception:
                        pass
            
            # Processar pessoal
            pessoal_count = to_int(request.form.get('pessoal_count')) or 0
            if pessoal_count == 0:
                pessoal_indices = collect_indices('pessoal_posto')
            else:
                pessoal_indices = list(range(pessoal_count))
            
            for p in pessoal_indices:
                posto = request.form.get(f'pessoal_posto_{p}')
                arma = request.form.get(f'pessoal_arma_{p}')
                especialidade = request.form.get(f'pessoal_especialidade_{p}')
                funcao = request.form.get(f'pessoal_funcao_{p}')
                tipo_servico_raw = request.form.get(f'pessoal_tipo_{p}')
                quantidade_raw = request.form.get(f'pessoal_quantidade_{p}')
                observacoes = request.form.get(f'pessoal_observacoes_{p}')

                # Ignorar cartões totalmente vazios
                if not any([posto, arma, especialidade, funcao, tipo_servico_raw, quantidade_raw, observacoes]):
                    continue

                quantidade = quantidade_raw if quantidade_raw not in (None, '') else 1

                tipo_servico = (tipo_servico_raw or '').strip().lower()
                if tipo_servico not in ('carreira', 'temporario'):
                    tipo_servico = 'carreira'
                
                db.execute(
                    '''INSERT INTO pessoal 
                    (orgao_provedor_id, posto_graduacao, arma_quadro_servico, especialidade,
                     funcao, tipo_servico, quantidade, observacoes) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (orgao_id, posto, arma, especialidade, funcao, tipo_servico, quantidade, observacoes)
                )
            
            # Processar viaturas
            viaturas_count = to_int(request.form.get('viaturas_count')) or 0
            if viaturas_count == 0:
                viaturas_indices = collect_indices('viatura_tipo')
            else:
                viaturas_indices = list(range(viaturas_count))
            
            if viaturas_indices:
                print('[DEBUG viaturas] count declarada:', viaturas_count, 'indices:', viaturas_indices)
                try:
                    db.execute('SAVEPOINT sp_viaturas_create')
                    for v in viaturas_indices:
                        # Campo categoria foi removido do formulário; manter vazio para compatibilidade
                        categoria = request.form.get(f'viatura_categoria_{v}') or ''
                        tipo_veiculo = request.form.get(f'viatura_tipo_{v}')
                        # EB é o código interno (substitui placa no formulário)
                        eb = request.form.get(f'viatura_eb_{v}')
                        placa = eb  # armazenamos o EB na coluna 'placa' para compatibilidade com o schema atual
                        especializacao = request.form.get(f'viatura_especializacao_{v}')
                        marca = request.form.get(f'viatura_marca_{v}')
                        modelo = request.form.get(f'viatura_modelo_{v}')
                        ano_fabricacao = request.form.get(f'viatura_ano_{v}')
                        capacidade_carga_kg = request.form.get(f'viatura_capacidade_{v}') or 0
                        lotacao_pessoas = request.form.get(f'viatura_lotacao_{v}')
                        situacao_raw = (request.form.get(f'viatura_situacao_{v}') or '').strip().lower()
                        if situacao_raw in ['operacional', 'disponivel', 'disponível']:
                            situacao = 'operacional'
                        elif situacao_raw in ['em_manutencao', 'em manutencao', 'manutencao', 'manutenção']:
                            situacao = 'em_manutencao'
                        elif situacao_raw in ['baixada', 'baixado']:
                            situacao = 'baixada'
                        elif situacao_raw in ['inoperante', 'indisponivel', 'indisponível']:
                            situacao = 'inoperante'
                        else:
                            situacao = 'operacional'
                        km_atual = request.form.get(f'viatura_km_{v}')
                        ultima_manutencao = request.form.get(f'viatura_ultima_manutencao_{v}')
                        proxima_manutencao = request.form.get(f'viatura_proxima_manutencao_{v}')
                        patrimonio = request.form.get(f'viatura_patrimonio_{v}')
                        raw_valor = request.form.get(f'viatura_valor_recuperacao_{v}')
                        valor_recuperacao = float(raw_valor) if raw_valor else None
                        observacoes = request.form.get(f'viatura_observacoes_{v}')

                        print('[DEBUG viatura card]', v, {
                            'tipo': tipo_veiculo, 'placa': placa, 'marca': marca,
                            'situacao_raw': situacao_raw, 'situacao_final': situacao, 'valor': valor_recuperacao
                        })

                        # Requer campos mínimos para passar pelo NOT NULL/UNIQUE
                        if not tipo_veiculo or not placa:
                            print('[DEBUG viatura card skip falta campos obrigatórios]', v)
                            continue
                        
                        try:
                            cursor = db.execute(
                                '''INSERT INTO viaturas 
                                (orgao_provedor_id, categoria, tipo_veiculo, especializacao, placa, marca, modelo,
                                 ano_fabricacao, capacidade_carga_kg, lotacao_pessoas, situacao, valor_recuperacao, km_atual, ultima_manutencao,
                                 proxima_manutencao, patrimonio, observacoes) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (orgao_id, categoria, tipo_veiculo, especializacao, placa, marca, modelo, ano_fabricacao,
                                 capacidade_carga_kg, lotacao_pessoas, situacao, valor_recuperacao, km_atual, ultima_manutencao, proxima_manutencao,
                                 patrimonio, observacoes)
                            )
                        except Exception as err:
                            print('[WARN cadastro viatura] skip insert por erro:', err, 'dados=', {
                                'tipo': tipo_veiculo, 'placa': placa, 'marca': marca, 'modelo': modelo,
                                'ano': ano_fabricacao, 'situacao': situacao, 'valor': valor_recuperacao
                            })
                            db.execute('ROLLBACK TO sp_viaturas_create')
                            continue
                        
                        viatura_id = cursor.lastrowid
                        
                        # Upload múltiplas fotos da viatura
                        if f'viatura_fotos_{v}[]' in request.files:
                            files = request.files.getlist(f'viatura_fotos_{v}[]')
                            for i, file in enumerate(files):
                                if file and file.filename != '' and allowed_file(file.filename):
                                    filename = secure_filename(file.filename)
                                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                                    filepath = os.path.join('viaturas', f'{orgao_id}_{v}_{i}_{unique_filename}')
                                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                                    file.save(full_path)
                                    
                                    # Inserir foto na tabela de fotos
                                    db.execute(
                                        '''INSERT INTO fotos 
                                        (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                        VALUES (?, ?, ?, ?)''',
                                        ('viatura', viatura_id, filepath, 'viatura')
                                    )
                    db.execute('RELEASE sp_viaturas_create')
                except Exception as outer_err:
                    print('[WARN cadastro viatura bloco] erro inesperado:', outer_err)
                    try:
                        db.execute('ROLLBACK TO sp_viaturas_create')
                        db.execute('RELEASE sp_viaturas_create')
                    except Exception:
                        pass
            
            # Processar instalações (COM CAPACIDADE EM TONELADAS)
            instalacoes_count = to_int(request.form.get('instalacoes_count')) or 0
            if instalacoes_count == 0:
                instalacoes_indices = collect_indices('tipo_instalacao')
            else:
                instalacoes_indices = list(range(instalacoes_count))
            
            for i in instalacoes_indices:
                tipo_instalacao = request.form.get(f'tipo_instalacao_{i}')
                nome_instalacao = request.form.get(f'instalacao_nome_{i}')
                descricao = request.form.get(f'descricao_{i}')
                data_construcao = request.form.get(f'data_construcao_{i}')
                tipo_cobertura = request.form.get(f'tipo_cobertura_{i}')
                capacidade_toneladas = request.form.get(f'capacidade_{i}') or 0
                largura = request.form.get(f'largura_{i}') or 0
                comprimento = request.form.get(f'comprimento_{i}') or 0
                altura = request.form.get(f'altura_{i}') or 0
                verticalizacao = request.form.get(f'verticalizacao_{i}')
                
                # Campos obrigatórios mínimos: tipo_instalacao
                if not tipo_instalacao:
                    continue

                cursor = db.execute(
                    '''INSERT INTO instalacoes 
                    (orgao_provedor_id, tipo_instalacao, nome_identificacao, descricao, data_construcao,
                     tipo_cobertura, capacidade_toneladas, largura, comprimento,
                     altura, verticalizacao) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (orgao_id, tipo_instalacao, nome_instalacao, descricao, data_construcao, tipo_cobertura,
                     capacidade_toneladas, largura, comprimento, altura, verticalizacao)
                )
                instalacao_id = cursor.lastrowid
                
                # Upload múltiplas fotos da instalação
                if f'instalacao_fotos_{i}[]' in request.files:
                    files = request.files.getlist(f'instalacao_fotos_{i}[]')
                    for j, file in enumerate(files):
                        if file and file.filename != '' and allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            unique_filename = f"{uuid.uuid4().hex}_{filename}"
                            filepath = os.path.join('instalacoes', f'{orgao_id}_{i}_{j}_{unique_filename}')
                            full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                            file.save(full_path)
                            
                            # Inserir foto na tabela de fotos
                            db.execute(
                                '''INSERT INTO fotos 
                                (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                VALUES (?, ?, ?, ?)''',
                                ('instalacao', instalacao_id, filepath, 'instalacao')
                            )
                
                # Processar empilhadeiras (só se for depósito)
                if tipo_instalacao and 'deposito' in tipo_instalacao:
                    empilhadeiras_count = to_int(request.form.get(f'empilhadeiras_count_{i}')) or 0
                    emp_indices = list(range(empilhadeiras_count)) if empilhadeiras_count > 0 else collect_indices(f'empilhadeira_tipo_{i}')
                    allowed_emp_situacoes = {'disponivel', 'indisponivel_recuperavel', 'indisponivel'}

                    if emp_indices:
                        print('[DEBUG empilhadeiras] instalacao idx', i, 'count declarada:', empilhadeiras_count, 'indices:', emp_indices)
                        try:
                            db.execute('SAVEPOINT sp_emp_create')
                            for j in emp_indices:
                                tipo = request.form.get(f'empilhadeira_tipo_{i}_{j}')
                                cap_raw = request.form.get(f'empilhadeira_capacidade_{i}_{j}')
                                qtd_raw = request.form.get(f'empilhadeira_quantidade_{i}_{j}')
                                ano_fabricacao = request.form.get(f'empilhadeira_ano_{i}_{j}')
                                situacao_raw = (request.form.get(f'empilhadeira_situacao_{i}_{j}') or '').strip().lower()
                                valor_raw = request.form.get(f'empilhadeira_valor_recuperacao_{i}_{j}')

                                print('[DEBUG empilhadeira card]', j, {
                                    'tipo': tipo, 'capacidade': cap_raw, 'quantidade': qtd_raw,
                                    'ano': ano_fabricacao, 'situacao_raw': situacao_raw, 'valor_raw': valor_raw
                                })

                                if not tipo:
                                    print('[DEBUG empilhadeira card skip sem tipo]', j)
                                    continue
                                if not any([tipo, cap_raw, qtd_raw, ano_fabricacao, situacao_raw, valor_raw]):
                                    print('[DEBUG empilhadeira card skip vazio]', j)
                                    continue

                                capacidade = cap_raw or 0
                                quantidade = qtd_raw or 1
                                valor_recuperacao = valor_raw or 0

                                if situacao_raw in ['indisponivel_recuperavel', 'indisponível recuperável', 'indisponivel recuperavel']:
                                    situacao = 'indisponivel_recuperavel'
                                elif situacao_raw in [
                                    'indisponivel', 'indisponível', 'indisponivel_descarga',
                                    'indisponivel para descarga', 'indisponivel_para_descarga',
                                    'inoperante', 'baixada'
                                ]:
                                    situacao = 'indisponivel'
                                elif situacao_raw in ['operacional', 'em_manutencao', 'em manutencao', 'disponivel']:
                                    situacao = 'disponivel'
                                else:
                                    situacao = 'disponivel'

                                if situacao not in allowed_emp_situacoes:
                                    situacao = 'disponivel'
                                if situacao not in allowed_emp_situacoes:
                                    print('[DEBUG empilhadeira card skip situacao invalida]', j, situacao_raw)
                                    continue

                                try:
                                    emp_cursor = db.execute(
                                        '''INSERT INTO empilhadeiras 
                                        (instalacao_id, tipo, capacidade, quantidade, ano_fabricacao,
                                         situacao, valor_recuperacao) 
                                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                        (instalacao_id, tipo, capacidade, quantidade, ano_fabricacao,
                                         situacao, valor_recuperacao)
                                    )
                                    empilhadeira_id = emp_cursor.lastrowid
                                except Exception as err:
                                    print('[WARN cadastro empilhadeira] skip insert por erro:', err, 'dados=', {
                                        'tipo': tipo, 'capacidade': capacidade, 'quantidade': quantidade,
                                        'ano': ano_fabricacao, 'situacao': situacao, 'raw': situacao_raw,
                                        'valor': valor_recuperacao
                                    })
                                    db.execute('ROLLBACK TO sp_emp_create')
                                    continue

                                if f'empilhadeira_fotos_{i}_{j}[]' in request.files:
                                    files = request.files.getlist(f'empilhadeira_fotos_{i}_{j}[]')
                                    for k, file in enumerate(files):
                                        if file and file.filename != '' and allowed_file(file.filename):
                                            filename = secure_filename(file.filename)
                                            unique_filename = f"{uuid.uuid4().hex}_{filename}"
                                            filepath = os.path.join('empilhadeiras', f'{instalacao_id}_{j}_{k}_{unique_filename}')
                                            full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                                            try:
                                                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                                                file.save(full_path)
                                            except Exception as save_err:
                                                print('[ERROR cadastro empilhadeira foto] falha ao salvar', full_path, save_err)
                                                continue
                                            db.execute(
                                                '''INSERT INTO fotos 
                                                (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                                VALUES (?, ?, ?, ?)''',
                                                ('empilhadeira', empilhadeira_id, filepath, 'empilhadeira')
                                            )
                            db.execute('RELEASE sp_emp_create')
                        except Exception as outer_err:
                            print('[WARN cadastro empilhadeira bloco] erro inesperado:', outer_err)
                            try:
                                db.execute('ROLLBACK TO sp_emp_create')
                                db.execute('RELEASE sp_emp_create')
                            except Exception:
                                pass
                    
                    # Processar sistemas de segurança
                    sistemas_count = int(request.form.get(f'sistemas_count_{i}', 0))
                    for j in range(sistemas_count):
                        tipo = request.form.get(f'sistema_tipo_{i}_{j}')
                        descricao = request.form.get(f'sistema_descricao_{i}_{j}')
                        situacao = request.form.get(f'sistema_situacao_{i}_{j}')
                        ultima_manutencao = request.form.get(f'sistema_ultima_manutencao_{i}_{j}')
                        proxima_manutencao = request.form.get(f'sistema_proxima_manutencao_{i}_{j}')

                        if not tipo:
                            continue

                        if not any([tipo, descricao, situacao, ultima_manutencao, proxima_manutencao]):
                            continue

                        sis_cursor = db.execute(
                            '''INSERT INTO sistemas_seguranca 
                            (instalacao_id, tipo, descricao, situacao, ultima_manutencao,
                             proxima_manutencao) 
                            VALUES (?, ?, ?, ?, ?, ?)''',
                            (instalacao_id, tipo, descricao, situacao, ultima_manutencao, proxima_manutencao)
                        )
                        sis_id = sis_cursor.lastrowid

                        if f'sistema_fotos_{i}_{j}[]' in request.files:
                            files = request.files.getlist(f'sistema_fotos_{i}_{j}[]')
                            for k, file in enumerate(files):
                                if file and file.filename != '' and allowed_file(file.filename):
                                    filename = secure_filename(file.filename)
                                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                                    filepath = os.path.join('sistemas_seguranca', f'{instalacao_id}_{j}_{k}_{unique_filename}')
                                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                                    file.save(full_path)
                                    db.execute(
                                        '''INSERT INTO fotos 
                                        (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                        VALUES (?, ?, ?, ?)''',
                                        ('sistema_seguranca', sis_id, filepath, 'sistema')
                                    )

                    # Processar equipamentos de unitização
                    equipamentos_count = int(request.form.get(f'equipamentos_count_{i}', 0))
                    
                    for j in range(equipamentos_count):
                        tipo = request.form.get(f'equipamento_tipo_{i}_{j}')
                        quantidade = request.form.get(f'equipamento_quantidade_{i}_{j}') or 1
                        capacidade_kg = request.form.get(f'equipamento_capacidade_{i}_{j}') or 0
                        situacao = request.form.get(f'equipamento_situacao_{i}_{j}')
                        observacoes = request.form.get(f'equipamento_observacoes_{i}_{j}')
                        
                        if not tipo:
                            continue

                        cursor = db.execute(
                            '''INSERT INTO equipamentos_unitizacao 
                            (instalacao_id, tipo, quantidade, capacidade_kg, situacao, observacoes) 
                            VALUES (?, ?, ?, ?, ?, ?)''',
                            (instalacao_id, tipo, quantidade, capacidade_kg, situacao, observacoes)
                        )
                        
                        equipamento_id = cursor.lastrowid
                        
                        # Upload múltiplas fotos do equipamento
                        if f'equipamento_fotos_{i}_{j}[]' in request.files:
                            files = request.files.getlist(f'equipamento_fotos_{i}_{j}[]')
                            for k, file in enumerate(files):
                                if file and file.filename != '' and allowed_file(file.filename):
                                    filename = secure_filename(file.filename)
                                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                                    filepath = os.path.join('equipamentos_unitizacao', f'{instalacao_id}_{j}_{k}_{unique_filename}')
                                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                                    file.save(full_path)
                                    
                                    # Inserir foto na tabela de fotos
                                    db.execute(
                                        '''INSERT INTO fotos 
                                        (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                        VALUES (?, ?, ?, ?)''',
                                        ('equipamento_unitizacao', equipamento_id, filepath, 'equipamento')
                                    )
            
            db.commit()
            flash('Cadastro realizado com sucesso!', 'success')
            return redirect(url_for('visualizar_orgao', id=orgao_id))
            
        except Exception as e:
            db.rollback()
            flash(f'Erro no cadastro: {str(e)}', 'error')
            return redirect(url_for('cadastro'))
    
    return render_template('cadastro_op.html')

# Rota para editar órgão
@app.route('/orgao/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_orgao(id):
    db = database.get_db()
    
    # Buscar dados do órgão
    orgao = db.execute('SELECT * FROM orgao_provedor WHERE id = ?', (id,)).fetchone()
    
    if not orgao:
        flash('Órgão Provedor não encontrado!', 'error')
        return redirect(url_for('index'))
    
    # Verificar permissões
    nivel_acesso = session.get('nivel_acesso', 'visualizador')
    if nivel_acesso == 'visualizador':
        flash('Acesso negado. Visualizadores não podem editar cadastros.', 'error')
        return redirect(url_for('index'))
    
    # Usuários com perfil 'cadastrador' só podem editar o cadastro do seu órgão provedor (não de outros)
    if nivel_acesso == 'cadastrador':
        usuario = db.execute('SELECT orgao_provedor FROM usuarios WHERE id = ?', (session['user_id'],)).fetchone()
        if not usuario or usuario['orgao_provedor'] != orgao['nome']:
            flash('Você só pode editar o cadastro do seu órgão provedor.', 'error')
            return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            try:
                print('[DEBUG editar] request.files keys:', list(request.files.keys()))
            except Exception:
                pass

            # Exclusão de fotos existentes (checkbox no formulário)
            delete_ids_raw = request.form.getlist('delete_foto_ids[]')
            delete_ids = []
            for val in delete_ids_raw:
                try:
                    delete_ids.append(int(val))
                except Exception:
                    continue
            if delete_ids:
                placeholders = ','.join('?' for _ in delete_ids)
                rows = db.execute(f"SELECT id, caminho_arquivo FROM fotos WHERE id IN ({placeholders})", delete_ids).fetchall()
                for row in rows:
                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], row['caminho_arquivo'].replace('/', os.sep))
                    try:
                        if os.path.exists(full_path):
                            os.remove(full_path)
                            print('[DEBUG editar] foto removida do disco', full_path)
                    except Exception as err_rm:
                        print('[WARN editar] falha ao remover arquivo', full_path, err_rm)
                db.execute(f"DELETE FROM fotos WHERE id IN ({placeholders})", delete_ids)
                print('[DEBUG editar] fotos removidas ids:', delete_ids)
            # Utilitário para descobrir índices existentes nos campos do form
            def collect_indices(prefix):
                indices = set()
                for key in request.form.keys():
                    if key.startswith(prefix):
                        # espera padrão prefix_<idx> ou prefix_x_y; pegar primeiro número
                        parts = key.split('_')
                        for part in parts[::-1]:
                            if part.isdigit():
                                indices.add(int(part))
                                break
                return sorted(indices)

            def to_int(val):
                if val is None:
                    return None
                text = str(val).strip().replace('.', '').replace(',', '.')
                if text == '':
                    return None
                try:
                    return int(float(text))
                except Exception:
                    return None

            def to_float(val):
                if val is None:
                    return None
                text = str(val).strip().replace('.', '').replace(',', '.')
                if text == '':
                    return None
                try:
                    return float(text)
                except Exception:
                    return None

            # Buscar registros atuais para manter valores quando o campo não for enviado
            energia = db.execute('SELECT * FROM energia_eletrica WHERE orgao_provedor_id = ?', (id,)).fetchone()

            form_keys = list(request.form.keys())
            def has_prefix(prefix_list):
                return any(any(k.startswith(p) for p in prefix_list) for k in form_keys)

            # Debug temporário: acompanhar payload de pessoal
            try:
                debug_pessoal = {
                    'payload_flag': request.form.get('pessoal_payload'),
                    'pessoal_count': request.form.get('pessoal_count'),
                    'pessoal_keys': [k for k in form_keys if k.startswith('pessoal_')][:10]
                }
                print('[DEBUG editar_orgao] Pessoal payload ->', debug_pessoal)
            except Exception:
                pass

            # Coletar dados do formulário (preservando valores antigos quando campo vier vazio)
            unidade_gestora = request.form.get('unidade_gestora') or orgao['unidade_gestora'] or ''
            codom = request.form.get('codom') or orgao['codom'] or ''
            om_licitacao_qs = request.form.get('om_licitacao_qs') or orgao['om_licitacao_qs'] or ''
            om_licitacao_qr = request.form.get('om_licitacao_qr') or orgao['om_licitacao_qr'] or ''
            subordinacao = request.form.get('subordinacao') or orgao['subordinacao'] or ''
            efetivo_raw = to_int(request.form.get('efetivo'))
            efetivo = efetivo_raw if efetivo_raw is not None else (orgao['efetivo_atendimento'] or 0)
            data_criacao = request.form.get('data_criacao') or orgao['data_criacao'] or ''
            # Obter OMs que apoiam (seleção múltipla)
            oms_que_apoia = request.form.getlist('oms_que_apoia[]')
            if len(oms_que_apoia) == 1 and ',' in (oms_que_apoia[0] or ''):
                oms_que_apoia = [s.strip() for s in oms_que_apoia[0].split(',') if s.strip()]
            historico = ', '.join(oms_que_apoia) if oms_que_apoia else (orgao['historico'] or '')
            missao = request.form.get('missao') or orgao['missao'] or ''

            consumo_secos_raw = to_float(request.form.get('consumo_secos'))
            consumo_secos = consumo_secos_raw if consumo_secos_raw is not None else (orgao['consumo_secos_mensal'] or 0)

            consumo_frigorificados_raw = to_float(request.form.get('consumo_frigorificados'))
            consumo_frigorificados = consumo_frigorificados_raw if consumo_frigorificados_raw is not None else (orgao['consumo_frigorificados_mensal'] or 0)

            suprimento_secos_raw = to_float(request.form.get('suprimento_secos'))
            suprimento_secos = suprimento_secos_raw if suprimento_secos_raw is not None else (orgao['suprimento_secos_mensal'] or 0)

            suprimento_frigorificados_raw = to_float(request.form.get('suprimento_frigorificados'))
            suprimento_frigorificados = suprimento_frigorificados_raw if suprimento_frigorificados_raw is not None else (orgao['suprimento_frigorificados_mensal'] or 0)

            area_edificavel_raw = to_float(request.form.get('area_edificavel'))
            area_edificavel = area_edificavel_raw if area_edificavel_raw is not None else (orgao['area_edificavel_disponivel'] or 0)

            classes_list = request.form.getlist('classes_provedor')
            classes_provedor = ', '.join([c for c in classes_list if c])
            apoia_classe_i = any('classe i' in (c or '').lower() or (c or '').strip().upper() == 'I' for c in classes_list)

            capacidade_total_toneladas_raw = to_float(request.form.get('capacidade_total_toneladas'))
            capacidade_total_toneladas = capacidade_total_toneladas_raw if capacidade_total_toneladas_raw is not None else (orgao['capacidade_total_toneladas'] or 0)

            capacidade_total_toneladas_seco_raw = to_float(request.form.get('capacidade_total_toneladas_seco'))
            capacidade_total_toneladas_seco = capacidade_total_toneladas_seco_raw if capacidade_total_toneladas_seco_raw is not None else (orgao['capacidade_total_toneladas_seco'] or 0)

            if not apoia_classe_i:
                efetivo = 0
                consumo_secos = 0
                consumo_frigorificados = 0
                suprimento_secos = 0
                suprimento_frigorificados = 0
            
            # Atualizar dados do órgão
            cursor = db.execute('''
                UPDATE orgao_provedor 
                                SET unidade_gestora = ?, codom = ?, om_licitacao_qs = ?, om_licitacao_qr = ?,
                                        subordinacao = ?, efetivo_atendimento = ?, data_criacao = ?,
                                        historico = ?, missao = ?, consumo_secos_mensal = ?,
                                        consumo_frigorificados_mensal = ?, suprimento_secos_mensal = ?,
                                        suprimento_frigorificados_mensal = ?, area_edificavel_disponivel = ?,
                                        classes_provedor = ?, capacidade_total_toneladas = ?, capacidade_total_toneladas_seco = ?
                WHERE id = ?
            ''', (unidade_gestora, codom, om_licitacao_qs, om_licitacao_qr,
                  subordinacao, efetivo, data_criacao, historico, missao,
                                    consumo_secos, consumo_frigorificados, suprimento_secos,
                                    suprimento_frigorificados, area_edificavel, classes_provedor, capacidade_total_toneladas, capacidade_total_toneladas_seco, id))
            updated_rows = cursor.rowcount

            # Energia elétrica (substitui registro anterior)
            dimensionamento_energia = request.form.get('dimensionamento_energia') or (energia['dimensionamento_adequado'] if energia else '')
            capacidade_total_kva_raw = to_float(request.form.get('capacidade_total_kva'))
            capacidade_total_kva = capacidade_total_kva_raw if capacidade_total_kva_raw is not None else ((energia['capacidade_total_kva'] if energia else 0) or 0)
            observacoes_energia = request.form.get('observacoes_energia') or (energia['observacoes_energia'] if energia else '')

            db.execute('DELETE FROM energia_eletrica WHERE orgao_provedor_id = ?', (id,))
            if dimensionamento_energia or capacidade_total_kva or observacoes_energia:
                db.execute(
                    '''INSERT INTO energia_eletrica 
                    (orgao_provedor_id, dimensionamento_adequado, capacidade_total_kva, observacoes_energia) 
                    VALUES (?, ?, ?, ?)''',
                    (id, dimensionamento_energia, capacidade_total_kva, observacoes_energia)
                )

            # Geradores: limpa existentes e regrava tudo conforme formulário (sempre)
            geradores_count = to_int(request.form.get('geradores_count')) or 0
            geradores_indices = list(range(geradores_count)) if geradores_count > 0 else collect_indices('gerador_capacidade')

            existing_g_ids = db.execute('SELECT id FROM geradores WHERE orgao_provedor_id = ?', (id,)).fetchall()
            if existing_g_ids:
                ids = [row['id'] for row in existing_g_ids]
                placeholders = ','.join(['?'] * len(ids))
                db.execute(f"DELETE FROM fotos WHERE tabela_origem='gerador' AND registro_id IN ({placeholders})", ids)
            db.execute('DELETE FROM geradores WHERE orgao_provedor_id = ?', (id,))

            allowed_situacoes_ger = {'operacional', 'em_manutencao', 'baixada', 'disponivel', 'indisponivel_recuperavel', 'indisponivel'}

            if geradores_indices:
                print('[DEBUG editar geradores] count declarada:', geradores_count, 'indices:', geradores_indices)
                try:
                    db.execute('SAVEPOINT sp_geradores_edit')
                    for g in geradores_indices:
                        capacidade = to_float(request.form.get(f'gerador_capacidade_{g}'))
                        marca = request.form.get(f'gerador_marca_{g}')
                        ano_fabricacao = to_int(request.form.get(f'gerador_ano_{g}'))
                        situacao_raw = (request.form.get(f'gerador_situacao_{g}') or '').strip().lower()
                        if situacao_raw in ['operacional', 'disponivel', 'disponível']:
                            situacao = 'disponivel'
                        elif situacao_raw in ['em_manutencao', 'em manutencao', 'manutencao', 'manutenção']:
                            situacao = 'indisponivel_recuperavel'
                        elif situacao_raw in ['baixada', 'inoperante']:
                            situacao = 'indisponivel'
                        elif situacao_raw in allowed_situacoes_ger:
                            situacao = situacao_raw
                        else:
                            situacao = 'disponivel'
                        valor_recuperacao = to_float(request.form.get(f'gerador_valor_recuperacao_{g}'))
                        pode_24h = to_int(request.form.get(f'gerador_24h_{g}', 0)) or 0
                        horas_operacao = to_float(request.form.get(f'gerador_horas_{g}'))
                        ultima_manutencao = request.form.get(f'gerador_ultima_manutencao_{g}')
                        proxima_manutencao = request.form.get(f'gerador_proxima_manutencao_{g}')
                        observacoes = request.form.get(f'gerador_observacoes_{g}')

                        print('[DEBUG editar gerador card]', g, {
                            'capacidade': capacidade, 'marca': marca, 'ano': ano_fabricacao,
                            'situacao_raw': situacao_raw, 'situacao_final': situacao,
                            'valor': valor_recuperacao, 'pode_24h': pode_24h, 'horas': horas_operacao
                        })

                        if not any([
                            capacidade, marca, ano_fabricacao, situacao_raw, valor_recuperacao,
                            pode_24h, horas_operacao, ultima_manutencao, proxima_manutencao, observacoes
                        ]):
                            print('[DEBUG editar gerador card skip vazio]', g)
                            continue

                        capacidade_final = capacidade if capacidade is not None else 0

                        try:
                            ger_cursor = db.execute(
                                '''INSERT INTO geradores 
                                (orgao_provedor_id, capacidade_kva, marca_modelo, ano_fabricacao, situacao, valor_recuperacao, 
                                 pode_operar_24h, horas_operacao_continuas, ultima_manutencao, 
                                 proxima_manutencao, observacoes) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (id, capacidade_final, marca, ano_fabricacao, situacao, valor_recuperacao, 
                                 pode_24h, horas_operacao, ultima_manutencao, proxima_manutencao, observacoes)
                            )
                        except Exception as err:
                            print('[WARN editar gerador] skip insert por erro:', err, 'dados=', {
                                'capacidade': capacidade_final, 'marca': marca, 'ano': ano_fabricacao,
                                'situacao': situacao, 'valor': valor_recuperacao, 'pode_24h': pode_24h,
                                'horas': horas_operacao, 'ultima': ultima_manutencao, 'proxima': proxima_manutencao
                            })
                            db.execute('ROLLBACK TO sp_geradores_edit')
                            continue

                        gerador_id = ger_cursor.lastrowid

                        if f'gerador_fotos_{g}[]' in request.files:
                            files = request.files.getlist(f'gerador_fotos_{g}[]')
                            for i, file in enumerate(files):
                                if file and file.filename and allowed_file(file.filename):
                                    filename = secure_filename(file.filename)
                                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                                    filepath = os.path.join('geradores', f'{id}_{g}_{i}_{unique_filename}')
                                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                                    file.save(full_path)
                                    db.execute(
                                        '''INSERT INTO fotos 
                                        (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                        VALUES (?, ?, ?, ?)''',
                                        ('gerador', gerador_id, filepath, 'gerador')
                                    )
                    db.execute('RELEASE sp_geradores_edit')
                except Exception as outer_err:
                    print('[WARN editar gerador bloco] erro inesperado:', outer_err)
                    try:
                        db.execute('ROLLBACK TO sp_geradores_edit')
                        db.execute('RELEASE sp_geradores_edit')
                    except Exception:
                        pass

            # Fotos área edificável: só se houver upload
            area_keys = [k for k in request.files.keys() if k.startswith('foto_area_edificavel')]
            if area_keys:
                print('[DEBUG editar] area_edificavel file keys:', area_keys)
                db.execute("DELETE FROM fotos WHERE tabela_origem = 'area_edificavel' AND registro_id = ?", (id,))
            else:
                print('[DEBUG editar] nenhuma foto_area_edificavel no payload')
            fotos_area_added = 0
            fotos_area_paths = []
            for key in area_keys:
                files_area = request.files.getlist(key)
                for idx, file in enumerate(files_area):
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4().hex}_{filename}"
                        filepath = f"areas_edificaveis/{id}_{idx}_{unique_filename}"
                        full_path = os.path.join(app.config['UPLOAD_FOLDER'], 'areas_edificaveis', f'{id}_{idx}_{unique_filename}')
                        try:
                            os.makedirs(os.path.dirname(full_path), exist_ok=True)
                            file.save(full_path)
                            print('[DEBUG editar] area_edificavel saved', full_path)
                        except Exception as save_err:
                            print('[ERROR editar] ao salvar area_edificavel', full_path, save_err)
                            continue
                        db.execute(
                            '''INSERT INTO fotos (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                               VALUES (?, ?, ?, ?)''',
                            ('area_edificavel', id, filepath, 'area_edificavel')
                        )
                        fotos_area_added += 1
                        fotos_area_paths.append(filepath)
            print('[DEBUG editar] area_edificavel inserted rows:', fotos_area_added, fotos_area_paths)

            # Pessoal: processa apenas se houver payload com ao menos 1 entrada
            try:
                pessoal_payload = int(request.form.get('pessoal_payload', '0') or 0)
            except Exception:
                pessoal_payload = 0

            if pessoal_payload > 0:
                pessoal_count = to_int(request.form.get('pessoal_count')) or 0

                # Não apaga se o payload está inconsistente (flag >0 mas count zerado)
                if pessoal_count == 0:
                    print('[DEBUG editar_orgao] Pessoal payload >0 mas pessoal_count=0; mantendo dados antigos')
                else:
                    db.execute('DELETE FROM pessoal WHERE orgao_provedor_id = ?', (id,))
                    pessoal_indices = list(range(pessoal_count)) if pessoal_count > 0 else collect_indices('pessoal_posto')
                    print('[DEBUG editar_orgao] Inserindo pessoal indices', pessoal_indices)
                    flash(f'Pessoal recebido: {len(pessoal_indices)} entradas', 'info')
                    for p in pessoal_indices:
                        posto = request.form.get(f'pessoal_posto_{p}')
                        arma = request.form.get(f'pessoal_arma_{p}')
                        especialidade = request.form.get(f'pessoal_especialidade_{p}')
                        funcao = request.form.get(f'pessoal_funcao_{p}')
                        tipo_servico_raw = request.form.get(f'pessoal_tipo_{p}')
                        quantidade_raw = request.form.get(f'pessoal_quantidade_{p}')
                        observacoes = request.form.get(f'pessoal_observacoes_{p}')
                        if not any([posto, arma, especialidade, funcao, tipo_servico_raw, quantidade_raw, observacoes]):
                            continue

                        quantidade = quantidade_raw if quantidade_raw not in (None, '') else 1

                        tipo_servico = (tipo_servico_raw or '').strip().lower()
                        if tipo_servico not in ('carreira', 'temporario'):
                            tipo_servico = 'carreira'

                        db.execute(
                            '''INSERT INTO pessoal 
                            (orgao_provedor_id, posto_graduacao, arma_quadro_servico, especialidade,
                             funcao, tipo_servico, quantidade, observacoes) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (id, posto, arma, especialidade, funcao, tipo_servico, quantidade, observacoes)
                        )

            # Viaturas: limpar e reprocessar sempre
            via_ids = [r['id'] for r in db.execute('SELECT id FROM viaturas WHERE orgao_provedor_id = ?', (id,)).fetchall()]
            if via_ids:
                placeholders = ','.join(['?'] * len(via_ids))
                db.execute(f"DELETE FROM fotos WHERE tabela_origem = 'viatura' AND registro_id IN ({placeholders})", via_ids)
            db.execute('DELETE FROM viaturas WHERE orgao_provedor_id = ?', (id,))

            viaturas_count = to_int(request.form.get('viaturas_count')) or 0
            viaturas_indices = list(range(viaturas_count)) if viaturas_count > 0 else collect_indices('viatura_tipo')
            if viaturas_indices:
                print('[DEBUG editar viaturas] count declarada:', viaturas_count, 'indices:', viaturas_indices)
                try:
                    db.execute('SAVEPOINT sp_viaturas_edit')
                    for v in viaturas_indices:
                        categoria = request.form.get(f'viatura_categoria_{v}') or ''
                        tipo_veiculo = request.form.get(f'viatura_tipo_{v}')
                        eb = request.form.get(f'viatura_eb_{v}')
                        placa = eb
                        especializacao = request.form.get(f'viatura_especializacao_{v}')
                        marca = request.form.get(f'viatura_marca_{v}')
                        modelo = request.form.get(f'viatura_modelo_{v}')
                        ano_fabricacao = request.form.get(f'viatura_ano_{v}')
                        capacidade_carga_kg = request.form.get(f'viatura_capacidade_{v}') or 0
                        lotacao_pessoas = request.form.get(f'viatura_lotacao_{v}')
                        situacao_raw = (request.form.get(f'viatura_situacao_{v}') or '').strip().lower()
                        if situacao_raw in ['operacional', 'disponivel', 'disponível']:
                            situacao = 'operacional'
                        elif situacao_raw in ['em_manutencao', 'em manutencao', 'manutencao', 'manutenção']:
                            situacao = 'em_manutencao'
                        elif situacao_raw in ['baixada', 'baixado']:
                            situacao = 'baixada'
                        elif situacao_raw in ['inoperante', 'indisponivel', 'indisponível']:
                            situacao = 'inoperante'
                        else:
                            situacao = 'operacional'
                        km_atual = request.form.get(f'viatura_km_{v}')
                        ultima_manutencao = request.form.get(f'viatura_ultima_manutencao_{v}')
                        proxima_manutencao = request.form.get(f'viatura_proxima_manutencao_{v}')
                        patrimonio = request.form.get(f'viatura_patrimonio_{v}')
                        raw_valor = request.form.get(f'viatura_valor_recuperacao_{v}')
                        valor_recuperacao = float(raw_valor) if raw_valor else None
                        observacoes = request.form.get(f'viatura_observacoes_{v}')

                        print('[DEBUG editar viatura card]', v, {
                            'tipo': tipo_veiculo, 'placa': placa, 'marca': marca,
                            'situacao_raw': situacao_raw, 'situacao_final': situacao, 'valor': valor_recuperacao
                        })

                        if not tipo_veiculo or not placa:
                            print('[DEBUG editar viatura card skip falta campos obrigatórios]', v)
                            continue

                        if not any([tipo_veiculo, eb, especializacao, marca, modelo, ano_fabricacao, capacidade_carga_kg, lotacao_pessoas, situacao, km_atual, ultima_manutencao, proxima_manutencao, patrimonio, valor_recuperacao, observacoes]):
                            print('[DEBUG editar viatura card skip vazio]', v)
                            continue

                        try:
                            cursor = db.execute(
                                '''INSERT INTO viaturas 
                                (orgao_provedor_id, categoria, tipo_veiculo, especializacao, placa, marca, modelo,
                                 ano_fabricacao, capacidade_carga_kg, lotacao_pessoas, situacao, valor_recuperacao, km_atual, ultima_manutencao,
                                 proxima_manutencao, patrimonio, observacoes) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (id, categoria, tipo_veiculo, especializacao, placa, marca, modelo, ano_fabricacao,
                                 capacidade_carga_kg, lotacao_pessoas, situacao, valor_recuperacao, km_atual, ultima_manutencao, proxima_manutencao,
                                 patrimonio, observacoes)
                            )
                        except Exception as err:
                            print('[WARN editar viatura] skip insert por erro:', err, 'dados=', {
                                'tipo': tipo_veiculo, 'placa': placa, 'marca': marca, 'modelo': modelo,
                                'ano': ano_fabricacao, 'situacao': situacao, 'valor': valor_recuperacao
                            })
                            db.execute('ROLLBACK TO sp_viaturas_edit')
                            continue
                        viatura_id = cursor.lastrowid

                        if f'viatura_fotos_{v}[]' in request.files:
                            files = request.files.getlist(f'viatura_fotos_{v}[]')
                            for i, file in enumerate(files):
                                if file and file.filename != '' and allowed_file(file.filename):
                                    filename = secure_filename(file.filename)
                                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                                    filepath = os.path.join('viaturas', f'{id}_{v}_{i}_{unique_filename}')
                                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                                    file.save(full_path)
                                    db.execute(
                                        '''INSERT INTO fotos 
                                        (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                        VALUES (?, ?, ?, ?)''',
                                        ('viatura', viatura_id, filepath, 'viatura')
                                    )
                    db.execute('RELEASE sp_viaturas_edit')
                except Exception as outer_err:
                    print('[WARN editar viatura bloco] erro inesperado:', outer_err)
                    try:
                        db.execute('ROLLBACK TO sp_viaturas_edit')
                        db.execute('RELEASE sp_viaturas_edit')
                    except Exception:
                        pass

            # Instalações e subitens: limpar e reprocessar sempre
            inst_ids = [r['id'] for r in db.execute('SELECT id FROM instalacoes WHERE orgao_provedor_id = ?', (id,)).fetchall()]
            if inst_ids:
                ph_inst = ','.join(['?'] * len(inst_ids))
                emp_ids = [r['id'] for r in db.execute(f'SELECT id FROM empilhadeiras WHERE instalacao_id IN ({ph_inst})', inst_ids).fetchall()]
                sis_ids = [r['id'] for r in db.execute(f'SELECT id FROM sistemas_seguranca WHERE instalacao_id IN ({ph_inst})', inst_ids).fetchall()]
                eq_ids = [r['id'] for r in db.execute(f'SELECT id FROM equipamentos_unitizacao WHERE instalacao_id IN ({ph_inst})', inst_ids).fetchall()]

                def del_with_ids(query_base, ids_list):
                    if not ids_list:
                        return
                    placeholders = ','.join(['?'] * len(ids_list))
                    db.execute(f"{query_base} ({placeholders})", ids_list)

                del_with_ids("DELETE FROM fotos WHERE tabela_origem = 'empilhadeira' AND registro_id IN", emp_ids)
                del_with_ids("DELETE FROM fotos WHERE tabela_origem = 'sistema_seguranca' AND registro_id IN", sis_ids)
                del_with_ids("DELETE FROM fotos WHERE tabela_origem = 'equipamento_unitizacao' AND registro_id IN", eq_ids)
                del_with_ids("DELETE FROM fotos WHERE tabela_origem = 'instalacao' AND registro_id IN", inst_ids)

                del_with_ids('DELETE FROM empilhadeiras WHERE instalacao_id IN', inst_ids)
                del_with_ids('DELETE FROM sistemas_seguranca WHERE instalacao_id IN', inst_ids)
                del_with_ids('DELETE FROM equipamentos_unitizacao WHERE instalacao_id IN', inst_ids)
                del_with_ids('DELETE FROM instalacoes WHERE id IN', inst_ids)

            instalacoes_count = to_int(request.form.get('instalacoes_count')) or 0
            instalacoes_indices = list(range(instalacoes_count)) if instalacoes_count > 0 else collect_indices('tipo_instalacao')

            for i in instalacoes_indices:
                tipo_instalacao = request.form.get(f'tipo_instalacao_{i}')
                nome_instalacao = request.form.get(f'instalacao_nome_{i}')
                descricao = request.form.get(f'descricao_{i}')
                data_construcao = request.form.get(f'data_construcao_{i}')
                tipo_cobertura = request.form.get(f'tipo_cobertura_{i}')
                capacidade_toneladas = request.form.get(f'capacidade_{i}') or 0
                largura = request.form.get(f'largura_{i}') or 0
                comprimento = request.form.get(f'comprimento_{i}') or 0
                altura = request.form.get(f'altura_{i}') or 0
                verticalizacao = request.form.get(f'verticalizacao_{i}')

                if not tipo_instalacao:
                    continue

                cursor = db.execute(
                    '''INSERT INTO instalacoes 
                    (orgao_provedor_id, tipo_instalacao, nome_identificacao, descricao, data_construcao,
                     tipo_cobertura, capacidade_toneladas, largura, comprimento,
                     altura, verticalizacao) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (id, tipo_instalacao, nome_instalacao, descricao, data_construcao, tipo_cobertura,
                     capacidade_toneladas, largura, comprimento, altura, verticalizacao)
                )
                instalacao_id = cursor.lastrowid

                if f'instalacao_fotos_{i}[]' in request.files:
                    files = request.files.getlist(f'instalacao_fotos_{i}[]')
                    for j, file in enumerate(files):
                        if file and file.filename != '' and allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            unique_filename = f"{uuid.uuid4().hex}_{filename}"
                            filepath = os.path.join('instalacoes', f'{id}_{i}_{j}_{unique_filename}')
                            full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                            file.save(full_path)
                            db.execute(
                                '''INSERT INTO fotos 
                                (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                VALUES (?, ?, ?, ?)''',
                                ('instalacao', instalacao_id, filepath, 'instalacao')
                            )

                if tipo_instalacao and 'deposito' in tipo_instalacao:
                    emp_count = to_int(request.form.get(f'empilhadeiras_count_{i}')) or 0
                    emp_indices = list(range(emp_count)) if emp_count > 0 else collect_indices(f'empilhadeira_tipo_{i}')
                    allowed_emp_situacoes = {'disponivel', 'indisponivel_recuperavel', 'indisponivel'}

                    if emp_indices:
                        print('[DEBUG editar empilhadeiras] instalacao idx', i, 'count declarada:', emp_count, 'indices:', emp_indices)
                        try:
                            db.execute('SAVEPOINT sp_emp_edit')
                            for j in emp_indices:
                                tipo = request.form.get(f'empilhadeira_tipo_{i}_{j}')
                                cap_raw = request.form.get(f'empilhadeira_capacidade_{i}_{j}')
                                qtd_raw = request.form.get(f'empilhadeira_quantidade_{i}_{j}')
                                ano_fabricacao = request.form.get(f'empilhadeira_ano_{i}_{j}')
                                situacao_raw = (request.form.get(f'empilhadeira_situacao_{i}_{j}') or '').strip().lower()
                                valor_raw = request.form.get(f'empilhadeira_valor_recuperacao_{i}_{j}')

                                print('[DEBUG editar empilhadeira card]', j, {
                                    'tipo': tipo, 'capacidade': cap_raw, 'quantidade': qtd_raw,
                                    'ano': ano_fabricacao, 'situacao_raw': situacao_raw, 'valor_raw': valor_raw
                                })

                                # Log extra se vier tudo vazio: ajudar a identificar nomes/numeracao
                                if not any([tipo, cap_raw, qtd_raw, ano_fabricacao, situacao_raw, valor_raw]):
                                    print('[DEBUG empilhadeira form keys]', [k for k in request.form.keys() if f'empilhadeira' in k])

                                if not tipo:
                                    print('[DEBUG editar empilhadeira card skip sem tipo]', j)
                                    continue

                                if not any([tipo, cap_raw, qtd_raw, ano_fabricacao, situacao_raw, valor_raw]):
                                    print('[DEBUG editar empilhadeira card skip vazio]', j)
                                    continue

                                capacidade = cap_raw or 0
                                quantidade = qtd_raw or 1
                                valor_recuperacao = valor_raw or 0

                                if situacao_raw in ['indisponivel_recuperavel', 'indisponível recuperável', 'indisponivel recuperavel']:
                                    situacao = 'indisponivel_recuperavel'
                                elif situacao_raw in [
                                    'indisponivel', 'indisponível', 'indisponivel_descarga',
                                    'indisponivel para descarga', 'indisponivel_para_descarga',
                                    'inoperante', 'baixada'
                                ]:
                                    situacao = 'indisponivel'
                                elif situacao_raw in ['operacional', 'em_manutencao', 'em manutencao', 'disponivel']:
                                    situacao = 'disponivel'
                                else:
                                    situacao = 'disponivel'

                                if situacao not in allowed_emp_situacoes:
                                    situacao = 'disponivel'
                                if situacao not in allowed_emp_situacoes:
                                    print('[DEBUG editar empilhadeira card skip situacao invalida]', j, situacao_raw)
                                    continue

                                try:
                                    emp_cursor = db.execute(
                                        '''INSERT INTO empilhadeiras 
                                        (instalacao_id, tipo, capacidade, quantidade, ano_fabricacao,
                                         situacao, valor_recuperacao) 
                                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                        (instalacao_id, tipo, capacidade, quantidade, ano_fabricacao,
                                         situacao, valor_recuperacao)
                                    )
                                    emp_id = emp_cursor.lastrowid
                                except Exception as err:
                                    print('[WARN editar empilhadeira] skip insert por erro:', err, 'dados=', {
                                        'tipo': tipo, 'capacidade': capacidade, 'quantidade': quantidade,
                                        'ano': ano_fabricacao, 'situacao': situacao, 'raw': situacao_raw,
                                        'valor': valor_recuperacao
                                    })
                                    db.execute('ROLLBACK TO sp_emp_edit')
                                    continue

                                if f'empilhadeira_fotos_{i}_{j}[]' in request.files:
                                    files = request.files.getlist(f'empilhadeira_fotos_{i}_{j}[]')
                                    for k, file in enumerate(files):
                                        if file and file.filename != '' and allowed_file(file.filename):
                                            filename = secure_filename(file.filename)
                                            unique_filename = f"{uuid.uuid4().hex}_{filename}"
                                            filepath = os.path.join('empilhadeiras', f'{instalacao_id}_{j}_{k}_{unique_filename}')
                                            full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                                            try:
                                                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                                                file.save(full_path)
                                            except Exception as save_err:
                                                print('[ERROR editar empilhadeira foto] falha ao salvar', full_path, save_err)
                                                continue
                                            db.execute(
                                                '''INSERT INTO fotos 
                                                (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                                VALUES (?, ?, ?, ?)''',
                                                ('empilhadeira', emp_id, filepath, 'empilhadeira')
                                            )
                            db.execute('RELEASE sp_emp_edit')
                        except Exception as outer_err:
                            print('[WARN editar empilhadeira bloco] erro inesperado:', outer_err)
                            try:
                                db.execute('ROLLBACK TO sp_emp_edit')
                                db.execute('RELEASE sp_emp_edit')
                            except Exception:
                                pass

                    sis_count = to_int(request.form.get(f'sistemas_count_{i}')) or 0
                    for j in range(sis_count):
                        tipo = request.form.get(f'sistema_tipo_{i}_{j}')
                        descricao = request.form.get(f'sistema_descricao_{i}_{j}')
                        situacao = request.form.get(f'sistema_situacao_{i}_{j}')
                        ultima_manutencao = request.form.get(f'sistema_ultima_manutencao_{i}_{j}')
                        proxima_manutencao = request.form.get(f'sistema_proxima_manutencao_{i}_{j}')

                        if not tipo:
                            continue

                        if not any([tipo, descricao, situacao, ultima_manutencao, proxima_manutencao]):
                            continue

                        sis_cursor = db.execute(
                            '''INSERT INTO sistemas_seguranca 
                            (instalacao_id, tipo, descricao, situacao, ultima_manutencao,
                             proxima_manutencao) 
                            VALUES (?, ?, ?, ?, ?, ?)''',
                            (instalacao_id, tipo, descricao, situacao, ultima_manutencao, proxima_manutencao)
                        )
                        sis_id = sis_cursor.lastrowid

                        if f'sistema_fotos_{i}_{j}[]' in request.files:
                            files = request.files.getlist(f'sistema_fotos_{i}_{j}[]')
                            for k, file in enumerate(files):
                                if file and file.filename != '' and allowed_file(file.filename):
                                    filename = secure_filename(file.filename)
                                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                                    filepath = os.path.join('sistemas_seguranca', f'{instalacao_id}_{j}_{k}_{unique_filename}')
                                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                                    file.save(full_path)
                                    db.execute(
                                        '''INSERT INTO fotos 
                                        (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                        VALUES (?, ?, ?, ?)''',
                                        ('sistema_seguranca', sis_id, filepath, 'sistema')
                                    )

                    eq_count = to_int(request.form.get(f'equipamentos_count_{i}')) or 0
                    for j in range(eq_count):
                        tipo = request.form.get(f'equipamento_tipo_{i}_{j}')
                        quantidade = request.form.get(f'equipamento_quantidade_{i}_{j}') or 1
                        capacidade_kg = request.form.get(f'equipamento_capacidade_{i}_{j}') or 0
                        situacao = request.form.get(f'equipamento_situacao_{i}_{j}')
                        observacoes = request.form.get(f'equipamento_observacoes_{i}_{j}')

                        if not tipo:
                            continue

                        if not any([tipo, quantidade, capacidade_kg, situacao, observacoes]):
                            continue

                        eq_cursor = db.execute(
                            '''INSERT INTO equipamentos_unitizacao 
                            (instalacao_id, tipo, quantidade, capacidade_kg, situacao, observacoes) 
                            VALUES (?, ?, ?, ?, ?, ?)''',
                            (instalacao_id, tipo, quantidade, capacidade_kg, situacao, observacoes)
                        )
                        eq_id = eq_cursor.lastrowid

                        if f'equipamento_fotos_{i}_{j}[]' in request.files:
                            files = request.files.getlist(f'equipamento_fotos_{i}_{j}[]')
                            for k, file in enumerate(files):
                                if file and file.filename != '' and allowed_file(file.filename):
                                    filename = secure_filename(file.filename)
                                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                                    filepath = os.path.join('equipamentos_unitizacao', f'{instalacao_id}_{j}_{k}_{unique_filename}')
                                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
                                    file.save(full_path)
                                    db.execute(
                                        '''INSERT INTO fotos 
                                        (tabela_origem, registro_id, caminho_arquivo, tipo_foto) 
                                        VALUES (?, ?, ?, ?)''',
                                        ('equipamento_unitizacao', eq_id, filepath, 'equipamento')
                                    )

            db.commit()

            if updated_rows == 0:
                flash('Nenhum registro foi alterado. Verifique os dados e tente novamente.', 'error')
            else:
                flash('Dados salvos com sucesso!', 'success')
            return redirect(url_for('editar_orgao', id=id))
            
        except Exception as e:
            db.rollback()
            flash(f'Erro na atualização: {str(e)}', 'error')
    
    # Para GET, mostrar página de edição
    orgao_dict = dict(orgao) if orgao else None

    # Normalizar valores para exibição no modo edição
    if orgao_dict:
        # Substituir None por string vazia para evitar "None" no front
        for k, v in list(orgao_dict.items()):
            if v is None:
                orgao_dict[k] = ''

        auto_dados = get_dados_automaticos_op(orgao_dict.get('sigla') or orgao_dict.get('nome') or '')

        # Preencher histórico a partir da planilha se estiver vazio
        if not orgao_dict.get('historico'):
            hist_auto = auto_dados.get('oms_apoiadas') or []
            orgao_dict['historico'] = ', '.join(hist_auto) if hist_auto else ''

        # Efetivo: usar salvo; se zero/vazio, cair para efetivo automático
        efetivo_val = orgao_dict.get('efetivo_atendimento') or 0
        if not efetivo_val and auto_dados.get('efetivo_total'):
            orgao_dict['efetivo_atendimento'] = auto_dados['efetivo_total']
            efetivo_val = auto_dados['efetivo_total']

        # Garantir números default para campos numéricos
        for key in [
            'consumo_secos_mensal', 'consumo_frigorificados_mensal',
            'suprimento_secos_mensal', 'suprimento_frigorificados_mensal',
            'capacidade_total_toneladas', 'capacidade_total_toneladas_seco',
            'area_edificavel_disponivel'
        ]:
            if orgao_dict.get(key) is None:
                orgao_dict[key] = 0

        # Calcular suprimentos se não preenchidos e houver efetivo
        if efetivo_val:
            if not orgao_dict.get('suprimento_frigorificados_mensal'):
                orgao_dict['suprimento_frigorificados_mensal'] = round(efetivo_val * 0.0004 * 22, 2)
            if not orgao_dict.get('suprimento_secos_mensal'):
                orgao_dict['suprimento_secos_mensal'] = round(efetivo_val * 0.00055 * 22, 2)

    # Pré-carregar dados de todas as abas
    def rows_to_dicts(rows):
        return [dict(r) for r in rows] if rows else []

    energia = db.execute('SELECT * FROM energia_eletrica WHERE orgao_provedor_id = ?', (id,)).fetchone()

    # Geradores + fotos
    geradores_rows = db.execute('SELECT * FROM geradores WHERE orgao_provedor_id = ?', (id,)).fetchall()
    geradores = []
    for g in geradores_rows:
        g_dict = dict(g)
        fotos = db.execute(
            'SELECT id, caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
            ('gerador', g['id'])
        ).fetchall()
        g_dict['fotos'] = [dict(f) for f in fotos]
        geradores.append(g_dict)

    pessoal = db.execute('SELECT * FROM pessoal WHERE orgao_provedor_id = ?', (id,)).fetchall()

    # Viaturas + fotos
    viaturas_rows = db.execute('SELECT * FROM viaturas WHERE orgao_provedor_id = ?', (id,)).fetchall()
    viaturas = []
    for v in viaturas_rows:
        v_dict = dict(v)
        fotos = db.execute(
            'SELECT id, caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
            ('viatura', v['id'])
        ).fetchall()
        v_dict['fotos'] = [dict(f) for f in fotos]
        viaturas.append(v_dict)

    instalacoes_rows = db.execute('SELECT * FROM instalacoes WHERE orgao_provedor_id = ?', (id,)).fetchall()
    fotos_area_rows = db.execute("SELECT id, caminho_arquivo FROM fotos WHERE tabela_origem = 'area_edificavel' AND registro_id = ?", (id,)).fetchall()

    instalacoes = []
    for inst in instalacoes_rows:
        inst_d = dict(inst)
        inst_id = inst_d.get('id')

        # Fotos da instalação
        fotos_inst = db.execute(
            'SELECT id, caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
            ('instalacao', inst_id)
        ).fetchall()
        inst_d['fotos'] = [dict(f) for f in fotos_inst]

        # Empilhadeiras + fotos (apenas para instalações que sejam depósitos)
        tipo_inst_norm = ''
        try:
            tipo_inst_norm = unicodedata.normalize('NFD', inst_d.get('tipo_instalacao', '') or '').encode('ascii', 'ignore').decode('ascii').lower()
        except Exception:
            tipo_inst_norm = (inst_d.get('tipo_instalacao') or '').lower()
        if 'deposit' in tipo_inst_norm:  # pega "deposito", "depósito", etc.
            emp_rows = db.execute('SELECT * FROM empilhadeiras WHERE instalacao_id = ?', (inst_id,)).fetchall()
            emp_list = []
            for emp in emp_rows:
                emp_d = dict(emp)
                fotos_emp = db.execute(
                    'SELECT id, caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
                    ('empilhadeira', emp['id'])
                ).fetchall()
                emp_d['fotos'] = [dict(f) for f in fotos_emp]
                emp_list.append(emp_d)
            inst_d['empilhadeiras'] = emp_list
        else:
            inst_d['empilhadeiras'] = []

        # Sistemas (mantém compatibilidade, sem fotos)
        inst_d['sistemas'] = rows_to_dicts(db.execute('SELECT * FROM sistemas_seguranca WHERE instalacao_id = ?', (inst_id,)).fetchall())

        # Equipamentos de unitização + fotos
        eq_rows = db.execute('SELECT * FROM equipamentos_unitizacao WHERE instalacao_id = ?', (inst_id,)).fetchall()
        eq_list = []
        for eq in eq_rows:
            eq_d = dict(eq)
            fotos_eq = db.execute(
                'SELECT id, caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
                ('equipamento_unitizacao', eq['id'])
            ).fetchall()
            eq_d['fotos'] = [dict(f) for f in fotos_eq]
            eq_list.append(eq_d)
        inst_d['equipamentos'] = eq_list

        instalacoes.append(inst_d)

    preload_data = dict(
        orgao=orgao_dict,
        energia=dict(energia) if energia else None,
        geradores=geradores,
        pessoal=rows_to_dicts(pessoal),
        viaturas=viaturas,
        instalacoes=instalacoes,
        fotos_area=[dict(row) for row in fotos_area_rows]
    )

    return render_template('cadastro_op.html', orgao=orgao_dict, edit_mode=True, preload_data=preload_data)

# Rota para visualizar órgão
@app.route('/orgao/<int:id>')
@login_required
def visualizar_orgao(id):
    db = database.get_db()
    
    try:
        # Buscar dados do órgão
        orgao = db.execute('SELECT * FROM orgao_provedor WHERE id = ?', (id,)).fetchone()
        
        if not orgao:
            flash('Órgão Provedor não encontrado!', 'error')
            return redirect(url_for('index'))
        
        # Verificar permissões
        nivel_acesso = session.get('nivel_acesso', 'visualizador')
        if nivel_acesso != 'admin':
            usuario = db.execute('SELECT orgao_provedor FROM usuarios WHERE id = ?', (session['user_id'],)).fetchone()
            if not usuario or usuario['orgao_provedor'] != orgao['nome']:
                flash('Você só pode visualizar o cadastro do seu próprio órgão.', 'error')
                return redirect(url_for('index'))

        # Normalizar dados do órgão e preencher faltantes para exibição
        orgao_dict = dict(orgao)

        # Guardar valores originais de suprimento antes de normalizar
        sup_frig_original = orgao_dict.get('suprimento_frigorificados_mensal')
        sup_seco_original = orgao_dict.get('suprimento_secos_mensal')

        # Substituir None ou string vazia por zero em campos numéricos
        for key in [
            'consumo_secos_mensal', 'consumo_frigorificados_mensal',
            'suprimento_secos_mensal', 'suprimento_frigorificados_mensal',
            'capacidade_total_toneladas', 'capacidade_total_toneladas_seco',
            'area_edificavel_disponivel'
        ]:
            if orgao_dict.get(key) in (None, ''):
                orgao_dict[key] = 0

        # Se não houver suprimento informado, calcular automaticamente a partir do efetivo
        auto_dados = get_dados_automaticos_op(orgao_dict.get('sigla') or orgao_dict.get('nome') or '')
        efetivo_val = orgao_dict.get('efetivo_atendimento') or auto_dados.get('efetivo_total') or 0
        if not orgao_dict.get('efetivo_atendimento') and efetivo_val:
            orgao_dict['efetivo_atendimento'] = efetivo_val

        if efetivo_val:
            if sup_frig_original in (None, ''):
                orgao_dict['suprimento_frigorificados_mensal'] = round(efetivo_val * 0.0004 * 22, 2)
            if sup_seco_original in (None, ''):
                orgao_dict['suprimento_secos_mensal'] = round(efetivo_val * 0.00055 * 22, 2)
        
        # Buscar energia elétrica
        energia = db.execute(
            'SELECT * FROM energia_eletrica WHERE orgao_provedor_id = ?', 
            (id,)
        ).fetchone()
        
        # Buscar geradores
        geradores = db.execute(
            'SELECT * FROM geradores WHERE orgao_provedor_id = ?', 
            (id,)
        ).fetchall()
        
        # Buscar fotos para geradores
        gerador_fotos = {}
        for gerador in geradores:
            fotos = db.execute(
                'SELECT caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
                ('gerador', gerador['id'])
            ).fetchall()
            gerador_fotos[gerador['id']] = [foto['caminho_arquivo'] for foto in fotos]
        
        # Buscar pessoal
        pessoal = db.execute(
            'SELECT * FROM pessoal WHERE orgao_provedor_id = ?',
            (id,)
        ).fetchall()
        
        # Buscar viaturas
        viaturas = db.execute('SELECT * FROM viaturas WHERE orgao_provedor_id = ?', (id,)).fetchall()
        
        # Buscar fotos para viaturas
        viatura_fotos = {}
        for viatura in viaturas:
            fotos = db.execute(
                'SELECT caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
                ('viatura', viatura['id'])
            ).fetchall()
            viatura_fotos[viatura['id']] = [foto['caminho_arquivo'] for foto in fotos]
        
        # Buscar instalações
        instalacoes = db.execute('SELECT * FROM instalacoes WHERE orgao_provedor_id = ?', (id,)).fetchall()
        
        dados_completos = []
        for inst in instalacoes:
            instalacao_data = dict(inst)
            
            # Buscar fotos da instalação
            fotos_instalacao = db.execute(
                'SELECT caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
                ('instalacao', inst['id'])
            ).fetchall()
            instalacao_data['fotos'] = [foto['caminho_arquivo'] for foto in fotos_instalacao]
            
            # Buscar empilhadeiras (só se for depósito)
            if 'deposito' in inst['tipo_instalacao']:
                empilhadeiras = db.execute(
                    'SELECT * FROM empilhadeiras WHERE instalacao_id = ?',
                    (inst['id'],)
                ).fetchall()
                
                empilhadeiras_com_fotos = []
                for emp in empilhadeiras:
                    emp_dict = dict(emp)
                    
                    # Buscar fotos da empilhadeira
                    fotos_emp = db.execute(
                        'SELECT caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
                        ('empilhadeira', emp['id'])
                    ).fetchall()
                    emp_dict['fotos'] = [foto['caminho_arquivo'] for foto in fotos_emp]
                    
                    empilhadeiras_com_fotos.append(emp_dict)
                
                instalacao_data['empilhadeiras'] = empilhadeiras_com_fotos
                
                # Buscar sistemas de segurança
                sistemas = db.execute(
                    'SELECT * FROM sistemas_seguranca WHERE instalacao_id = ?',
                    (inst['id'],)
                ).fetchall()
                
                sistemas_com_fotos = []
                for sis in sistemas:
                    sis_dict = dict(sis)
                    
                    # Buscar fotos do sistema
                    fotos_sis = db.execute(
                        'SELECT caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
                        ('sistema_seguranca', sis['id'])
                    ).fetchall()
                    sis_dict['fotos'] = [foto['caminho_arquivo'] for foto in fotos_sis]
                    
                    sistemas_com_fotos.append(sis_dict)
                
                instalacao_data['sistemas'] = sistemas_com_fotos
                
                # Buscar equipamentos de unitização
                equipamentos = db.execute(
                    'SELECT * FROM equipamentos_unitizacao WHERE instalacao_id = ?',
                    (inst['id'],)
                ).fetchall()
                
                equipamentos_com_fotos = []
                for eq in equipamentos:
                    eq_dict = dict(eq)
                    
                    # Buscar fotos do equipamento
                    fotos_eq = db.execute(
                        'SELECT caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
                        ('equipamento_unitizacao', eq['id'])
                    ).fetchall()
                    eq_dict['fotos'] = [foto['caminho_arquivo'] for foto in fotos_eq]
                    
                    equipamentos_com_fotos.append(eq_dict)
                
                instalacao_data['equipamentos'] = equipamentos_com_fotos
            
            dados_completos.append(instalacao_data)
        
        # Buscar fotos da área edificável
        fotos_area = db.execute(
            'SELECT caminho_arquivo FROM fotos WHERE tabela_origem = ? AND registro_id = ?',
            ('area_edificavel', id)
        ).fetchall()
        fotos_area_list = [foto['caminho_arquivo'] for foto in fotos_area]
        
        return render_template('visualizar_op.html', 
                      orgao=orgao_dict, 
                              energia=energia,
                              geradores=geradores,
                              gerador_fotos=gerador_fotos,
                              pessoal=pessoal,
                              viaturas=viaturas,
                              viatura_fotos=viatura_fotos,
                              instalacoes=dados_completos,
                              fotos_area=fotos_area_list)
    
    except Exception as e:
        flash(f'Erro ao carregar dados: {str(e)}', 'error')
        return redirect(url_for('index'))

# Rota para uploads
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def init_database():
    """Inicializa o banco de dados se necessário"""
    try:
        with app.app_context():
            # Inicializar banco
            database.init_db()
            
            # Criar usuário admin
            criar_usuario_admin()
            
            print("✓ Banco de dados inicializado com sucesso!")
    except Exception as e:
        print(f"✗ Erro ao inicializar banco de dados: {e}")

if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5000'))
    init_database()
    app.run(debug=DEBUG_MODE, host=host, port=port)