from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date,
    Numeric, Enum, ForeignKey
)
from sqlalchemy.orm import relationship
from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
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
    salario_base = Column(Numeric(12, 2), default=0.00, nullable=True)
    telefone = Column(String(30), nullable=True)
    cargo = Column(String(120), nullable=True)
    area_atuacao = Column(String(120), nullable=True)
    formacao = Column(String(200), nullable=True)
    habilidades = Column(String(255), nullable=True)
    linkedin_url = Column(String(255), nullable=True)
    resumo_profissional = Column(Text, nullable=True)
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


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    usuario_portal_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    nome_empresa = Column(String(150), nullable=False)
    contato_nome = Column(String(120), nullable=False)
    email = Column(String(150), nullable=False)
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
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
    nome = Column(String(120), nullable=False)
    empresa = Column(String(150), nullable=True)
    email = Column(String(150), nullable=False)
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
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
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
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False)
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
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
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
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    descricao = Column(String(200), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    status = Column(
        Enum("pendente", "pago", "atrasado", "cancelado", name="status_fatura"),
        default="pendente",
        native_enum=False,
        nullable=False,
    )
    vencimento = Column(Date, nullable=False)
    pago_em = Column(DateTime, nullable=True)

    projeto = relationship("Projeto", back_populates="faturas")
    cliente = relationship("Cliente", back_populates="faturas")


class Holerite(Base):
    __tablename__ = "holerites"

    id = Column(Integer, primary_key=True, index=True)
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
    observacoes = Column(Text, nullable=True)
    anexo_nome = Column(String(255), nullable=True)
    anexo_data = Column(Text, nullable=True)
    publicado_por = Column(String(120), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="holerites")


class InformeRendimento(Base):
    __tablename__ = "informes_rendimentos"

    id = Column(Integer, primary_key=True, index=True)
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
    usuario_nome = Column(String(120), nullable=False)
    acao = Column(String(80), nullable=False)
    detalhes = Column(String(255), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)
