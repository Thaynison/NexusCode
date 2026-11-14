from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict


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
    salario_base: Optional[Decimal] = Decimal("0.00")
    telefone: Optional[str] = None
    cargo: Optional[str] = None
    area_atuacao: Optional[str] = None
    formacao: Optional[str] = None
    habilidades: Optional[str] = None
    linkedin_url: Optional[str] = None
    resumo_profissional: Optional[str] = None
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
    salario_base: Optional[Decimal] = None
    telefone: Optional[str] = None
    cargo: Optional[str] = None
    area_atuacao: Optional[str] = None
    formacao: Optional[str] = None
    habilidades: Optional[str] = None
    linkedin_url: Optional[str] = None
    resumo_profissional: Optional[str] = None
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
