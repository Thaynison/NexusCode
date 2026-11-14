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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: "UsuarioOut"


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
    data_inicio: Optional[date] = None
    data_entrega: Optional[date] = None


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
    data_inicio: Optional[date] = None
    data_entrega: Optional[date] = None


class ProjetoOut(ProjetoBase):
    id: int
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
    projeto_id: int
    cliente_id: int
    descricao: str
    valor: Decimal
    status: Literal["pendente", "pago", "atrasado", "cancelado"] = "pendente"
    vencimento: date


class FaturaUpdate(BaseModel):
    status: Optional[Literal["pendente", "pago", "atrasado", "cancelado"]] = None
    vencimento: Optional[date] = None
    pago_em: Optional[datetime] = None


class FaturaOut(FaturaCreate):
    id: int
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
