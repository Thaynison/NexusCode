import os
from contextlib import asynccontextmanager
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
import calendar
import hmac
import json
import re
import unicodedata
import smtplib
from email.message import EmailMessage

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from jose import JWTError, jwt
from sqlalchemy import func, inspect, text, or_
from sqlalchemy.orm import Session, defer

from database import Base, engine, get_db, SessionLocal
from models import (
    Organizacao, PlanoSaas,
    Usuario, Cliente, SolicitacaoOrcamento, Projeto,
    Tarefa, Interacao, Fatura, Holerite, InformeRendimento,
    RegistroPonto, ModuloRegistro, LogAuditoria,
    ConfiguracaoEmpresa, PropostaComercial, Despesa,
    ContratoRecorrente, ApontamentoHora, ChamadoSuporte,
    AtivoInfra, Notificacao, BancoHoras, ReembolsoDespesa, PedidoLoja, ProdutoLoja,
)
from schemas import (
    LoginRequest, RegisterRequest, ForgotPasswordRequest, ResetPasswordRequest, TokenResponse,
    UsuarioCreate, UsuarioUpdate, UsuarioOut, UsuarioListOut,
    ClienteCreate, ClienteUpdate, ClienteOut,
    SolicitacaoPublicCreate, SolicitacaoPortalCreate, SolicitacaoResponder, SolicitacaoUpdate, SolicitacaoOut,
    ProjetoCreate, ProjetoUpdate, ProjetoHomologacaoCliente, ProjetoOut,
    TarefaCreate, TarefaUpdate, TarefaOut,
    InteracaoCreate, InteracaoOut,
    FaturaCreate, FaturaUpdate, FaturaComprovanteUpload, FaturaOut, FaturaListOut,
    HoleriteCreate, HoleriteUpdate, HoleriteOut, HoleriteListOut,
    InformeRendimentoCreate, InformeRendimentoOut, InformeListOut,
    PontoBatidaRequest, PontoAjusteCreate, PontoAjusteDecisao, RegistroPontoOut,
    GerarHoleriteAutoRequest,
    ModuloRegistroCreate, ModuloRegistroOut, LogAuditoriaOut,
    ConfiguracaoEmpresaUpdate, ConfiguracaoEmpresaOut,
    PropostaCreate, PropostaUpdate, PropostaDecisaoCliente, PropostaOut,
    DespesaCreate, DespesaUpdate, DespesaOut,
    ContratoRecorrenteCreate, ContratoRecorrenteUpdate, ContratoRecorrenteOut,
    ApontamentoHoraCreate, ApontamentoHoraOut,
    ChamadoCreate, ChamadoMensagemCreate, ChamadoUpdate, ChamadoOut,
    AtivoInfraCreate, AtivoInfraUpdate, AtivoInfraOut,
    NotificacaoOut, ReembolsoCreate, ReembolsoUpdate, ReembolsoOut,
    PedidoLojaCreate, PedidoLojaUpdate, PedidoLojaOut,
    ProdutoLojaCreate, ProdutoLojaUpdate, ProdutoLojaOut,
    OrganizacaoCreate, OrganizacaoUpdate, OrganizacaoOut,
    PlanoSaasCreate, PlanoSaasUpdate, PlanoSaasOut,
    SaasOnboardingCreate, BrandingUpdate,
)
from payroll_engine import (
    buscar_cbos,
    calcular_jornada_diaria,
    calcular_holerite_automatico,
)
from auth import (
    SECRET_KEY, ALGORITHM,
    gerar_hash_senha, verificar_senha, criar_token_acesso,
    get_usuario_atual, get_usuario_db, exigir_equipe, exigir_admin, exigir_master_admin,
)

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

RESERVED_SLUGS = {
    "www", "api", "app", "admin", "mail", "smtp", "ftp", "nexus",
    "portal", "static", "assets", "root", "suporte", "support", "blog"
}

DEFAULT_BRANDING_MASTER = {
    "nome_plataforma": "NEXUS CODE",
    "subtitulo_plataforma": "BRASIL",
    "logo_url": "",
    "favicon_url": "",
    "cor_primaria": "#0096B4",
    "cor_secundaria": "#0A1D37",
    "cor_sidebar": "#0A1D37",
    "tema_padrao": "light",
    "ocultar_powered_by": True,
}

DEFAULT_MODULOS_TENANT = {
    "dashboard": True,
    "projetos": True,
    "tarefas": True,
    "timesheet": True,
    "orcamentos": True,
    "propostas": True,
    "clientes": True,
    "chamados": True,
    "financeiro_dre": True,
    "faturas": True,
    "despesas": True,
    "contratos": True,
    "ponto": True,
    "holerite": True,
    "ativos": True,
    "usuarios": True,
    "empresa": True,
    "auditoria": True,
    "portal_cliente": True,
    "loja": False,
}

DEFAULT_PERMISSOES = {
    "admin": {
        "dashboard": True, "projetos": True, "tarefas": True, "timesheet": True,
        "orcamentos": True, "propostas": True, "clientes": True, "chamados": True,
        "financeiro_dre": True, "faturas": True, "despesas": True, "contratos": True,
        "ponto": True, "holerite": True, "ativos": True, "usuarios": True,
        "empresa": True, "auditoria": True, "loja": True, "reembolsos": True,
    },
    "colaborador": {
        "dashboard": True, "projetos": True, "tarefas": True, "timesheet": True,
        "orcamentos": True, "propostas": True, "clientes": True, "chamados": True,
        "financeiro_dre": False, "faturas": True, "despesas": False, "contratos": False,
        "ponto": True, "holerite": True, "ativos": True, "usuarios": False,
        "empresa": False, "auditoria": False, "loja": False, "reembolsos": True,
    },
}


def _slugify_tenant(texto: str) -> str:
    norm = unicodedata.normalize("NFKD", texto or "empresa").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", norm.lower()).strip("-")
    return slug[:50] or "empresa"


def _parse_json_dict(raw: Optional[str], fallback: dict) -> dict:
    if not raw:
        return dict(fallback)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            res = dict(fallback)
            res.update(parsed)
            return res
    except Exception:
        pass
    return dict(fallback)


def _get_org_or_404(db: Session, org_id: int) -> Organizacao:
    org = db.query(Organizacao).filter(Organizacao.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada.")
    if not org.is_master and org.status_assinatura == "suspenso":
        raise HTTPException(
            status_code=403,
            detail="A assinatura deste portal encontra-se suspensa. Entre em contato com o suporte.",
        )
    return org


def _verificar_modulo(org: Organizacao, modulo: str):
    if org.is_master:
        return
    mods = _parse_json_dict(org.modulos_json, DEFAULT_MODULOS_TENANT)
    if mods.get(modulo) is False:
        raise HTTPException(
            status_code=403,
            detail=f"O módulo '{modulo}' não está habilitado no plano atual desta empresa.",
        )


def _resolver_org_por_request(req: Request, db: Session) -> Organizacao:
    tenant_hint = (
        req.headers.get("X-Tenant-Slug")
        or req.query_params.get("tenant")
        or ""
    ).strip().lower()

    if tenant_hint:
        org = (
            db.query(Organizacao)
            .filter(
                or_(
                    func.lower(Organizacao.slug) == tenant_hint,
                    func.lower(Organizacao.dominio_customizado) == tenant_hint,
                )
            )
            .first()
        )
        if org:
            return org

    host_raw = (req.headers.get("X-Forwarded-Host") or req.headers.get("Host") or "").split(":")[0].strip().lower()
    if host_raw:
        org_dom = db.query(Organizacao).filter(func.lower(Organizacao.dominio_customizado) == host_raw).first()
        if org_dom:
            return org_dom

        parts = host_raw.split(".")
        if len(parts) >= 3 and parts[0] not in ("www", "app", "api", "nexuscodebrasil"):
            sub = parts[0]
            org_sub = db.query(Organizacao).filter(func.lower(Organizacao.slug) == sub).first()
            if org_sub:
                return org_sub
        elif len(parts) == 2 and parts[1] == "localhost" and parts[0] not in ("www", "app", "api"):
            org_sub = db.query(Organizacao).filter(func.lower(Organizacao.slug) == parts[0]).first()
            if org_sub:
                return org_sub

    master = db.query(Organizacao).filter(Organizacao.is_master == True).first()
    if master:
        return master
    first_org = db.query(Organizacao).order_by(Organizacao.id.asc()).first()
    if first_org:
        return first_org
    raise HTTPException(status_code=500, detail="Organização principal não inicializada.")


def enviar_email(destinatario: str, assunto: str, mensagem_html: str):
    if not SMTP_USER or not SMTP_PASS:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = assunto
        msg["From"] = f"Nexus Code Brasil <{SMTP_USER}>"
        msg["To"] = destinatario
        msg.set_content(mensagem_html, subtype="html")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=8) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[Erro SMTP] {str(e)}")
        return False


def registrar_log(db: Session, usuario_nome: str, acao: str, detalhes: str, org_id: int = 1):
    db.add(LogAuditoria(organizacao_id=org_id, usuario_nome=usuario_nome, acao=acao, detalhes=detalhes[:250]))


def criar_notificacao(
    db: Session,
    titulo: str,
    mensagem: str,
    link_pagina: str = "dashboard",
    usuario_id: Optional[int] = None,
    perfil_destino: Optional[str] = None,
    org_id: int = 1,
):
    db.add(
        Notificacao(
            organizacao_id=org_id,
            usuario_id=usuario_id,
            perfil_destino=perfil_destino,
            titulo=titulo[:160],
            mensagem=mensagem[:300],
            link_pagina=link_pagina[:50],
            lida=False,
        )
    )


def _obter_cliente_do_usuario(db: Session, usuario: Usuario) -> Optional[Cliente]:
    return (
        db.query(Cliente)
        .filter(
            Cliente.organizacao_id == usuario.organizacao_id,
            or_(Cliente.usuario_portal_id == usuario.id, Cliente.email == usuario.email),
        )
        .first()
    )


def _garantir_cliente_para_portal(db: Session, usuario: Usuario) -> Cliente:
    cliente = _obter_cliente_do_usuario(db, usuario)
    if cliente:
        if not cliente.usuario_portal_id:
            cliente.usuario_portal_id = usuario.id
        return cliente
    cliente = Cliente(
        organizacao_id=usuario.organizacao_id,
        usuario_portal_id=usuario.id,
        nome_empresa=usuario.nome,
        contato_nome=usuario.nome,
        email=usuario.email,
        telefone=usuario.telefone,
        status_funil="lead",
        origem="Portal do Cliente",
    )
    db.add(cliente)
    db.flush()
    return cliente


def _converter_proposta_em_projeto(db: Session, prop: PropostaComercial, autor_nome: str):
    if prop.projeto_gerado_id:
        return db.query(Projeto).filter(Projeto.id == prop.projeto_gerado_id).first()

    org_id = prop.organizacao_id
    admin_user = (
        db.query(Usuario)
        .filter(Usuario.organizacao_id == org_id, Usuario.perfil == "admin", Usuario.ativo == True)
        .first()
    )
    hoje = date.today()
    entrega = hoje + timedelta(days=int(prop.prazo_dias or 30))

    projeto = Projeto(
        organizacao_id=org_id,
        cliente_id=prop.cliente_id,
        responsavel_id=prop.criado_por_id or (admin_user.id if admin_user else None),
        titulo=prop.titulo,
        descricao=prop.escopo,
        status="planejamento",
        prioridade="alta",
        progresso=0,
        valor_total=prop.valor_total,
        horas_estimadas=Decimal(str(max(8, int(prop.prazo_dias or 30) * 2))),
        aprovacao_cliente_status="pendente",
        data_inicio=hoje,
        data_entrega=entrega,
    )
    db.add(projeto)
    db.flush()

    entregaveis = []
    if prop.entregaveis_json:
        try:
            parsed = json.loads(prop.entregaveis_json)
            if isinstance(parsed, list):
                entregaveis = parsed
        except Exception:
            pass

    if not entregaveis:
        entregaveis = [
            {"titulo": "Kickoff, Arquitetura e Planejamento Técnico", "prazo_dias": 5},
            {"titulo": "Desenvolvimento e Integração dos Módulos", "prazo_dias": max(10, int(prop.prazo_dias * 0.65))},
            {"titulo": "Homologação com Cliente e Implantação em Produção", "prazo_dias": int(prop.prazo_dias or 30)},
        ]

    for idx, item in enumerate(entregaveis):
        t_titulo = item.get("titulo") if isinstance(item, dict) else str(item)
        dias_off = int(item.get("prazo_dias", (idx + 1) * 7)) if isinstance(item, dict) else (idx + 1) * 7
        if t_titulo and t_titulo.strip():
            db.add(
                Tarefa(
                    organizacao_id=org_id,
                    projeto_id=projeto.id,
                    responsavel_id=projeto.responsavel_id,
                    titulo=t_titulo.strip()[:180],
                    descricao=f"Etapa originada da proposta {prop.codigo}.",
                    status="pendente",
                    prioridade="alta" if idx == 0 else "media",
                    data_inicio=hoje,
                    prazo=hoje + timedelta(days=dias_off),
                )
            )

    n_parcelas = max(1, int(prop.parcelas or 1))
    valor_total_num = float(prop.valor_total or 0)
    if valor_total_num > 0:
        valor_parcela = round(valor_total_num / n_parcelas, 2)
        for p_idx in range(n_parcelas):
            venc = hoje + timedelta(days=30 * p_idx + 5)
            val_atual = valor_parcela if p_idx < n_parcelas - 1 else round(valor_total_num - valor_parcela * (n_parcelas - 1), 2)
            db.add(
                Fatura(
                    organizacao_id=org_id,
                    projeto_id=projeto.id,
                    cliente_id=prop.cliente_id,
                    descricao=f"{prop.titulo} — Parcela {p_idx + 1}/{n_parcelas} ({prop.codigo})",
                    valor=Decimal(str(max(0, val_atual))),
                    status="pendente",
                    forma_pagamento="PIX",
                    vencimento=venc,
                )
            )

    cliente = db.query(Cliente).filter(Cliente.id == prop.cliente_id, Cliente.organizacao_id == org_id).first()
    if cliente and cliente.status_funil in ("lead", "proposta", "negociacao"):
        cliente.status_funil = "ativo"

    if prop.solicitacao_id:
        sol = db.query(SolicitacaoOrcamento).filter(SolicitacaoOrcamento.id == prop.solicitacao_id).first()
        if sol:
            sol.status = "convertido"

    prop.projeto_gerado_id = projeto.id
    registrar_log(
        db,
        autor_nome,
        "PROPOSTA_CONVERTIDA",
        f"Proposta {prop.codigo} convertida automaticamente no Projeto #{projeto.id} ({n_parcelas} fatura(s)).",
        org_id=org_id,
    )
    return projeto


_db_ready = False


def _run_full_schema_sync():
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if not existing_tables:
        return

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_cols = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing_cols:
                    col_type = column.type.compile(dialect=engine.dialect)
                    default_sql = ""
                    if column.default is not None and column.default.is_scalar:
                        val = column.default.arg
                        if isinstance(val, str):
                            escaped_val = val.replace("'", "''")
                            default_sql = f" DEFAULT '{escaped_val}'"
                        elif isinstance(val, bool):
                            default_sql = f" DEFAULT {'TRUE' if val else 'FALSE'}"
                        elif isinstance(val, (int, float)):
                            default_sql = f" DEFAULT {val}"
                    conn.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN IF NOT EXISTS "{column.name}" {col_type}{default_sql}')
                    )
        if "faturas" in existing_tables:
            conn.execute(text("ALTER TABLE faturas ALTER COLUMN projeto_id DROP NOT NULL"))


def ensure_db_initialized(force_sync: bool = False):
    global _db_ready
    if _db_ready and not force_sync:
        return

    if not force_sync:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM organizacoes LIMIT 1"))
                conn.execute(text("SELECT 1 FROM planos_saas LIMIT 1"))
                conn.execute(text("SELECT 1 FROM produtos_loja LIMIT 1"))
                conn.execute(text("SELECT organizacao_id FROM usuarios LIMIT 1"))
            _db_ready = True
            return
        except Exception:
            pass

    _run_full_schema_sync()

    db = SessionLocal()
    try:
        master_org = db.query(Organizacao).filter(Organizacao.is_master == True).first()
        if not master_org:
            first_org = db.query(Organizacao).filter(Organizacao.id == 1).first()
            if first_org:
                first_org.is_master = True
                master_org = first_org
            else:
                master_modulos = dict(DEFAULT_MODULOS_TENANT)
                master_modulos["loja"] = True
                master_modulos["saas_tenants"] = True
                master_org = Organizacao(
                    nome="Nexus Code Brasil",
                    slug="nexus",
                    is_master=True,
                    plano="enterprise",
                    status_assinatura="ativo",
                    valor_mensal=Decimal("0.00"),
                    limite_usuarios=999,
                    limite_clientes=9999,
                    modulos_json=json.dumps(master_modulos, ensure_ascii=False),
                    branding_json=json.dumps(DEFAULT_BRANDING_MASTER, ensure_ascii=False),
                )
                db.add(master_org)
            db.commit()
            db.refresh(master_org)

        if not db.query(PlanoSaas.id).first():
            starter_mods = {
                "dashboard": True, "projetos": True, "tarefas": True, "timesheet": False,
                "orcamentos": True, "propostas": True, "clientes": True, "chamados": True,
                "financeiro_dre": False, "faturas": True, "despesas": False, "contratos": False,
                "ponto": False, "holerite": False, "ativos": False, "usuarios": True,
                "empresa": True, "auditoria": False, "portal_cliente": True, "loja": False,
            }
            pro_mods = {
                "dashboard": True, "projetos": True, "tarefas": True, "timesheet": True,
                "orcamentos": True, "propostas": True, "clientes": True, "chamados": True,
                "financeiro_dre": True, "faturas": True, "despesas": True, "contratos": True,
                "ponto": False, "holerite": False, "ativos": True, "usuarios": True,
                "empresa": True, "auditoria": True, "portal_cliente": True, "loja": False,
            }
            ent_mods = dict(DEFAULT_MODULOS_TENANT)

            db.add_all([
                PlanoSaas(
                    codigo="starter",
                    nome="Starter CRM",
                    subtitulo="Ideal para pequenas equipes e agências iniciarem a operação comercial",
                    preco_mensal=Decimal("197.00"),
                    limite_usuarios=5,
                    limite_clientes=250,
                    destaque=False,
                    modulos_json=json.dumps(starter_mods, ensure_ascii=False),
                    recursos_json=json.dumps([
                        "Até 5 usuários internos",
                        "CRM, Leads e Funil Kanban",
                        "Propostas Comerciais & Faturas",
                        "Portal do Cliente White-Label",
                        "Subdomínio personalizado incluso",
                    ], ensure_ascii=False),
                    ativo=True,
                    ordem=1,
                ),
                PlanoSaas(
                    codigo="pro",
                    nome="Pro Gestão & Financeiro",
                    subtitulo="Operação completa com DRE gerencial, Timesheet, MRR e Service Desk",
                    preco_mensal=Decimal("397.00"),
                    limite_usuarios=15,
                    limite_clientes=1000,
                    destaque=True,
                    modulos_json=json.dumps(pro_mods, ensure_ascii=False),
                    recursos_json=json.dumps([
                        "Até 15 usuários internos",
                        "Tudo do plano Starter + Timesheet",
                        "DRE Gerencial & Fluxo de Caixa",
                        "Contas a Pagar & Contratos MRR",
                        "Central de Chamados & Ativos",
                        "Marca, Cores e Logo 100% próprios",
                    ], ensure_ascii=False),
                    ativo=True,
                    ordem=2,
                ),
                PlanoSaas(
                    codigo="enterprise",
                    nome="Enterprise Full ERP + RH",
                    subtitulo="Suite corporativa completa com Ponto Eletrônico e Folha Automática",
                    preco_mensal=Decimal("697.00"),
                    limite_usuarios=50,
                    limite_clientes=5000,
                    destaque=False,
                    modulos_json=json.dumps(ent_mods, ensure_ascii=False),
                    recursos_json=json.dumps([
                        "Até 50 usuários internos",
                        "Todos os módulos do plano Pro",
                        "Gestão de Ponto Eletrônico",
                        "Holerite & Folha Automática (INSS/IRRF)",
                        "Domínio próprio (CNAME) + Suporte VIP",
                    ], ensure_ascii=False),
                    ativo=True,
                    ordem=3,
                ),
            ])
            db.commit()

        if not db.query(ConfiguracaoEmpresa.id).filter(ConfiguracaoEmpresa.organizacao_id == master_org.id).first():
            db.add(
                ConfiguracaoEmpresa(
                    organizacao_id=master_org.id,
                    razao_social="Nexus Code Brasil Tecnologia Ltda",
                    nome_fantasia="Nexus Code Brasil",
                    cnpj="00.000.000/0001-00",
                    email_financeiro="contato@nexuscodebrasil.com.br",
                    telefone="(27) 99999-9999",
                    endereco="Aracruz - ES",
                    cidade="Aracruz",
                    estado="ES",
                    banco_nome="Banco Inter / Nubank PJ",
                    chave_pix="contato@nexuscodebrasil.com.br",
                    titular_pix="Nexus Code Brasil Tecnologia Ltda",
                    permissoes_json=json.dumps(DEFAULT_PERMISSOES, ensure_ascii=False),
                )
            )
            db.commit()

        if not db.query(ProdutoLoja.id).filter(ProdutoLoja.organizacao_id == master_org.id).first():
            db.add_all([
                ProdutoLoja(
                    organizacao_id=master_org.id,
                    slug="blusa",
                    nome="Blusa Nexus Code Brasil",
                    descricao="Blusa preta 100% algodão com estampa oficial Negativa Branca & Ciano Digital.",
                    preco=Decimal("39.90"),
                    badge="Novo",
                    spec_label="Tamanhos: P ao GG",
                    imagem_url="assets/brand/Estampa_Negativa_Branca.svg",
                    fundo_escuro=True,
                    tamanhos_json=json.dumps(["P", "M", "G", "GG"], ensure_ascii=False),
                    cores_json=json.dumps(["Preto", "Azul Enterprise"], ensure_ascii=False),
                    ordem=1,
                    ativo=True,
                ),
                ProdutoLoja(
                    organizacao_id=master_org.id,
                    slug="moletom",
                    nome="Moletom Nexus Code Brasil",
                    descricao="Moletom canguru com capuz, tecido premium e monograma circuito em contraste.",
                    preco=Decimal("139.90"),
                    badge="Destaque",
                    spec_label="Tamanhos: P ao GG",
                    imagem_url="assets/brand/Estampa_Negativa_Branca.svg",
                    fundo_escuro=True,
                    tamanhos_json=json.dumps(["P", "M", "G", "GG"], ensure_ascii=False),
                    cores_json=json.dumps(["Preto", "Azul Enterprise"], ensure_ascii=False),
                    ordem=2,
                    ativo=True,
                ),
                ProdutoLoja(
                    organizacao_id=master_org.id,
                    slug="garrafinha",
                    nome="Garrafinha Térmica 500ml",
                    descricao="Garrafa térmica inox com estampa padrão Azul Enterprise & Ciano Digital.",
                    preco=Decimal("29.90"),
                    badge="Eco",
                    spec_label="500ml Inox",
                    imagem_url="assets/brand/Estampa_Padrao.svg",
                    fundo_escuro=False,
                    tamanhos_json=json.dumps(["500ml"], ensure_ascii=False),
                    cores_json=json.dumps(["Branco", "Ciano Digital"], ensure_ascii=False),
                    ordem=3,
                    ativo=True,
                ),
                ProdutoLoja(
                    organizacao_id=master_org.id,
                    slug="mochila",
                    nome="Mochila Executiva Tech",
                    descricao='Mochila executiva para notebook até 15.6" com emblema oficial Nexus Code Brasil.',
                    preco=Decimal("159.90"),
                    badge="Enterprise",
                    spec_label='Até 15.6"',
                    imagem_url="assets/brand/Estampa_Padrao.svg",
                    fundo_escuro=False,
                    tamanhos_json=json.dumps(["Único"], ensure_ascii=False),
                    cores_json=json.dumps(["Azul Enterprise", "Preto"], ensure_ascii=False),
                    ordem=4,
                    ativo=True,
                ),
            ])
            db.commit()

        if not db.query(Usuario.id).first():
            admin = Usuario(
                organizacao_id=master_org.id,
                nome="Administrador Nexus",
                email="admin@nexuscode.com",
                senha_hash=gerar_hash_senha("Nexus@2026"),
                perfil="admin",
                ativo=True,
            )
            db.add(admin)
            db.flush()

            cliente_demo = Cliente(
                organizacao_id=master_org.id,
                nome_empresa="TechNova Soluções",
                contato_nome="Mariana Silva",
                email="contato@technova.com.br",
                telefone="(27) 99999-1234",
                status_funil="ativo",
                origem="Site Nexus Code",
            )
            db.add(cliente_demo)
            db.flush()

            projeto_demo = Projeto(
                organizacao_id=master_org.id,
                cliente_id=cliente_demo.id,
                responsavel_id=admin.id,
                titulo="Plataforma Web & Gestão Integrada",
                descricao="Desenvolvimento completo do portal institucional e painel administrativo.",
                status="em_andamento",
                prioridade="alta",
                progresso=65,
                valor_total=12500.00,
                horas_estimadas=80,
                data_inicio=date.today(),
            )
            db.add(projeto_demo)
            db.flush()

            db.add_all([
                Tarefa(organizacao_id=master_org.id, projeto_id=projeto_demo.id, responsavel_id=admin.id, titulo="Levantamento de requisitos e arquitetura da plataforma", status="concluida"),
                Tarefa(organizacao_id=master_org.id, projeto_id=projeto_demo.id, responsavel_id=admin.id, titulo="Homologação do portal corporativo com o cliente", status="fazendo"),
            ])
            registrar_log(db, "Sistema", "INIT", "Ambiente SaaS Multi-Tenant Nexus Code Enterprise inicializado.", org_id=master_org.id)
            db.commit()
        _db_ready = True
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_db_initialized()
    yield


app = FastAPI(
    title=os.getenv("APP_NAME", "Nexus Code Enterprise SaaS ERP & CRM"),
    version="2.3.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def init_db_middleware(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api") and path not in ("/", "/docs", "/openapi.json", "/redoc") and not path.startswith(("/app", "/assets", "/img", "/js", "/index.html", "/login.html")):
        request.scope["path"] = "/api" + (path if path.startswith("/") else "/" + path)
        path = request.scope["path"]

    if path.startswith("/api") and path != "/api/health":
        ensure_db_initialized(force_sync=(request.query_params.get("migrate") == "1"))
    elif path == "/api/health" and request.query_params.get("db") == "1":
        ensure_db_initialized(force_sync=True)
    return await call_next(request)


router = APIRouter(prefix="/api")


@router.get("/health", tags=["Status"])
def raiz():
    return {
        "status": "online",
        "sistema": "Nexus Code Enterprise SaaS ERP & CRM API",
        "versao": "2.3.0",
        "regiao": os.getenv("VERCEL_REGION", "local"),
    }


@router.post("/admin/sync-db", tags=["Status"])
def forcar_migracao_banco(_: Usuario = Depends(exigir_master_admin)):
    ensure_db_initialized(force_sync=True)
    return {"ok": True, "message": "Estrutura Multi-Tenant de tabelas e colunas sincronizada com sucesso."}


# ==================== WHITE-LABEL BRANDING & SAAS ONBOARDING PÚBLICO ====================
@router.get("/public/tenant-branding", tags=["SaaS White-Label"])
def obter_branding_tenant(req: Request, db: Session = Depends(get_db)):
    org = _resolver_org_por_request(req, db)
    cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org.id).first()
    branding = _parse_json_dict(org.branding_json, DEFAULT_BRANDING_MASTER)
    if not branding.get("nome_plataforma") or (not org.is_master and branding.get("nome_plataforma") == "NEXUS CODE"):
        branding["nome_plataforma"] = (cfg.nome_fantasia if cfg else org.nome) or org.nome
        if not org.is_master and branding.get("subtitulo_plataforma") == "BRASIL":
            branding["subtitulo_plataforma"] = "PORTAL EMPRESARIAL"

    modulos = dict(DEFAULT_MODULOS_TENANT)
    if org.is_master:
        modulos["loja"] = True
        modulos["saas_tenants"] = True
    else:
        modulos = _parse_json_dict(org.modulos_json, DEFAULT_MODULOS_TENANT)

    return {
        "organizacao_id": org.id,
        "nome": org.nome,
        "slug": org.slug,
        "dominio_customizado": org.dominio_customizado,
        "subdominio_url": f"https://{org.slug}.nexuscodebrasil.com.br",
        "is_master": bool(org.is_master),
        "status_assinatura": org.status_assinatura,
        "branding": branding,
        "modulos": modulos,
    }


@router.get("/public/saas/check-slug", tags=["SaaS White-Label"])
def verificar_disponibilidade_subdominio(slug: str, db: Session = Depends(get_db)):
    clean = _slugify_tenant(slug)
    if len(clean) < 3 or clean in RESERVED_SLUGS:
        return {"disponivel": False, "slug": clean, "motivo": "Subdomínio reservado ou muito curto (mínimo 3 letras)."}
    exists = db.query(Organizacao.id).filter(func.lower(Organizacao.slug) == clean).first()
    return {
        "disponivel": not bool(exists),
        "slug": clean,
        "url_prevista": f"https://{clean}.nexuscodebrasil.com.br",
        "motivo": "Subdomínio já está em uso por outra empresa." if exists else "Disponível para ativação imediata!",
    }


def _provisionar_nova_organizacao(
    db: Session,
    nome_empresa: str,
    raw_slug: str,
    plano_codigo: str,
    admin_nome: str,
    admin_email: str,
    admin_senha: str,
    status_assinatura: str = "trial",
    valor_mensal: Optional[Decimal] = None,
    limite_usuarios: Optional[int] = None,
    limite_clientes: Optional[int] = None,
    trial_ate: Optional[date] = None,
    vencimento_assinatura: Optional[date] = None,
    modulos_json: Optional[str] = None,
    branding_json: Optional[str] = None,
    dominio_customizado: Optional[str] = None,
    telefone: Optional[str] = None,
    cnpj: Optional[str] = None,
    observacoes: Optional[str] = None,
    gerar_contrato_master: bool = True,
    dia_vencimento: int = 10,
) -> tuple[Organizacao, Usuario]:
    clean_slug = _slugify_tenant(raw_slug)
    if len(clean_slug) < 3 or clean_slug in RESERVED_SLUGS:
        raise HTTPException(status_code=400, detail="Subdomínio inválido ou reservado. Escolha outro identificador (ex.: sua-empresa).")

    if db.query(Organizacao.id).filter(func.lower(Organizacao.slug) == clean_slug).first():
        raise HTTPException(status_code=400, detail=f"O subdomínio '{clean_slug}.nexuscodebrasil.com.br' já está em uso.")

    dom_clean = (dominio_customizado or "").strip().lower() or None
    if dom_clean:
        if db.query(Organizacao.id).filter(func.lower(Organizacao.dominio_customizado) == dom_clean).first():
            raise HTTPException(status_code=400, detail=f"O domínio '{dom_clean}' já está vinculado a outro portal.")

    if db.query(Usuario.id).filter(func.lower(Usuario.email) == admin_email.strip().lower()).first():
        raise HTTPException(status_code=400, detail="O e-mail do administrador já está cadastrado na plataforma.")

    plano_obj = db.query(PlanoSaas).filter(PlanoSaas.codigo == plano_codigo).first()
    if not plano_obj:
        plano_obj = db.query(PlanoSaas).filter(PlanoSaas.ativo == True).order_by(PlanoSaas.ordem.asc()).first()

    final_valor = valor_mensal if valor_mensal is not None else (plano_obj.preco_mensal if plano_obj else Decimal("297.00"))
    final_lim_users = limite_usuarios if limite_usuarios is not None else (plano_obj.limite_usuarios if plano_obj else 10)
    final_lim_clients = limite_clientes if limite_clientes is not None else (plano_obj.limite_clientes if plano_obj else 300)
    final_modulos = modulos_json or (plano_obj.modulos_json if plano_obj and plano_obj.modulos_json else json.dumps(DEFAULT_MODULOS_TENANT, ensure_ascii=False))

    default_brand = {
        "nome_plataforma": nome_empresa.strip()[:28].upper(),
        "subtitulo_plataforma": "GESTÃO EMPRESARIAL",
        "logo_url": "",
        "favicon_url": "",
        "cor_primaria": "#0096B4",
        "cor_secundaria": "#0A1D37",
        "cor_sidebar": "#0A1D37",
        "tema_padrao": "light",
        "ocultar_powered_by": False,
    }
    final_branding = branding_json or json.dumps(default_brand, ensure_ascii=False)

    hoje = date.today()
    if status_assinatura == "trial" and not trial_ate:
        trial_ate = hoje + timedelta(days=14)
    if not vencimento_assinatura:
        vencimento_assinatura = trial_ate or (hoje + timedelta(days=30))

    org = Organizacao(
        nome=nome_empresa.strip(),
        slug=clean_slug,
        dominio_customizado=dom_clean,
        is_master=False,
        plano=plano_obj.codigo if plano_obj else plano_codigo,
        status_assinatura=status_assinatura,
        valor_mensal=final_valor,
        limite_usuarios=final_lim_users,
        limite_clientes=final_lim_clients,
        trial_ate=trial_ate,
        vencimento_assinatura=vencimento_assinatura,
        modulos_json=final_modulos,
        branding_json=final_branding,
        observacoes=observacoes,
    )
    db.add(org)
    db.flush()

    db.add(
        ConfiguracaoEmpresa(
            organizacao_id=org.id,
            razao_social=nome_empresa.strip(),
            nome_fantasia=nome_empresa.strip(),
            cnpj=cnpj or None,
            email_financeiro=admin_email.strip().lower(),
            telefone=telefone or None,
            chave_pix=admin_email.strip().lower(),
            titular_pix=nome_empresa.strip(),
            permissoes_json=json.dumps(DEFAULT_PERMISSOES, ensure_ascii=False),
        )
    )

    admin_user = Usuario(
        organizacao_id=org.id,
        nome=admin_nome.strip(),
        email=admin_email.strip().lower(),
        senha_hash=gerar_hash_senha(admin_senha),
        perfil="admin",
        cargo="Administrador Geral",
        telefone=telefone or None,
        ativo=True,
    )
    db.add(admin_user)
    db.flush()

    master_org = db.query(Organizacao).filter(Organizacao.is_master == True).first()
    if master_org and gerar_contrato_master:
        cli_master = db.query(Cliente).filter(
            Cliente.organizacao_id == master_org.id,
            Cliente.email == admin_email.strip().lower(),
        ).first()
        if not cli_master:
            cli_master = Cliente(
                organizacao_id=master_org.id,
                nome_empresa=nome_empresa.strip(),
                contato_nome=admin_nome.strip(),
                email=admin_email.strip().lower(),
                telefone=telefone or None,
                documento=cnpj or None,
                status_funil="ativo" if status_assinatura == "ativo" else "negociacao",
                origem=f"Portal SaaS ({clean_slug}.nexuscodebrasil.com.br)",
                observacoes=f"Assinante Portal Nexus SaaS — Plano {org.plano.upper()} ({status_assinatura}).",
            )
            db.add(cli_master)
            db.flush()
        org.cliente_master_id = cli_master.id

        if float(final_valor or 0) > 0:
            ct_master = ContratoRecorrente(
                organizacao_id=master_org.id,
                cliente_id=cli_master.id,
                titulo=f"Licença Portal Nexus SaaS — {org.nome} ({org.plano.upper()})",
                valor_mensal=final_valor,
                dia_vencimento=dia_vencimento,
                data_inicio=trial_ate if status_assinatura == "trial" and trial_ate else hoje,
                status="ativo" if status_assinatura == "ativo" else "pausado",
                descricao=f"Subdomínio: {clean_slug}.nexuscodebrasil.com.br | Limite: {final_lim_users} usuários.",
            )
            db.add(ct_master)
            db.flush()
            org.contrato_master_id = ct_master.id

            if status_assinatura == "ativo":
                db.add(
                    Fatura(
                        organizacao_id=master_org.id,
                        cliente_id=cli_master.id,
                        descricao=f"Assinatura Portal Nexus SaaS ({org.plano.upper()}) — {org.nome}",
                        valor=final_valor,
                        status="pendente",
                        forma_pagamento="PIX",
                        vencimento=vencimento_assinatura or (hoje + timedelta(days=5)),
                    )
                )

        criar_notificacao(
            db,
            titulo=f"Novo Portal SaaS Ativado: {org.nome}",
            mensagem=f"Subdomínio {clean_slug}.nexuscodebrasil.com.br ({status_assinatura.upper()}) criado.",
            link_pagina="saas_tenants",
            perfil_destino="admin",
            org_id=master_org.id,
        )

    registrar_log(db, admin_nome.strip(), "CRIAR_PORTAL_SAAS", f"Portal '{org.nome}' ({clean_slug}) provisionado.", org_id=org.id)
    return org, admin_user


@router.post("/public/saas/onboarding", response_model=TokenResponse, status_code=201, tags=["SaaS White-Label"])
def onboarding_automatizado_saas(
    dados: SaasOnboardingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    brand_init = {
        "nome_plataforma": dados.nome_empresa.strip()[:28].upper(),
        "subtitulo_plataforma": "GESTÃO EMPRESARIAL",
        "logo_url": "",
        "favicon_url": "",
        "cor_primaria": dados.cor_primaria or "#0096B4",
        "cor_secundaria": dados.cor_sidebar or "#0A1D37",
        "cor_sidebar": dados.cor_sidebar or "#0A1D37",
        "tema_padrao": "light",
        "ocultar_powered_by": False,
    }
    org, admin_user = _provisionar_nova_organizacao(
        db=db,
        nome_empresa=dados.nome_empresa,
        raw_slug=dados.slug,
        plano_codigo=dados.plano,
        admin_nome=dados.admin_nome,
        admin_email=dados.admin_email,
        admin_senha=dados.admin_senha,
        status_assinatura="trial",
        branding_json=json.dumps(brand_init, ensure_ascii=False),
        telefone=dados.telefone,
        cnpj=dados.cnpj,
        gerar_contrato_master=True,
    )
    db.commit()
    db.refresh(admin_user)

    background_tasks.add_task(
        enviar_email,
        admin_user.email,
        f"Seu Portal Empresarial {org.nome} está pronto!",
        f"<p>Olá, <b>{admin_user.nome}</b>! Seu ambiente exclusivo foi ativado em <b>https://{org.slug}.nexuscodebrasil.com.br</b> com 14 dias de teste gratuito.</p>",
    )

    token = criar_token_acesso({
        "sub": str(admin_user.id),
        "org_id": org.id,
        "is_master": False,
        "perfil": admin_user.perfil,
        "nome": admin_user.nome,
        "email": admin_user.email,
    })
    return {"access_token": token, "token_type": "bearer", "usuario": admin_user}


# ==================== PAINEL MASTER SAAS (GESTÃO DE PORTAIS COMPRADORES & PLANOS) ====================
@router.get("/saas/dashboard", tags=["SaaS Master"])
def obter_painel_master_saas(
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_master_admin),
):
    orgs = db.query(Organizacao).order_by(Organizacao.is_master.desc(), Organizacao.criado_em.desc()).all()
    planos = db.query(PlanoSaas).order_by(PlanoSaas.ordem.asc(), PlanoSaas.id.asc()).all()

    user_counts = dict(db.query(Usuario.organizacao_id, func.count(Usuario.id)).group_by(Usuario.organizacao_id).all())
    client_counts = dict(db.query(Cliente.organizacao_id, func.count(Cliente.id)).group_by(Cliente.organizacao_id).all())

    orgs_out = []
    for o in orgs:
        item = OrganizacaoOut.model_validate(o).model_dump()
        item["usuarios_count"] = int(user_counts.get(o.id, 0))
        item["clientes_count"] = int(client_counts.get(o.id, 0))
        orgs_out.append(item)

    tenants_only = [o for o in orgs if not o.is_master]
    ativos_count = sum(1 for o in tenants_only if o.status_assinatura == "ativo")
    trial_count = sum(1 for o in tenants_only if o.status_assinatura == "trial")
    inad_count = sum(1 for o in tenants_only if o.status_assinatura in ("inadimplente", "suspenso"))
    mrr_saas = sum(float(o.valor_mensal or 0) for o in tenants_only if o.status_assinatura == "ativo")

    return {
        "kpi": {
            "total_portais": len(tenants_only),
            "portais_ativos": ativos_count,
            "portais_trial": trial_count,
            "portais_inadimplentes": inad_count,
            "mrr_saas": round(mrr_saas, 2),
        },
        "organizacoes": orgs_out,
        "planos": [PlanoSaasOut.model_validate(p).model_dump() for p in planos],
    }


@router.post("/saas/organizacoes", response_model=OrganizacaoOut, status_code=201, tags=["SaaS Master"])
def criar_portal_comprador_assistido(
    dados: OrganizacaoCreate,
    db: Session = Depends(get_db),
    master_admin: Usuario = Depends(exigir_master_admin),
):
    org, _ = _provisionar_nova_organizacao(
        db=db,
        nome_empresa=dados.nome,
        raw_slug=dados.slug,
        plano_codigo=dados.plano,
        admin_nome=dados.admin_nome,
        admin_email=dados.admin_email,
        admin_senha=dados.admin_senha,
        status_assinatura=dados.status_assinatura,
        valor_mensal=dados.valor_mensal,
        limite_usuarios=dados.limite_usuarios,
        limite_clientes=dados.limite_clientes,
        trial_ate=dados.trial_ate,
        vencimento_assinatura=dados.vencimento_assinatura,
        modulos_json=dados.modulos_json,
        branding_json=dados.branding_json,
        dominio_customizado=dados.dominio_customizado,
        telefone=dados.telefone,
        cnpj=dados.cnpj,
        observacoes=dados.observacoes,
        gerar_contrato_master=dados.gerar_contrato_master,
        dia_vencimento=dados.dia_vencimento,
    )
    registrar_log(db, master_admin.nome, "VENDA_ASSISTIDA_SAAS", f"Criou portal '{org.nome}' ({org.slug}.nexuscodebrasil.com.br)", org_id=master_admin.organizacao_id)
    db.commit()
    db.refresh(org)
    out = OrganizacaoOut.model_validate(org)
    out.usuarios_count = 1
    out.clientes_count = 0
    return out


@router.patch("/saas/organizacoes/{org_id}", response_model=OrganizacaoOut, tags=["SaaS Master"])
def atualizar_portal_comprador(
    org_id: int,
    dados: OrganizacaoUpdate,
    db: Session = Depends(get_db),
    master_admin: Usuario = Depends(exigir_master_admin),
):
    org = db.query(Organizacao).filter(Organizacao.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Portal não encontrado.")

    payload = dados.model_dump(exclude_unset=True)
    if "slug" in payload and payload["slug"]:
        new_slug = _slugify_tenant(payload["slug"])
        if new_slug != org.slug:
            if new_slug in RESERVED_SLUGS or db.query(Organizacao.id).filter(func.lower(Organizacao.slug) == new_slug, Organizacao.id != org.id).first():
                raise HTTPException(status_code=400, detail="Este subdomínio já está em uso ou é reservado.")
            payload["slug"] = new_slug

    if "dominio_customizado" in payload:
        dom = (payload["dominio_customizado"] or "").strip().lower() or None
        if dom and db.query(Organizacao.id).filter(func.lower(Organizacao.dominio_customizado) == dom, Organizacao.id != org.id).first():
            raise HTTPException(status_code=400, detail="Este domínio customizado já está vinculado a outro portal.")
        payload["dominio_customizado"] = dom

    for campo, valor in payload.items():
        setattr(org, campo, valor)

    if org.contrato_master_id:
        ct = db.query(ContratoRecorrente).filter(ContratoRecorrente.id == org.contrato_master_id).first()
        if ct:
            if "valor_mensal" in payload and payload["valor_mensal"] is not None:
                ct.valor_mensal = payload["valor_mensal"]
            if "status_assinatura" in payload:
                ct.status = "ativo" if payload["status_assinatura"] == "ativo" else ("encerrado" if payload["status_assinatura"] == "suspenso" else "pausado")

    registrar_log(db, master_admin.nome, "ATUALIZAR_PORTAL_SAAS", f"Atualizou portal #{org.id} ({org.nome})", org_id=master_admin.organizacao_id)
    db.commit()
    db.refresh(org)
    out = OrganizacaoOut.model_validate(org)
    out.usuarios_count = db.query(func.count(Usuario.id)).filter(Usuario.organizacao_id == org.id).scalar() or 0
    out.clientes_count = db.query(func.count(Cliente.id)).filter(Cliente.organizacao_id == org.id).scalar() or 0
    return out


@router.delete("/saas/organizacoes/{org_id}", status_code=204, tags=["SaaS Master"])
def remover_portal_comprador(
    org_id: int,
    db: Session = Depends(get_db),
    master_admin: Usuario = Depends(exigir_master_admin),
):
    org = db.query(Organizacao).filter(Organizacao.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Portal não encontrado.")
    if org.is_master:
        raise HTTPException(status_code=400, detail="A organização Master principal não pode ser excluída.")
    registrar_log(db, master_admin.nome, "EXCLUIR_PORTAL_SAAS", f"Removeu portal '{org.nome}' ({org.slug})", org_id=master_admin.organizacao_id)
    db.delete(org)
    db.commit()


@router.post("/saas/organizacoes/{org_id}/impersonate", tags=["SaaS Master"])
def acessar_portal_comprador_como_admin(
    org_id: int,
    db: Session = Depends(get_db),
    master_admin: Usuario = Depends(exigir_master_admin),
):
    org = db.query(Organizacao).filter(Organizacao.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Portal não encontrado.")
    target_admin = (
        db.query(Usuario)
        .filter(Usuario.organizacao_id == org.id, Usuario.perfil == "admin", Usuario.ativo == True)
        .order_by(Usuario.id.asc())
        .first()
    )
    if not target_admin:
        raise HTTPException(status_code=404, detail="Nenhum administrador ativo encontrado neste portal.")

    token = criar_token_acesso(
        {
            "sub": str(target_admin.id),
            "org_id": org.id,
            "is_master": bool(org.is_master),
            "perfil": "admin",
            "nome": target_admin.nome,
            "email": target_admin.email,
        },
        expires_minutes=120,
    )
    registrar_log(db, master_admin.nome, "IMPERSONATE_SAAS", f"Acessou portal '{org.nome}' ({org.slug}) como administrador.", org_id=master_admin.organizacao_id)
    db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant_slug": org.slug,
        "usuario": UsuarioListOut.model_validate(target_admin),
    }


@router.post("/saas/planos", response_model=PlanoSaasOut, status_code=201, tags=["SaaS Master"])
def criar_plano_saas(
    dados: PlanoSaasCreate,
    db: Session = Depends(get_db),
    master_admin: Usuario = Depends(exigir_master_admin),
):
    cod = _slugify_tenant(dados.codigo)
    if db.query(PlanoSaas.id).filter(PlanoSaas.codigo == cod).first():
        raise HTTPException(status_code=400, detail="Já existe um plano com este código.")
    payload = dados.model_dump()
    payload["codigo"] = cod
    pl = PlanoSaas(**payload)
    db.add(pl)
    registrar_log(db, master_admin.nome, "CRIAR_PLANO_SAAS", f"Criou plano SaaS '{pl.nome}'", org_id=master_admin.organizacao_id)
    db.commit()
    db.refresh(pl)
    return pl


@router.patch("/saas/planos/{plano_id}", response_model=PlanoSaasOut, tags=["SaaS Master"])
def atualizar_plano_saas(
    plano_id: int,
    dados: PlanoSaasUpdate,
    db: Session = Depends(get_db),
    master_admin: Usuario = Depends(exigir_master_admin),
):
    pl = db.query(PlanoSaas).filter(PlanoSaas.id == plano_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Plano SaaS não encontrado.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(pl, campo, valor)
    registrar_log(db, master_admin.nome, "EDITAR_PLANO_SAAS", f"Atualizou plano SaaS '{pl.nome}'", org_id=master_admin.organizacao_id)
    db.commit()
    db.refresh(pl)
    return pl


@router.delete("/saas/planos/{plano_id}", status_code=204, tags=["SaaS Master"])
def remover_plano_saas(
    plano_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_master_admin),
):
    pl = db.query(PlanoSaas).filter(PlanoSaas.id == plano_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Plano SaaS não encontrado.")
    db.delete(pl)
    db.commit()


# ==================== AUTENTICAÇÃO ====================
@router.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = (
        db.query(Usuario)
        .options(defer(Usuario.foto_url), defer(Usuario.resumo_profissional))
        .filter(func.lower(Usuario.email) == dados.email.strip().lower())
        .first()
    )
    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas. Verifique o e-mail e a senha informados.")
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Conta desativada. Entre em contato com o administrador.")

    org = db.query(Organizacao).filter(Organizacao.id == usuario.organizacao_id).first()
    if org and not org.is_master and org.status_assinatura == "suspenso":
        raise HTTPException(status_code=403, detail="A assinatura do portal desta empresa encontra-se suspensa. Entre em contato com o suporte.")

    token = criar_token_acesso({
        "sub": str(usuario.id),
        "org_id": usuario.organizacao_id,
        "is_master": bool(org.is_master if org else False),
        "perfil": usuario.perfil,
        "nome": usuario.nome,
        "email": usuario.email,
    })
    return {"access_token": token, "token_type": "bearer", "usuario": usuario}


@router.post("/auth/register", response_model=TokenResponse, status_code=201, tags=["Auth"])
def registrar_conta(dados: RegisterRequest, req: Request, db: Session = Depends(get_db)):
    if db.query(Usuario.id).filter(func.lower(Usuario.email) == dados.email.strip().lower()).first():
        raise HTTPException(status_code=400, detail="Este endereço de e-mail já está vinculado a uma conta.")

    org = _resolver_org_por_request(req, db)
    if not org.is_master and org.status_assinatura == "suspenso":
        raise HTTPException(status_code=403, detail="Este portal está temporariamente suspenso.")

    novo = Usuario(
        organizacao_id=org.id,
        nome=dados.nome,
        email=dados.email.strip().lower(),
        senha_hash=gerar_hash_senha(dados.senha),
        perfil="cliente",
        ativo=True,
    )
    db.add(novo)
    db.flush()

    cliente_existente = db.query(Cliente).filter(
        Cliente.organizacao_id == org.id,
        Cliente.email == novo.email,
    ).first()
    if cliente_existente:
        if not cliente_existente.usuario_portal_id:
            cliente_existente.usuario_portal_id = novo.id
    else:
        db.add(
            Cliente(
                organizacao_id=org.id,
                usuario_portal_id=novo.id,
                nome_empresa=novo.nome,
                contato_nome=novo.nome,
                email=novo.email,
                status_funil="lead",
                origem="Cadastro Portal do Cliente",
            )
        )

    registrar_log(db, novo.nome, "CADASTRO", f"Nova conta de cliente criada: {novo.email}", org_id=org.id)
    db.commit()
    db.refresh(novo)

    token = criar_token_acesso({
        "sub": str(novo.id),
        "org_id": org.id,
        "is_master": bool(org.is_master),
        "perfil": novo.perfil,
        "nome": novo.nome,
        "email": novo.email,
    })
    return {"access_token": token, "token_type": "bearer", "usuario": novo}


@router.post("/auth/forgot-password", tags=["Auth"])
def recuperar_senha(dados: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(func.lower(Usuario.email) == dados.email.strip().lower()).first()
    if usuario and usuario.ativo:
        org = db.query(Organizacao).filter(Organizacao.id == usuario.organizacao_id).first()
        base_host = "www.nexuscodebrasil.com.br" if (not org or org.is_master) else f"{org.slug}.nexuscodebrasil.com.br"
        reset_token = jwt.encode(
            {"sub": str(usuario.id), "exp": datetime.utcnow() + timedelta(minutes=20), "type": "reset"},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        link = f"https://{base_host}/login.html?reset_token={reset_token}"
        corpo_email = f"""
        <div style="font-family: Arial, sans-serif; color: #0A1D37;">
            <h2 style="color: #00B4D8;">Recuperação de Senha</h2>
            <p>Olá, {usuario.nome}.</p>
            <p>Recebemos uma solicitação para redefinir sua senha na plataforma {org.nome if org else 'Nexus Code Brasil'}.</p>
            <p><a href="{link}" style="background-color: #00B4D8; color: #0A1D37; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold;">Redefinir Minha Senha</a></p>
            <p style="font-size:12px; color:#64748b;">O link expira em 20 minutos. Caso não tenha solicitado, ignore este e-mail.</p>
        </div>
        """
        background_tasks.add_task(enviar_email, usuario.email, f"Redefinição de Senha - {org.nome if org else 'Nexus Code'}", corpo_email)
        registrar_log(db, usuario.nome, "RECUPERAR_SENHA", f"Token de recuperação gerado para {usuario.email}", org_id=usuario.organizacao_id)
        db.commit()

    return {
        "message": "Caso o e-mail informado esteja cadastrado, enviaremos as instruções para redefinição de senha."
    }


@router.post("/auth/reset-password", tags=["Auth"])
def redefinir_senha_com_token(dados: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(dados.token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "reset":
            raise HTTPException(status_code=400, detail="Token inválido.")
        uid = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Link de recuperação inválido ou expirado.")

    usuario = db.query(Usuario).filter(Usuario.id == uid).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    usuario.senha_hash = gerar_hash_senha(dados.nova_senha)
    registrar_log(db, usuario.nome, "REDEFINIR_SENHA", "Senha redefinida via link seguro.", org_id=usuario.organizacao_id)
    db.commit()
    return {"message": "Senha redefinida com sucesso! Você já pode entrar com sua nova senha."}


@router.patch("/auth/me", response_model=UsuarioOut, tags=["Auth"])
def atualizar_meu_perfil(dados: UsuarioUpdate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_db)):
    payload = dados.model_dump(exclude_unset=True)
    payload.pop("perfil", None)
    payload.pop("ativo", None)

    if "senha" in payload:
        nova_senha = payload.pop("senha")
        if nova_senha:
            usuario.senha_hash = gerar_hash_senha(nova_senha)

    if "email" in payload and payload["email"] and payload["email"] != usuario.email:
        if db.query(Usuario.id).filter(Usuario.email == payload["email"], Usuario.id != usuario.id).first():
            raise HTTPException(status_code=400, detail="Este e-mail já está em uso por outra conta.")

    for campo, valor in payload.items():
        setattr(usuario, campo, valor)

    usuario.termos_aceitos_em = datetime.utcnow()

    registrar_log(db, usuario.nome, "EDITAR_PERFIL", "Atualizou dados cadastrais, currículo e consentimento LGPD.", org_id=usuario.organizacao_id)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("/auth/me", response_model=UsuarioOut, tags=["Auth"])
def perfil_logado(usuario: Usuario = Depends(get_usuario_db)):
    return usuario
