import sqlite3
from flask import g
import os
import sqlite3

DATABASE = 'database.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def atualizar_tabelas():
    """Atualiza tabelas existentes com novas colunas"""
    db = get_db()
    
    # Lista de colunas a adicionar com seus tipos para a tabela usuarios
    novas_colunas_usuarios = [
        ('nome_guerra', 'TEXT'),
        ('posto_graduacao', 'TEXT'),
        ('orgao_provedor', 'TEXT'),
        ('email', 'TEXT'),
        ('ultimo_acesso', 'TIMESTAMP')
    ]
    
    print("Atualizando tabela usuarios...")
    for coluna, tipo in novas_colunas_usuarios:
        try:
            # Verificar se a coluna já existe
            db.execute(f"SELECT {coluna} FROM usuarios LIMIT 1")
            print(f"✓ Coluna {coluna} já existe em usuarios")
        except sqlite3.OperationalError:
            try:
                # Adicionar coluna se não existir
                db.execute(f"ALTER TABLE usuarios ADD COLUMN {coluna} {tipo}")
                print(f"✓ Coluna {coluna} adicionada em usuarios")
            except Exception as e:
                print(f"⚠ Erro ao adicionar coluna {coluna}: {e}")
    
    # Lista de colunas para orgao_provedor (já existentes)
    novas_colunas_orgao = [
        ('unidade_gestora', 'TEXT'),
        ('codom', 'TEXT'),
        ('om_licitacao_qs', 'TEXT'),
        ('om_licitacao_qr', 'TEXT'),
        ('capacidade_total_toneladas', 'REAL'),
        ('capacidade_total_toneladas_seco', 'REAL'),
        ('criado_por', 'INTEGER'),
        ('classes_provedor', 'TEXT')
    ]
    
    print("\nAtualizando tabela orgao_provedor...")
    for coluna, tipo in novas_colunas_orgao:
        try:
            db.execute(f"SELECT {coluna} FROM orgao_provedor LIMIT 1")
            print(f"✓ Coluna {coluna} já existe em orgao_provedor")
        except sqlite3.OperationalError:
            try:
                db.execute(f"ALTER TABLE orgao_provedor ADD COLUMN {coluna} {tipo}")
                print(f"✓ Coluna {coluna} adicionada em orgao_provedor")
            except Exception as e:
                print(f"⚠ Erro ao adicionar coluna {coluna}: {e}")
    
    # Atualizar tabela instalacoes
    print("\nAtualizando tabela instalacoes...")
    try:
        db.execute("SELECT capacidade_toneladas FROM instalacoes LIMIT 1")
        print("✓ Coluna capacidade_toneladas já existe em instalacoes")
    except sqlite3.OperationalError:
        try:
            db.execute("ALTER TABLE instalacoes ADD COLUMN capacidade_toneladas REAL")
            print("✓ Coluna capacidade_toneladas adicionada em instalacoes")
        except Exception as e:
            print(f"⚠ Erro ao adicionar coluna capacidade_toneladas: {e}")

    # Garantir coluna de nome/identificação em instalacoes
    try:
        db.execute("SELECT nome_identificacao FROM instalacoes LIMIT 1")
        print("✓ Coluna nome_identificacao já existe em instalacoes")
    except sqlite3.OperationalError:
        try:
            db.execute("ALTER TABLE instalacoes ADD COLUMN nome_identificacao TEXT")
            print("✓ Coluna nome_identificacao adicionada em instalacoes")
        except Exception as e:
            print(f"⚠ Erro ao adicionar coluna nome_identificacao: {e}")

    # Garantir coluna valor_recuperacao em geradores (bancos antigos)
    print("\nAtualizando tabela geradores...")
    try:
        db.execute("SELECT valor_recuperacao FROM geradores LIMIT 1")
        print("✓ Coluna valor_recuperacao já existe em geradores")
    except sqlite3.OperationalError:
        try:
            db.execute("ALTER TABLE geradores ADD COLUMN valor_recuperacao REAL")
            print("✓ Coluna valor_recuperacao adicionada em geradores")
        except Exception as e:
            print(f"⚠ Erro ao adicionar coluna valor_recuperacao: {e}")

    # Garantir colunas da tabela viaturas compatíveis com o schema atual
    novas_colunas_viaturas = [
        ('especializacao', 'TEXT'),
        ('tipo_refrigeracao', 'TEXT'),
        ('temperatura_min', 'REAL'),
        ('temperatura_max', 'REAL'),
        ('numero_inventario', 'TEXT'),
        ('valor_recuperacao', 'REAL')
    ]

    print("\nAtualizando tabela viaturas...")
    for coluna, tipo in novas_colunas_viaturas:
        try:
            db.execute(f"SELECT {coluna} FROM viaturas LIMIT 1")
            print(f"✓ Coluna {coluna} já existe em viaturas")
        except sqlite3.OperationalError:
            try:
                db.execute(f"ALTER TABLE viaturas ADD COLUMN {coluna} {tipo}")
                print(f"✓ Coluna {coluna} adicionada em viaturas")
            except Exception as e:
                print(f"⚠ Erro ao adicionar coluna {coluna} em viaturas: {e}")
    
    db.commit()

def init_db():
    try:
        db = get_db()
        
        # Tabela principal de Órgãos Provedores
        db.execute('''
            CREATE TABLE IF NOT EXISTS orgao_provedor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                sigla TEXT NOT NULL UNIQUE,
                unidade_gestora TEXT,
                codom TEXT,
                om_licitacao_qs TEXT,
                om_licitacao_qr TEXT,
                subordinacao TEXT NOT NULL,
                efetivo_atendimento INTEGER NOT NULL,
                data_criacao DATE,
                historico TEXT,
                missao TEXT,
                consumo_secos_mensal REAL,
                consumo_frigorificados_mensal REAL,
                suprimento_secos_mensal REAL,
                suprimento_frigorificados_mensal REAL,
                area_edificavel_disponivel REAL,
                capacidade_total_toneladas REAL,
                capacidade_total_toneladas_seco REAL,
                classes_provedor TEXT,
                criado_por INTEGER,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (criado_por) REFERENCES usuarios (id)
            )
        ''')
        
        # Tabela de Usuários (ATUALIZADA)
        db.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nome_completo TEXT NOT NULL,
                nome_guerra TEXT,
                posto_graduacao TEXT,
                orgao_provedor TEXT,
                email TEXT,
                nivel_acesso TEXT DEFAULT 'visualizador' CHECK(nivel_acesso IN ('admin', 'cadastrador', 'visualizador')),
                ativo INTEGER DEFAULT 1,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ultimo_acesso TIMESTAMP,
                FOREIGN KEY (orgao_provedor) REFERENCES orgao_provedor (nome)
            )
        ''')
        
        # NOVA TABELA: Pessoal
        db.execute('''
            CREATE TABLE IF NOT EXISTS pessoal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                orgao_provedor_id INTEGER NOT NULL,
                posto_graduacao TEXT NOT NULL,
                arma_quadro_servico TEXT NOT NULL,
                especialidade TEXT,
                funcao TEXT,
                tipo_servico TEXT NOT NULL CHECK(tipo_servico IN ('carreira', 'temporario')),
                quantidade INTEGER NOT NULL DEFAULT 1,
                observacoes TEXT,
                FOREIGN KEY (orgao_provedor_id) REFERENCES orgao_provedor (id)
            )
        ''')
        
        # NOVA TABELA: Energia Elétrica
        db.execute('''
            CREATE TABLE IF NOT EXISTS energia_eletrica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                orgao_provedor_id INTEGER NOT NULL,
                dimensionamento_adequado TEXT NOT NULL CHECK(dimensionamento_adequado IN ('adequado', 'insuficiente', 'precario')),
                capacidade_total_kva REAL,
                observacoes_energia TEXT,
                FOREIGN KEY (orgao_provedor_id) REFERENCES orgao_provedor (id)
            )
        ''')
        
        # NOVA TABELA: Geradores
        db.execute('''
            CREATE TABLE IF NOT EXISTS geradores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                orgao_provedor_id INTEGER NOT NULL,
                capacidade_kva REAL NOT NULL,
                marca_modelo TEXT,
                ano_fabricacao INTEGER,
                situacao TEXT NOT NULL CHECK(situacao IN ('operacional', 'em_manutencao', 'baixada')),
                valor_recuperacao REAL,
                pode_operar_24h INTEGER NOT NULL DEFAULT 0 CHECK(pode_operar_24h IN (0, 1)),
                horas_operacao_continuas INTEGER,
                ultima_manutencao DATE,
                proxima_manutencao DATE,
                observacoes TEXT,
                FOREIGN KEY (orgao_provedor_id) REFERENCES orgao_provedor (id)
            )
        ''')
        
        # NOVA TABELA: Fotos (para múltiplas fotos)
        db.execute('''
            CREATE TABLE IF NOT EXISTS fotos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tabela_origem TEXT NOT NULL,
                registro_id INTEGER NOT NULL,
                caminho_arquivo TEXT NOT NULL,
                tipo_foto TEXT,
                descricao TEXT,
                data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de instalações do OP (ATUALIZADA)
        db.execute('''
            CREATE TABLE IF NOT EXISTS instalacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                orgao_provedor_id INTEGER NOT NULL,
                tipo_instalacao TEXT NOT NULL,
                nome_identificacao TEXT,
                descricao TEXT,
                data_construcao DATE,
                tipo_cobertura TEXT,
                capacidade_toneladas REAL,
                largura REAL,
                comprimento REAL,
                altura REAL,
                verticalizacao TEXT,
                FOREIGN KEY (orgao_provedor_id) REFERENCES orgao_provedor (id)
            )
        ''')
        
        # Tabela de empilhadeiras
        db.execute('''
            CREATE TABLE IF NOT EXISTS empilhadeiras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instalacao_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                capacidade REAL,
                quantidade INTEGER,
                ano_fabricacao INTEGER,
                situacao TEXT NOT NULL CHECK(situacao IN ('disponivel', 'indisponivel_recuperavel', 'indisponivel')),
                valor_recuperacao REAL,
                FOREIGN KEY (instalacao_id) REFERENCES instalacoes (id)
            )
        ''')
        
        # Tabela: Sistemas de Segurança
        db.execute('''
            CREATE TABLE IF NOT EXISTS sistemas_seguranca (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instalacao_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                descricao TEXT,
                situacao TEXT CHECK(situacao IN ('operacional', 'inoperante', 'em_manutencao')),
                ultima_manutencao DATE,
                proxima_manutencao DATE,
                FOREIGN KEY (instalacao_id) REFERENCES instalacoes (id)
            )
        ''')
        
        # Tabela: Equipamentos de Unitização
        db.execute('''
            CREATE TABLE IF NOT EXISTS equipamentos_unitizacao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instalacao_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                quantidade INTEGER,
                capacidade_kg REAL,
                situacao TEXT CHECK(situacao IN ('operacional', 'inoperante', 'em_manutencao')),
                observacoes TEXT,
                FOREIGN KEY (instalacao_id) REFERENCES instalacoes (id)
            )
        ''')
        
        # TABELA ATUALIZADA: Viaturas
        db.execute('''
            CREATE TABLE IF NOT EXISTS viaturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                orgao_provedor_id INTEGER NOT NULL,
                categoria TEXT NOT NULL,
                tipo_veiculo TEXT NOT NULL,
                especializacao TEXT,
                placa TEXT NOT NULL UNIQUE,
                marca TEXT,
                modelo TEXT,
                ano_fabricacao INTEGER,
                capacidade_carga_kg REAL,
                lotacao_pessoas INTEGER,
                valor_recuperacao REAL,
                tipo_refrigeracao TEXT,
                temperatura_min REAL,
                temperatura_max REAL,
                situacao TEXT NOT NULL CHECK(situacao IN ('operacional', 'inoperante', 'em_manutencao', 'baixada')),
                ultima_manutencao DATE,
                proxima_manutencao DATE,
                km_atual INTEGER,
                numero_inventario TEXT,
                patrimonio TEXT,
                observacoes TEXT,
                FOREIGN KEY (orgao_provedor_id) REFERENCES orgao_provedor (id)
            )
        ''')
        
        db.commit()
        print("✓ Tabelas criadas com sucesso!")
        
        # Atualizar tabelas existentes
        atualizar_tabelas()
        
    except Exception as e:
        print(f"✗ Erro ao criar tabelas: {e}")
        raise