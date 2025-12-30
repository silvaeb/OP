import sqlite3
import os

def corrigir_banco_de_dados():
    print("Iniciando correção do banco de dados...")
    
    # Fazer backup do banco atual se existir
    if os.path.exists('database.db'):
        try:
            os.rename('database.db', 'database_backup.db')
            print("✓ Backup do banco de dados criado: database_backup.db")
        except Exception as e:
            print(f"⚠ Não foi possível criar backup: {e}")
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    try:
        print("\n=== CRIANDO TABELAS DO SISTEMA ===\n")
        
        # 1. Tabela de Usuários (COM TODAS AS COLUNAS)
        print("Criando tabela de usuários...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nome_completo TEXT NOT NULL,
                nome_guerra TEXT,
                posto_graduacao TEXT,
                orgao_provedor_id INTEGER,
                email TEXT,
                nivel_acesso TEXT DEFAULT 'visualizador' CHECK(nivel_acesso IN ('admin', 'cadastrador', 'visualizador')),
                ativo INTEGER DEFAULT 1,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ultimo_acesso TIMESTAMP,
                FOREIGN KEY (orgao_provedor_id) REFERENCES orgao_provedor (id)
            )
        ''')
        print("✓ Tabela 'usuarios' criada com sucesso")
        
        # 2. Tabela de Órgãos Provedores
        print("\nCriando tabela de órgãos provedores...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orgao_provedor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                sigla TEXT,
                unidade_gestora TEXT,
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
                criado_por INTEGER,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (criado_por) REFERENCES usuarios (id)
            )
        ''')
        print("✓ Tabela 'orgao_provedor' criada com sucesso")
        
        # 3. Tabela de Energia Elétrica
        print("\nCriando tabela de energia elétrica...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS energia_eletrica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                orgao_provedor_id INTEGER NOT NULL,
                dimensionamento_adequado TEXT NOT NULL CHECK(dimensionamento_adequado IN ('adequado', 'insuficiente', 'precario')),
                capacidade_total_kva REAL,
                observacoes_energia TEXT,
                FOREIGN KEY (orgao_provedor_id) REFERENCES orgao_provedor (id)
            )
        ''')
        print("✓ Tabela 'energia_eletrica' criada com sucesso")
        
        # 4. Tabela de Geradores
        print("\nCriando tabela de geradores...")
        cursor.execute('''
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
        print("✓ Tabela 'geradores' criada com sucesso")
        
        # 5. Tabela de Fotos
        print("\nCriando tabela de fotos...")
        cursor.execute('''
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
        print("✓ Tabela 'fotos' criada com sucesso")
        
        # 6. Tabela de Instalações
        print("\nCriando tabela de instalações...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS instalacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                orgao_provedor_id INTEGER NOT NULL,
                tipo_instalacao TEXT NOT NULL,
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
        print("✓ Tabela 'instalacoes' criada com sucesso")
        
        # 7. Tabela de Empilhadeiras
        print("\nCriando tabela de empilhadeiras...")
        cursor.execute('''
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
        print("✓ Tabela 'empilhadeiras' criada com sucesso")
        
        # 8. Tabela de Sistemas de Segurança
        print("\nCriando tabela de sistemas de segurança...")
        cursor.execute('''
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
        print("✓ Tabela 'sistemas_seguranca' criada com sucesso")
        
        # 9. Tabela de Equipamentos de Unitização
        print("\nCriando tabela de equipamentos de unitização...")
        cursor.execute('''
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
        print("✓ Tabela 'equipamentos_unitizacao' criada com sucesso")
        
        # 10. Tabela de Pessoal
        print("\nCriando tabela de pessoal...")
        cursor.execute('''
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
        print("✓ Tabela 'pessoal' criada com sucesso")
        
        # 11. Tabela de Viaturas
        print("\nCriando tabela de viaturas...")
        cursor.execute('''
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
        print("✓ Tabela 'viaturas' criada com sucesso")
        
        conn.commit()
        
        print("\n=== CRIANDO USUÁRIO ADMINISTRADOR ===\n")
        
        # Criar usuário admin
        from werkzeug.security import generate_password_hash
        senha_hash = generate_password_hash('admin123')
        
        try:
            cursor.execute('''
                INSERT INTO usuarios 
                (username, password_hash, nome_completo, nome_guerra, 
                 posto_graduacao, email, nivel_acesso, ativo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('admin', senha_hash, 'Administrador do Sistema', 'Admin', 
                  'Administrador', 'admin@sistema.com', 'admin', 1))
            
            conn.commit()
            print("✓ Usuário administrador criado com sucesso!")
            print("  Login: admin")
            print("  Senha: admin123")
            print("  Perfil: Administrador")
            
        except sqlite3.IntegrityError:
            print("✓ Usuário admin já existe")
        
        print("\n=== VERIFICAÇÃO FINAL ===\n")
        
        # Verificar se todas as tabelas foram criadas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = cursor.fetchall()
        
        tabelas_esperadas = [
            'usuarios', 'orgao_provedor', 'energia_eletrica', 'geradores',
            'fotos', 'instalacoes', 'empilhadeiras', 'sistemas_seguranca',
            'equipamentos_unitizacao', 'pessoal', 'viaturas'
        ]
        
        tabelas_criadas = [t[0] for t in tabelas]
        
        print(f"Total de tabelas criadas: {len(tabelas_criadas)}")
        
        for tabela in tabelas_esperadas:
            if tabela in tabelas_criadas:
                print(f"✓ {tabela}")
            else:
                print(f"✗ {tabela} (FALTANDO)")
        
        print("\n=== BANCO DE DADOS PRONTO ===")
        print("O banco de dados foi criado/corrigido com sucesso!")
        print("Agora você pode iniciar o servidor Flask normalmente.")
        
    except Exception as e:
        print(f"\n✗ ERRO: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    corrigir_banco_de_dados()