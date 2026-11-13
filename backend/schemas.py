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


class UsuarioCreate(UsuarioBase):
    senha: str = Field(..., min_length=6)


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    perfil: Optional[Literal["admin", "colaborador", "cliente"]] = None
    ativo: Optional[bool] = None
    senha: Optional[str] = Field(default=None, min_length=6)


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
    website: Optional[str] = None  # honeypot


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
    prazo: Optional[date] = None


class TarefaCreate(TarefaBase):
    pass


class TarefaUpdate(BaseModel):
    responsavel_id: Optional[int] = None
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    status: Optional[Literal["pendente", "fazendo", "revisao", "concluida"]] = None
    prazo: Optional[date] = None


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
