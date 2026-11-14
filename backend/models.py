from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date,
    Numeric, Enum, ForeignKey
)
from sqlalchemy.orm import relationship
from database import Base


class Organizacao(Base):
    __tablename__ = "organizacoes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    slug = Column(String(80), unique=True, index=True, nullable=False)
    dominio_customizado = Column(String(180), unique=True, index=True, nullable=True)
    is_master = Column(Boolean, default=False, server_default="false", nullable=False)
    plano = Column(String(40), default="pro", server_default="pro", nullable=False)
    status_assinatura = Column(String(30), default="ativo", server_default="ativo", nullable=False)
    valor_mensal = Column(Numeric(12, 2), default=0.00, server_default="0.00", nullable=False)
    limite_usuarios = Column(Integer, default=10, server_default="10", nullable=False)
    limite_clientes = Column(Integer, default=200, server_default="200", nullable=False)
    trial_ate = Column(Date, nullable=True)
    vencimento_assinatura = Column(Date, nullable=True)
    modulos_json = Column(Text, nullable=True)
    branding_json = Column(Text, nullable=True)
    cliente_master_id = Column(Integer, nullable=True)
    contrato_master_id = Column(Integer, nullable=True)
    observacoes = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class PlanoSaas(Base):
    __tablename__ = "planos_saas"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(40), unique=True, index=True, nullable=False)
    nome = Column(String(100), nullable=False)
    subtitulo = Column(String(200), nullable=True)
    preco_mensal = Column(Numeric(12, 2), default=0.00, nullable=False)
    limite_usuarios = Column(Integer, default=5, nullable=False)
    limite_clientes = Column(Integer, default=100, nullable=False)
    destaque = Column(Boolean, default=False, nullable=False)
    modulos_json = Column(Text, nullable=True)
    recursos_json = Column(Text, nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    ordem = Column(Integer, default=1, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    perfil = Column(
        Enum("admin", "colaborador", "cliente", name="perfil_usuario"),
        default="colaborador",
        native_enum=False,
        nullable=False,
    )
    ativo = Column(Boolean, default=True, nullable=False)
    cpf = Column(String(20), nullable=True)
    data_nascimento = Column(Date, nullable=True)
    data_contratacao = Column(Date, nullable=True)
    data_fim_contrato = Column(Date, nullable=True)
    tipo_contrato = Column(String(40), default="clt_fixo", server_default="clt_fixo", nullable=True)
    cbo_codigo = Column(String(20), nullable=True)
    cbo_descricao = Column(String(180), nullable=True)
    carga_horaria_diaria = Column(Numeric(4, 2), default=8.00, server_default="8.00", nullable=True)
    horario_entrada = Column(String(10), default="08:00", server_default="08:00", nullable=True)
    horario_saida = Column(String(10), default="17:00", server_default="17:00", nullable=True)
    dependentes_irrf = Column(Integer, default=0, server_default="0", nullable=True)
    vale_transporte = Column(Boolean, default=False, nullable=True)
    valor_vt_mensal = Column(Numeric(12, 2), default=0.00, server_default="0.00", nullable=True)
    salario_base = Column(Numeric(12, 2), default=0.00, nullable=True)
    pix_tipo = Column(String(20), default="cpf", server_default="cpf", nullable=True)
    pix_chave = Column(String(150), nullable=True)
    telefone = Column(String(30), nullable=True)
    cargo = Column(String(120), nullable=True)
    area_atuacao = Column(String(120), nullable=True)
    formacao = Column(String(200), nullable=True)
    habilidades = Column(String(255), nullable=True)
    linkedin_url = Column(String(255), nullable=True)
    resumo_profissional = Column(Text, nullable=True)
    foto_url = Column(Text, nullable=True)
    cep = Column(String(20), nullable=True)
    endereco = Column(String(255), nullable=True)
    bairro = Column(String(120), nullable=True)
    cidade = Column(String(100), nullable=True)
    estado = Column(String(2), nullable=True)
    termos_aceitos_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    projetos_responsavel = relationship("Projeto", back_populates="responsavel")
    tarefas_responsavel = relationship("Tarefa", back_populates="responsavel")
    holerites = relationship("Holerite", back_populates="usuario", cascade="all, delete-orphan")
    informes_rendimentos = relationship("InformeRendimento", back_populates="usuario", cascade="all, delete-orphan")
    registros_ponto = relationship("RegistroPonto", back_populates="usuario", cascade="all, delete-orphan")


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    usuario_portal_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    nome_empresa = Column(String(150), nullable=False)
    contato_nome = Column(String(120), nullable=False)
    email = Column(String(150), index=True, nullable=False)
    telefone = Column(String(30), nullable=True)
    documento = Column(String(30), nullable=True)
    status_funil = Column(
        Enum("lead", "proposta", "negociacao", "ativo", "inativo", name="status_funil_cliente"),
        default="lead",
        native_enum=False,
        nullable=False,
    )
    origem = Column(String(80), nullable=True)
    observacoes = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    projetos = relationship("Projeto", back_populates="cliente", cascade="all, delete-orphan")
    interacoes = relationship("Interacao", back_populates="cliente", cascade="all, delete-orphan")
    faturas = relationship("Fatura", back_populates="cliente", cascade="all, delete-orphan")
    solicitacoes = relationship("SolicitacaoOrcamento", back_populates="cliente")


class SolicitacaoOrcamento(Base):
    __tablename__ = "solicitacoes_orcamento"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
    nome = Column(String(120), nullable=False)
    empresa = Column(String(150), nullable=True)
    email = Column(String(150), index=True, nullable=False)
    telefone = Column(String(30), nullable=True)
    tipo_projeto = Column(String(80), nullable=True)
    mensagem = Column(Text, nullable=False)
    status = Column(
        Enum("novo", "em_atendimento", "respondido", "convertido", "arquivado", name="status_solicitacao"),
        default="novo",
        native_enum=False,
        nullable=False,
    )
    resposta = Column(Text, nullable=True)
    respondido_por = Column(String(120), nullable=True)
    respondido_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente", back_populates="solicitacoes")


class Projeto(Base):
    __tablename__ = "projetos"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    responsavel_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    titulo = Column(String(180), nullable=False)
    descricao = Column(Text, nullable=True)
    status = Column(
        Enum("planejamento", "em_andamento", "homologacao", "concluido", "cancelado", name="status_projeto"),
        default="planejamento",
        native_enum=False,
        nullable=False,
    )
    prioridade = Column(
        Enum("baixa", "media", "alta", "urgente", name="prioridade_projeto"),
        default="media",
        native_enum=False,
        nullable=False,
    )
    progresso = Column(Integer, default=0, nullable=False)
    valor_total = Column(Numeric(12, 2), default=0.00, nullable=False)
    horas_estimadas = Column(Numeric(8, 2), default=0.00, server_default="0.00", nullable=True)
    url_homologacao = Column(String(255), nullable=True)
    url_producao = Column(String(255), nullable=True)
    repositorio_url = Column(String(255), nullable=True)
    aprovacao_cliente_status = Column(String(30), default="pendente", server_default="pendente", nullable=True)
    aprovacao_cliente_obs = Column(Text, nullable=True)
    aprovado_em = Column(DateTime, nullable=True)
    data_inicio = Column(Date, nullable=True)
    data_entrega = Column(Date, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente", back_populates="projetos")
    responsavel = relationship("Usuario", back_populates="projetos_responsavel")
    tarefas = relationship("Tarefa", back_populates="projeto", cascade="all, delete-orphan")
    faturas = relationship("Fatura", back_populates="projeto", cascade="all, delete-orphan")


class Tarefa(Base):
    __tablename__ = "tarefas"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False, index=True)
    responsavel_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    titulo = Column(String(180), nullable=False)
    descricao = Column(Text, nullable=True)
    status = Column(
        Enum("pendente", "fazendo", "revisao", "concluida", name="status_tarefa"),
        default="pendente",
        native_enum=False,
        nullable=False,
    )
    prioridade = Column(String(20), default="media", server_default="media", nullable=False)
    data_inicio = Column(Date, nullable=True)
    prazo = Column(Date, nullable=True)
    checklist_json = Column(Text, nullable=True)
    anexos_json = Column(Text, nullable=True)
    comentarios_json = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    projeto = relationship("Projeto", back_populates="tarefas")
    responsavel = relationship("Usuario", back_populates="tarefas_responsavel")


class Interacao(Base):
    __tablename__ = "interacoes"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    tipo = Column(
        Enum("reuniao", "email", "whatsapp", "ligacao", "proposta", name="tipo_interacao"),
        default="whatsapp",
        native_enum=False,
        nullable=False,
    )
    resumo = Column(Text, nullable=False)
    proxima_acao = Column(String(255), nullable=True)
    data_interacao = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente", back_populates="interacoes")


class Fatura(Base):
    __tablename__ = "faturas"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    descricao = Column(String(200), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    status = Column(
        Enum("pendente", "pago", "atrasado", "cancelado", name="status_fatura"),
        default="pendente",
        native_enum=False,
        nullable=False,
    )
    forma_pagamento = Column(String(40), default="PIX", server_default="PIX", nullable=True)
    comprovante_nome = Column(String(255), nullable=True)
    comprovante_data = Column(Text, nullable=True)
    observacoes = Column(Text, nullable=True)
    vencimento = Column(Date, nullable=False)
    mp_order_id = Column(String(80), nullable=True, index=True)
    mp_payment_id = Column(String(80), nullable=True, index=True)
    mp_preference_id = Column(String(120), nullable=True)
    mp_qr_code = Column(Text, nullable=True)
    mp_qr_code_base64 = Column(Text, nullable=True)
    mp_checkout_url = Column(Text, nullable=True)
    mp_status_detalhe = Column(String(80), nullable=True)
    pago_em = Column(DateTime, nullable=True)

    projeto = relationship("Projeto", back_populates="faturas")
    cliente = relationship("Cliente", back_populates="faturas")


class Holerite(Base):
    __tablename__ = "holerites"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    competencia = Column(String(20), nullable=False)
    tipo = Column(String(50), default="Salário Mensal", nullable=False)
    salario_base = Column(Numeric(12, 2), default=0.00, nullable=False)
    proventos = Column(Numeric(12, 2), default=0.00, nullable=False)
    descricao_proventos = Column(String(255), nullable=True)
    descontos = Column(Numeric(12, 2), default=0.00, nullable=False)
    descricao_descontos = Column(String(255), nullable=True)
    valor_liquido = Column(Numeric(12, 2), default=0.00, nullable=False)
    fgts_valor = Column(Numeric(12, 2), default=0.00, nullable=False)
    data_pagamento = Column(Date, nullable=True)
    status = Column(String(20), default="pago", nullable=False)
    mp_payout_id = Column(String(80), nullable=True)
    mp_payout_status = Column(String(40), nullable=True)
    mp_payout_comprovante = Column(Text, nullable=True)
    observacoes = Column(Text, nullable=True)
    anexo_nome = Column(String(255), nullable=True)
    anexo_data = Column(Text, nullable=True)
    publicado_por = Column(String(120), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="holerites")


class InformeRendimento(Base):
    __tablename__ = "informes_rendimentos"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    ano_calendario = Column(String(10), nullable=False)
    ano_exercicio = Column(String(10), nullable=False)
    rendimentos_tributaveis = Column(Numeric(12, 2), default=0.00, nullable=False)
    contribuicao_previdenciaria = Column(Numeric(12, 2), default=0.00, nullable=False)
    irrf_retido = Column(Numeric(12, 2), default=0.00, nullable=False)
    decimo_terceiro = Column(Numeric(12, 2), default=0.00, nullable=False)
    rendimentos_isentos = Column(Numeric(12, 2), default=0.00, nullable=False)
    observacoes = Column(Text, nullable=True)
    anexo_nome = Column(String(255), nullable=True)
    anexo_data = Column(Text, nullable=True)
    publicado_por = Column(String(120), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="informes_rendimentos")


class ModuloRegistro(Base):
    __tablename__ = "modulos_registros"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    modulo = Column(String(60), index=True, nullable=False)
    titulo = Column(String(180), nullable=False)
    subtitulo = Column(String(180), nullable=True)
    email = Column(String(150), nullable=True)
    telefone = Column(String(40), nullable=True)
    status = Column(String(40), default="ativo", nullable=False)
    descricao = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class LogAuditoria(Base):
    __tablename__ = "logs_auditoria"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    usuario_nome = Column(String(120), nullable=False)
    acao = Column(String(80), nullable=False)
    detalhes = Column(String(255), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


class RegistroPonto(Base):
    __tablename__ = "registros_ponto"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    data_ponto = Column(Date, nullable=False, index=True)
    entrada = Column(String(10), nullable=True)
    saida_almoco = Column(String(10), nullable=True)
    retorno_almoco = Column(String(10), nullable=True)
    saida = Column(String(10), nullable=True)
    minutos_trabalhados = Column(Integer, default=0, nullable=False)
    minutos_extras_50 = Column(Integer, default=0, nullable=False)
    minutos_extras_100 = Column(Integer, default=0, nullable=False)
    minutos_atraso = Column(Integer, default=0, nullable=False)
    eh_feriado_ou_domingo = Column(Boolean, default=False, nullable=False)
    tipo_dia = Column(String(30), default="normal", nullable=False)
    status_ajuste = Column(String(20), default="aprovado", nullable=False)
    justificativa_ajuste = Column(Text, nullable=True)
    ajuste_solicitado_json = Column(Text, nullable=True)
    ip_registro = Column(String(60), nullable=True)
    observacao = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="registros_ponto")


class ConfiguracaoEmpresa(Base):
    __tablename__ = "configuracoes_empresa"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    razao_social = Column(String(180), default="Nexus Code Brasil Tecnologia Ltda", nullable=False)
    nome_fantasia = Column(String(150), default="Nexus Code Brasil", nullable=False)
    cnpj = Column(String(25), default="00.000.000/0001-00", nullable=True)
    inscricao_estadual = Column(String(40), nullable=True)
    email_financeiro = Column(String(150), default="contato@nexuscodebrasil.com.br", nullable=True)
    telefone = Column(String(40), default="(27) 99999-9999", nullable=True)
    endereco = Column(String(255), default="Aracruz - ES", nullable=True)
    cidade = Column(String(100), default="Aracruz", nullable=True)
    estado = Column(String(2), default="ES", nullable=True)
    cep = Column(String(20), nullable=True)
    banco_nome = Column(String(100), default="Banco Inter / Nubank PJ", nullable=True)
    agencia = Column(String(20), nullable=True)
    conta = Column(String(30), nullable=True)
    chave_pix = Column(String(150), default="contato@nexuscodebrasil.com.br", nullable=True)
    titular_pix = Column(String(150), default="Nexus Code Brasil Tecnologia Ltda", nullable=True)
    multa_atraso_percent = Column(Numeric(5, 2), default=2.00, nullable=True)
    juros_mensal_percent = Column(Numeric(5, 2), default=1.00, nullable=True)
    permissoes_json = Column(Text, nullable=True)
    mp_ativo = Column(Boolean, default=False, server_default="false", nullable=False)
    mp_api_tipo = Column(String(20), default="orders", server_default="orders", nullable=False)
    mp_ambiente = Column(String(20), default="producao", server_default="producao", nullable=False)
    mp_public_key = Column(String(255), nullable=True)
    mp_access_token = Column(String(255), nullable=True)
    mp_webhook_secret = Column(String(255), nullable=True)
    registrar_provedor = Column(String(40), default="sandbox", server_default="sandbox", nullable=False)
    registrar_api_user = Column(String(150), nullable=True)
    registrar_api_key = Column(String(255), nullable=True)
    registrar_client_ip = Column(String(60), nullable=True)
    vercel_token = Column(String(255), nullable=True)
    vercel_project_id = Column(String(150), nullable=True)
    vercel_team_id = Column(String(150), nullable=True)
    dominio_precos_json = Column(Text, nullable=True)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PropostaComercial(Base):
    __tablename__ = "propostas_comerciais"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    codigo = Column(String(30), unique=True, index=True, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    solicitacao_id = Column(Integer, ForeignKey("solicitacoes_orcamento.id", ondelete="SET NULL"), nullable=True)
    criado_por_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    titulo = Column(String(180), nullable=False)
    escopo = Column(Text, nullable=False)
    entregaveis_json = Column(Text, nullable=True)
    valor_total = Column(Numeric(12, 2), default=0.00, nullable=False)
    condicoes_pagamento = Column(String(200), default="50% na aprovação + 50% na entrega", nullable=True)
    parcelas = Column(Integer, default=1, nullable=False)
    prazo_dias = Column(Integer, default=30, nullable=False)
    validade_ate = Column(Date, nullable=True)
    status = Column(String(30), default="enviada", nullable=False)
    feedback_cliente = Column(Text, nullable=True)
    aprovado_por_cliente = Column(String(120), nullable=True)
    aprovado_em = Column(DateTime, nullable=True)
    projeto_gerado_id = Column(Integer, ForeignKey("projetos.id", ondelete="SET NULL"), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class Despesa(Base):
    __tablename__ = "despesas"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    descricao = Column(String(200), nullable=False)
    categoria = Column(String(50), default="infraestrutura", nullable=False)
    fornecedor = Column(String(150), nullable=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="SET NULL"), nullable=True)
    valor = Column(Numeric(12, 2), nullable=False)
    vencimento = Column(Date, nullable=False, index=True)
    status = Column(String(25), default="pendente", nullable=False)
    recorrente = Column(Boolean, default=False, nullable=False)
    pago_em = Column(DateTime, nullable=True)
    observacoes = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class ContratoRecorrente(Base):
    __tablename__ = "contratos_recorrentes"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="SET NULL"), nullable=True)
    titulo = Column(String(180), nullable=False)
    valor_mensal = Column(Numeric(12, 2), nullable=False)
    dia_vencimento = Column(Integer, default=10, nullable=False)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=True)
    status = Column(String(25), default="ativo", nullable=False)
    descricao = Column(Text, nullable=True)
    ultima_geracao = Column(String(15), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class ApontamentoHora(Base):
    __tablename__ = "apontamentos_horas"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False, index=True)
    tarefa_id = Column(Integer, ForeignKey("tarefas.id", ondelete="SET NULL"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    data_trabalho = Column(Date, nullable=False)
    horas = Column(Numeric(6, 2), nullable=False)
    descricao = Column(String(255), nullable=False)
    faturavel = Column(Boolean, default=True, nullable=False)
    custo_hora_snapshot = Column(Numeric(10, 2), default=0.00, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


class ChamadoSuporte(Base):
    __tablename__ = "chamados_suporte"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    protocolo = Column(String(30), unique=True, index=True, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="SET NULL"), nullable=True)
    aberto_por_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    responsavel_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    titulo = Column(String(180), nullable=False)
    categoria = Column(String(40), default="suporte_tecnico", nullable=False)
    prioridade = Column(String(20), default="media", nullable=False)
    status = Column(String(30), default="aberto", nullable=False)
    sla_horas = Column(Integer, default=24, nullable=False)
    descricao = Column(Text, nullable=False)
    mensagens_json = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AtivoInfra(Base):
    __tablename__ = "ativos_infra"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="SET NULL"), nullable=True)
    tipo = Column(String(40), default="dominio", nullable=False)
    nome = Column(String(180), nullable=False)
    provedor = Column(String(120), nullable=True)
    url_acesso = Column(String(255), nullable=True)
    usuario_acesso = Column(String(150), nullable=True)
    segredo_acesso = Column(String(255), nullable=True)
    valor_renovacao = Column(Numeric(12, 2), default=0.00, nullable=False)
    data_vencimento = Column(Date, nullable=True)
    status = Column(String(25), default="ativo", nullable=False)
    observacoes = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=True, index=True)
    perfil_destino = Column(String(30), nullable=True)
    titulo = Column(String(160), nullable=False)
    mensagem = Column(String(300), nullable=False)
    link_pagina = Column(String(50), default="dashboard", nullable=False)
    lida = Column(Boolean, default=False, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


class BancoHoras(Base):
    __tablename__ = "banco_horas"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    competencia = Column(String(15), nullable=False)
    saldo_minutos = Column(Integer, default=0, nullable=False)
    observacao = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class ReembolsoDespesa(Base):
    __tablename__ = "reembolsos_despesas"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="SET NULL"), nullable=True)
    descricao = Column(String(200), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    data_despesa = Column(Date, nullable=False)
    status = Column(String(25), default="pendente", nullable=False)
    comprovante_data = Column(Text, nullable=True)
    observacoes_gestor = Column(Text, nullable=True)
    despesa_gerada_id = Column(Integer, ForeignKey("despesas.id", ondelete="SET NULL"), nullable=True)
    mp_payout_id = Column(String(80), nullable=True)
    mp_payout_status = Column(String(40), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class PedidoLoja(Base):
    __tablename__ = "pedidos_loja"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    codigo = Column(String(30), unique=True, index=True, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
    nome_comprador = Column(String(150), nullable=False)
    email_comprador = Column(String(150), index=True, nullable=False)
    telefone_comprador = Column(String(30), nullable=True)
    itens_json = Column(Text, nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    desconto = Column(Numeric(12, 2), default=0.00, nullable=False)
    frete = Column(Numeric(12, 2), default=0.00, nullable=False)
    valor_total = Column(Numeric(12, 2), nullable=False)
    status = Column(String(25), default="aguardando_pagamento", nullable=False)
    fatura_gerada_id = Column(Integer, ForeignKey("faturas.id", ondelete="SET NULL"), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class ProdutoLoja(Base):
    __tablename__ = "produtos_loja"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    slug = Column(String(60), index=True, nullable=False)
    nome = Column(String(150), nullable=False)
    descricao = Column(Text, nullable=True)
    preco = Column(Numeric(12, 2), nullable=False)
    badge = Column(String(40), nullable=True)
    spec_label = Column(String(80), nullable=True)
    imagem_url = Column(Text, nullable=True)
    fundo_escuro = Column(Boolean, default=False, nullable=False)
    tamanhos_json = Column(Text, nullable=True)
    cores_json = Column(Text, nullable=True)
    ordem = Column(Integer, default=1, nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


class PedidoDominio(Base):
    __tablename__ = "pedidos_dominios"

    id = Column(Integer, primary_key=True, index=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), default=1, server_default="1", nullable=False, index=True)
    codigo = Column(String(30), unique=True, index=True, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    dominio = Column(String(180), index=True, nullable=False)
    extensao = Column(String(30), nullable=False)
    anos = Column(Integer, default=1, nullable=False)
    titular_nome = Column(String(150), nullable=False)
    titular_documento = Column(String(30), nullable=True)
    titular_email = Column(String(150), nullable=False)
    titular_telefone = Column(String(30), nullable=True)
    preco_custo = Column(Numeric(12, 2), default=0.00, nullable=False)
    valor_venda = Column(Numeric(12, 2), nullable=False)
    status = Column(String(30), default="aguardando_pagamento", nullable=False)
    dns_status = Column(String(30), default="pendente", nullable=False)
    vincular_portal_saas = Column(Boolean, default=False, nullable=False)
    fatura_id = Column(Integer, ForeignKey("faturas.id", ondelete="SET NULL"), nullable=True)
    ativo_id = Column(Integer, ForeignKey("ativos_infra.id", ondelete="SET NULL"), nullable=True)
    contrato_id = Column(Integer, ForeignKey("contratos_recorrentes.id", ondelete="SET NULL"), nullable=True)
    mp_order_id = Column(String(80), nullable=True, index=True)
    mp_payment_id = Column(String(80), nullable=True, index=True)
    mp_qr_code = Column(Text, nullable=True)
    mp_qr_code_base64 = Column(Text, nullable=True)
    mp_checkout_url = Column(Text, nullable=True)
    registrar_order_id = Column(String(120), nullable=True)
    registrar_resposta_json = Column(Text, nullable=True)
    expira_em = Column(Date, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
