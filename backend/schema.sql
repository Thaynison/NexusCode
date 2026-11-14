-- Schema PostgreSQL (Neon) - Nexus Code Gestão Empresarial
-- Execute este script no Editor SQL do Neon caso deseje criar as tabelas manualmente
-- (O sistema também cria todas as tabelas automaticamente na inicialização).

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    perfil VARCHAR(20) NOT NULL DEFAULT 'colaborador' CHECK (perfil IN ('admin', 'colaborador', 'cliente')),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    cpf VARCHAR(20) NULL,
    data_nascimento DATE NULL,
    telefone VARCHAR(30) NULL,
    cargo VARCHAR(120) NULL,
    area_atuacao VARCHAR(120) NULL,
    formacao VARCHAR(200) NULL,
    habilidades VARCHAR(255) NULL,
    linkedin_url VARCHAR(255) NULL,
    resumo_profissional TEXT NULL,
    cep VARCHAR(20) NULL,
    endereco VARCHAR(255) NULL,
    bairro VARCHAR(120) NULL,
    cidade VARCHAR(100) NULL,
    estado VARCHAR(2) NULL,
    termos_aceitos_em TIMESTAMP NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    usuario_portal_id INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    nome_empresa VARCHAR(150) NOT NULL,
    contato_nome VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL,
    telefone VARCHAR(30) NULL,
    documento VARCHAR(30) NULL,
    status_funil VARCHAR(20) NOT NULL DEFAULT 'lead' CHECK (status_funil IN ('lead', 'proposta', 'negociacao', 'ativo', 'inativo')),
    origem VARCHAR(80) NULL,
    observacoes TEXT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS solicitacoes_orcamento (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NULL REFERENCES clientes(id) ON DELETE SET NULL,
    nome VARCHAR(120) NOT NULL,
    empresa VARCHAR(150) NULL,
    email VARCHAR(150) NOT NULL,
    telefone VARCHAR(30) NULL,
    tipo_projeto VARCHAR(80) NULL,
    mensagem TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'novo' CHECK (status IN ('novo', 'em_atendimento', 'respondido', 'convertido', 'arquivado')),
    resposta TEXT NULL,
    respondido_por VARCHAR(120) NULL,
    respondido_em TIMESTAMP NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projetos (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    responsavel_id INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    titulo VARCHAR(180) NOT NULL,
    descricao TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planejamento' CHECK (status IN ('planejamento', 'em_andamento', 'homologacao', 'concluido', 'cancelado')),
    prioridade VARCHAR(20) NOT NULL DEFAULT 'media' CHECK (prioridade IN ('baixa', 'media', 'alta', 'urgente')),
    progresso INTEGER NOT NULL DEFAULT 0,
    valor_total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    data_inicio DATE NULL,
    data_entrega DATE NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tarefas (
    id SERIAL PRIMARY KEY,
    projeto_id INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    responsavel_id INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    titulo VARCHAR(180) NOT NULL,
    descricao TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'fazendo', 'revisao', 'concluida')),
    prazo DATE NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interacoes (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    usuario_id INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    tipo VARCHAR(20) NOT NULL DEFAULT 'whatsapp' CHECK (tipo IN ('reuniao', 'email', 'whatsapp', 'ligacao', 'proposta')),
    resumo TEXT NOT NULL,
    proxima_acao VARCHAR(255) NULL,
    data_interacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS faturas (
    id SERIAL PRIMARY KEY,
    projeto_id INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    descricao VARCHAR(200) NOT NULL,
    valor NUMERIC(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'pago', 'atrasado', 'cancelado')),
    vencimento DATE NOT NULL,
    pago_em TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS modulos_registros (
    id SERIAL PRIMARY KEY,
    modulo VARCHAR(60) NOT NULL,
    titulo VARCHAR(180) NOT NULL,
    subtitulo VARCHAR(180) NULL,
    email VARCHAR(150) NULL,
    telefone VARCHAR(40) NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'ativo',
    descricao TEXT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS logs_auditoria (
    id SERIAL PRIMARY KEY,
    usuario_nome VARCHAR(120) NOT NULL,
    acao VARCHAR(80) NOT NULL,
    detalhes VARCHAR(255) NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clientes_email ON clientes(email);
CREATE INDEX IF NOT EXISTS idx_solicitacoes_status ON solicitacoes_orcamento(status);
CREATE INDEX IF NOT EXISTS idx_solicitacoes_email ON solicitacoes_orcamento(email);
CREATE INDEX IF NOT EXISTS idx_projetos_cliente ON projetos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_tarefas_projeto ON tarefas(projeto_id);
CREATE INDEX IF NOT EXISTS idx_faturas_cliente ON faturas(cliente_id);
