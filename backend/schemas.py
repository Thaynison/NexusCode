from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class RegisterRequest(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(..., min_length=6)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    nova_senha: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: "UsuarioListOut"


class UsuarioBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    perfil: Literal["admin", "colaborador", "cliente"] = "colaborador"
    ativo: bool = True
    cpf: Optional[str] = None
    data_nascimento: Optional[date] = None
    data_contratacao: Optional[date] = None
    data_fim_contrato: Optional[date] = None
    tipo_contrato: Optional[str] = "clt_fixo"
    cbo_codigo: Optional[str] = None
    cbo_descricao: Optional[str] = None
    carga_horaria_diaria: Optional[Decimal] = Decimal("8.00")
    horario_entrada: Optional[str] = "08:00"
    horario_saida: Optional[str] = "17:00"
    dependentes_irrf: Optional[int] = 0
    vale_transporte: Optional[bool] = False
    valor_vt_mensal: Optional[Decimal] = Decimal("0.00")
    salario_base: Optional[Decimal] = Decimal("0.00")
    telefone: Optional[str] = None
    cargo: Optional[str] = None

    @field_validator("tipo_contrato", mode="before")
    @classmethod
    def _default_tipo_contrato(cls, v):
        return v or "clt_fixo"

    @field_validator("carga_horaria_diaria", mode="before")
    @classmethod
    def _default_carga(cls, v):
        return Decimal("8.00") if v is None else v

    @field_validator("horario_entrada", mode="before")
    @classmethod
    def _default_h_ent(cls, v):
        return v or "08:00"

    @field_validator("horario_saida", mode="before")
    @classmethod
    def _default_h_sai(cls, v):
        return v or "17:00"

    @field_validator("dependentes_irrf", mode="before")
    @classmethod
    def _default_dep(cls, v):
        return 0 if v is None else v

    @field_validator("vale_transporte", mode="before")
    @classmethod
    def _default_vt_bool(cls, v):
        return False if v is None else v

    @field_validator("valor_vt_mensal", "salario_base", mode="before")
    @classmethod
    def _default_dec_usr(cls, v):
        return Decimal("0.00") if v is None else v

    area_atuacao: Optional[str] = None
    formacao: Optional[str] = None
    habilidades: Optional[str] = None
    linkedin_url: Optional[str] = None
    resumo_profissional: Optional[str] = None
    foto_url: Optional[str] = None
    cep: Optional[str] = None
    endereco: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    termos_aceitos_em: Optional[datetime] = None


class UsuarioCreate(UsuarioBase):
    senha: str = Field(..., min_length=6)


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    perfil: Optional[Literal["admin", "colaborador", "cliente"]] = None
    ativo: Optional[bool] = None
    senha: Optional[str] = Field(default=None, min_length=6)
    cpf: Optional[str] = None
    data_nascimento: Optional[date] = None
    data_contratacao: Optional[date] = None
    data_fim_contrato: Optional[date] = None
    tipo_contrato: Optional[str] = None
    cbo_codigo: Optional[str] = None
    cbo_descricao: Optional[str] = None
    carga_horaria_diaria: Optional[Decimal] = None
    horario_entrada: Optional[str] = None
    horario_saida: Optional[str] = None
    dependentes_irrf: Optional[int] = None
    vale_transporte: Optional[bool] = None
    valor_vt_mensal: Optional[Decimal] = None
    salario_base: Optional[Decimal] = None
    telefone: Optional[str] = None
    cargo: Optional[str] = None
    area_atuacao: Optional[str] = None
    formacao: Optional[str] = None
    habilidades: Optional[str] = None
    linkedin_url: Optional[str] = None
    resumo_profissional: Optional[str] = None
    foto_url: Optional[str] = None
    cep: Optional[str] = None
    endereco: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    termos_aceitos_em: Optional[datetime] = None


class UsuarioOut(UsuarioBase):
    id: int
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class UsuarioListOut(BaseModel):
    """Schema enxuto sem foto_url Base64 para respostas instantâneas em listas e login."""
    id: int
    nome: str
    email: str
    perfil: str
    ativo: bool
    cpf: Optional[str] = None
    data_nascimento: Optional[date] = None
    data_contratacao: Optional[date] = None
    data_fim_contrato: Optional[date] = None
    tipo_contrato: Optional[str] = "clt_fixo"
    cbo_codigo: Optional[str] = None
    cbo_descricao: Optional[str] = None
    carga_horaria_diaria: Optional[Decimal] = Decimal("8.00")
    horario_entrada: Optional[str] = "08:00"
    horario_saida: Optional[str] = "17:00"
    dependentes_irrf: Optional[int] = 0
    vale_transporte: Optional[bool] = False
    valor_vt_mensal: Optional[Decimal] = Decimal("0.00")
    salario_base: Optional[Decimal] = Decimal("0.00")
    telefone: Optional[str] = None
    cargo: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class ClienteBase(BaseModel):
    usuario_portal_id: Optional[int] = None
    nome_empresa: str = Field(..., max_length=150)
    contato_nome: str = Field(..., max_length=120)
    email: EmailStr
    telefone: Optional[str] = None
    documento: Optional[str] = None
    status_funil: Literal["lead", "proposta", "negociacao", "ativo", "inativo"] = "lead"
    origem: Optional[str] = None
    observacoes: Optional[str] = None


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    usuario_portal_id: Optional[int] = None
    nome_empresa: Optional[str] = None
    contato_nome: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    documento: Optional[str] = None
    status_funil: Optional[Literal["lead", "proposta", "negociacao", "ativo", "inativo"]] = None
    origem: Optional[str] = None
    observacoes: Optional[str] = None


class ClienteOut(ClienteBase):
    id: int
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class SolicitacaoPublicCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    empresa: Optional[str] = Field(default=None, max_length=150)
    email: EmailStr
    telefone: Optional[str] = Field(default=None, max_length=30)
    tipo_projeto: Optional[str] = Field(default="Não especificado", max_length=80)
    mensagem: str = Field(..., min_length=3, max_length=4000)
    website: Optional[str] = None


class SolicitacaoPortalCreate(BaseModel):
    tipo_projeto: str = Field(default="Desenvolvimento Web", max_length=80)
    titulo: str = Field(..., min_length=3, max_length=160)
    urgencia: Literal["normal", "alta", "urgente"] = "normal"
    orcamento_estimado: Optional[str] = Field(default=None, max_length=80)
    mensagem: str = Field(..., min_length=5, max_length=4000)


class SolicitacaoResponder(BaseModel):
    resposta: str = Field(..., min_length=2, max_length=4000)
    status: Literal["novo", "em_atendimento", "respondido", "convertido", "arquivado"] = "respondido"


class SolicitacaoUpdate(BaseModel):
    status: Optional[Literal["novo", "em_atendimento", "respondido", "convertido", "arquivado"]] = None
    resposta: Optional[str] = None


class SolicitacaoOut(BaseModel):
    id: int
    cliente_id: Optional[int] = None
    nome: str
    empresa: Optional[str] = None
    email: str
    telefone: Optional[str] = None
    tipo_projeto: Optional[str] = None
    mensagem: str
    status: str
    resposta: Optional[str] = None
    respondido_por: Optional[str] = None
    respondido_em: Optional[datetime] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class ProjetoBase(BaseModel):
    cliente_id: int
    responsavel_id: Optional[int] = None
    titulo: str = Field(..., max_length=180)
    descricao: Optional[str] = None
    status: Literal["planejamento", "em_andamento", "homologacao", "concluido", "cancelado"] = "planejamento"
    prioridade: Literal["baixa", "media", "alta", "urgente"] = "media"
    progresso: int = Field(default=0, ge=0, le=100)
    valor_total: Decimal = Decimal("0.00")
    horas_estimadas: Optional[Decimal] = Decimal("0.00")
    url_homologacao: Optional[str] = None
    url_producao: Optional[str] = None
    repositorio_url: Optional[str] = None
    aprovacao_cliente_status: Optional[str] = "pendente"
    aprovacao_cliente_obs: Optional[str] = None
    data_inicio: Optional[date] = None
    data_entrega: Optional[date] = None

    @field_validator("horas_estimadas", mode="before")
    @classmethod
    def _default_horas_est(cls, v):
        return Decimal("0.00") if v is None else v

    @field_validator("aprovacao_cliente_status", mode="before")
    @classmethod
    def _default_aprov_status(cls, v):
        return v or "pendente"


class ProjetoCreate(ProjetoBase):
    pass


class ProjetoUpdate(BaseModel):
    responsavel_id: Optional[int] = None
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    status: Optional[Literal["planejamento", "em_andamento", "homologacao", "concluido", "cancelado"]] = None
    prioridade: Optional[Literal["baixa", "media", "alta", "urgente"]] = None
    progresso: Optional[int] = Field(default=None, ge=0, le=100)
    valor_total: Optional[Decimal] = None
    horas_estimadas: Optional[Decimal] = None
    url_homologacao: Optional[str] = None
    url_producao: Optional[str] = None
    repositorio_url: Optional[str] = None
    aprovacao_cliente_status: Optional[str] = None
    aprovacao_cliente_obs: Optional[str] = None
    data_inicio: Optional[date] = None
    data_entrega: Optional[date] = None


class ProjetoHomologacaoCliente(BaseModel):
    decisao: Literal["aprovado", "ajuste_solicitado"]
    observacao: Optional[str] = None


class ProjetoOut(ProjetoBase):
    id: int
    aprovado_em: Optional[datetime] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class TarefaBase(BaseModel):
    projeto_id: int
    responsavel_id: Optional[int] = None
    titulo: str = Field(..., max_length=180)
    descricao: Optional[str] = None
    status: Literal["pendente", "fazendo", "revisao", "concluida"] = "pendente"
    prioridade: Literal["baixa", "media", "alta", "urgente"] = "media"
    data_inicio: Optional[date] = None
    prazo: Optional[date] = None
    checklist_json: Optional[str] = None
    anexos_json: Optional[str] = None
    comentarios_json: Optional[str] = None

    @field_validator("status", mode="before")
    @classmethod
    def _default_status(cls, v):
        return v or "pendente"

    @field_validator("prioridade", mode="before")
    @classmethod
    def _default_prioridade(cls, v):
        return v if v in ("baixa", "media", "alta", "urgente") else "media"


class TarefaCreate(TarefaBase):
    pass


class TarefaUpdate(BaseModel):
    projeto_id: Optional[int] = None
    responsavel_id: Optional[int] = None
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    status: Optional[Literal["pendente", "fazendo", "revisao", "concluida"]] = None
    prioridade: Optional[Literal["baixa", "media", "alta", "urgente"]] = None
    data_inicio: Optional[date] = None
    prazo: Optional[date] = None
    checklist_json: Optional[str] = None
    anexos_json: Optional[str] = None
    comentarios_json: Optional[str] = None


class TarefaOut(TarefaBase):
    id: int
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class InteracaoCreate(BaseModel):
    cliente_id: int
    tipo: Literal["reuniao", "email", "whatsapp", "ligacao", "proposta"] = "whatsapp"
    resumo: str
    proxima_acao: Optional[str] = None


class InteracaoOut(InteracaoCreate):
    id: int
    usuario_id: Optional[int] = None
    data_interacao: datetime
    model_config = ConfigDict(from_attributes=True)


class FaturaCreate(BaseModel):
    projeto_id: Optional[int] = None
    cliente_id: int
    descricao: str
    valor: Decimal
    status: Literal["pendente", "pago", "atrasado", "cancelado"] = "pendente"
    forma_pagamento: Optional[str] = "PIX"
    observacoes: Optional[str] = None
    vencimento: date


class FaturaUpdate(BaseModel):
    status: Optional[Literal["pendente", "pago", "atrasado", "cancelado"]] = None
    forma_pagamento: Optional[str] = None
    observacoes: Optional[str] = None
    vencimento: Optional[date] = None
    pago_em: Optional[datetime] = None


class FaturaComprovanteUpload(BaseModel):
    comprovante_nome: str = Field(..., max_length=255)
    comprovante_data: str
    observacoes: Optional[str] = None


class FaturaOut(FaturaCreate):
    id: int
    comprovante_nome: Optional[str] = None
    comprovante_data: Optional[str] = None
    pago_em: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class FaturaListOut(FaturaCreate):
    id: int
    comprovante_nome: Optional[str] = None
    pago_em: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class HoleriteBase(BaseModel):
    usuario_id: int
    competencia: str = Field(..., max_length=20)
    tipo: str = Field(default="Salário Mensal", max_length=50)
    salario_base: Decimal = Decimal("0.00")
    proventos: Decimal = Decimal("0.00")
    descricao_proventos: Optional[str] = None
    descontos: Decimal = Decimal("0.00")
    descricao_descontos: Optional[str] = None
    valor_liquido: Decimal = Decimal("0.00")
    fgts_valor: Decimal = Decimal("0.00")
    data_pagamento: Optional[date] = None
    status: Literal["pago", "programado", "pendente"] = "pago"
    observacoes: Optional[str] = None
    anexo_nome: Optional[str] = None
    anexo_data: Optional[str] = None

    @field_validator("salario_base", "proventos", "descontos", "valor_liquido", "fgts_valor", mode="before")
    @classmethod
    def _coerce_decimal(cls, v):
        return Decimal("0.00") if v is None else v

    @field_validator("status", mode="before")
    @classmethod
    def _default_hol_status(cls, v):
        return v if v in ("pago", "programado", "pendente") else "pago"


class HoleriteCreate(HoleriteBase):
    pass


class HoleriteUpdate(BaseModel):
    competencia: Optional[str] = None
    tipo: Optional[str] = None
    salario_base: Optional[Decimal] = None
    proventos: Optional[Decimal] = None
    descricao_proventos: Optional[str] = None
    descontos: Optional[Decimal] = None
    descricao_descontos: Optional[str] = None
    valor_liquido: Optional[Decimal] = None
    fgts_valor: Optional[Decimal] = None
    data_pagamento: Optional[date] = None
    status: Optional[Literal["pago", "programado", "pendente"]] = None
    observacoes: Optional[str] = None
    anexo_nome: Optional[str] = None
    anexo_data: Optional[str] = None


class HoleriteOut(HoleriteBase):
    id: int
    publicado_por: Optional[str] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class HoleriteListOut(BaseModel):
    id: int
    usuario_id: int
    competencia: str
    tipo: str
    salario_base: Decimal
    proventos: Decimal
    descricao_proventos: Optional[str] = None
    descontos: Decimal
    descricao_descontos: Optional[str] = None
    valor_liquido: Decimal
    fgts_valor: Decimal
    data_pagamento: Optional[date] = None
    status: str
    observacoes: Optional[str] = None
    anexo_nome: Optional[str] = None
    publicado_por: Optional[str] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class InformeRendimentoBase(BaseModel):
    usuario_id: int
    ano_calendario: str = Field(..., max_length=10)
    ano_exercicio: str = Field(..., max_length=10)
    rendimentos_tributaveis: Decimal = Decimal("0.00")
    contribuicao_previdenciaria: Decimal = Decimal("0.00")
    irrf_retido: Decimal = Decimal("0.00")
    decimo_terceiro: Decimal = Decimal("0.00")
    rendimentos_isentos: Decimal = Decimal("0.00")
    observacoes: Optional[str] = None
    anexo_nome: Optional[str] = None
    anexo_data: Optional[str] = None


class InformeRendimentoCreate(InformeRendimentoBase):
    pass


class InformeRendimentoOut(InformeRendimentoBase):
    id: int
    publicado_por: Optional[str] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class InformeListOut(BaseModel):
    id: int
    usuario_id: int
    ano_calendario: str
    ano_exercicio: str
    rendimentos_tributaveis: Decimal
    contribuicao_previdenciaria: Decimal
    irrf_retido: Decimal
    decimo_terceiro: Decimal
    rendimentos_isentos: Decimal
    observacoes: Optional[str] = None
    anexo_nome: Optional[str] = None
    publicado_por: Optional[str] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class ModuloRegistroCreate(BaseModel):
    titulo: str = Field(..., max_length=180)
    subtitulo: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    status: str = "ativo"
    descricao: Optional[str] = None


class ModuloRegistroOut(ModuloRegistroCreate):
    id: int
    modulo: str
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class LogAuditoriaOut(BaseModel):
    id: int
    usuario_nome: str
    acao: str
    detalhes: str
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class PontoBatidaRequest(BaseModel):
    tipo_batida: Literal["entrada", "saida_almoco", "retorno_almoco", "saida"]
    hora_manual: Optional[str] = None
    observacao: Optional[str] = None


class PontoAjusteCreate(BaseModel):
    data_ponto: date
    entrada: Optional[str] = None
    saida_almoco: Optional[str] = None
    retorno_almoco: Optional[str] = None
    saida: Optional[str] = None
    tipo_dia: Literal["normal", "feriado_domingo", "folga", "atestado", "falta_justificada"] = "normal"
    justificativa: str = Field(..., min_length=3, max_length=1000)


class PontoAjusteDecisao(BaseModel):
    decisao: Literal["aprovado", "rejeitado"]
    observacao_gestor: Optional[str] = None


class RegistroPontoOut(BaseModel):
    id: int
    usuario_id: int
    data_ponto: date
    entrada: Optional[str] = None
    saida_almoco: Optional[str] = None
    retorno_almoco: Optional[str] = None
    saida: Optional[str] = None
    minutos_trabalhados: int = 0
    minutos_extras_50: int = 0
    minutos_extras_100: int = 0
    minutos_atraso: int = 0
    eh_feriado_ou_domingo: bool = False
    tipo_dia: str = "normal"
    status_ajuste: str = "aprovado"
    justificativa_ajuste: Optional[str] = None
    ajuste_solicitado_json: Optional[str] = None
    ip_registro: Optional[str] = None
    observacao: Optional[str] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class GerarHoleriteAutoRequest(BaseModel):
    usuario_id: Optional[int] = None
    gerar_todos: bool = False
    competencia: str = Field(..., max_length=20)
    tipo: str = Field(default="Salário Mensal", max_length=50)
    data_pagamento: Optional[date] = None
    status: Literal["pago", "programado", "pendente"] = "pago"
    observacoes: Optional[str] = None


class ConfiguracaoEmpresaUpdate(BaseModel):
    razao_social: Optional[str] = None
    nome_fantasia: Optional[str] = None
    cnpj: Optional[str] = None
    inscricao_estadual: Optional[str] = None
    email_financeiro: Optional[str] = None
    telefone: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    banco_nome: Optional[str] = None
    agencia: Optional[str] = None
    conta: Optional[str] = None
    chave_pix: Optional[str] = None
    titular_pix: Optional[str] = None
    multa_atraso_percent: Optional[Decimal] = None
    juros_mensal_percent: Optional[Decimal] = None
    permissoes_json: Optional[str] = None


class ConfiguracaoEmpresaOut(ConfiguracaoEmpresaUpdate):
    id: int
    atualizado_em: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class PropostaCreate(BaseModel):
    cliente_id: int
    solicitacao_id: Optional[int] = None
    titulo: str = Field(..., max_length=180)
    escopo: str
    entregaveis_json: Optional[str] = None
    valor_total: Decimal = Decimal("0.00")
    condicoes_pagamento: Optional[str] = "50% na aprovação + 50% na entrega"
    parcelas: int = Field(default=1, ge=1, le=36)
    prazo_dias: int = Field(default=30, ge=1, le=730)
    validade_ate: Optional[date] = None
    status: Literal["rascunho", "enviada", "aprovada", "ajuste_solicitado", "recusada"] = "enviada"


class PropostaUpdate(BaseModel):
    titulo: Optional[str] = None
    escopo: Optional[str] = None
    entregaveis_json: Optional[str] = None
    valor_total: Optional[Decimal] = None
    condicoes_pagamento: Optional[str] = None
    parcelas: Optional[int] = Field(default=None, ge=1, le=36)
    prazo_dias: Optional[int] = Field(default=None, ge=1, le=730)
    validade_ate: Optional[date] = None
    status: Optional[Literal["rascunho", "enviada", "aprovada", "ajuste_solicitado", "recusada"]] = None
    feedback_cliente: Optional[str] = None


class PropostaDecisaoCliente(BaseModel):
    decisao: Literal["aprovada", "ajuste_solicitado", "recusada"]
    feedback: Optional[str] = None


class PropostaOut(BaseModel):
    id: int
    codigo: str
    cliente_id: int
    solicitacao_id: Optional[int] = None
    criado_por_id: Optional[int] = None
    titulo: str
    escopo: str
    entregaveis_json: Optional[str] = None
    valor_total: Decimal
    condicoes_pagamento: Optional[str] = None
    parcelas: int
    prazo_dias: int
    validade_ate: Optional[date] = None
    status: str
    feedback_cliente: Optional[str] = None
    aprovado_por_cliente: Optional[str] = None
    aprovado_em: Optional[datetime] = None
    projeto_gerado_id: Optional[int] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class DespesaCreate(BaseModel):
    descricao: str = Field(..., max_length=200)
    categoria: Literal["infraestrutura", "folha_rh", "impostos", "software_saas", "marketing", "fornecedores", "outros"] = "infraestrutura"
    fornecedor: Optional[str] = None
    projeto_id: Optional[int] = None
    valor: Decimal
    vencimento: date
    status: Literal["pendente", "pago", "atrasado", "cancelado"] = "pendente"
    recorrente: bool = False
    observacoes: Optional[str] = None


class DespesaUpdate(BaseModel):
    descricao: Optional[str] = None
    categoria: Optional[Literal["infraestrutura", "folha_rh", "impostos", "software_saas", "marketing", "fornecedores", "outros"]] = None
    fornecedor: Optional[str] = None
    projeto_id: Optional[int] = None
    valor: Optional[Decimal] = None
    vencimento: Optional[date] = None
    status: Optional[Literal["pendente", "pago", "atrasado", "cancelado"]] = None
    recorrente: Optional[bool] = None
    observacoes: Optional[str] = None


class DespesaOut(DespesaCreate):
    id: int
    pago_em: Optional[datetime] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class ContratoRecorrenteCreate(BaseModel):
    cliente_id: int
    projeto_id: Optional[int] = None
    titulo: str = Field(..., max_length=180)
    valor_mensal: Decimal
    dia_vencimento: int = Field(default=10, ge=1, le=28)
    data_inicio: date
    data_fim: Optional[date] = None
    status: Literal["ativo", "pausado", "encerrado"] = "ativo"
    descricao: Optional[str] = None


class ContratoRecorrenteUpdate(BaseModel):
    titulo: Optional[str] = None
    valor_mensal: Optional[Decimal] = None
    dia_vencimento: Optional[int] = Field(default=None, ge=1, le=28)
    data_fim: Optional[date] = None
    status: Optional[Literal["ativo", "pausado", "encerrado"]] = None
    descricao: Optional[str] = None


class ContratoRecorrenteOut(ContratoRecorrenteCreate):
    id: int
    ultima_geracao: Optional[str] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class ApontamentoHoraCreate(BaseModel):
    projeto_id: int
    tarefa_id: Optional[int] = None
    usuario_id: Optional[int] = None
    data_trabalho: date
    horas: Decimal = Field(..., gt=0, le=24)
    descricao: str = Field(..., min_length=2, max_length=255)
    faturavel: bool = True


class ApontamentoHoraOut(BaseModel):
    id: int
    projeto_id: int
    tarefa_id: Optional[int] = None
    usuario_id: int
    data_trabalho: date
    horas: Decimal
    descricao: str
    faturavel: bool
    custo_hora_snapshot: Decimal
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class ChamadoCreate(BaseModel):
    cliente_id: Optional[int] = None
    projeto_id: Optional[int] = None
    responsavel_id: Optional[int] = None
    titulo: str = Field(..., min_length=3, max_length=180)
    categoria: Literal["suporte_tecnico", "nova_funcionalidade", "bug_correcao", "duvida_financeira", "infraestrutura"] = "suporte_tecnico"
    prioridade: Literal["baixa", "media", "alta", "critica"] = "media"
    sla_horas: int = Field(default=24, ge=1, le=720)
    descricao: str = Field(..., min_length=3, max_length=4000)
    anexo_nome: Optional[str] = None
    anexo_data: Optional[str] = None


class ChamadoMensagemCreate(BaseModel):
    texto: str = Field(..., min_length=1, max_length=4000)
    anexo_nome: Optional[str] = None
    anexo_data: Optional[str] = None
    novo_status: Optional[Literal["aberto", "em_analise", "aguardando_cliente", "resolvido", "fechado"]] = None


class ChamadoUpdate(BaseModel):
    responsavel_id: Optional[int] = None
    prioridade: Optional[Literal["baixa", "media", "alta", "critica"]] = None
    status: Optional[Literal["aberto", "em_analise", "aguardando_cliente", "resolvido", "fechado"]] = None
    sla_horas: Optional[int] = None


class ChamadoOut(BaseModel):
    id: int
    protocolo: str
    cliente_id: int
    projeto_id: Optional[int] = None
    aberto_por_id: Optional[int] = None
    responsavel_id: Optional[int] = None
    titulo: str
    categoria: str
    prioridade: str
    status: str
    sla_horas: int
    descricao: str
    mensagens_json: Optional[str] = None
    criado_em: datetime
    atualizado_em: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class AtivoInfraCreate(BaseModel):
    cliente_id: Optional[int] = None
    projeto_id: Optional[int] = None
    tipo: Literal["dominio", "hospedagem_cloud", "licenca_software", "equipamento", "credencial_acesso"] = "dominio"
    nome: str = Field(..., max_length=180)
    provedor: Optional[str] = None
    url_acesso: Optional[str] = None
    usuario_acesso: Optional[str] = None
    segredo_acesso: Optional[str] = None
    valor_renovacao: Decimal = Decimal("0.00")
    data_vencimento: Optional[date] = None
    status: Literal["ativo", "vencendo", "expirado", "inativo"] = "ativo"
    observacoes: Optional[str] = None


class AtivoInfraUpdate(BaseModel):
    cliente_id: Optional[int] = None
    projeto_id: Optional[int] = None
    tipo: Optional[Literal["dominio", "hospedagem_cloud", "licenca_software", "equipamento", "credencial_acesso"]] = None
    nome: Optional[str] = None
    provedor: Optional[str] = None
    url_acesso: Optional[str] = None
    usuario_acesso: Optional[str] = None
    segredo_acesso: Optional[str] = None
    valor_renovacao: Optional[Decimal] = None
    data_vencimento: Optional[date] = None
    status: Optional[Literal["ativo", "vencendo", "expirado", "inativo"]] = None
    observacoes: Optional[str] = None


class AtivoInfraOut(AtivoInfraCreate):
    id: int
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class NotificacaoOut(BaseModel):
    id: int
    usuario_id: Optional[int] = None
    perfil_destino: Optional[str] = None
    titulo: str
    mensagem: str
    link_pagina: str
    lida: bool
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class ReembolsoCreate(BaseModel):
    projeto_id: Optional[int] = None
    descricao: str = Field(..., max_length=200)
    valor: Decimal = Field(..., gt=0)
    data_despesa: date
    comprovante_data: Optional[str] = None


class ReembolsoUpdate(BaseModel):
    status: Literal["pendente", "aprovado", "recusado", "pago"]
    observacoes_gestor: Optional[str] = None


class ReembolsoOut(BaseModel):
    id: int
    usuario_id: int
    projeto_id: Optional[int] = None
    descricao: str
    valor: Decimal
    data_despesa: date
    status: str
    comprovante_data: Optional[str] = None
    observacoes_gestor: Optional[str] = None
    despesa_gerada_id: Optional[int] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class PedidoLojaCreate(BaseModel):
    nome_comprador: str = Field(..., max_length=150)
    email_comprador: EmailStr
    telefone_comprador: Optional[str] = None
    itens_json: str
    subtotal: Decimal
    desconto: Decimal = Decimal("0.00")
    frete: Decimal = Decimal("0.00")
    valor_total: Decimal


class PedidoLojaUpdate(BaseModel):
    status: Literal["novo", "aguardando_pagamento", "pago", "enviado", "cancelado"]


class PedidoLojaOut(BaseModel):
    id: int
    codigo: str
    cliente_id: Optional[int] = None
    nome_comprador: str
    email_comprador: str
    telefone_comprador: Optional[str] = None
    itens_json: str
    subtotal: Decimal
    desconto: Decimal
    frete: Decimal
    valor_total: Decimal
    status: str
    fatura_gerada_id: Optional[int] = None
    criado_em: datetime
    model_config = ConfigDict(from_attributes=True)
