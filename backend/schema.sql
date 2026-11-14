-- Schema PostgreSQL (Neon) - Nexus Code Gestão Empresarial

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    perfil VARCHAR(20) NOT NULL DEFAULT 'colaborador' CHECK (perfil IN ('admin', 'colaborador', 'cliente')),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    cpf VARCHAR(20) NULL,
    data_nascimento DATE NULL,
    data_contratacao DATE NULL,
    data_fim_contrato DATE NULL,
    tipo_contrato VARCHAR(40) NULL DEFAULT 'clt_fixo',
    cbo_codigo VARCHAR(20) NULL,
    cbo_descricao VARCHAR(180) NULL,
    carga_horaria_diaria NUMERIC(4, 2) NULL DEFAULT 8.00,
    horario_entrada VARCHAR(10) NULL DEFAULT '08:00',
    horario_saida VARCHAR(10) NULL DEFAULT '17:00',
    dependentes_irrf INTEGER NULL DEFAULT 0,
    vale_transporte BOOLEAN NULL DEFAULT FALSE,
    valor_vt_mensal NUMERIC(12, 2) NULL DEFAULT 0.00,
    salario_base NUMERIC(12, 2) NULL DEFAULT 0.00,
    telefone VARCHAR(30) NULL,
    cargo VARCHAR(120) NULL,
    area_atuacao VARCHAR(120) NULL,
    formacao VARCHAR(200) NULL,
    habilidades VARCHAR(255) NULL,
    linkedin_url VARCHAR(255) NULL,
    resumo_profissional TEXT NULL,
    foto_url TEXT NULL,
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
    prioridade VARCHAR(20) NOT NULL DEFAULT 'media',
    data_inicio DATE NULL,
    prazo DATE NULL,
    checklist_json TEXT NULL,
    anexos_json TEXT NULL,
    comentarios_json TEXT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS holerites (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    competencia VARCHAR(20) NOT NULL,
    tipo VARCHAR(50) NOT NULL DEFAULT 'Salário Mensal',
    salario_base NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    proventos NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    descricao_proventos VARCHAR(255) NULL,
    descontos NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    descricao_descontos VARCHAR(255) NULL,
    valor_liquido NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    fgts_valor NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    data_pagamento DATE NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pago',
    observacoes TEXT NULL,
    anexo_nome VARCHAR(255) NULL,
    anexo_data TEXT NULL,
    publicado_por VARCHAR(120) NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS informes_rendimentos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    ano_calendario VARCHAR(10) NOT NULL,
    ano_exercicio VARCHAR(10) NOT NULL,
    rendimentos_tributaveis NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    contribuicao_previdenciaria NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    irrf_retido NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    decimo_terceiro NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    rendimentos_isentos NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    observacoes TEXT NULL,
    anexo_nome VARCHAR(255) NULL,
    anexo_data TEXT NULL,
    publicado_por VARCHAR(120) NULL,
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
CREATE INDEX IF NOT EXISTS idx_holerites_usuario ON holerites(usuario_id);
CREATE INDEX IF NOT EXISTS idx_informes_usuario ON informes_rendimentos(usuario_id);

CREATE TABLE IF NOT EXISTS registros_ponto (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    data_ponto DATE NOT NULL,
    entrada VARCHAR(10) NULL,
    saida_almoco VARCHAR(10) NULL,
    retorno_almoco VARCHAR(10) NULL,
    saida VARCHAR(10) NULL,
    minutos_trabalhados INTEGER NOT NULL DEFAULT 0,
    minutos_extras_50 INTEGER NOT NULL DEFAULT 0,
    minutos_extras_100 INTEGER NOT NULL DEFAULT 0,
    minutos_atraso INTEGER NOT NULL DEFAULT 0,
    eh_feriado_ou_domingo BOOLEAN NOT NULL DEFAULT FALSE,
    tipo_dia VARCHAR(30) NOT NULL DEFAULT 'normal',
    status_ajuste VARCHAR(20) NOT NULL DEFAULT 'aprovado',
    justificativa_ajuste TEXT NULL,
    ajuste_solicitado_json TEXT NULL,
    ip_registro VARCHAR(60) NULL,
    observacao TEXT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ponto_usuario_data ON registros_ponto(usuario_id, data_ponto);
