-- Schema PostgreSQL (Neon) - Nexus Code Enterprise SaaS White-Label Multi-Tenant

CREATE TABLE IF NOT EXISTS organizacoes (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    slug VARCHAR(80) NOT NULL UNIQUE,
    dominio_customizado VARCHAR(180) NULL UNIQUE,
    is_master BOOLEAN NOT NULL DEFAULT FALSE,
    plano VARCHAR(40) NOT NULL DEFAULT 'pro',
    status_assinatura VARCHAR(30) NOT NULL DEFAULT 'ativo',
    valor_mensal NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    limite_usuarios INTEGER NOT NULL DEFAULT 10,
    limite_clientes INTEGER NOT NULL DEFAULT 200,
    trial_ate DATE NULL,
    vencimento_assinatura DATE NULL,
    modulos_json TEXT NULL,
    branding_json TEXT NULL,
    cliente_master_id INTEGER NULL,
    contrato_master_id INTEGER NULL,
    observacoes TEXT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS planos_saas (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(40) NOT NULL UNIQUE,
    nome VARCHAR(100) NOT NULL,
    subtitulo VARCHAR(200) NULL,
    preco_mensal NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    limite_usuarios INTEGER NOT NULL DEFAULT 5,
    limite_clientes INTEGER NOT NULL DEFAULT 100,
    destaque BOOLEAN NOT NULL DEFAULT FALSE,
    modulos_json TEXT NULL,
    recursos_json TEXT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    ordem INTEGER NOT NULL DEFAULT 1,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    nome VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL,
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
    permissoes_individuais_json TEXT NULL,
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
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
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
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
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
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    responsavel_id INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    titulo VARCHAR(180) NOT NULL,
    descricao TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planejamento' CHECK (status IN ('planejamento', 'em_andamento', 'homologacao', 'concluido', 'cancelado')),
    prioridade VARCHAR(20) NOT NULL DEFAULT 'media' CHECK (prioridade IN ('baixa', 'media', 'alta', 'urgente')),
    progresso INTEGER NOT NULL DEFAULT 0,
    valor_total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    horas_estimadas NUMERIC(8, 2) NULL DEFAULT 0.00,
    url_homologacao VARCHAR(255) NULL,
    url_producao VARCHAR(255) NULL,
    repositorio_url VARCHAR(255) NULL,
    aprovacao_cliente_status VARCHAR(30) NULL DEFAULT 'pendente',
    aprovacao_cliente_obs TEXT NULL,
    aprovado_em TIMESTAMP NULL,
    data_inicio DATE NULL,
    data_entrega DATE NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tarefas (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    projeto_id INTEGER NULL REFERENCES projetos(id) ON DELETE CASCADE,
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
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
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
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
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
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    usuario_id INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    tipo VARCHAR(20) NOT NULL DEFAULT 'whatsapp' CHECK (tipo IN ('reuniao', 'email', 'whatsapp', 'ligacao', 'proposta')),
    resumo TEXT NOT NULL,
    proxima_acao VARCHAR(255) NULL,
    data_interacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS faturas (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    projeto_id INTEGER NULL REFERENCES projetos(id) ON DELETE CASCADE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    descricao VARCHAR(200) NOT NULL,
    valor NUMERIC(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'pago', 'atrasado', 'cancelado')),
    forma_pagamento VARCHAR(40) NULL DEFAULT 'PIX',
    comprovante_nome VARCHAR(255) NULL,
    comprovante_data TEXT NULL,
    observacoes TEXT NULL,
    vencimento DATE NOT NULL,
    pago_em TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS modulos_registros (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
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
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    usuario_nome VARCHAR(120) NOT NULL,
    acao VARCHAR(80) NOT NULL,
    detalhes VARCHAR(255) NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS registros_ponto (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
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

CREATE TABLE IF NOT EXISTS configuracoes_empresa (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    razao_social VARCHAR(180) NOT NULL DEFAULT 'Nexus Code Brasil Tecnologia Ltda',
    nome_fantasia VARCHAR(150) NOT NULL DEFAULT 'Nexus Code Brasil',
    cnpj VARCHAR(25) NULL,
    inscricao_estadual VARCHAR(40) NULL,
    email_financeiro VARCHAR(150) NULL,
    telefone VARCHAR(40) NULL,
    endereco VARCHAR(255) NULL,
    cidade VARCHAR(100) NULL,
    estado VARCHAR(2) NULL,
    cep VARCHAR(20) NULL,
    banco_nome VARCHAR(100) NULL,
    agencia VARCHAR(20) NULL,
    conta VARCHAR(30) NULL,
    chave_pix VARCHAR(150) NULL,
    titular_pix VARCHAR(150) NULL,
    multa_atraso_percent NUMERIC(5, 2) NULL DEFAULT 2.00,
    juros_mensal_percent NUMERIC(5, 2) NULL DEFAULT 1.00,
    permissoes_json TEXT NULL,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS propostas_comerciais (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    solicitacao_id INTEGER NULL REFERENCES solicitacoes_orcamento(id) ON DELETE SET NULL,
    criado_por_id INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    titulo VARCHAR(180) NOT NULL,
    escopo TEXT NOT NULL,
    entregaveis_json TEXT NULL,
    valor_total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    condicoes_pagamento VARCHAR(200) NULL,
    parcelas INTEGER NOT NULL DEFAULT 1,
    prazo_dias INTEGER NOT NULL DEFAULT 30,
    validade_ate DATE NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'enviada',
    feedback_cliente TEXT NULL,
    aprovado_por_cliente VARCHAR(120) NULL,
    aprovado_em TIMESTAMP NULL,
    projeto_gerado_id INTEGER NULL REFERENCES projetos(id) ON DELETE SET NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS despesas (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    descricao VARCHAR(200) NOT NULL,
    categoria VARCHAR(50) NOT NULL DEFAULT 'infraestrutura',
    fornecedor VARCHAR(150) NULL,
    projeto_id INTEGER NULL REFERENCES projetos(id) ON DELETE SET NULL,
    valor NUMERIC(12, 2) NOT NULL,
    vencimento DATE NOT NULL,
    status VARCHAR(25) NOT NULL DEFAULT 'pendente',
    recorrente BOOLEAN NOT NULL DEFAULT FALSE,
    pago_em TIMESTAMP NULL,
    observacoes TEXT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contratos_recorrentes (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    projeto_id INTEGER NULL REFERENCES projetos(id) ON DELETE SET NULL,
    titulo VARCHAR(180) NOT NULL,
    valor_mensal NUMERIC(12, 2) NOT NULL,
    dia_vencimento INTEGER NOT NULL DEFAULT 10,
    data_inicio DATE NOT NULL,
    data_fim DATE NULL,
    status VARCHAR(25) NOT NULL DEFAULT 'ativo',
    descricao TEXT NULL,
    ultima_geracao VARCHAR(15) NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS apontamentos_horas (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    projeto_id INTEGER NULL REFERENCES projetos(id) ON DELETE CASCADE,
    tarefa_id INTEGER NULL REFERENCES tarefas(id) ON DELETE SET NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    data_trabalho DATE NOT NULL,
    horas NUMERIC(6, 2) NOT NULL,
    descricao VARCHAR(255) NOT NULL,
    faturavel BOOLEAN NOT NULL DEFAULT TRUE,
    custo_hora_snapshot NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chamados_suporte (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    protocolo VARCHAR(30) NOT NULL UNIQUE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    projeto_id INTEGER NULL REFERENCES projetos(id) ON DELETE SET NULL,
    aberto_por_id INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    responsavel_id INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    titulo VARCHAR(180) NOT NULL,
    categoria VARCHAR(40) NOT NULL DEFAULT 'suporte_tecnico',
    prioridade VARCHAR(20) NOT NULL DEFAULT 'media',
    status VARCHAR(30) NOT NULL DEFAULT 'aberto',
    sla_horas INTEGER NOT NULL DEFAULT 24,
    descricao TEXT NOT NULL,
    mensagens_json TEXT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ativos_infra (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    cliente_id INTEGER NULL REFERENCES clientes(id) ON DELETE SET NULL,
    projeto_id INTEGER NULL REFERENCES projetos(id) ON DELETE SET NULL,
    tipo VARCHAR(40) NOT NULL DEFAULT 'dominio',
    nome VARCHAR(180) NOT NULL,
    provedor VARCHAR(120) NULL,
    url_acesso VARCHAR(255) NULL,
    usuario_acesso VARCHAR(150) NULL,
    segredo_acesso VARCHAR(255) NULL,
    valor_renovacao NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    data_vencimento DATE NULL,
    status VARCHAR(25) NOT NULL DEFAULT 'ativo',
    observacoes TEXT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notificacoes (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    usuario_id INTEGER NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    perfil_destino VARCHAR(30) NULL,
    titulo VARCHAR(160) NOT NULL,
    mensagem VARCHAR(300) NOT NULL,
    link_pagina VARCHAR(50) NOT NULL DEFAULT 'dashboard',
    lida BOOLEAN NOT NULL DEFAULT FALSE,
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
CREATE INDEX IF NOT EXISTS idx_ponto_usuario_data ON registros_ponto(usuario_id, data_ponto);
CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_org_email ON usuarios(organizacao_id, email);
CREATE INDEX IF NOT EXISTS idx_propostas_cliente ON propostas_comerciais(cliente_id);
CREATE INDEX IF NOT EXISTS idx_despesas_vencimento ON despesas(vencimento);
CREATE INDEX IF NOT EXISTS idx_contratos_cliente ON contratos_recorrentes(cliente_id);
CREATE INDEX IF NOT EXISTS idx_timesheet_projeto ON apontamentos_horas(projeto_id);
CREATE INDEX IF NOT EXISTS idx_chamados_cliente ON chamados_suporte(cliente_id);
CREATE INDEX IF NOT EXISTS idx_notificacoes_usuario ON notificacoes(usuario_id);

CREATE TABLE IF NOT EXISTS produtos_loja (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    slug VARCHAR(80) NOT NULL UNIQUE,
    nome VARCHAR(150) NOT NULL,
    descricao TEXT NULL,
    preco NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    badge VARCHAR(40) NULL,
    spec_label VARCHAR(60) NULL,
    imagem_url TEXT NULL,
    fundo_escuro BOOLEAN NOT NULL DEFAULT TRUE,
    tamanhos_json TEXT NULL,
    cores_json TEXT NULL,
    ordem INTEGER NOT NULL DEFAULT 0,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS banco_horas (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    competencia VARCHAR(15) NOT NULL,
    saldo_minutos INTEGER NOT NULL DEFAULT 0,
    observacao TEXT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reembolsos_despesas (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    projeto_id INTEGER NULL REFERENCES projetos(id) ON DELETE SET NULL,
    descricao VARCHAR(200) NOT NULL,
    valor NUMERIC(12, 2) NOT NULL,
    data_despesa DATE NOT NULL,
    status VARCHAR(25) NOT NULL DEFAULT 'pendente',
    comprovante_data TEXT NULL,
    observacoes_gestor TEXT NULL,
    despesa_gerada_id INTEGER NULL REFERENCES despesas(id) ON DELETE SET NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pedidos_loja (
    id SERIAL PRIMARY KEY,
    organizacao_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizacoes(id) ON DELETE CASCADE,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    cliente_id INTEGER NULL REFERENCES clientes(id) ON DELETE SET NULL,
    nome_comprador VARCHAR(150) NOT NULL,
    email_comprador VARCHAR(150) NOT NULL,
    telefone_comprador VARCHAR(30) NULL,
    itens_json TEXT NOT NULL,
    subtotal NUMERIC(12, 2) NOT NULL,
    desconto NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    frete NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    valor_total NUMERIC(12, 2) NOT NULL,
    status VARCHAR(25) NOT NULL DEFAULT 'aguardando_pagamento',
    fatura_gerada_id INTEGER NULL REFERENCES faturas(id) ON DELETE SET NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
