import os
from contextlib import asynccontextmanager
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
import calendar
import hashlib
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
    PedidoDominio,
)
from schemas import (
    LoginRequest, RegisterRequest, ForgotPasswordRequest, ResetPasswordRequest, TokenResponse,
    UsuarioCreate, UsuarioUpdate, UsuarioOut, UsuarioListOut,
    ClienteCreate, ClienteUpdate, ClienteOut,
    SolicitacaoPublicCreate, SolicitacaoPortalCreate, SolicitacaoResponder, SolicitacaoUpdate, SolicitacaoOut,
    GerarOrcamentoAutoRequest,
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




DEFAULT_CATALOGO_SERVICOS = [
    {
        "codigo": "web-institucional",
        "categoria": "Desenvolvimento Web",
        "nome": "Site Institucional & Landing Page High-Conversion",
        "descricao": "Site corporativo moderno, ultra-rápido, responsivo e integrado ao CRM e WhatsApp.",
        "valor_base": 1800.00,
        "prazo_dias": 10,
        "parcelas_padrao": 2,
        "ativo": True,
        "entregaveis": [
            "Design UI/UX Responsivo (Desktop & Mobile)",
            "Otimização SEO Técnico e Alta Performance",
            "Formulário Comercial Integrado ao CRM Nexus",
            "Configuração de Domínio, Certificado SSL e Deploy"
        ]
    },
    {
        "codigo": "sistema-web",
        "categoria": "Sistemas & Portais",
        "nome": "Sistema Web Personalizado / Portal Corporativo",
        "descricao": "Aplicação Full Stack sob medida com painel administrativo, autenticação JWT e banco de dados.",
        "valor_base": 4500.00,
        "prazo_dias": 25,
        "parcelas_padrao": 3,
        "ativo": True,
        "entregaveis": [
            "Arquitetura Full Stack & Modelagem de Banco de Dados",
            "Painel Administrativo, Dashboards e Controle de Perfis",
            "Desenvolvimento de APIs REST e Regras de Negócio",
            "Homologação Assistida e Implantação em Produção"
        ]
    },
    {
        "codigo": "modpack-server",
        "categoria": "Servidores & Modpacks",
        "nome": "Servidor & Modpack Customizado (Gaming Enterprise)",
        "descricao": "Desenvolvimento, otimização de TPS/performance, balanceamento de mods/scripts e integração web.",
        "valor_base": 1500.00,
        "prazo_dias": 12,
        "parcelas_padrao": 2,
        "ativo": True,
        "entregaveis": [
            "Curadoria, Configuração e Balanceamento do Modpack",
            "Otimização de Servidor Dedicado, Memória e TPS",
            "Scripts Customizados, Permissões e Segurança Anti-Exploit",
            "Testes de Estresse, Documentação e Entrega em Produção"
        ]
    },
    {
        "codigo": "ecommerce",
        "categoria": "E-commerce & Pagamentos",
        "nome": "Loja Virtual / E-commerce Completo com Checkout PIX",
        "descricao": "Plataforma de vendas online com catálogo, carrinho, frete e gateway Mercado Pago integrado.",
        "valor_base": 3800.00,
        "prazo_dias": 20,
        "parcelas_padrao": 3,
        "ativo": True,
        "entregaveis": [
            "Vitrine de Produtos, Variações e Carrinho Inteligente",
            "Checkout PIX Instantâneo & Cartão (Mercado Pago)",
            "Gestão de Pedidos, Faturas e Notificações por E-mail",
            "Publicação com Certificado SSL e Treinamento"
        ]
    },
    {
        "codigo": "app-mobile",
        "categoria": "Aplicativos Mobile",
        "nome": "Aplicativo Mobile (Android & iOS)",
        "descricao": "Aplicativo multiplataforma conectado em tempo real à API da sua empresa com notificações push.",
        "valor_base": 6500.00,
        "prazo_dias": 35,
        "parcelas_padrao": 4,
        "ativo": True,
        "entregaveis": [
            "Protótipo Navegável UI/UX e Fluxo de Telas",
            "Desenvolvimento Multiplataforma Android e iOS",
            "Integração com Backend REST API e Push Notifications",
            "Empacotamento e Suporte à Publicação nas Lojas"
        ]
    },
    {
        "codigo": "automacao-api",
        "categoria": "Automação & APIs",
        "nome": "Integração de APIs, Webhooks & Automação",
        "descricao": "Conectores automáticos entre ERPs, gateways financeiros, GitHub, WhatsApp e fluxos internos.",
        "valor_base": 2200.00,
        "prazo_dias": 12,
        "parcelas_padrao": 2,
        "ativo": True,
        "entregaveis": [
            "Mapeamento de Endpoints, Webhooks e Regras",
            "Desenvolvimento de Microsserviço / Worker Automatizado",
            "Logs de Auditoria, Retentativas e Tratamento de Erros",
            "Documentação Técnica e Implantação"
        ]
    },
    {
        "codigo": "cloud-devops",
        "categoria": "Infraestrutura & Cloud",
        "nome": "Infraestrutura Cloud, Domínio, CI/CD & Segurança",
        "descricao": "Configuração completa de domínio, DNS, SSL, esteira GitHub + Vercel e hardening de segurança.",
        "valor_base": 1200.00,
        "prazo_dias": 7,
        "parcelas_padrao": 1,
        "ativo": True,
        "entregaveis": [
            "Configuração de Domínio Corporativo, DNS e SSL/HTTPS",
            "Pipeline Automatizado de Deploy (GitHub + Cloud)",
            "Auditoria de Segurança OWASP e Backup Automatizado",
            "Entrega de Credenciais e Relatório de Arquitetura"
        ]
    },
    {
        "codigo": "portal-saas",
        "categoria": "SaaS Enterprise",
        "nome": "Implantação Portal Nexus Enterprise White-Label",
        "descricao": "Ambiente ERP & CRM completo com marca própria, subdomínio, RH, Ponto e Financeiro.",
        "valor_base": 2900.00,
        "prazo_dias": 10,
        "parcelas_padrao": 2,
        "ativo": True,
        "entregaveis": [
            "Provisionamento de Ambiente Multi-Tenant Isolado",
            "Identidade Visual White-Label e Domínio Customizado",
            "Configuração de Gateway Financeiro e Permissões",
            "Onboarding Executivo e Treinamento da Equipe"
        ]
    }
]


def _get_catalogo_servicos_empresa(cfg: Optional[ConfiguracaoEmpresa]) -> list:
    if cfg and cfg.catalogo_servicos_json:
        try:
            parsed = json.loads(cfg.catalogo_servicos_json)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
        except Exception:
            pass
    return [dict(item) for item in DEFAULT_CATALOGO_SERVICOS]


def _get_parametros_orcamento_empresa(cfg: Optional[ConfiguracaoEmpresa]) -> dict:
    return {
        "imposto_servico_percent": float(cfg.imposto_servico_percent) if (cfg and cfg.imposto_servico_percent is not None) else 6.00,
        "multa_atraso_percent": float(cfg.multa_atraso_percent) if (cfg and cfg.multa_atraso_percent is not None) else 2.00,
        "juros_mensal_percent": float(cfg.juros_mensal_percent) if (cfg and cfg.juros_mensal_percent is not None) else 1.00,
        "multa_rescisao_percent": float(cfg.multa_rescisao_percent) if (cfg and cfg.multa_rescisao_percent is not None) else 10.00,
        "urgencia_multiplicadores": {
            "normal": 0.0,
            "alta": 15.0,
            "urgente": 30.0,
        },
    }

def _slugify_tenant(texto: str) -> str:
    norm = unicodedata.normalize("NFKD", texto or "empresa").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", norm.lower()).strip("-")
    return slug[:50] or "empresa"


def _validar_dominio_customizado(raw_dom: Optional[str], plano_codigo: str, is_master: bool = False) -> Optional[str]:
    if not raw_dom:
        return None
    dom = raw_dom.strip().lower()
    dom = re.sub(r"^https?://", "", dom).split("/")[0].split(":")[0].strip().rstrip(".")
    if not dom:
        return None

    if not is_master and (plano_codigo or "").strip().lower() != "enterprise":
        raise HTTPException(
            status_code=403,
            detail="O apontamento de domínio próprio (CNAME) é um recurso exclusivo do plano Enterprise Full. Os planos Starter e Pro operam em subdomínio gerenciado (.nexuscodebrasil.com.br).",
        )

    if dom.endswith(".nexuscodebrasil.com.br") or dom in ("nexuscodebrasil.com.br", "www.nexuscodebrasil.com.br", "localhost", "127.0.0.1") or dom.endswith(".vercel.app"):
        raise HTTPException(
            status_code=400,
            detail="Informe um domínio externo próprio da sua empresa (ex.: sistema.suaempresa.com.br).",
        )

    if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", dom):
        raise HTTPException(
            status_code=400,
            detail="Formato de domínio inválido. Utilize um endereço válido (ex.: portal.suaempresa.com.br).",
        )

    return dom


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
                    (
                        (func.lower(Organizacao.dominio_customizado) == tenant_hint)
                        & ((Organizacao.is_master == True) | (func.lower(Organizacao.plano) == "enterprise"))
                    ),
                )
            )
            .first()
        )
        if org:
            return org

    host_raw = (req.headers.get("X-Forwarded-Host") or req.headers.get("Host") or "").split(":")[0].strip().lower()
    if host_raw:
        org_dom = (
            db.query(Organizacao)
            .filter(
                func.lower(Organizacao.dominio_customizado) == host_raw,
                (Organizacao.is_master == True) | (func.lower(Organizacao.plano) == "enterprise"),
            )
            .first()
        )
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

def _format_brl(valor) -> str:
    try:
        num = float(valor or 0)
    except Exception:
        num = 0.0
    s = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _format_dt_br(dt: Optional[datetime]) -> str:
    if not dt:
        dt = datetime.utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    br = dt.astimezone(timezone(timedelta(hours=-3)))
    return br.strftime("%d/%m/%Y às %H:%M")


def _gerar_dados_recibo_fatura(db: Session, fat: Fatura) -> dict:
    org = db.query(Organizacao).filter(Organizacao.id == fat.organizacao_id).first()
    cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == fat.organizacao_id).first()
    cli = db.query(Cliente).filter(Cliente.id == fat.cliente_id).first()
    proj = db.query(Projeto).filter(Projeto.id == fat.projeto_id).first() if fat.projeto_id else None

    branding = _parse_json_dict(org.branding_json if org else None, DEFAULT_BRANDING_MASTER)
    brand_name = (branding.get("nome_plataforma") or (cfg.nome_fantasia if cfg else None) or (org.nome if org else "NEXUS CODE")).strip()
    brand_sub = (branding.get("subtitulo_plataforma") or ("BRASIL" if (not org or org.is_master) else "GESTÃO EMPRESARIAL")).strip()
    cor_primaria = branding.get("cor_primaria") or "#00B4D8"
    cor_sidebar = branding.get("cor_sidebar") or "#0A1D37"

    pago_dt = fat.pago_em or datetime.utcnow()
    ano_ref = pago_dt.year if hasattr(pago_dt, "year") else date.today().year
    numero_comprovante = f"REC-{ano_ref}-{int(fat.id):05d}"

    seed = f"NEXUS-REC|{fat.id}|{fat.organizacao_id}|{float(fat.valor or 0):.2f}|{pago_dt.isoformat()}|{fat.mp_order_id or ''}|{fat.mp_payment_id or ''}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
    codigo_autenticacao = f"NC-{digest[:4]}-{digest[4:8]}-{digest[8:12]}"

    portal_url = "https://www.nexuscodebrasil.com.br/app/portal.html"
    if org and not org.is_master:
        if org.dominio_customizado and (org.plano or "").lower() == "enterprise":
            portal_url = f"https://{org.dominio_customizado}/app/portal.html"
        elif org.slug:
            portal_url = f"https://{org.slug}.nexuscodebrasil.com.br/app/portal.html"

    cidade_uf = ""
    if cfg:
        if cfg.cidade and cfg.estado:
            cidade_uf = f"{cfg.cidade}, {cfg.estado} - Brasil"
        elif cfg.endereco:
            cidade_uf = cfg.endereco
    if not cidade_uf:
        cidade_uf = "Aracruz, ES - Brasil"

    return {
        "numero_comprovante": numero_comprovante,
        "codigo_autenticacao": codigo_autenticacao,
        "portal_url": portal_url,
        "branding": {
            "nome_plataforma": brand_name,
            "subtitulo_plataforma": brand_sub,
            "cor_primaria": cor_primaria,
            "cor_sidebar": cor_sidebar,
            "logo_url": branding.get("logo_url") or "",
        },
        "emissor": {
            "razao_social": (cfg.razao_social if cfg else None) or (org.nome if org else "Nexus Code Brasil Tecnologia Ltda"),
            "nome_fantasia": (cfg.nome_fantasia if cfg else None) or (org.nome if org else "Nexus Code Brasil"),
            "cnpj": (cfg.cnpj if cfg else None) or "00.000.000/0001-00",
            "email": (cfg.email_financeiro if cfg else None) or "contato@nexuscodebrasil.com.br",
            "telefone": (cfg.telefone if cfg else None) or "(27) 99999-9999",
            "localizacao": cidade_uf,
        },
        "pagador": {
            "nome_empresa": cli.nome_empresa if cli else "Cliente",
            "contato_nome": cli.contato_nome if cli else "Cliente",
            "email": cli.email if cli else "",
            "documento": (cli.documento if cli and cli.documento else None) or "Não informado",
            "telefone": (cli.telefone if cli and cli.telefone else None) or "",
        },
        "fatura": {
            "id": fat.id,
            "descricao": fat.descricao,
            "projeto": proj.titulo if proj else None,
            "valor": float(fat.valor or 0),
            "valor_formatado": _format_brl(fat.valor),
            "status": fat.status,
            "forma_pagamento": fat.forma_pagamento or "Mercado Pago",
            "vencimento": fat.vencimento.strftime("%d/%m/%Y") if fat.vencimento else "-",
            "pago_em": _format_dt_br(fat.pago_em) if fat.status == "pago" else "-",
            "mp_order_id": fat.mp_order_id or "",
            "mp_payment_id": fat.mp_payment_id or "",
            "mp_status_detalhe": fat.mp_status_detalhe or ("accredited" if fat.status == "pago" else ""),
            "mp_checkout_url": fat.mp_checkout_url or "",
            "observacoes": fat.observacoes or "",
        },
    }


def _build_payment_receipt_email_html(recibo: dict) -> tuple[str, str]:
    b = recibo["branding"]
    em = recibo["emissor"]
    pg = recibo["pagador"]
    ft = recibo["fatura"]

    primary = b["cor_primaria"] or "#00B4D8"
    navy = b["cor_sidebar"] or "#0A1D37"
    deep = "#061224"

    tx_id = ft["mp_order_id"] or ft["mp_payment_id"] or recibo["numero_comprovante"]
    tx_label = "Order ID (Mercado Pago)" if ft["mp_order_id"] else ("ID Transação (Mercado Pago)" if ft["mp_payment_id"] else "Protocolo Interno")

    assunto = f"Comprovante de Pagamento {recibo['numero_comprovante']} • {ft['descricao']} ({ft['valor_formatado']})"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{assunto}</title>
</head>
<body style="margin:0; padding:0; background-color:#061224; font-family:'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#0F172A;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#061224; padding:32px 14px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px; width:100%; background-color:#FFFFFF; border-radius:20px; overflow:hidden; box-shadow:0 24px 48px rgba(0,0,0,0.45); border:1px solid #1E3A5F;">
          
          <!-- HEADER CYBER & ENTERPRISE -->
          <tr>
            <td style="background:linear-gradient(135deg, {deep} 0%, {navy} 62%, #0F2E56 100%); background-color:{navy}; padding:30px 32px 26px; text-align:center; border-bottom:3px solid {primary};">
              <table role="presentation" align="center" cellspacing="0" cellpadding="0" border="0" style="margin:0 auto 12px;">
                <tr>
                  <td style="width:44px; height:44px; background-color:{deep}; border:1.5px solid {primary}; border-radius:12px; text-align:center; vertical-align:middle; font-family:Montserrat, Arial, sans-serif; font-weight:900; font-size:20px; color:#FFFFFF;">
                    N
                  </td>
                  <td style="padding-left:12px; text-align:left;">
                    <div style="font-family:Montserrat, Arial, sans-serif; font-size:20px; font-weight:900; letter-spacing:1.2px; color:#FFFFFF; line-height:1.1;">
                      {b['nome_plataforma']}
                    </div>
                    <div style="font-family:Montserrat, Arial, sans-serif; font-size:10px; font-weight:800; letter-spacing:4px; color:{primary}; margin-top:3px;">
                      {b['subtitulo_plataforma']}
                    </div>
                  </td>
                </tr>
              </table>

              <div style="display:inline-block; background-color:rgba(16,185,129,0.16); border:1px solid rgba(16,185,129,0.45); color:#34D399; font-size:11px; font-weight:800; letter-spacing:1.2px; text-transform:uppercase; padding:6px 14px; border-radius:999px; margin-top:6px;">
                &#10003; PAGAMENTO CONFIRMADO
              </div>
              <h1 style="margin:14px 0 4px; font-size:22px; font-weight:800; color:#FFFFFF; letter-spacing:-0.3px;">
                Comprovante Oficial de Pagamento
              </h1>
              <p style="margin:0; font-size:13px; color:#CBD5E1;">
                Recibo Digital Nº <strong style="color:{primary};">{recibo['numero_comprovante']}</strong>
              </p>
            </td>
          </tr>

          <!-- SAUDAÇÃO & VALOR DESTAQUE -->
          <tr>
            <td style="padding:28px 32px 10px;">
              <p style="margin:0 0 18px; font-size:15px; line-height:1.6; color:#334155;">
                Olá, <strong style="color:{navy};">{pg['contato_nome']}</strong>!<br>
                Confirmamos a compensação do seu pagamento referente a <strong style="color:{navy};">{ft['descricao']}</strong>. Sua fatura já foi quitada automaticamente em nosso sistema.
              </p>

              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%); background-color:#F8FAFC; border:1.5px solid #BAE6FD; border-radius:16px; margin-bottom:22px;">
                <tr>
                  <td style="padding:20px 24px; text-align:center;">
                    <div style="font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:1.2px; color:#0284C7; margin-bottom:6px;">
                      Valor Total Liquidado
                    </div>
                    <div style="font-size:32px; font-weight:900; color:{navy}; letter-spacing:-0.5px;">
                      {ft['valor_formatado']}
                    </div>
                    <div style="font-size:12px; color:#475569; margin-top:6px;">
                      Pago em <strong>{ft['pago_em']}</strong> &bull; Via <strong>{ft['forma_pagamento']}</strong>
                    </div>
                  </td>
                </tr>
              </table>

              <!-- TABELA DE DETALHES DA TRANSAÇÃO -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #E2E8F0; border-radius:14px; overflow:hidden; font-size:13px;">
                <tr style="background-color:#F8FAFC;">
                  <td style="padding:11px 16px; color:#64748B; font-weight:600; border-bottom:1px solid #E2E8F0; width:42%;">Nº do Recibo</td>
                  <td style="padding:11px 16px; color:{navy}; font-weight:800; text-align:right; border-bottom:1px solid #E2E8F0;">{recibo['numero_comprovante']}</td>
                </tr>
                <tr>
                  <td style="padding:11px 16px; color:#64748B; font-weight:600; border-bottom:1px solid #E2E8F0;">Descrição / Serviço</td>
                  <td style="padding:11px 16px; color:#0F172A; font-weight:700; text-align:right; border-bottom:1px solid #E2E8F0;">{ft['descricao']}</td>
                </tr>
                <tr style="background-color:#F8FAFC;">
                  <td style="padding:11px 16px; color:#64748B; font-weight:600; border-bottom:1px solid #E2E8F0;">Pagador / Cliente</td>
                  <td style="padding:11px 16px; color:#0F172A; font-weight:600; text-align:right; border-bottom:1px solid #E2E8F0;">{pg['nome_empresa']}</td>
                </tr>
                <tr>
                  <td style="padding:11px 16px; color:#64748B; font-weight:600; border-bottom:1px solid #E2E8F0;">Meio de Pagamento</td>
                  <td style="padding:11px 16px; color:#0F172A; font-weight:600; text-align:right; border-bottom:1px solid #E2E8F0;">{ft['forma_pagamento']}</td>
                </tr>
                <tr style="background-color:#F8FAFC;">
                  <td style="padding:11px 16px; color:#64748B; font-weight:600; border-bottom:1px solid #E2E8F0;">{tx_label}</td>
                  <td style="padding:11px 16px; color:#0284C7; font-family:monospace; font-size:12px; font-weight:700; text-align:right; border-bottom:1px solid #E2E8F0;">{tx_id}</td>
                </tr>
                <tr>
                  <td style="padding:11px 16px; color:#64748B; font-weight:600; border-bottom:1px solid #E2E8F0;">Vencimento Original</td>
                  <td style="padding:11px 16px; color:#0F172A; text-align:right; border-bottom:1px solid #E2E8F0;">{ft['vencimento']}</td>
                </tr>
                <tr style="background-color:#F0FDF4;">
                  <td style="padding:11px 16px; color:#15803D; font-weight:700;">Autenticação Digital</td>
                  <td style="padding:11px 16px; color:#15803D; font-family:monospace; font-size:12px; font-weight:800; text-align:right;">{recibo['codigo_autenticacao']}</td>
                </tr>
              </table>

              <!-- CTA PORTAL DO CLIENTE -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:26px 0 18px;">
                <tr>
                  <td align="center">
                    <a href="{recibo['portal_url']}" target="_blank" style="display:inline-block; background-color:{primary}; color:{navy}; font-size:14px; font-weight:800; text-decoration:none; padding:14px 28px; border-radius:12px; box-shadow:0 8px 20px rgba(0,180,216,0.35);">
                      Visualizar e Baixar Comprovante PDF &rarr;
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 18px; font-size:12px; color:#64748B; text-align:center; line-height:1.5;">
                Este comprovante eletrônico tem validade de quitação junto a <strong>{em['razao_social']}</strong> (CNPJ: {em['cnpj']}).
              </p>
            </td>
          </tr>

          <!-- RODAPÉ INSTITUCIONAL -->
          <tr>
            <td style="background-color:{deep}; padding:22px 32px; text-align:center; border-top:1px solid rgba(0,180,216,0.25);">
              <div style="font-size:13px; font-weight:800; color:#FFFFFF; margin-bottom:4px;">
                {em['razao_social']}
              </div>
              <div style="font-size:11.5px; color:#94A3B8; line-height:1.6;">
                CNPJ: {em['cnpj']} &bull; {em['localizacao']}<br>
                E-mail: <a href="mailto:{em['email']}" style="color:{primary}; text-decoration:none;">{em['email']}</a> &bull; Tel: {em['telefone']}
              </div>
              <div style="font-size:10.5px; color:#64748B; margin-top:10px;">
                Enviado automaticamente pelo ecossistema financeiro {b['nome_plataforma']}. Em conformidade com a LGPD (Lei nº 13.709/2018).
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return assunto, html


def _notificar_pagamento_fatura_confirmado(db: Session, fat: Fatura, background_tasks: Optional[BackgroundTasks] = None):
    """Gera o recibo oficial e dispara o e-mail HTML estilizado ao pagador."""
    try:
        recibo = _gerar_dados_recibo_fatura(db, fat)
        dest_email = (recibo["pagador"].get("email") or "").strip()
        if not dest_email:
            return
        assunto, html_body = _build_payment_receipt_email_html(recibo)
        if background_tasks is not None:
            background_tasks.add_task(enviar_email, dest_email, assunto, html_body)
        else:
            enviar_email(dest_email, assunto, html_body)
    except Exception as mail_err:
        print(f"[Recibo Email Warning] Fatura #{fat.id}: {mail_err}")



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

    ddl_statements = []
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
                ddl_statements.append(
                    f'ALTER TABLE "{table.name}" ADD COLUMN IF NOT EXISTS "{column.name}" {col_type}{default_sql}'
                )
    if "faturas" in existing_tables:
        ddl_statements.append("ALTER TABLE faturas ALTER COLUMN projeto_id DROP NOT NULL")
    if "usuarios" in existing_tables:
        ddl_statements.append(
            "UPDATE usuarios SET tipo_contrato = NULL, carga_horaria_diaria = NULL, "
            "horario_entrada = NULL, horario_saida = NULL, cbo_codigo = NULL, cbo_descricao = NULL, "
            "salario_base = 0, vale_transporte = FALSE, valor_vt_mensal = 0, dependentes_irrf = 0, "
            "pix_tipo = NULL, pix_chave = NULL "
            "WHERE perfil = 'cliente' AND (tipo_contrato IS NOT NULL OR carga_horaria_diaria IS NOT NULL)"
        )

    for stmt in ddl_statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception as ddl_err:
            print(f"[Schema Sync Warning] {stmt} -> {ddl_err}")


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
                conn.execute(text("SELECT organizacao_id, pix_tipo, pix_chave FROM usuarios LIMIT 1"))
                conn.execute(text("SELECT mp_ativo, mp_api_tipo, dominio_precos_json FROM configuracoes_empresa LIMIT 1"))
                conn.execute(text("SELECT mp_order_id, mp_payment_id FROM faturas LIMIT 1"))
                conn.execute(text("SELECT mp_payout_id FROM holerites LIMIT 1"))
                conn.execute(text("SELECT mp_payout_id FROM reembolsos_despesas LIMIT 1"))
                conn.execute(text("SELECT mp_order_id FROM pedidos_dominios LIMIT 1"))
                conn.execute(text("SELECT github_ativo, github_org, github_token, github_visibilidade_padrao, imposto_servico_percent, multa_rescisao_percent, catalogo_servicos_json FROM configuracoes_empresa LIMIT 1"))
                conn.execute(text("SELECT github_repo_full_name, github_default_branch, github_visibilidade, vercel_project_id, ultimo_deploy_status, ultimo_deploy_em FROM projetos LIMIT 1"))
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
                    subtitulo="Estrutura comercial e atendimento centralizado para equipes em crescimento",
                    preco_mensal=Decimal("197.00"),
                    limite_usuarios=5,
                    limite_clientes=250,
                    destaque=False,
                    modulos_json=json.dumps(starter_mods, ensure_ascii=False),
                    recursos_json=json.dumps([
                        "Até 5 usuários internos",
                        "CRM, Leads e Funil Kanban",
                        "Propostas Comerciais & Faturamento",
                        "Portal do Cliente White-Label",
                        "Subdomínio gerenciado (.nexuscodebrasil.com.br)",
                    ], ensure_ascii=False),
                    ativo=True,
                    ordem=1,
                ),
                PlanoSaas(
                    codigo="pro",
                    nome="Pro Gestão & Financeiro",
                    subtitulo="Gestão integrada com DRE gerencial, Timesheet, contratos recorrentes e Service Desk",
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
                        "Identidade visual e subdomínio gerenciado",
                    ], ensure_ascii=False),
                    ativo=True,
                    ordem=2,
                ),
                PlanoSaas(
                    codigo="enterprise",
                    nome="Enterprise Full ERP + RH",
                    subtitulo="Suíte corporativa completa com Ponto Eletrônico, Folha Automática e domínio próprio",
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
                        "Domínio próprio corporativo (CNAME) + Suporte Prioritário",
                    ], ensure_ascii=False),
                    ativo=True,
                    ordem=3,
                ),
            ])
            db.commit()
        else:
            # Atualiza textos legados nos planos padrão caso ainda existam
            for pl_item in db.query(PlanoSaas).all():
                changed = False
                if pl_item.subtitulo and "Suite corporativa" in pl_item.subtitulo:
                    pl_item.subtitulo = pl_item.subtitulo.replace("Suite corporativa", "Suíte corporativa")
                    changed = True
                if pl_item.recursos_json:
                    new_rec = (
                        pl_item.recursos_json
                        .replace("Subdomínio personalizado incluso", "Subdomínio gerenciado (.nexuscodebrasil.com.br)")
                        .replace("Marca, Cores e Logo 100% próprios", "Identidade visual e subdomínio gerenciado")
                        .replace("Domínio próprio (CNAME) + Suporte VIP", "Domínio próprio corporativo (CNAME) + Suporte Prioritário")
                    )
                    if new_rec != pl_item.recursos_json:
                        pl_item.recursos_json = new_rec
                        changed = True
                if changed:
                    db.add(pl_item)
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
        try:
            ensure_db_initialized(force_sync=(request.query_params.get("migrate") == "1"))
        except Exception as init_err:
            print(f"[Init DB Warning] {init_err}")
            if path != "/api/public/tenant-branding":
                raise
    return await call_next(request)


router = APIRouter(prefix="/api")


@router.get("/health", tags=["Status"])
def raiz(db: int = 0):
    db_status = "skipped"
    db_error = None
    if db == 1:
        try:
            ensure_db_initialized(force_sync=True)
            db_status = "connected_and_synced"
        except Exception as exc:
            db_status = "error"
            db_error = str(exc)
    return {
        "status": "online" if db_status != "error" else "degraded",
        "sistema": "Nexus Code Enterprise SaaS ERP & CRM API",
        "versao": "2.5.1-prod",
        "regiao": os.getenv("VERCEL_REGION", "local"),
        "database_url_configurada": bool(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")),
        "db_status": db_status,
        **({"db_error": db_error} if db_error else {}),
    }


@router.post("/admin/sync-db", tags=["Status"])
def forcar_migracao_banco(_: Usuario = Depends(exigir_master_admin)):
    ensure_db_initialized(force_sync=True)
    return {"ok": True, "message": "Estrutura Multi-Tenant de tabelas e colunas sincronizada com sucesso."}


# ==================== WHITE-LABEL BRANDING & SAAS ONBOARDING PÚBLICO ====================
@router.get("/public/tenant-branding", tags=["SaaS White-Label"])
def obter_branding_tenant(req: Request, db: Session = Depends(get_db)):
    try:
        org = _resolver_org_por_request(req, db)
    except Exception as exc:
        print(f"[Branding Fallback] {exc}")
        master_mods = dict(DEFAULT_MODULOS_TENANT)
        master_mods["loja"] = True
        master_mods["saas_tenants"] = True
        return {
            "organizacao_id": 1,
            "nome": "Nexus Code Brasil",
            "slug": "nexus",
            "dominio_customizado": None,
            "subdominio_url": "https://www.nexuscodebrasil.com.br",
            "is_master": True,
            "status_assinatura": "ativo",
            "branding": dict(DEFAULT_BRANDING_MASTER),
            "modulos": master_mods,
        }
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

    plano_obj = db.query(PlanoSaas).filter(PlanoSaas.codigo == plano_codigo).first()
    if not plano_obj:
        plano_obj = db.query(PlanoSaas).filter(PlanoSaas.ativo == True).order_by(PlanoSaas.ordem.asc()).first()
    efetivo_plano = plano_obj.codigo if plano_obj else plano_codigo

    dom_clean = _validar_dominio_customizado(dominio_customizado, efetivo_plano, is_master=False)
    if dom_clean:
        if db.query(Organizacao.id).filter(func.lower(Organizacao.dominio_customizado) == dom_clean).first():
            raise HTTPException(status_code=400, detail=f"O domínio '{dom_clean}' já está vinculado a outro portal.")

    if db.query(Usuario.id).filter(func.lower(Usuario.email) == admin_email.strip().lower()).first():
        raise HTTPException(status_code=400, detail="O e-mail do administrador já está cadastrado na plataforma.")

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
        dominio_customizado=dados.dominio_customizado,
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

    efetivo_plano_upd = (payload.get("plano") or org.plano or "").strip().lower()
    if not org.is_master and efetivo_plano_upd != "enterprise":
        if payload.get("dominio_customizado"):
            raise HTTPException(
                status_code=403,
                detail="O apontamento de domínio próprio (CNAME) é exclusivo do plano Enterprise Full.",
            )
        payload["dominio_customizado"] = None
    elif "dominio_customizado" in payload:
        dom = _validar_dominio_customizado(payload["dominio_customizado"], efetivo_plano_upd, is_master=bool(org.is_master))
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
    try:
        usuario = (
            db.query(Usuario)
            .options(defer(Usuario.foto_url), defer(Usuario.resumo_profissional))
            .filter(func.lower(Usuario.email) == dados.email.strip().lower())
            .first()
        )
    except Exception:
        db.rollback()
        ensure_db_initialized(force_sync=True)
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
    org = _resolver_org_por_request(req, db)
    if db.query(Usuario.id).filter(Usuario.organizacao_id == org.id, func.lower(Usuario.email) == dados.email.strip().lower()).first():
        raise HTTPException(status_code=400, detail="Este endereço de e-mail já está vinculado a uma conta neste ambiente.")
    if not org.is_master and org.status_assinatura == "suspenso":
        raise HTTPException(status_code=403, detail="Este portal está temporariamente suspenso.")

    novo = Usuario(
        organizacao_id=org.id,
        nome=dados.nome,
        email=dados.email.strip().lower(),
        senha_hash=gerar_hash_senha(dados.senha),
        perfil="cliente",
        ativo=True,
        tipo_contrato=None,
        carga_horaria_diaria=None,
        horario_entrada=None,
        horario_saida=None,
        salario_base=0,
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
        if db.query(Usuario.id).filter(Usuario.organizacao_id == usuario.organizacao_id, Usuario.email == payload["email"], Usuario.id != usuario.id).first():
            raise HTTPException(status_code=400, detail="Este e-mail já está em uso por outra conta neste ambiente.")

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



# ==================== SOLICITAÇÕES DE ORÇAMENTO (SITE & PORTAL -> CRM) ====================
@router.post("/public/orcamentos", status_code=201, tags=["Orçamentos"])
def receber_solicitacao_site(dados: SolicitacaoPublicCreate, req: Request, db: Session = Depends(get_db)):
    if dados.website:
        return {"message": "Solicitação recebida com sucesso."}

    org = _resolver_org_por_request(req, db)

    tipo_map = {
        "web": "Desenvolvimento Web",
        "mobile": "Aplicativo Mobile",
        "system": "Sistema Personalizado",
        "ecommerce": "E-commerce",
        "saas": "Portal Nexus Enterprise SaaS",
        "other": "Outro",
    }
    tipo_legivel = tipo_map.get(dados.tipo_projeto or "", dados.tipo_projeto or "Não especificado")

    cliente = db.query(Cliente).filter(Cliente.organizacao_id == org.id, Cliente.email == dados.email).first()
    if not cliente:
        cliente = Cliente(
            organizacao_id=org.id,
            nome_empresa=(dados.empresa or dados.nome).strip(),
            contato_nome=dados.nome.strip(),
            email=dados.email,
            telefone=dados.telefone.strip() if dados.telefone else None,
            status_funil="lead",
            origem="Formulário do Site",
            observacoes=f"[{tipo_legivel}] {dados.mensagem.strip()}",
        )
        db.add(cliente)
        db.flush()
    else:
        nota_nova = f"[{tipo_legivel}] {dados.mensagem.strip()}"
        cliente.observacoes = f"{cliente.observacoes}\n---\n{nota_nova}" if cliente.observacoes else nota_nova
        if dados.telefone and not cliente.telefone:
            cliente.telefone = dados.telefone.strip()

    solicitacao = SolicitacaoOrcamento(
        organizacao_id=org.id,
        cliente_id=cliente.id,
        nome=dados.nome.strip(),
        empresa=dados.empresa.strip() if dados.empresa else None,
        email=dados.email,
        telefone=dados.telefone.strip() if dados.telefone else None,
        tipo_projeto=tipo_legivel,
        mensagem=dados.mensagem.strip(),
        status="novo",
    )
    db.add(solicitacao)
    db.flush()

    db.add(Interacao(
        organizacao_id=org.id,
        cliente_id=cliente.id,
        tipo="proposta",
        resumo=f"Solicitação via site ({tipo_legivel}): {dados.mensagem.strip()}",
        proxima_acao="Realizar atendimento comercial",
    ))

    criar_notificacao(
        db,
        titulo="Nova Solicitação pelo Site",
        mensagem=f"{dados.nome.strip()} solicitou orçamento para {tipo_legivel}.",
        link_pagina="quotes",
        perfil_destino="equipe",
        org_id=org.id,
    )

    registrar_log(
        db,
        dados.nome.strip(),
        "SOLICITACAO_SITE",
        f"Nova solicitação de orçamento ({tipo_legivel}) de {dados.email}",
        org_id=org.id,
    )
    db.commit()
    db.refresh(solicitacao)

    return {
        "id": solicitacao.id,
        "message": "Sua solicitação foi recebida. Nossa equipe comercial analisará as informações e retornará o contato em breve.",
    }


@router.post("/portal/solicitar-projeto", response_model=SolicitacaoOut, status_code=201, tags=["Portal Cliente"])
def solicitar_novo_projeto_portal(
    dados: SolicitacaoPortalCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    cliente = _garantir_cliente_para_portal(db, usuario)
    detalhes = f"[{dados.titulo.strip()}] (Urgência: {dados.urgencia.upper()}"
    if dados.orcamento_estimado:
        detalhes += f" | Investimento previsto: {dados.orcamento_estimado.strip()}"
    detalhes += f")\n{dados.mensagem.strip()}"

    sol = SolicitacaoOrcamento(
        organizacao_id=usuario.organizacao_id,
        cliente_id=cliente.id,
        nome=usuario.nome,
        empresa=cliente.nome_empresa,
        email=usuario.email,
        telefone=usuario.telefone or cliente.telefone,
        tipo_projeto=dados.tipo_projeto,
        mensagem=detalhes,
        status="novo",
    )
    db.add(sol)
    db.flush()

    criar_notificacao(
        db,
        titulo="Novo Projeto Solicitado no Portal",
        mensagem=f"{cliente.nome_empresa} solicitou: {dados.titulo.strip()} ({dados.tipo_projeto}).",
        link_pagina="quotes",
        perfil_destino="equipe",
        org_id=usuario.organizacao_id,
    )
    registrar_log(db, usuario.nome, "SOLICITACAO_PORTAL", f"Solicitou novo projeto via portal: {dados.titulo}", org_id=usuario.organizacao_id)
    db.commit()
    db.refresh(sol)
    return sol


@router.get("/orcamentos", response_model=List[SolicitacaoOut], tags=["Orçamentos"])
def listar_solicitacoes(
    status_solicitacao: Optional[str] = None,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    query = db.query(SolicitacaoOrcamento).filter(SolicitacaoOrcamento.organizacao_id == equipe.organizacao_id)
    if status_solicitacao:
        query = query.filter(SolicitacaoOrcamento.status == status_solicitacao)
    return query.order_by(SolicitacaoOrcamento.criado_em.desc()).all()


@router.get("/portal/orcamentos", response_model=List[SolicitacaoOut], tags=["Orçamentos"])
def listar_solicitacoes_cliente(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    return (
        db.query(SolicitacaoOrcamento)
        .filter(
            SolicitacaoOrcamento.organizacao_id == usuario.organizacao_id,
            SolicitacaoOrcamento.email == usuario.email,
        )
        .order_by(SolicitacaoOrcamento.criado_em.desc())
        .all()
    )


@router.patch("/orcamentos/{orcamento_id}/responder", response_model=SolicitacaoOut, tags=["Orçamentos"])
def responder_solicitacao(
    orcamento_id: int,
    dados: SolicitacaoResponder,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    sol = db.query(SolicitacaoOrcamento).filter(
        SolicitacaoOrcamento.id == orcamento_id,
        SolicitacaoOrcamento.organizacao_id == equipe.organizacao_id,
    ).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    org = db.query(Organizacao).filter(Organizacao.id == equipe.organizacao_id).first()
    org_nome = org.nome if org else "Nexus Code Brasil"

    sol.resposta = dados.resposta.strip()
    sol.status = dados.status
    sol.respondido_por = equipe.nome
    sol.respondido_em = datetime.utcnow()

    if sol.cliente_id:
        cliente = db.query(Cliente).filter(Cliente.id == sol.cliente_id, Cliente.organizacao_id == equipe.organizacao_id).first()
        if cliente:
            if cliente.status_funil == "lead":
                cliente.status_funil = "proposta"
            if cliente.usuario_portal_id:
                criar_notificacao(
                    db,
                    titulo="Sua solicitação foi respondida",
                    mensagem=f"{equipe.nome} respondeu à sua solicitação ({sol.tipo_projeto}).",
                    link_pagina="quotes",
                    usuario_id=cliente.usuario_portal_id,
                    org_id=equipe.organizacao_id,
                )
        db.add(Interacao(
            organizacao_id=equipe.organizacao_id,
            cliente_id=sol.cliente_id,
            usuario_id=equipe.id,
            tipo="proposta",
            resumo=f"Resposta enviada por {equipe.nome}: {sol.resposta}",
        ))

    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; color: #0A1D37;">
        <h2 style="color: #00B4D8;">Olá, {sol.nome}.</h2>
        <p>A equipe da <b>{org_nome}</b> respondeu à sua solicitação de projeto ({sol.tipo_projeto}):</p>
        <div style="padding: 15px; border-left: 4px solid #00B4D8; background-color: #f8fafc; margin-bottom: 20px;">
            {sol.resposta.replace(chr(10), '<br>')}
        </div>
        <p>Acesse o Portal do Cliente para acompanhar o status e interagir com nossa equipe.</p>
    </div>
    """
    background_tasks.add_task(enviar_email, sol.email, f"Retorno: {sol.tipo_projeto} - {org_nome}", corpo_email)

    registrar_log(db, equipe.nome, "RESPONDER_ORCAMENTO", f"Respondeu solicitação #{sol.id} ({sol.nome})", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(sol)
    return sol




@router.post("/orcamentos/{orcamento_id}/gerar-orcamento-automatico", tags=["Orçamentos"])
def gerar_orcamento_automatico_para_cliente(
    orcamento_id: int,
    dados: GerarOrcamentoAutoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    sol = db.query(SolicitacaoOrcamento).filter(
        SolicitacaoOrcamento.id == orcamento_id,
        SolicitacaoOrcamento.organizacao_id == org.id,
    ).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação de orçamento não encontrada.")

    cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org.id).first()
    catalogo = _get_catalogo_servicos_empresa(cfg)
    params_padrao = _get_parametros_orcamento_empresa(cfg)

    servico_obj = next((s for s in catalogo if s.get("codigo") == dados.servico_codigo), None) if dados.servico_codigo else None

    # Garante cliente vinculado no CRM
    cliente = db.query(Cliente).filter(Cliente.id == sol.cliente_id, Cliente.organizacao_id == org.id).first() if sol.cliente_id else None
    if not cliente:
        cliente = db.query(Cliente).filter(Cliente.organizacao_id == org.id, Cliente.email == sol.email).first()
    if not cliente:
        cliente = Cliente(
            organizacao_id=org.id,
            nome_empresa=(sol.empresa or sol.nome).strip(),
            contato_nome=sol.nome.strip(),
            email=sol.email,
            telefone=sol.telefone,
            status_funil="proposta",
            origem="Solicitação de Orçamento",
        )
        db.add(cliente)
        db.flush()
    sol.cliente_id = cliente.id

    # Cálculo financeiro automático
    valor_base = round(float(dados.valor_base or 0), 2)
    urg_map = {"normal": 0.0, "alta": 15.0, "urgente": 30.0}
    urg_pct = urg_map.get(dados.urgencia, 0.0)
    valor_urgencia = round(valor_base * (urg_pct / 100.0), 2)
    desconto = round(float(dados.desconto or 0), 2)
    subtotal_tecnico = round(max(0.0, valor_base + valor_urgencia - desconto), 2)

    imposto_pct = float(dados.imposto_percent) if dados.imposto_percent is not None else params_padrao["imposto_servico_percent"]
    multa_atraso_pct = float(dados.multa_atraso_percent) if dados.multa_atraso_percent is not None else params_padrao["multa_atraso_percent"]
    juros_mensal_pct = float(dados.juros_mensal_percent) if dados.juros_mensal_percent is not None else params_padrao["juros_mensal_percent"]
    multa_rescisao_pct = float(dados.multa_rescisao_percent) if dados.multa_rescisao_percent is not None else params_padrao["multa_rescisao_percent"]

    valor_imposto = round(subtotal_tecnico * (imposto_pct / 100.0), 2)
    valor_total_final = round(subtotal_tecnico + valor_imposto, 2)
    n_parcelas = max(1, int(dados.parcelas or 1))
    valor_parcela = round(valor_total_final / n_parcelas, 2)
    prazo_dias = max(1, int(dados.prazo_dias or (servico_obj.get("prazo_dias") if servico_obj else 15)))

    titulo_final = (
        (dados.titulo_proposta or "").strip()
        or (servico_obj.get("nome") if servico_obj else None)
        or sol.tipo_projeto
        or f"Projeto {cliente.nome_empresa}"
    )

    entregaveis_raw = dados.entregaveis if (dados.entregaveis and len(dados.entregaveis) > 0) else (servico_obj.get("entregaveis") if servico_obj else [])
    if not entregaveis_raw:
        entregaveis_raw = [
            "Levantamento Técnico e Arquitetura da Solução",
            "Desenvolvimento e Integração dos Módulos",
            "Homologação com Cliente e Publicação em Produção",
        ]
    entregaveis_struct = [
        {"titulo": item.strip(), "prazo_dias": max(2, round(((idx + 1) / len(entregaveis_raw)) * prazo_dias))}
        for idx, item in enumerate(entregaveis_raw)
        if str(item).strip()
    ]

    seq = (db.query(func.count(PropostaComercial.id)).scalar() or 0) + 1
    codigo_prop = f"PROP-{date.today().year}-{seq:04d}"

    clausulas_financeiras = (
        f"DEMONSTRATIVO AUTOMÁTICO DE INVESTIMENTO ({codigo_prop})\n"
        f"• Serviço / Categoria: {titulo_final}\n"
        f"• Custo Técnico Base: {_format_brl(valor_base)}\n"
        + (f"• Adicional de Urgência ({dados.urgencia.upper()} +{urg_pct:.0f}%): {_format_brl(valor_urgencia)}\n" if valor_urgencia > 0 else "")
        + (f"• Desconto Comercial Concedido: -{_format_brl(desconto)}\n" if desconto > 0 else "")
        + f"• Subtotal Líquido Técnico: {_format_brl(subtotal_tecnico)}\n"
        + f"• Impostos & Tributos Incidentes ({imposto_pct:.2f}%): {_format_brl(valor_imposto)}\n"
        + f"• VALOR TOTAL DO ORÇAMENTO: {_format_brl(valor_total_final)} ({n_parcelas}x de {_format_brl(valor_parcela)})\n"
        + f"• Prazo Estimado de Entrega: {prazo_dias} dias corridos\n\n"
        + f"CLÁUSULAS DE MULTAS E ENCARGOS CONTRATUAIS\n"
        + f"• Multa por Atraso de Pagamento: {multa_atraso_pct:.2f}% sobre o valor da parcela vencida.\n"
        + f"• Juros Moratórios: {juros_mensal_pct:.2f}% ao mês (pro-rata die) após o vencimento.\n"
        + f"• Multa por Rescisão Imotivada: {multa_rescisao_pct:.2f}% sobre o saldo contratual remanescente."
    )

    escopo_completo = (
        (f"{dados.escopo_adicional.strip()}\n\n" if (dados.escopo_adicional and dados.escopo_adicional.strip()) else (f"{servico_obj.get('descricao')}\n\n" if servico_obj else ""))
        + clausulas_financeiras
    )

    condicoes_pgto = (
        f"{n_parcelas}x de {_format_brl(valor_parcela)} (PIX / Checkout) | "
        f"Multa atraso: {multa_atraso_pct:.1f}% + Juros {juros_mensal_pct:.1f}% a.m. | "
        f"Rescisão: {multa_rescisao_pct:.1f}%"
    )

    prop = PropostaComercial(
        organizacao_id=org.id,
        codigo=codigo_prop,
        cliente_id=cliente.id,
        solicitacao_id=sol.id,
        criado_por_id=equipe.id,
        titulo=titulo_final[:180],
        escopo=escopo_completo,
        entregaveis_json=json.dumps(entregaveis_struct, ensure_ascii=False),
        valor_total=Decimal(str(valor_total_final)),
        condicoes_pagamento=condicoes_pgto[:200],
        parcelas=n_parcelas,
        prazo_dias=prazo_dias,
        validade_ate=date.today() + timedelta(days=int(dados.validade_dias or 15)),
        status="aprovada" if dados.converter_em_projeto else "enviada",
    )
    db.add(prop)
    db.flush()

    projeto_criado = None
    if dados.converter_em_projeto:
        prop.aprovado_por_cliente = f"Aprovado na emissão por {equipe.nome}"
        prop.aprovado_em = datetime.utcnow()
        projeto_criado = _converter_proposta_em_projeto(db, prop, equipe.nome)
        sol.status = "convertido"
    else:
        sol.status = "respondido"
        if cliente.status_funil == "lead":
            cliente.status_funil = "proposta"

    sol.resposta = clausulas_financeiras
    sol.respondido_por = equipe.nome
    sol.respondido_em = datetime.utcnow()

    db.add(Interacao(
        organizacao_id=org.id,
        cliente_id=cliente.id,
        usuario_id=equipe.id,
        tipo="proposta",
        resumo=f"Orçamento automático {codigo_prop} gerado ({_format_brl(valor_total_final)} em {n_parcelas}x, impostos {imposto_pct:.1f}%).",
        proxima_acao="Aguardar aprovação do cliente no Portal",
    ))

    if cliente.usuario_portal_id:
        criar_notificacao(
            db,
            titulo=f"Orçamento Oficial Disponível ({codigo_prop})",
            mensagem=f"Seu orçamento para '{titulo_final}' ({_format_brl(valor_total_final)}) está pronto para aprovação.",
            link_pagina="proposals",
            usuario_id=cliente.usuario_portal_id,
            org_id=org.id,
        )

    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; color: #0A1D37; max-width: 620px; margin: 0 auto;">
      <div style="background: #0A1D37; color: #fff; padding: 22px 26px; border-radius: 12px 12px 0 0; border-bottom: 3px solid #00B4D8;">
        <div style="font-size: 11px; font-weight: 800; letter-spacing: 2px; color: #00B4D8;">ORÇAMENTO &amp; PROPOSTA COMERCIAL</div>
        <h2 style="margin: 6px 0 0; font-size: 20px;">{titulo_final} ({codigo_prop})</h2>
      </div>
      <div style="padding: 24px; border: 1px solid #e2e8f0; border-top: 0; border-radius: 0 0 12px 12px; background: #ffffff;">
        <p>Olá, <b>{sol.nome}</b>! Preparamos o orçamento detalhado para sua solicitação junto à <b>{org.nome}</b>:</p>
        <table style="width:100%; border-collapse: collapse; font-size: 13.5px; margin: 16px 0;">
          <tr style="background:#f8fafc;"><td style="padding:9px 12px; border:1px solid #e2e8f0;">Custo Base do Projeto</td><td style="padding:9px 12px; border:1px solid #e2e8f0; text-align:right;"><b>{_format_brl(valor_base)}</b></td></tr>
          {"<tr><td style='padding:9px 12px; border:1px solid #e2e8f0;'>Adicional Urgência (" + dados.urgencia.upper() + f" +{urg_pct:.0f}%)</td><td style='padding:9px 12px; border:1px solid #e2e8f0; text-align:right;'>{_format_brl(valor_urgencia)}</td></tr>" if valor_urgencia > 0 else ""}
          {"<tr><td style='padding:9px 12px; border:1px solid #e2e8f0;'>Desconto Comercial</td><td style='padding:9px 12px; border:1px solid #e2e8f0; text-align:right; color:#15803d;'>-" + _format_brl(desconto) + "</td></tr>" if desconto > 0 else ""}
          <tr><td style="padding:9px 12px; border:1px solid #e2e8f0;">Impostos &amp; Tributos ({imposto_pct:.2f}%)</td><td style="padding:9px 12px; border:1px solid #e2e8f0; text-align:right;">{_format_brl(valor_imposto)}</td></tr>
          <tr style="background:#eff6ff;"><td style="padding:11px 12px; border:1px solid #bae6fd; font-weight:800;">INVESTIMENTO TOTAL ({n_parcelas}x de {_format_brl(valor_parcela)})</td><td style="padding:11px 12px; border:1px solid #bae6fd; text-align:right; font-size:16px; font-weight:900; color:#0284c7;">{_format_brl(valor_total_final)}</td></tr>
        </table>
        <p style="font-size: 12px; color: #475569; background: #f8fafc; padding: 10px 12px; border-radius: 8px; border: 1px solid #e2e8f0;">
          <b>Condições &amp; Multas Contratuais:</b> Prazo estimado de <b>{prazo_dias} dias</b>. Multa por atraso de <b>{multa_atraso_pct:.2f}%</b> + juros de <b>{juros_mensal_pct:.2f}% a.m.</b> Multa rescisória de <b>{multa_rescisao_pct:.2f}%</b> sobre o saldo remanescente.
        </p>
        <p style="margin-top: 18px;">Acesse o <b>Portal do Cliente</b> para visualizar o documento completo e aprovar com 1 clique.</p>
      </div>
    </div>
    """
    background_tasks.add_task(enviar_email, sol.email, f"Orçamento Oficial {codigo_prop} — {titulo_final} ({org.nome})", corpo_email)

    registrar_log(
        db,
        equipe.nome,
        "GERAR_ORCAMENTO_AUTO",
        f"Gerou orçamento automático {codigo_prop} ({_format_brl(valor_total_final)}) para solicitação #{sol.id}",
        org_id=org.id,
    )
    db.commit()
    db.refresh(prop)
    db.refresh(sol)
    return {
        "ok": True,
        "proposta": PropostaOut.model_validate(prop),
        "solicitacao": SolicitacaoOut.model_validate(sol),
        "projeto_id": projeto_criado.id if projeto_criado else None,
        "resumo_financeiro": {
            "valor_base": valor_base,
            "valor_urgencia": valor_urgencia,
            "desconto": desconto,
            "subtotal_tecnico": subtotal_tecnico,
            "imposto_percent": imposto_pct,
            "valor_imposto": valor_imposto,
            "valor_total": valor_total_final,
            "parcelas": n_parcelas,
            "valor_parcela": valor_parcela,
            "multa_atraso_percent": multa_atraso_pct,
            "juros_mensal_percent": juros_mensal_pct,
            "multa_rescisao_percent": multa_rescisao_pct,
        },
    }

@router.patch("/orcamentos/{orcamento_id}", response_model=SolicitacaoOut, tags=["Orçamentos"])
def atualizar_solicitacao(
    orcamento_id: int,
    dados: SolicitacaoUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    sol = db.query(SolicitacaoOrcamento).filter(
        SolicitacaoOrcamento.id == orcamento_id,
        SolicitacaoOrcamento.organizacao_id == equipe.organizacao_id,
    ).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    payload = dados.model_dump(exclude_unset=True)
    for campo, valor in payload.items():
        setattr(sol, campo, valor)

    registrar_log(db, equipe.nome, "EDITAR_ORCAMENTO", f"Atualizou solicitação #{sol.id}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(sol)
    return sol


@router.delete("/orcamentos/{orcamento_id}", status_code=204, tags=["Orçamentos"])
def remover_solicitacao(
    orcamento_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    sol = db.query(SolicitacaoOrcamento).filter(
        SolicitacaoOrcamento.id == orcamento_id,
        SolicitacaoOrcamento.organizacao_id == equipe.organizacao_id,
    ).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    registrar_log(db, equipe.nome, "EXCLUIR_ORCAMENTO", f"Removeu solicitação #{sol.id} ({sol.nome})", org_id=equipe.organizacao_id)
    db.delete(sol)
    db.commit()


# ==================== BOOTSTRAP CONSOLIDADO MULTI-TENANT ====================
def _executar_bootstrap_painel(db: Session, usuario: Usuario) -> dict:
    org_id = usuario.organizacao_id
    org = _get_org_or_404(db, org_id)

    branding = _parse_json_dict(org.branding_json, DEFAULT_BRANDING_MASTER)
    modulos = dict(DEFAULT_MODULOS_TENANT)
    if org.is_master:
        modulos["loja"] = True
        modulos["saas_tenants"] = True
    else:
        modulos = _parse_json_dict(org.modulos_json, DEFAULT_MODULOS_TENANT)

    empresa_cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org_id).first()
    
    # 4.1: Resolver permissões do colaborador para o backend (simulando a mesma matriz do frontend)
    colab_perms = None
    if usuario.perfil != "admin":
        cbo_text = ((usuario.cbo_descricao or '') + ' ' + (usuario.cbo_codigo or '') + ' ' + (usuario.cargo or '')).lower()
        colab_perms = {
            "projetos": True, "tarefas": True, "timesheet": True, "orcamentos": True,
            "propostas": True, "clientes": True, "chamados": True, "financeiro_dre": False,
            "faturas": True, "despesas": False, "contratos": False, "ponto": True,
            "holerite": True, "ativos": True, "usuarios": False, "auditoria": False, "loja": False, "reembolsos": True
        }
        if "administrativo" in cbo_text or "4110" in cbo_text:
            colab_perms.update({"projetos": False, "orcamentos": False, "propostas": False, "clientes": False, "despesas": True, "ativos": False})
        elif any(x in cbo_text for x in ["financeiro", "contabilidade", "2525", "2522", "4131"]):
            colab_perms.update({"projetos": False, "orcamentos": False, "propostas": False, "clientes": False, "chamados": False, "financeiro_dre": True, "despesas": True, "contratos": True, "ativos": False})
        elif any(x in cbo_text for x in ["vendas", "comercial", "3541", "1423"]):
            colab_perms.update({"projetos": False, "chamados": False, "faturas": False, "loja": True})
        elif any(x in cbo_text for x in ["desenvolvedor", "programador", "engenheiro", "designer", "3171", "2624"]):
            colab_perms.update({"orcamentos": False, "propostas": False, "clientes": False, "faturas": False})
        elif any(x in cbo_text for x in ["recursos humanos", "rh ", "2524"]):
            colab_perms.update({"projetos": False, "orcamentos": False, "propostas": False, "clientes": False, "chamados": False, "faturas": False, "usuarios": True})
            
        if empresa_cfg and empresa_cfg.permissoes_json:
            try:
                parsed_perms = json.loads(empresa_cfg.permissoes_json)
                if "colaborador" in parsed_perms:
                    for k, v in parsed_perms["colaborador"].items():
                        colab_perms[k] = colab_perms[k] and v
            except:
                pass
                
        # Combinar limites do SaaS (Tenant) com limites do Colaborador
        for k in colab_perms:
            colab_perms[k] = colab_perms[k] and modulos.get(k, False)
            
    def _has_perm(key: str) -> bool:
        if usuario.perfil == "admin": return True
        return colab_perms.get(key, False) if colab_perms else False

    clientes = db.query(Cliente).filter(Cliente.organizacao_id == org_id).order_by(Cliente.criado_em.desc()).all() if _has_perm("clientes") else []
    usuarios = (db.query(Usuario).options(defer(Usuario.foto_url), defer(Usuario.resumo_profissional)).filter(Usuario.organizacao_id == org_id).order_by(Usuario.nome).all()) if _has_perm("usuarios") else []
    projetos = db.query(Projeto).filter(Projeto.organizacao_id == org_id).order_by(Projeto.criado_em.desc()).all() if _has_perm("projetos") else []
    orcamentos = db.query(SolicitacaoOrcamento).filter(SolicitacaoOrcamento.organizacao_id == org_id).order_by(SolicitacaoOrcamento.criado_em.desc()).all() if _has_perm("orcamentos") else []
    tarefas = db.query(Tarefa).filter(Tarefa.organizacao_id == org_id).order_by(Tarefa.criado_em.desc()).all() if _has_perm("tarefas") else []
    propostas = db.query(PropostaComercial).filter(PropostaComercial.organizacao_id == org_id).order_by(PropostaComercial.criado_em.desc()).all() if _has_perm("propostas") else []
    despesas = db.query(Despesa).filter(Despesa.organizacao_id == org_id).order_by(Despesa.vencimento.asc()).all() if _has_perm("despesas") else []
    contratos = db.query(ContratoRecorrente).filter(ContratoRecorrente.organizacao_id == org_id).order_by(ContratoRecorrente.criado_em.desc()).all() if _has_perm("contratos") else []
    apontamentos = db.query(ApontamentoHora).filter(ApontamentoHora.organizacao_id == org_id).order_by(ApontamentoHora.data_trabalho.desc(), ApontamentoHora.id.desc()).all() if _has_perm("timesheet") else []
    chamados = db.query(ChamadoSuporte).filter(ChamadoSuporte.organizacao_id == org_id).order_by(ChamadoSuporte.criado_em.desc()).all() if _has_perm("chamados") else []
    ativos = db.query(AtivoInfra).filter(AtivoInfra.organizacao_id == org_id).order_by(AtivoInfra.data_vencimento.asc().nullslast()).all() if _has_perm("ativos") else []

    notificacoes = (
        db.query(Notificacao)
        .filter(
            Notificacao.organizacao_id == org_id,
            or_(
                Notificacao.usuario_id == usuario.id,
                Notificacao.perfil_destino == "equipe",
                Notificacao.perfil_destino == usuario.perfil,
            ),
        )
        .order_by(Notificacao.criado_em.desc())
        .limit(25)
        .all()
    )

    agg = db.execute(
        text("""
            SELECT
                COALESCE((SELECT SUM(valor) FROM faturas WHERE organizacao_id = :oid AND status = 'pago'), 0) AS receita_paga,
                COALESCE((SELECT SUM(valor) FROM faturas WHERE organizacao_id = :oid AND status IN ('pendente', 'atrasado')), 0) AS receita_pendente,
                COALESCE((SELECT COUNT(*) FROM registros_ponto WHERE organizacao_id = :oid AND status_ajuste = 'pendente_ajuste'), 0) AS ponto_pendentes
        """),
        {"oid": org_id},
    ).first()

    leads_abertos = sum(1 for c in clientes if c.status_funil in ("lead", "proposta", "negociacao"))
    solicitacoes_novas = sum(1 for o in orcamentos if o.status in ("novo", "em_atendimento"))
    projetos_ativos = sum(1 for p in projetos if p.status in ("planejamento", "em_andamento", "homologacao"))
    tarefas_pendentes = sum(1 for t in tarefas if t.status != "concluida")
    propostas_abertas = sum(1 for pr in propostas if pr.status in ("enviada", "ajuste_solicitado"))
    chamados_abertos = sum(1 for ch in chamados if ch.status in ("aberto", "em_analise", "aguardando_cliente"))

    receita_paga = float(agg.receita_paga or 0)
    receita_pendente = float(agg.receita_pendente or 0)
    ponto_pendentes = int(agg.ponto_pendentes or 0)

    despesas_pagas = sum(float(d.valor or 0) for d in despesas if d.status == "pago")
    despesas_pendentes = sum(float(d.valor or 0) for d in despesas if d.status in ("pendente", "atrasado"))
    mrr_ativo = sum(float(ct.valor_mensal or 0) for ct in contratos if ct.status == "ativo")
    horas_totais = sum(float(ap.horas or 0) for ap in apontamentos)

    kpi = {
        "total_clientes": len(clientes),
        "leads_abertos": leads_abertos,
        "solicitacoes_novas": solicitacoes_novas,
        "projetos_ativos": projetos_ativos,
        "tarefas_pendentes": tarefas_pendentes,
        "ponto_pendentes": ponto_pendentes,
        "receita_paga": receita_paga,
        "receita_pendente": receita_pendente,
        "despesas_pagas": round(despesas_pagas, 2),
        "despesas_pendentes": round(despesas_pendentes, 2),
        "lucro_realizado": round(receita_paga - despesas_pagas, 2),
        "mrr_ativo": round(mrr_ativo, 2),
        "propostas_abertas": propostas_abertas,
        "chamados_abertos": chamados_abertos,
        "horas_totais": round(horas_totais, 2),
    }

    holerite_q = db.query(Holerite).options(defer(Holerite.anexo_data)).filter(Holerite.organizacao_id == org_id)
    informe_q = db.query(InformeRendimento).options(defer(InformeRendimento.anexo_data)).filter(InformeRendimento.organizacao_id == org_id)
    if usuario.perfil != "admin":
        holerite_q = holerite_q.filter(Holerite.usuario_id == usuario.id)
        informe_q = informe_q.filter(InformeRendimento.usuario_id == usuario.id)

    holerites = holerite_q.order_by(Holerite.criado_em.desc()).all()
    informes = informe_q.order_by(InformeRendimento.ano_calendario.desc(), InformeRendimento.criado_em.desc()).all()
    produtos_loja = db.query(ProdutoLoja).filter(ProdutoLoja.organizacao_id == org_id).order_by(ProdutoLoja.ordem.asc(), ProdutoLoja.id.asc()).all()
    pedidos_loja = db.query(PedidoLoja).filter(PedidoLoja.organizacao_id == org_id).order_by(PedidoLoja.criado_em.desc()).limit(50).all()
    reembolsos_q = db.query(ReembolsoDespesa).options(defer(ReembolsoDespesa.comprovante_data)).filter(ReembolsoDespesa.organizacao_id == org_id)
    if usuario.perfil != "admin":
        reembolsos_q = reembolsos_q.filter(ReembolsoDespesa.usuario_id == usuario.id)
    reembolsos = reembolsos_q.order_by(ReembolsoDespesa.criado_em.desc()).all()

    return {
        "organizacao": {
            "id": org.id,
            "nome": org.nome,
            "slug": org.slug,
            "dominio_customizado": org.dominio_customizado,
            "subdominio_url": f"https://{org.slug}.nexuscodebrasil.com.br",
            "is_master": bool(org.is_master),
            "plano": org.plano,
            "status_assinatura": org.status_assinatura,
            "limite_usuarios": org.limite_usuarios,
            "limite_clientes": org.limite_clientes,
            "trial_ate": org.trial_ate.isoformat() if org.trial_ate else None,
            "vencimento_assinatura": org.vencimento_assinatura.isoformat() if org.vencimento_assinatura else None,
            "branding": branding,
            "modulos": modulos,
        },
        "kpi": kpi,
        "clientes": [ClienteOut.model_validate(c) for c in clientes],
        "usuarios": [UsuarioListOut.model_validate(u) for u in usuarios],
        "projetos": [ProjetoOut.model_validate(p) for p in projetos],
        "orcamentos": [SolicitacaoOut.model_validate(o) for o in orcamentos],
        "tarefas": [TarefaOut.model_validate(t) for t in tarefas],
        "propostas": [PropostaOut.model_validate(pr) for pr in propostas],
        "despesas": [DespesaOut.model_validate(d) for d in despesas],
        "contratos": [ContratoRecorrenteOut.model_validate(ct) for ct in contratos],
        "apontamentos": [ApontamentoHoraOut.model_validate(ap) for ap in apontamentos],
        "chamados": [ChamadoOut.model_validate(ch) for ch in chamados],
        "ativos": [AtivoInfraOut.model_validate(at) for at in ativos],
        "notificacoes": [NotificacaoOut.model_validate(n) for n in notificacoes],
        "empresa_config": ConfiguracaoEmpresaOut.model_validate(empresa_cfg) if empresa_cfg else None,
        "catalogo_servicos": _get_catalogo_servicos_empresa(empresa_cfg),
        "parametros_orcamento": _get_parametros_orcamento_empresa(empresa_cfg),
        "holerites": [HoleriteListOut.model_validate(h) for h in holerites],
        "informes": [InformeListOut.model_validate(i) for i in informes],
        "produtos_loja": [ProdutoLojaOut.model_validate(pl) for pl in produtos_loja],
        "pedidos_loja": [PedidoLojaOut.model_validate(ped) for ped in pedidos_loja],
        "reembolsos": [ReembolsoOut.model_validate(rb) for rb in reembolsos],
    }


@router.get("/bootstrap", tags=["Dashboard"])
def bootstrap_painel(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    try:
        return _executar_bootstrap_painel(db, usuario)
    except HTTPException:
        raise
    except Exception as boot_err:
        print(f"[Bootstrap Auto-Heal Retry] {boot_err}")
        db.rollback()
        ensure_db_initialized(force_sync=True)
        return _executar_bootstrap_painel(db, usuario)


@router.get("/dashboard/resumo", tags=["Dashboard"])
def resumo_dashboard(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    return bootstrap_painel(db=db, usuario=usuario)["kpi"]


# ==================== PORTAL DO CLIENTE: BOOTSTRAP & WORKFLOWS ====================
@router.get("/portal/bootstrap", tags=["Portal Cliente"])
def bootstrap_portal_cliente(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    org_id = usuario.organizacao_id
    org = _get_org_or_404(db, org_id)
    branding = _parse_json_dict(org.branding_json, DEFAULT_BRANDING_MASTER)
    modulos = _parse_json_dict(org.modulos_json, DEFAULT_MODULOS_TENANT) if not org.is_master else dict(DEFAULT_MODULOS_TENANT)

    cliente = _obter_cliente_do_usuario(db, usuario)
    empresa_cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org_id).first()

    orcamentos = (
        db.query(SolicitacaoOrcamento)
        .filter(
            SolicitacaoOrcamento.organizacao_id == org_id,
            SolicitacaoOrcamento.email == usuario.email,
        )
        .order_by(SolicitacaoOrcamento.criado_em.desc())
        .all()
    )

    projetos = []
    tarefas = []
    faturas = []
    propostas = []
    chamados = []

    if cliente:
        projetos = db.query(Projeto).filter(Projeto.organizacao_id == org_id, Projeto.cliente_id == cliente.id).order_by(Projeto.criado_em.desc()).all()
        proj_ids = [p.id for p in projetos]
        if proj_ids:
            tarefas = db.query(Tarefa).filter(Tarefa.organizacao_id == org_id, Tarefa.projeto_id.in_(proj_ids)).order_by(Tarefa.id.asc()).all()
        faturas = (
            db.query(Fatura)
            .options(defer(Fatura.comprovante_data))
            .filter(Fatura.organizacao_id == org_id, Fatura.cliente_id == cliente.id)
            .order_by(Fatura.vencimento.asc())
            .all()
        )
        propostas = db.query(PropostaComercial).filter(PropostaComercial.organizacao_id == org_id, PropostaComercial.cliente_id == cliente.id).order_by(PropostaComercial.criado_em.desc()).all()
        chamados = db.query(ChamadoSuporte).filter(ChamadoSuporte.organizacao_id == org_id, ChamadoSuporte.cliente_id == cliente.id).order_by(ChamadoSuporte.criado_em.desc()).all()

    notificacoes = (
        db.query(Notificacao)
        .filter(
            Notificacao.organizacao_id == org_id,
            or_(
                Notificacao.usuario_id == usuario.id,
                Notificacao.perfil_destino == "cliente",
            ),
        )
        .order_by(Notificacao.criado_em.desc())
        .limit(25)
        .all()
    )

    pagamento_info = {
        "empresa": empresa_cfg.razao_social if empresa_cfg else org.nome,
        "cnpj": empresa_cfg.cnpj if empresa_cfg else "",
        "banco": empresa_cfg.banco_nome if empresa_cfg else "",
        "agencia": empresa_cfg.agencia if empresa_cfg else "",
        "conta": empresa_cfg.conta if empresa_cfg else "",
        "chave_pix": empresa_cfg.chave_pix if empresa_cfg else (empresa_cfg.email_financeiro if empresa_cfg else ""),
        "titular_pix": empresa_cfg.titular_pix if empresa_cfg else org.nome,
    }

    return {
        "organizacao": {
            "id": org.id,
            "nome": org.nome,
            "slug": org.slug,
            "is_master": bool(org.is_master),
            "branding": branding,
            "modulos": modulos,
        },
        "cliente": ClienteOut.model_validate(cliente) if cliente else None,
        "projetos": [ProjetoOut.model_validate(p) for p in projetos],
        "tarefas": [TarefaOut.model_validate(t) for t in tarefas],
        "faturas": [FaturaListOut.model_validate(f) for f in faturas],
        "propostas": [PropostaOut.model_validate(pr) for pr in propostas],
        "orcamentos": [SolicitacaoOut.model_validate(o) for o in orcamentos],
        "chamados": [ChamadoOut.model_validate(ch) for ch in chamados],
        "notificacoes": [NotificacaoOut.model_validate(n) for n in notificacoes],
        "pagamento_info": pagamento_info,
        "catalogo_servicos": [s for s in _get_catalogo_servicos_empresa(empresa_cfg) if s.get("ativo", True)],
        "parametros_orcamento": _get_parametros_orcamento_empresa(empresa_cfg),
    }


@router.post("/portal/propostas/{proposta_id}/decidir", response_model=PropostaOut, tags=["Portal Cliente"])
def cliente_decidir_proposta(
    proposta_id: int,
    dados: PropostaDecisaoCliente,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    cliente = _obter_cliente_do_usuario(db, usuario)
    prop = db.query(PropostaComercial).filter(
        PropostaComercial.id == proposta_id,
        PropostaComercial.organizacao_id == usuario.organizacao_id,
    ).first()
    if not prop or not cliente or prop.cliente_id != cliente.id:
        raise HTTPException(status_code=404, detail="Proposta comercial não encontrada.")

    prop.status = dados.decisao
    if dados.feedback:
        prop.feedback_cliente = dados.feedback.strip()

    if dados.decisao == "aprovada":
        prop.aprovado_por_cliente = usuario.nome
        prop.aprovado_em = datetime.utcnow()
        projeto = _converter_proposta_em_projeto(db, prop, usuario.nome)
        criar_notificacao(
            db,
            titulo=f"Proposta {prop.codigo} Aprovada!",
            mensagem=f"{cliente.nome_empresa} aprovou a proposta '{prop.titulo}'. Projeto #{projeto.id} ativado.",
            link_pagina="propostas",
            perfil_destino="equipe",
            org_id=usuario.organizacao_id,
        )
    else:
        criar_notificacao(
            db,
            titulo=f"Retorno na Proposta {prop.codigo}",
            mensagem=f"{cliente.nome_empresa} marcou a proposta como '{dados.decisao}'.",
            link_pagina="propostas",
            perfil_destino="equipe",
            org_id=usuario.organizacao_id,
        )

    registrar_log(db, usuario.nome, "DECISAO_PROPOSTA", f"Marcou proposta {prop.codigo} como {dados.decisao}", org_id=usuario.organizacao_id)
    db.commit()
    db.refresh(prop)
    return prop


@router.post("/portal/projetos/{projeto_id}/homologar", response_model=ProjetoOut, tags=["Portal Cliente"])
def cliente_homologar_projeto(
    projeto_id: int,
    dados: ProjetoHomologacaoCliente,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    cliente = _obter_cliente_do_usuario(db, usuario)
    proj = db.query(Projeto).filter(
        Projeto.id == projeto_id,
        Projeto.organizacao_id == usuario.organizacao_id,
    ).first()
    if not proj or not cliente or proj.cliente_id != cliente.id:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")

    proj.aprovacao_cliente_status = dados.decisao
    if dados.observacao:
        proj.aprovacao_cliente_obs = dados.observacao.strip()

    if dados.decisao == "aprovado":
        proj.aprovado_em = datetime.utcnow()
        proj.status = "concluido"
        proj.progresso = 100
    else:
        proj.status = "em_andamento"

    criar_notificacao(
        db,
        titulo=f"Homologação de Projeto ({dados.decisao.upper()})",
        mensagem=f"{cliente.nome_empresa} registrou parecer em '{proj.titulo}'.",
        link_pagina="projects",
        perfil_destino="equipe",
        org_id=usuario.organizacao_id,
    )
    registrar_log(db, usuario.nome, "HOMOLOGAR_PROJETO", f"Homologou projeto #{proj.id}: {dados.decisao}", org_id=usuario.organizacao_id)
    db.commit()
    db.refresh(proj)
    return proj


@router.post("/portal/faturas/{fatura_id}/comprovante", response_model=FaturaListOut, tags=["Portal Cliente"])
def cliente_anexar_comprovante_fatura(
    fatura_id: int,
    dados: FaturaComprovanteUpload,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    cliente = _obter_cliente_do_usuario(db, usuario)
    fat = db.query(Fatura).filter(
        Fatura.id == fatura_id,
        Fatura.organizacao_id == usuario.organizacao_id,
    ).first()
    if not fat or not cliente or fat.cliente_id != cliente.id:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")

    fat.comprovante_nome = dados.comprovante_nome
    fat.comprovante_data = dados.comprovante_data
    if dados.observacoes:
        fat.observacoes = dados.observacoes.strip()

    criar_notificacao(
        db,
        titulo="Comprovante de Pagamento Recebido",
        mensagem=f"{cliente.nome_empresa} enviou comprovante na fatura '{fat.descricao}'.",
        link_pagina="invoices",
        perfil_destino="equipe",
        org_id=usuario.organizacao_id,
    )
    registrar_log(db, usuario.nome, "COMPROVANTE_FATURA", f"Enviou comprovante na fatura #{fat.id}", org_id=usuario.organizacao_id)
    db.commit()
    db.refresh(fat)
    return fat


# ==================== PROPOSTAS COMERCIAIS ====================
@router.get("/propostas", response_model=List[PropostaOut], tags=["Propostas"])
def listar_propostas(db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    return db.query(PropostaComercial).filter(PropostaComercial.organizacao_id == equipe.organizacao_id).order_by(PropostaComercial.criado_em.desc()).all()


@router.post("/propostas", response_model=PropostaOut, status_code=201, tags=["Propostas"])
def criar_proposta(
    dados: PropostaCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    _verificar_modulo(org, "propostas")

    cliente = db.query(Cliente).filter(Cliente.id == dados.cliente_id, Cliente.organizacao_id == org.id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    seq = (db.query(func.count(PropostaComercial.id)).scalar() or 0) + 1
    codigo = f"PROP-{date.today().year}-{seq:04d}"

    prop = PropostaComercial(
        organizacao_id=org.id,
        codigo=codigo,
        cliente_id=dados.cliente_id,
        solicitacao_id=dados.solicitacao_id,
        criado_por_id=equipe.id,
        titulo=dados.titulo.strip(),
        escopo=dados.escopo.strip(),
        entregaveis_json=dados.entregaveis_json,
        valor_total=dados.valor_total,
        condicoes_pagamento=dados.condicoes_pagamento,
        parcelas=dados.parcelas,
        prazo_dias=dados.prazo_dias,
        validade_ate=dados.validade_ate,
        status=dados.status,
    )
    db.add(prop)
    db.flush()

    if cliente.status_funil == "lead":
        cliente.status_funil = "proposta"

    if dados.status == "enviada":
        if cliente.usuario_portal_id:
            criar_notificacao(
                db,
                titulo=f"Nova Proposta Comercial ({codigo})",
                mensagem=f"A proposta '{prop.titulo}' está disponível para análise e aprovação no seu portal.",
                link_pagina="proposals",
                usuario_id=cliente.usuario_portal_id,
                org_id=org.id,
            )
        if cliente.email:
            background_tasks.add_task(
                enviar_email,
                cliente.email,
                f"Proposta Comercial {codigo} — {org.nome}",
                f"<p>Olá, <b>{cliente.contato_nome}</b>. Sua proposta comercial <b>{codigo} ({prop.titulo})</b> já está disponível para análise e aprovação digital no Portal do Cliente.</p>",
            )

    registrar_log(db, equipe.nome, "CRIAR_PROPOSTA", f"Criou proposta {codigo} para {cliente.nome_empresa}", org_id=org.id)
    db.commit()
    db.refresh(prop)
    return prop


@router.patch("/propostas/{proposta_id}", response_model=PropostaOut, tags=["Propostas"])
def atualizar_proposta(
    proposta_id: int,
    dados: PropostaUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    prop = db.query(PropostaComercial).filter(
        PropostaComercial.id == proposta_id,
        PropostaComercial.organizacao_id == equipe.organizacao_id,
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(prop, campo, valor)

    if prop.status == "aprovada" and not prop.projeto_gerado_id:
        _converter_proposta_em_projeto(db, prop, equipe.nome)

    registrar_log(db, equipe.nome, "EDITAR_PROPOSTA", f"Atualizou proposta {prop.codigo}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(prop)
    return prop


@router.post("/propostas/{proposta_id}/aprovar", response_model=PropostaOut, tags=["Propostas"])
def aprovar_e_converter_proposta(
    proposta_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    prop = db.query(PropostaComercial).filter(
        PropostaComercial.id == proposta_id,
        PropostaComercial.organizacao_id == equipe.organizacao_id,
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")

    prop.status = "aprovada"
    prop.aprovado_por_cliente = prop.aprovado_por_cliente or f"Confirmado por {equipe.nome}"
    prop.aprovado_em = prop.aprovado_em or datetime.utcnow()
    _converter_proposta_em_projeto(db, prop, equipe.nome)

    db.commit()
    db.refresh(prop)
    return prop


@router.delete("/propostas/{proposta_id}", status_code=204, tags=["Propostas"])
def remover_proposta(
    proposta_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    prop = db.query(PropostaComercial).filter(
        PropostaComercial.id == proposta_id,
        PropostaComercial.organizacao_id == equipe.organizacao_id,
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")
    registrar_log(db, equipe.nome, "EXCLUIR_PROPOSTA", f"Removeu proposta {prop.codigo}", org_id=equipe.organizacao_id)
    db.delete(prop)
    db.commit()


# ==================== FINANCEIRO: DESPESAS, MRR, DRE & WEBHOOK ====================
@router.get("/despesas", response_model=List[DespesaOut], tags=["Financeiro"])
def listar_despesas(db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    return db.query(Despesa).filter(Despesa.organizacao_id == equipe.organizacao_id).order_by(Despesa.vencimento.asc()).all()


@router.post("/despesas", response_model=DespesaOut, status_code=201, tags=["Financeiro"])
def criar_despesa(
    dados: DespesaCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    _verificar_modulo(org, "despesas")
    desp = Despesa(**dados.model_dump(), organizacao_id=org.id)
    if desp.status == "pago":
        desp.pago_em = datetime.utcnow()
    db.add(desp)
    registrar_log(db, equipe.nome, "CRIAR_DESPESA", f"Lançou despesa '{desp.descricao}' ({desp.valor})", org_id=org.id)
    db.commit()
    db.refresh(desp)
    return desp


@router.patch("/despesas/{despesa_id}", response_model=DespesaOut, tags=["Financeiro"])
def atualizar_despesa(
    despesa_id: int,
    dados: DespesaUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    desp = db.query(Despesa).filter(Despesa.id == despesa_id, Despesa.organizacao_id == equipe.organizacao_id).first()
    if not desp:
        raise HTTPException(status_code=404, detail="Despesa não encontrada.")
    payload = dados.model_dump(exclude_unset=True)
    if payload.get("status") == "pago" and not desp.pago_em:
        desp.pago_em = datetime.utcnow()
    for campo, valor in payload.items():
        setattr(desp, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_DESPESA", f"Atualizou despesa #{despesa_id}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(desp)
    return desp


@router.delete("/despesas/{despesa_id}", status_code=204, tags=["Financeiro"])
def remover_despesa(
    despesa_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    desp = db.query(Despesa).filter(Despesa.id == despesa_id, Despesa.organizacao_id == admin.organizacao_id).first()
    if not desp:
        raise HTTPException(status_code=404, detail="Despesa não encontrada.")
    db.delete(desp)
    db.commit()


@router.get("/contratos-recorrentes", response_model=List[ContratoRecorrenteOut], tags=["Financeiro"])
def listar_contratos_recorrentes(db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    return db.query(ContratoRecorrente).filter(ContratoRecorrente.organizacao_id == equipe.organizacao_id).order_by(ContratoRecorrente.criado_em.desc()).all()


@router.post("/contratos-recorrentes", response_model=ContratoRecorrenteOut, status_code=201, tags=["Financeiro"])
def criar_contrato_recorrente(
    dados: ContratoRecorrenteCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    _verificar_modulo(org, "contratos")
    ct = ContratoRecorrente(**dados.model_dump(), organizacao_id=org.id)
    db.add(ct)
    registrar_log(db, equipe.nome, "CRIAR_CONTRATO_MRR", f"Criou assinatura recorrente '{ct.titulo}'", org_id=org.id)
    db.commit()
    db.refresh(ct)
    return ct


@router.patch("/contratos-recorrentes/{contrato_id}", response_model=ContratoRecorrenteOut, tags=["Financeiro"])
def atualizar_contrato_recorrente(
    contrato_id: int,
    dados: ContratoRecorrenteUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    ct = db.query(ContratoRecorrente).filter(ContratoRecorrente.id == contrato_id, ContratoRecorrente.organizacao_id == equipe.organizacao_id).first()
    if not ct:
        raise HTTPException(status_code=404, detail="Contrato recorrente não encontrado.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(ct, campo, valor)
    db.commit()
    db.refresh(ct)
    return ct


@router.delete("/contratos-recorrentes/{contrato_id}", status_code=204, tags=["Financeiro"])
def remover_contrato_recorrente(
    contrato_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    ct = db.query(ContratoRecorrente).filter(ContratoRecorrente.id == contrato_id, ContratoRecorrente.organizacao_id == admin.organizacao_id).first()
    if not ct:
        raise HTTPException(status_code=404, detail="Contrato recorrente não encontrado.")
    db.delete(ct)
    db.commit()


@router.post("/contratos-recorrentes/gerar-faturas-mes", tags=["Financeiro"])
def gerar_faturas_recorrentes_mes(
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org_id = equipe.organizacao_id
    hoje = date.today()
    comp = f"{hoje.month:02d}/{hoje.year}"
    ativos = db.query(ContratoRecorrente).filter(
        ContratoRecorrente.organizacao_id == org_id,
        ContratoRecorrente.status == "ativo",
    ).all()
    geradas = 0

    for ct in ativos:
        if ct.ultima_geracao == comp:
            continue
        proj_id = ct.projeto_id
        if not proj_id:
            proj = db.query(Projeto).filter(Projeto.organizacao_id == org_id, Projeto.cliente_id == ct.cliente_id).first()
            if not proj:
                proj = Projeto(
                    organizacao_id=org_id,
                    cliente_id=ct.cliente_id,
                    responsavel_id=equipe.id,
                    titulo=f"Contrato Recorrente — {ct.titulo}",
                    status="em_andamento",
                    progresso=100,
                    valor_total=ct.valor_mensal,
                    data_inicio=hoje,
                )
                db.add(proj)
                db.flush()
            proj_id = proj.id

        _, ult_dia = calendar.monthrange(hoje.year, hoje.month)
        dia_v = min(int(ct.dia_vencimento or 10), ult_dia)
        venc = date(hoje.year, hoje.month, dia_v)

        db.add(
            Fatura(
                organizacao_id=org_id,
                projeto_id=proj_id,
                cliente_id=ct.cliente_id,
                descricao=f"{ct.titulo} — Mensalidade {comp}",
                valor=ct.valor_mensal,
                status="pendente",
                forma_pagamento="PIX",
                vencimento=venc,
            )
        )
        ct.ultima_geracao = comp
        geradas += 1

    registrar_log(db, equipe.nome, "FATURAMENTO_MRR", f"Gerou {geradas} fatura(s) recorrente(s) da competência {comp}", org_id=org_id)
    db.commit()
    return {"competencia": comp, "faturas_geradas": geradas}


@router.get("/financeiro/dre", tags=["Financeiro"])
def obter_dre_gerencial(db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    if equipe.perfil != "admin":
        # Need to check colab perms
        org = _get_org_or_404(db, equipe.organizacao_id)
        emp_cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org.id).first()
        cbo_text = ((equipe.cbo_descricao or '') + ' ' + (equipe.cbo_codigo or '') + ' ' + (equipe.cargo or '')).lower()
        if not any(x in cbo_text for x in ["financeiro", "contabilidade", "2525", "2522", "4131"]):
            raise HTTPException(status_code=403, detail="Acesso restrito.")
        if emp_cfg and emp_cfg.permissoes_json:
            try:
                p = json.loads(emp_cfg.permissoes_json)
                if not p.get("colaborador", {}).get("financeiro_dre", False):
                    raise HTTPException(status_code=403, detail="Acesso restrito.")
            except:
                pass
    org_id = equipe.organizacao_id
    faturas = db.query(Fatura.valor, Fatura.status, Fatura.vencimento).filter(Fatura.organizacao_id == org_id).all()
    despesas = db.query(Despesa.valor, Despesa.status, Despesa.categoria, Despesa.vencimento).filter(Despesa.organizacao_id == org_id).all()
    holerites = db.query(Holerite.valor_liquido, Holerite.competencia).filter(Holerite.organizacao_id == org_id, Holerite.status == "pago").all()
    mrr_mensal = float(
        db.query(func.coalesce(func.sum(ContratoRecorrente.valor_mensal), 0))
        .filter(ContratoRecorrente.organizacao_id == org_id, ContratoRecorrente.status == "ativo")
        .scalar() or 0
    )

    receita_bruta_paga = sum(float(f.valor or 0) for f in faturas if f.status == "pago")
    receita_prevista_aberta = sum(float(f.valor or 0) for f in faturas if f.status in ("pendente", "atrasado"))
    despesas_operacionais_pagas = sum(float(d.valor or 0) for d in despesas if d.status == "pago")
    despesas_operacionais_abertas = sum(float(d.valor or 0) for d in despesas if d.status in ("pendente", "atrasado"))
    custo_folha_paga = sum(float(h.valor_liquido or 0) for h in holerites)

    por_categoria = {}
    for d in despesas:
        cat = d.categoria or "outros"
        por_categoria[cat] = round(por_categoria.get(cat, 0.0) + float(d.valor or 0), 2)
    if custo_folha_paga > 0:
        por_categoria["folha_salarios_holerites"] = round(custo_folha_paga, 2)

    hoje = date.today()
    meses_serie = []
    for offset in range(5, -1, -1):
        ano = hoje.year
        mes = hoje.month - offset
        while mes <= 0:
            mes += 12
            ano -= 1
        label = f"{mes:02d}/{ano}"
        rec_m = sum(
            float(f.valor or 0)
            for f in faturas
            if f.status == "pago" and f.vencimento and f.vencimento.year == ano and f.vencimento.month == mes
        )
        desp_m = sum(
            float(d.valor or 0)
            for d in despesas
            if d.status == "pago" and d.vencimento and d.vencimento.year == ano and d.vencimento.month == mes
        )
        folha_m = sum(
            float(h.valor_liquido or 0)
            for h in holerites
            if h.competencia == label
        )
        total_saida_m = round(desp_m + folha_m, 2)
        meses_serie.append({
            "competencia": label,
            "receitas": round(rec_m, 2),
            "despesas": total_saida_m,
            "resultado": round(rec_m - total_saida_m, 2),
        })

    total_despesas_pagas = round(despesas_operacionais_pagas + custo_folha_paga, 2)
    lucro_liquido = round(receita_bruta_paga - total_despesas_pagas, 2)
    margem_percent = round((lucro_liquido / receita_bruta_paga) * 100, 1) if receita_bruta_paga > 0 else 0.0

    return {
        "receita_bruta_paga": round(receita_bruta_paga, 2),
        "receita_prevista_aberta": round(receita_prevista_aberta, 2),
        "despesas_operacionais_pagas": round(despesas_operacionais_pagas, 2),
        "despesas_operacionais_abertas": round(despesas_operacionais_abertas, 2),
        "custo_folha_paga": round(custo_folha_paga, 2),
        "total_despesas_pagas": total_despesas_pagas,
        "lucro_liquido": lucro_liquido,
        "margem_percent": margem_percent,
        "mrr_mensal": round(mrr_mensal, 2),
        "por_categoria": por_categoria,
        "serie_mensal": meses_serie,
    }


@router.post("/webhook/pagamento", tags=["Financeiro"])
def webhook_compensacao_pagamento(req: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    webhook_secret = os.getenv("WEBHOOK_SECRET", "").strip()
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="WEBHOOK_SECRET não configurado no servidor.")

    provided_secret = (req.headers.get("X-Webhook-Secret") or req.query_params.get("secret") or "").strip()
    if not hmac.compare_digest(provided_secret, webhook_secret):
        raise HTTPException(status_code=401, detail="Assinatura de webhook inválida ou ausente.")

    fatura_id = (req.query_params.get("fatura_id") or "").strip()
    status_pg = (req.query_params.get("status") or "").strip()
    if not fatura_id.isdigit() or not status_pg:
        raise HTTPException(status_code=400, detail="Parâmetros fatura_id (numérico) e status são obrigatórios.")

    fatura = db.query(Fatura).filter(Fatura.id == int(fatura_id)).first()
    if not fatura:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")

    if status_pg == "paid" and fatura.status != "pago":
        fatura.status = "pago"
        fatura.pago_em = datetime.utcnow()
        fatura.forma_pagamento = "Gateway/Webhook"

        pedido = db.query(PedidoLoja).filter(PedidoLoja.fatura_gerada_id == fatura.id).first()
        if pedido:
            pedido.status = "pago"

        registrar_log(db, "Webhook Gateway", "BAIXA_FATURA_AUTO", f"Fatura #{fatura.id} compensada automaticamente.", org_id=fatura.organizacao_id)
        db.commit()
        db.refresh(fatura)
        _notificar_pagamento_fatura_confirmado(db, fatura, background_tasks)

    return {"ok": True, "fatura_id": fatura.id, "status": fatura.status}


# ==================== LOJA VIRTUAL (SITE -> CRM & FATURAMENTO) ====================
@router.post("/public/loja/pedidos", response_model=PedidoLojaOut, status_code=201, tags=["Loja"])
def registrar_pedido_loja(dados: PedidoLojaCreate, req: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    org = _resolver_org_por_request(req, db)
    cliente = db.query(Cliente).filter(Cliente.organizacao_id == org.id, Cliente.email == dados.email_comprador).first()
    if not cliente:
        cliente = Cliente(
            organizacao_id=org.id,
            nome_empresa=dados.nome_comprador.strip(),
            contato_nome=dados.nome_comprador.strip(),
            email=dados.email_comprador,
            telefone=dados.telefone_comprador,
            status_funil="lead",
            origem="Loja Virtual",
        )
        db.add(cliente)
        db.flush()

    seq = (db.query(func.count(PedidoLoja.id)).scalar() or 0) + 1
    codigo_pedido = f"STORE-{date.today().year}-{seq:05d}"

    pedido = PedidoLoja(
        organizacao_id=org.id,
        codigo=codigo_pedido,
        cliente_id=cliente.id,
        nome_comprador=dados.nome_comprador.strip(),
        email_comprador=dados.email_comprador,
        telefone_comprador=dados.telefone_comprador,
        itens_json=dados.itens_json,
        subtotal=dados.subtotal,
        desconto=dados.desconto,
        frete=dados.frete,
        valor_total=dados.valor_total,
        status="aguardando_pagamento",
    )
    db.add(pedido)
    db.flush()

    fatura = Fatura(
        organizacao_id=org.id,
        projeto_id=None,
        cliente_id=cliente.id,
        descricao=f"Pedido Loja {codigo_pedido}",
        valor=pedido.valor_total,
        status="pendente",
        forma_pagamento="PIX",
        vencimento=date.today() + timedelta(days=2),
    )
    db.add(fatura)
    db.flush()
    pedido.fatura_gerada_id = fatura.id

    cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org.id).first()
    background_tasks.add_task(
        enviar_email,
        pedido.email_comprador,
        f"Pedido {pedido.codigo} - {org.nome}",
        f"<p>Olá, <b>{pedido.nome_comprador}</b>. Seu pedido <b>{pedido.codigo}</b> (R$ {pedido.valor_total}) foi registrado. Chave PIX: <b>{cfg.chave_pix if cfg else 'contato@nexuscodebrasil.com.br'}</b>.</p>",
    )
    criar_notificacao(db, "Novo Pedido na Loja", f"Pedido {pedido.codigo} (R$ {pedido.valor_total}) registrado.", "invoices", None, "equipe", org_id=org.id)
    registrar_log(db, pedido.nome_comprador, "NOVO_PEDIDO_LOJA", f"Pedido {pedido.codigo} criado.", org_id=org.id)
    db.commit()
    db.refresh(pedido)
    return pedido


@router.get("/pedidos-loja", response_model=List[PedidoLojaOut], tags=["Loja"])
def listar_pedidos_loja(db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    return db.query(PedidoLoja).filter(PedidoLoja.organizacao_id == equipe.organizacao_id).order_by(PedidoLoja.criado_em.desc()).all()


@router.patch("/pedidos-loja/{pedido_id}", response_model=PedidoLojaOut, tags=["Loja"])
def atualizar_pedido_loja(pedido_id: int, dados: PedidoLojaUpdate, db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    ped = db.query(PedidoLoja).filter(PedidoLoja.id == pedido_id, PedidoLoja.organizacao_id == equipe.organizacao_id).first()
    if not ped:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    ped.status = dados.status
    registrar_log(db, equipe.nome, "EDITAR_PEDIDO_LOJA", f"Atualizou pedido {ped.codigo} para {dados.status}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(ped)
    return ped


# ==================== VITRINE PÚBLICA, LOJA & PLANOS SAAS (SITE <-> PAINEL) ====================
_SITE_CONFIG_CACHE = {"data": None, "ts": 0.0}


def _slugify_produto(texto: str) -> str:
    norm = unicodedata.normalize("NFKD", texto or "produto").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", norm.lower()).strip("-")
    return slug or "produto"


@router.get("/public/site-config", tags=["Site & Loja"])
def obter_configuracao_publica_site(db: Session = Depends(get_db)):
    now_ts = datetime.utcnow().timestamp()
    if _SITE_CONFIG_CACHE["data"] is not None and (now_ts - _SITE_CONFIG_CACHE["ts"]) < 20:
        return _SITE_CONFIG_CACHE["data"]

    master_org = db.query(Organizacao).filter(Organizacao.is_master == True).first()
    master_id = master_org.id if master_org else 1

    cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == master_id).first()
    produtos = (
        db.query(ProdutoLoja)
        .filter(ProdutoLoja.organizacao_id == master_id, ProdutoLoja.ativo == True)
        .order_by(ProdutoLoja.ordem.asc(), ProdutoLoja.id.asc())
        .all()
    )
    planos = (
        db.query(PlanoSaas)
        .filter(PlanoSaas.ativo == True)
        .order_by(PlanoSaas.ordem.asc(), PlanoSaas.id.asc())
        .all()
    )

    cidade = (cfg.cidade or "").strip() if cfg else "Aracruz"
    estado = (cfg.estado or "").strip() if cfg else "ES"
    endereco = (cfg.endereco or "").strip() if cfg else ""
    if cidade and estado:
        localizacao = f"{cidade}, {estado} - Brasil"
    elif endereco:
        localizacao = endereco
    else:
        localizacao = "Aracruz, ES - Brasil"

    payload = {
        "empresa": {
            "nome_fantasia": cfg.nome_fantasia if cfg else "Nexus Code Brasil",
            "razao_social": cfg.razao_social if cfg else "Nexus Code Brasil Tecnologia Ltda",
            "email": (cfg.email_financeiro or "contato@nexuscodebrasil.com.br") if cfg else "contato@nexuscodebrasil.com.br",
            "telefone": (cfg.telefone or "(27) 99999-9999") if cfg else "(27) 99999-9999",
            "endereco": endereco,
            "cidade": cidade,
            "estado": estado,
            "localizacao": localizacao,
            "chave_pix": (cfg.chave_pix or "contato@nexuscodebrasil.com.br") if cfg else "contato@nexuscodebrasil.com.br",
        },
        "produtos": [ProdutoLojaOut.model_validate(p).model_dump(mode="json") for p in produtos],
        "planos_saas": [PlanoSaasOut.model_validate(pl).model_dump(mode="json") for pl in planos],
        "catalogo_servicos": [s for s in _get_catalogo_servicos_empresa(cfg) if s.get("ativo", True)],
        "parametros_orcamento": _get_parametros_orcamento_empresa(cfg),
    }
    _SITE_CONFIG_CACHE["data"] = payload
    _SITE_CONFIG_CACHE["ts"] = now_ts
    return payload


@router.get("/loja/produtos", response_model=List[ProdutoLojaOut], tags=["Site & Loja"])
def listar_produtos_loja_admin(db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    return db.query(ProdutoLoja).filter(ProdutoLoja.organizacao_id == equipe.organizacao_id).order_by(ProdutoLoja.ordem.asc(), ProdutoLoja.id.asc()).all()


@router.post("/loja/produtos", response_model=ProdutoLojaOut, status_code=201, tags=["Site & Loja"])
def criar_produto_loja(
    dados: ProdutoLojaCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org_id = equipe.organizacao_id
    base_slug = _slugify_produto(dados.slug or dados.nome)
    slug = base_slug
    idx = 2
    while db.query(ProdutoLoja.id).filter(ProdutoLoja.organizacao_id == org_id, ProdutoLoja.slug == slug).first():
        slug = f"{base_slug}-{idx}"
        idx += 1

    payload = dados.model_dump()
    payload["slug"] = slug
    prod = ProdutoLoja(**payload, organizacao_id=org_id)
    db.add(prod)
    registrar_log(db, equipe.nome, "CRIAR_PRODUTO_LOJA", f"Adicionou produto '{prod.nome}' na loja", org_id=org_id)
    db.commit()
    db.refresh(prod)
    _SITE_CONFIG_CACHE["data"] = None
    return prod


@router.patch("/loja/produtos/{produto_id}", response_model=ProdutoLojaOut, tags=["Site & Loja"])
def atualizar_produto_loja(
    produto_id: int,
    dados: ProdutoLojaUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    prod = db.query(ProdutoLoja).filter(ProdutoLoja.id == produto_id, ProdutoLoja.organizacao_id == equipe.organizacao_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(prod, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_PRODUTO_LOJA", f"Atualizou produto '{prod.nome}' (#{produto_id})", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(prod)
    _SITE_CONFIG_CACHE["data"] = None
    return prod


@router.delete("/loja/produtos/{produto_id}", status_code=204, tags=["Site & Loja"])
def remover_produto_loja(
    produto_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    prod = db.query(ProdutoLoja).filter(ProdutoLoja.id == produto_id, ProdutoLoja.organizacao_id == admin.organizacao_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_PRODUTO_LOJA", f"Removeu produto '{prod.nome}'", org_id=admin.organizacao_id)
    db.delete(prod)
    db.commit()
    _SITE_CONFIG_CACHE["data"] = None


# ==================== TIMESHEET & RENTABILIDADE DE PROJETOS ====================
@router.get("/timesheet", response_model=List[ApontamentoHoraOut], tags=["Timesheet"])
def listar_apontamentos_horas(
    projeto_id: Optional[int] = None,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    q = db.query(ApontamentoHora).filter(ApontamentoHora.organizacao_id == equipe.organizacao_id)
    if projeto_id:
        q = q.filter(ApontamentoHora.projeto_id == projeto_id)
    return q.order_by(ApontamentoHora.data_trabalho.desc(), ApontamentoHora.id.desc()).all()


@router.post("/timesheet", response_model=ApontamentoHoraOut, status_code=201, tags=["Timesheet"])
def registrar_apontamento_hora(
    dados: ApontamentoHoraCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    _verificar_modulo(org, "timesheet")
    target_uid = dados.usuario_id if (equipe.perfil == "admin" and dados.usuario_id) else equipe.id
    colab = db.query(Usuario.id, Usuario.salario_base, Usuario.carga_horaria_diaria).filter(
        Usuario.id == target_uid,
        Usuario.organizacao_id == org.id,
    ).first()
    if not colab:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")

    sal = float(colab.salario_base or 0)
    carga = float(colab.carga_horaria_diaria or 8.0)
    divisor = 220.0 if abs(carga - 8.0) < 0.01 else max(1.0, carga * 27.5)
    custo_hora = round(sal / divisor, 2) if sal > 0 else 50.0

    ap = ApontamentoHora(
        organizacao_id=org.id,
        projeto_id=dados.projeto_id,
        tarefa_id=dados.tarefa_id,
        usuario_id=target_uid,
        data_trabalho=dados.data_trabalho,
        horas=dados.horas,
        descricao=dados.descricao.strip(),
        faturavel=dados.faturavel,
        custo_hora_snapshot=Decimal(str(custo_hora)),
    )
    db.add(ap)
    registrar_log(db, equipe.nome, "APONTAR_HORAS", f"Registrou {dados.horas}h no projeto #{dados.projeto_id}", org_id=org.id)
    db.commit()
    db.refresh(ap)
    return ap


@router.delete("/timesheet/{apontamento_id}", status_code=204, tags=["Timesheet"])
def remover_apontamento_hora(
    apontamento_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    ap = db.query(ApontamentoHora).filter(ApontamentoHora.id == apontamento_id, ApontamentoHora.organizacao_id == equipe.organizacao_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="Apontamento não encontrado.")
    if equipe.perfil != "admin" and ap.usuario_id != equipe.id:
        raise HTTPException(status_code=403, detail="Você só pode excluir seus próprios apontamentos.")
    db.delete(ap)
    db.commit()


# ==================== CENTRAL DE SUPORTE & CHAMADOS ====================
def _append_mensagem_chamado(chamado: ChamadoSuporte, autor_nome: str, autor_perfil: str, texto: str, anexo_nome: Optional[str] = None, anexo_data: Optional[str] = None):
    msgs = []
    if chamado.mensagens_json:
        try:
            parsed = json.loads(chamado.mensagens_json)
            if isinstance(parsed, list):
                msgs = parsed
        except Exception:
            pass
    msgs.append({
        "id": int(datetime.utcnow().timestamp() * 1000),
        "autor": autor_nome,
        "perfil": autor_perfil,
        "texto": texto.strip(),
        "anexo_nome": anexo_nome,
        "anexo_data": anexo_data,
        "criado_em": datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M"),
    })
    chamado.mensagens_json = json.dumps(msgs, ensure_ascii=False)
    chamado.atualizado_em = datetime.utcnow()


@router.get("/chamados", response_model=List[ChamadoOut], tags=["Chamados"])
def listar_chamados_equipe(db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    return db.query(ChamadoSuporte).filter(ChamadoSuporte.organizacao_id == equipe.organizacao_id).order_by(ChamadoSuporte.criado_em.desc()).all()


@router.post("/chamados", response_model=ChamadoOut, status_code=201, tags=["Chamados"])
def criar_chamado_equipe(
    dados: ChamadoCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    _verificar_modulo(org, "chamados")
    if not dados.cliente_id:
        raise HTTPException(status_code=400, detail="Selecione o cliente vinculado ao chamado.")
    cliente = db.query(Cliente).filter(Cliente.id == dados.cliente_id, Cliente.organizacao_id == org.id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    seq = (db.query(func.count(ChamadoSuporte.id)).scalar() or 0) + 1
    protocolo = f"CHM-{date.today().year}-{seq:05d}"

    ch = ChamadoSuporte(
        organizacao_id=org.id,
        protocolo=protocolo,
        cliente_id=dados.cliente_id,
        projeto_id=dados.projeto_id,
        aberto_por_id=equipe.id,
        responsavel_id=dados.responsavel_id or equipe.id,
        titulo=dados.titulo.strip(),
        categoria=dados.categoria,
        prioridade=dados.prioridade,
        status="aberto",
        sla_horas=dados.sla_horas,
        descricao=dados.descricao.strip(),
    )
    _append_mensagem_chamado(ch, equipe.nome, equipe.perfil, dados.descricao, dados.anexo_nome, dados.anexo_data)
    db.add(ch)
    registrar_log(db, equipe.nome, "ABRIR_CHAMADO", f"Abriu chamado {protocolo} ({ch.titulo})", org_id=org.id)
    db.commit()
    db.refresh(ch)
    return ch


@router.post("/chamados/{chamado_id}/mensagens", response_model=ChamadoOut, tags=["Chamados"])
def responder_chamado_equipe(
    chamado_id: int,
    dados: ChamadoMensagemCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    ch = db.query(ChamadoSuporte).filter(ChamadoSuporte.id == chamado_id, ChamadoSuporte.organizacao_id == equipe.organizacao_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")

    _append_mensagem_chamado(ch, equipe.nome, equipe.perfil, dados.texto, dados.anexo_nome, dados.anexo_data)
    if dados.novo_status:
        ch.status = dados.novo_status
    elif ch.status == "aberto":
        ch.status = "em_analise"

    cliente = db.query(Cliente).filter(Cliente.id == ch.cliente_id).first()
    if cliente and cliente.usuario_portal_id:
        criar_notificacao(
            db,
            titulo=f"Atualização no Chamado {ch.protocolo}",
            mensagem=f"{equipe.nome} respondeu no chamado '{ch.titulo}'.",
            link_pagina="tickets",
            usuario_id=cliente.usuario_portal_id,
            org_id=equipe.organizacao_id,
        )

    registrar_log(db, equipe.nome, "RESPONDER_CHAMADO", f"Respondeu no chamado {ch.protocolo}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(ch)
    return ch


@router.patch("/chamados/{chamado_id}", response_model=ChamadoOut, tags=["Chamados"])
def atualizar_chamado_equipe(
    chamado_id: int,
    dados: ChamadoUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    ch = db.query(ChamadoSuporte).filter(ChamadoSuporte.id == chamado_id, ChamadoSuporte.organizacao_id == equipe.organizacao_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(ch, campo, valor)
    ch.atualizado_em = datetime.utcnow()
    db.commit()
    db.refresh(ch)
    return ch


@router.delete("/chamados/{chamado_id}", status_code=204, tags=["Chamados"])
def remover_chamado_equipe(
    chamado_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    ch = db.query(ChamadoSuporte).filter(ChamadoSuporte.id == chamado_id, ChamadoSuporte.organizacao_id == admin.organizacao_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")
    db.delete(ch)
    db.commit()


@router.post("/portal/chamados", response_model=ChamadoOut, status_code=201, tags=["Portal Cliente"])
def abrir_chamado_cliente(
    dados: ChamadoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    cliente = _garantir_cliente_para_portal(db, usuario)
    seq = (db.query(func.count(ChamadoSuporte.id)).scalar() or 0) + 1
    protocolo = f"CHM-{date.today().year}-{seq:05d}"

    sla_map = {"critica": 4, "alta": 8, "media": 24, "baixa": 48}
    ch = ChamadoSuporte(
        organizacao_id=usuario.organizacao_id,
        protocolo=protocolo,
        cliente_id=cliente.id,
        projeto_id=dados.projeto_id,
        aberto_por_id=usuario.id,
        titulo=dados.titulo.strip(),
        categoria=dados.categoria,
        prioridade=dados.prioridade,
        status="aberto",
        sla_horas=sla_map.get(dados.prioridade, 24),
        descricao=dados.descricao.strip(),
    )
    _append_mensagem_chamado(ch, usuario.nome, "cliente", dados.descricao, dados.anexo_nome, dados.anexo_data)
    db.add(ch)

    criar_notificacao(
        db,
        titulo=f"Novo Chamado {protocolo}",
        mensagem=f"{cliente.nome_empresa} abriu o chamado '{ch.titulo}' ({ch.prioridade.upper()}).",
        link_pagina="chamados",
        perfil_destino="equipe",
        org_id=usuario.organizacao_id,
    )
    registrar_log(db, usuario.nome, "ABRIR_CHAMADO_PORTAL", f"Cliente abriu chamado {protocolo}", org_id=usuario.organizacao_id)
    db.commit()
    db.refresh(ch)
    return ch


@router.post("/portal/chamados/{chamado_id}/mensagens", response_model=ChamadoOut, tags=["Portal Cliente"])
def mensagem_chamado_cliente(
    chamado_id: int,
    dados: ChamadoMensagemCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    cliente = _obter_cliente_do_usuario(db, usuario)
    ch = db.query(ChamadoSuporte).filter(ChamadoSuporte.id == chamado_id, ChamadoSuporte.organizacao_id == usuario.organizacao_id).first()
    if not ch or not cliente or ch.cliente_id != cliente.id:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")

    _append_mensagem_chamado(ch, usuario.nome, "cliente", dados.texto, dados.anexo_nome, dados.anexo_data)
    if ch.status in ("aguardando_cliente", "resolvido"):
        ch.status = "em_analise"

    criar_notificacao(
        db,
        titulo=f"Nova Mensagem no Chamado {ch.protocolo}",
        mensagem=f"{cliente.nome_empresa} respondeu no ticket '{ch.titulo}'.",
        link_pagina="chamados",
        perfil_destino="equipe",
        org_id=usuario.organizacao_id,
    )
    db.commit()
    db.refresh(ch)
    return ch


# ==================== ATIVOS, DOMÍNIOS & CRON DE VENCIMENTOS ====================
@router.get("/ativos", response_model=List[AtivoInfraOut], tags=["Infraestrutura"])
def listar_ativos_infra(db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    return db.query(AtivoInfra).filter(AtivoInfra.organizacao_id == equipe.organizacao_id).order_by(AtivoInfra.data_vencimento.asc().nullslast()).all()


@router.post("/ativos", response_model=AtivoInfraOut, status_code=201, tags=["Infraestrutura"])
def criar_ativo_infra(
    dados: AtivoInfraCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    _verificar_modulo(org, "ativos")
    ativo = AtivoInfra(**dados.model_dump(), organizacao_id=org.id)
    db.add(ativo)
    registrar_log(db, equipe.nome, "CRIAR_ATIVO", f"Cadastrou ativo '{ativo.nome}' ({ativo.tipo})", org_id=org.id)
    db.commit()
    db.refresh(ativo)
    return ativo


@router.patch("/ativos/{ativo_id}", response_model=AtivoInfraOut, tags=["Infraestrutura"])
def atualizar_ativo_infra(
    ativo_id: int,
    dados: AtivoInfraUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    ativo = db.query(AtivoInfra).filter(AtivoInfra.id == ativo_id, AtivoInfra.organizacao_id == equipe.organizacao_id).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(ativo, campo, valor)
    db.commit()
    db.refresh(ativo)
    return ativo


@router.delete("/ativos/{ativo_id}", status_code=204, tags=["Infraestrutura"])
def remover_ativo_infra(
    ativo_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    ativo = db.query(AtivoInfra).filter(AtivoInfra.id == ativo_id, AtivoInfra.organizacao_id == admin.organizacao_id).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    db.delete(ativo)
    db.commit()


@router.get("/cron/verificar-vencimentos", tags=["Infraestrutura"])
def cron_verificar_vencimentos(req: Request, db: Session = Depends(get_db)):
    cron_secret = os.getenv("CRON_SECRET", "").strip()
    if cron_secret:
        auth_header = (req.headers.get("Authorization") or "").strip()
        expected = f"Bearer {cron_secret}"
        if not hmac.compare_digest(auth_header, expected):
            raise HTTPException(status_code=401, detail="Token de execução Cron inválido.")

    hoje = date.today()
    ativos = db.query(AtivoInfra).filter(AtivoInfra.status.in_(["ativo", "vencendo"])).all()
    notificados = 0
    for a in ativos:
        if not a.data_vencimento:
            continue
        delta = (a.data_vencimento - hoje).days
        if delta < 0 and a.status != "expirado":
            a.status = "expirado"
            criar_notificacao(db, f"Ativo Expirado: {a.nome}", f"O ativo {a.tipo} expirou em {a.data_vencimento}.", "ativos", None, "equipe", org_id=a.organizacao_id)
            notificados += 1
        elif delta in (30, 15, 5):
            a.status = "vencendo"
            criar_notificacao(db, f"Renovação Próxima: {a.nome}", f"O ativo {a.tipo} vence em {delta} dias ({a.data_vencimento}).", "ativos", None, "equipe", org_id=a.organizacao_id)
            notificados += 1

    faturas_vencidas = db.query(Fatura).filter(Fatura.status == "pendente", Fatura.vencimento < hoje).all()
    for fat in faturas_vencidas:
        fat.status = "atrasado"

    # Verifica trials expirados
    trials_expirados = db.query(Organizacao).filter(
        Organizacao.is_master == False,
        Organizacao.status_assinatura == "trial",
        Organizacao.trial_ate != None,
        Organizacao.trial_ate < hoje,
    ).all()
    for org_exp in trials_expirados:
        org_exp.status_assinatura = "inadimplente"

    db.commit()
    return {
        "ok": True,
        "ativos_alertados": notificados,
        "faturas_vencidas_atualizadas": len(faturas_vencidas),
        "trials_atualizados": len(trials_expirados),
    }


# ==================== REEMBOLSOS (RH AVANÇADO) ====================
@router.get("/reembolsos", response_model=List[ReembolsoOut], tags=["RH"])
def listar_reembolsos(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    query = db.query(ReembolsoDespesa).filter(ReembolsoDespesa.organizacao_id == usuario.organizacao_id)
    if usuario.perfil != "admin":
        query = query.filter(ReembolsoDespesa.usuario_id == usuario.id)
    return query.order_by(ReembolsoDespesa.criado_em.desc()).all()


@router.post("/reembolsos", response_model=ReembolsoOut, status_code=201, tags=["RH"])
def solicitar_reembolso(dados: ReembolsoCreate, db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    r = ReembolsoDespesa(**dados.model_dump(), organizacao_id=equipe.organizacao_id, usuario_id=equipe.id)
    db.add(r)
    criar_notificacao(db, "Nova Solicitação de Reembolso", f"{equipe.nome} solicitou R$ {r.valor} para {r.descricao}.", "despesas", None, "admin", org_id=equipe.organizacao_id)
    registrar_log(db, equipe.nome, "SOLICITAR_REEMBOLSO", f"Solicitou reembolso de R$ {r.valor}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(r)
    return r


@router.patch("/reembolsos/{reembolso_id}", response_model=ReembolsoOut, tags=["RH"])
def julgar_reembolso(reembolso_id: int, dados: ReembolsoUpdate, db: Session = Depends(get_db), admin: Usuario = Depends(exigir_admin)):
    r = db.query(ReembolsoDespesa).filter(ReembolsoDespesa.id == reembolso_id, ReembolsoDespesa.organizacao_id == admin.organizacao_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reembolso não encontrado.")
    r.status = dados.status
    if dados.observacoes_gestor:
        r.observacoes_gestor = dados.observacoes_gestor
    if dados.status == "aprovado" and not r.despesa_gerada_id:
        desp = Despesa(
            organizacao_id=admin.organizacao_id,
            descricao=f"Reembolso: {r.descricao}",
            categoria="folha_rh",
            projeto_id=r.projeto_id,
            valor=r.valor,
            vencimento=date.today(),
            status="pendente",
        )
        db.add(desp)
        db.flush()
        r.despesa_gerada_id = desp.id
    criar_notificacao(db, f"Reembolso {dados.status.capitalize()}", f"Sua solicitação de R$ {r.valor} foi {dados.status}.", "dashboard", r.usuario_id, None, org_id=admin.organizacao_id)
    registrar_log(db, admin.nome, "JULGAR_REEMBOLSO", f"Marcou reembolso #{r.id} como {dados.status}", org_id=admin.organizacao_id)
    db.commit()
    db.refresh(r)
    return r


# ==================== CONFIGURAÇÕES DA EMPRESA, PERMISSÕES & WHITE-LABEL ====================
@router.get("/empresa", response_model=ConfiguracaoEmpresaOut, tags=["Empresa"])
def obter_configuracoes_empresa(db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == equipe.organizacao_id).first()
    if not cfg:
        org = db.query(Organizacao).filter(Organizacao.id == equipe.organizacao_id).first()
        cfg = ConfiguracaoEmpresa(
            organizacao_id=equipe.organizacao_id,
            razao_social=org.nome if org else "Empresa",
            nome_fantasia=org.nome if org else "Empresa",
            permissoes_json=json.dumps(DEFAULT_PERMISSOES),
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.put("/empresa", response_model=ConfiguracaoEmpresaOut, tags=["Empresa"])
def salvar_configuracoes_empresa(
    dados: ConfiguracaoEmpresaUpdate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == admin.organizacao_id).first()
    if not cfg:
        cfg = ConfiguracaoEmpresa(organizacao_id=admin.organizacao_id)
        db.add(cfg)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(cfg, campo, valor)
    cfg.atualizado_em = datetime.utcnow()
    registrar_log(db, admin.nome, "CONFIG_EMPRESA", "Atualizou parâmetros institucionais, bancários e permissões.", org_id=admin.organizacao_id)
    db.commit()
    if admin.organizacao_id == 1:
        _SITE_CONFIG_CACHE["data"] = None
    db.refresh(cfg)
    return cfg


@router.put("/empresa/branding", tags=["Empresa"])
def salvar_branding_empresa(
    dados: BrandingUpdate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    org = db.query(Organizacao).filter(Organizacao.id == admin.organizacao_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada.")

    payload_brand = dados.model_dump(exclude_unset=True)
    if "dominio_customizado" in payload_brand:
        raw_dom = payload_brand.pop("dominio_customizado")
        dom_validado = _validar_dominio_customizado(raw_dom, org.plano, is_master=bool(org.is_master))
        if dom_validado and db.query(Organizacao.id).filter(func.lower(Organizacao.dominio_customizado) == dom_validado, Organizacao.id != org.id).first():
            raise HTTPException(status_code=400, detail="Este domínio corporativo já está vinculado a outro ambiente na plataforma.")
        org.dominio_customizado = dom_validado

    cur_brand = _parse_json_dict(org.branding_json, DEFAULT_BRANDING_MASTER)
    for k, v in payload_brand.items():
        if v is not None:
            cur_brand[k] = v

    org.branding_json = json.dumps(cur_brand, ensure_ascii=False)
    registrar_log(db, admin.nome, "WHITE_LABEL_BRANDING", "Atualizou identidade visual White-Label e configurações de domínio do portal.", org_id=org.id)
    db.commit()
    return {"ok": True, "branding": cur_brand, "dominio_customizado": org.dominio_customizado}


# ==================== CENTRAL DE NOTIFICAÇÕES ====================
@router.patch("/notificacoes/{notif_id}/lida", tags=["Notificações"])
def marcar_notificacao_lida(
    notif_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    n = db.query(Notificacao).filter(Notificacao.id == notif_id, Notificacao.organizacao_id == usuario.organizacao_id).first()
    if n:
        n.lida = True
        db.commit()
    return {"ok": True}


@router.post("/notificacoes/ler-todas", tags=["Notificações"])
def marcar_todas_notificacoes_lidas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if usuario.perfil == "cliente":
        db.query(Notificacao).filter(
            Notificacao.organizacao_id == usuario.organizacao_id,
            or_(Notificacao.usuario_id == usuario.id, Notificacao.perfil_destino == "cliente"),
            Notificacao.lida == False,
        ).update({"lida": True}, synchronize_session=False)
    else:
        db.query(Notificacao).filter(
            Notificacao.organizacao_id == usuario.organizacao_id,
            or_(
                Notificacao.usuario_id == usuario.id,
                Notificacao.perfil_destino == "equipe",
                Notificacao.perfil_destino == usuario.perfil,
            ),
            Notificacao.lida == False,
        ).update({"lida": True}, synchronize_session=False)
    db.commit()
    return {"ok": True}


# ==================== USUÁRIOS ====================
@router.get("/usuarios", response_model=List[UsuarioListOut], tags=["Usuários"])
def listar_usuarios(db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    return (
        db.query(Usuario)
        .options(defer(Usuario.foto_url), defer(Usuario.resumo_profissional))
        .filter(Usuario.organizacao_id == equipe.organizacao_id)
        .order_by(Usuario.nome)
        .all()
    )


@router.post("/usuarios", response_model=UsuarioListOut, status_code=201, tags=["Usuários"])
def criar_usuario(
    dados: UsuarioCreate,
    req: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    org = _get_org_or_404(db, admin.organizacao_id)
    if dados.perfil in ("admin", "colaborador") and not org.is_master:
        qtd_staff = (
            db.query(func.count(Usuario.id))
            .filter(Usuario.organizacao_id == org.id, Usuario.perfil != "cliente", Usuario.ativo == True)
            .scalar() or 0
        )
        if qtd_staff >= org.limite_usuarios:
            raise HTTPException(
                status_code=403,
                detail=f"Limite de {org.limite_usuarios} usuário(s) internos do plano {org.plano.upper()} atingido.",
            )

    if db.query(Usuario.id).filter(Usuario.organizacao_id == org.id, func.lower(Usuario.email) == dados.email.strip().lower()).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado neste ambiente.")
    is_client_role = dados.perfil == "cliente"
    cargo_final = None if is_client_role else (dados.cargo or dados.cbo_descricao)

    if admin.perfil != 'admin' and dados.perfil == 'admin':
        raise HTTPException(status_code=403, detail="Apenas administradores podem criar perfis Admin.")
    if dados.perfil == 'cliente':
         # Se esta vindo pela tela de RH, bloqueia o Cliente Externo
         if req.url.path == '/api/usuarios' and 'colaboradores' not in str(req.url):
              pass # this is fine, it handles both. But we must assure RBAC
    
    chave_pix = dados.pix_chave
    if not is_client_role and dados.pix_tipo:
        if dados.pix_tipo == 'cpf' and dados.cpf and not chave_pix: chave_pix = dados.cpf
        elif dados.pix_tipo == 'email' and not chave_pix: chave_pix = dados.email
        elif dados.pix_tipo == 'telefone' and dados.telefone and not chave_pix: chave_pix = dados.telefone
        
    novo = Usuario(
        organizacao_id=org.id,
        nome=dados.nome,
        email=dados.email.strip().lower(),
        senha_hash=gerar_hash_senha(dados.senha),
        perfil=dados.perfil,
        ativo=dados.ativo,
        cpf=dados.cpf,
        cargo=cargo_final,
        cbo_codigo=None if is_client_role else dados.cbo_codigo,
        cbo_descricao=None if is_client_role else dados.cbo_descricao,
        tipo_contrato=None if is_client_role else (dados.tipo_contrato or "clt_fixo"),
        data_nascimento=dados.data_nascimento,
        data_contratacao=None if is_client_role else dados.data_contratacao,
        data_fim_contrato=None if is_client_role else dados.data_fim_contrato,
        carga_horaria_diaria=None if is_client_role else (dados.carga_horaria_diaria if dados.carga_horaria_diaria is not None else 8.00),
        horario_entrada=None if is_client_role else (dados.horario_entrada or "08:00"),
        horario_saida=None if is_client_role else (dados.horario_saida or "17:00"),
        dependentes_irrf=0 if is_client_role else (dados.dependentes_irrf or 0),
        vale_transporte=False if is_client_role else bool(dados.vale_transporte),
        valor_vt_mensal=0 if is_client_role else (dados.valor_vt_mensal or 0),
        salario_base=0 if is_client_role else (dados.salario_base or 0),
        pix_tipo=None if is_client_role else (dados.pix_tipo or "cpf"),
        pix_chave=None if is_client_role else chave_pix,
        telefone=dados.telefone,
    )
    db.add(novo)
    db.flush()
    if is_client_role:
        _garantir_cliente_para_portal(db, novo)
    registrar_log(db, admin.nome, "CRIAR_USUARIO", f"Criou {'acesso cliente' if is_client_role else 'colaborador'} {novo.email} ({novo.perfil})", org_id=org.id)
    db.commit()
    db.refresh(novo)
    return novo


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioListOut, tags=["Usuários"])
def atualizar_usuario(
    usuario_id: int,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.organizacao_id == admin.organizacao_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    payload = dados.model_dump(exclude_unset=True)
    
    if "perfil" in payload and payload["perfil"] != usuario.perfil:
        if admin.perfil != 'admin':
            raise HTTPException(status_code=403, detail="Você não tem permissão para alterar níveis de acesso (RBAC).")
        if payload["perfil"] == 'cliente' and usuario.perfil != 'cliente':
            raise HTTPException(status_code=400, detail="Não é permitido rebaixar um Colaborador para Cliente Externo. Exclua a conta e crie no Portal do Cliente.")

    if "senha" in payload:
        nova_senha = payload.pop("senha")
        if nova_senha:
            usuario.senha_hash = gerar_hash_senha(nova_senha)
    for campo, valor in payload.items():
        setattr(usuario, campo, valor)

    if usuario.perfil == "cliente":
        usuario.tipo_contrato = None
        usuario.cbo_codigo = None
        usuario.cbo_descricao = None
        usuario.cargo = None
        usuario.carga_horaria_diaria = None
        usuario.horario_entrada = None
        usuario.horario_saida = None
        usuario.dependentes_irrf = 0
        usuario.vale_transporte = False
        usuario.valor_vt_mensal = 0
        usuario.salario_base = 0
        usuario.pix_tipo = None
        usuario.pix_chave = None
        usuario.data_contratacao = None
        usuario.data_fim_contrato = None
        _garantir_cliente_para_portal(db, usuario)
    else:
        if not usuario.tipo_contrato:
            usuario.tipo_contrato = "clt_fixo"
        if usuario.carga_horaria_diaria is None:
            usuario.carga_horaria_diaria = Decimal("8.00")
        if not usuario.horario_entrada:
            usuario.horario_entrada = "08:00"
        if not usuario.horario_saida:
            usuario.horario_saida = "17:00"

    registrar_log(db, admin.nome, "EDITAR_USUARIO", f"Atualizou usuário #{usuario_id} ({usuario.perfil})", org_id=admin.organizacao_id)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/usuarios/{usuario_id}", status_code=204, tags=["Usuários"])
def remover_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    if usuario_id == admin.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta.")
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.organizacao_id == admin.organizacao_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_USUARIO", f"Removeu usuário {usuario.email}", org_id=admin.organizacao_id)
    db.delete(usuario)
    db.commit()


# ==================== CLIENTES / LEADS ====================
@router.get("/clientes", response_model=List[ClienteOut], tags=["Clientes"])
def listar_clientes(
    status_funil: Optional[str] = None,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    query = db.query(Cliente).filter(Cliente.organizacao_id == equipe.organizacao_id)
    if status_funil:
        query = query.filter(Cliente.status_funil == status_funil)
    return query.order_by(Cliente.criado_em.desc()).all()


@router.post("/clientes", response_model=ClienteOut, status_code=201, tags=["Clientes"])
def criar_cliente(
    dados: ClienteCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    _verificar_modulo(org, "clientes")
    if not org.is_master:
        qtd_cli = db.query(func.count(Cliente.id)).filter(Cliente.organizacao_id == org.id).scalar() or 0
        if qtd_cli >= org.limite_clientes:
            raise HTTPException(
                status_code=403,
                detail=f"Limite de {org.limite_clientes} clientes/leads do plano {org.plano.upper()} atingido.",
            )

    cliente = Cliente(**dados.model_dump(), organizacao_id=org.id)
    db.add(cliente)
    registrar_log(db, equipe.nome, "CRIAR_CLIENTE", f"Cadastrou {cliente.nome_empresa}", org_id=org.id)
    db.commit()
    db.refresh(cliente)
    return cliente


@router.patch("/clientes/{cliente_id}", response_model=ClienteOut, tags=["Clientes"])
def atualizar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.organizacao_id == equipe.organizacao_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(cliente, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_CLIENTE", f"Atualizou cliente #{cliente_id}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(cliente)
    return cliente


@router.delete("/clientes/{cliente_id}", status_code=204, tags=["Clientes"])
def remover_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.organizacao_id == admin.organizacao_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_CLIENTE", f"Removeu cliente {cliente.nome_empresa}", org_id=admin.organizacao_id)
    db.delete(cliente)
    db.commit()


# ==================== PROJETOS ====================
@router.get("/projetos", response_model=List[ProjetoOut], tags=["Projetos"])
def listar_projetos(
    status_projeto: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    query = db.query(Projeto).filter(Projeto.organizacao_id == usuario.organizacao_id)
    if usuario.perfil == "cliente":
        query = query.join(Cliente).filter(
            (Cliente.usuario_portal_id == usuario.id) | (Cliente.email == usuario.email)
        )
    if status_projeto:
        query = query.filter(Projeto.status == status_projeto)
    return query.order_by(Projeto.criado_em.desc()).all()




def _normalizar_url_homologacao_nexus(raw_url: Optional[str], fallback_slug: str) -> str:
    clean_slug = slugify_repo_name(fallback_slug)[:45] or "projeto"
    val = (raw_url or "").strip()
    if not val:
        return f"https://{clean_slug}.nexuscodebrasil.com.br"
    val_no_proto = re.sub(r"^https?://", "", val, flags=re.IGNORECASE).strip().rstrip("/")
    if "." not in val_no_proto:
        sub = slugify_repo_name(val_no_proto)[:45] or clean_slug
        return f"https://{sub}.nexuscodebrasil.com.br"
    if not re.match(r"^https?://", val, flags=re.IGNORECASE):
        return f"https://{val_no_proto}"
    return val

@router.post("/projetos", response_model=ProjetoOut, status_code=201, tags=["Projetos"])
def criar_projeto(
    dados: ProjetoCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    _verificar_modulo(org, "projetos")
    cliente = db.query(Cliente).filter(Cliente.id == dados.cliente_id, Cliente.organizacao_id == org.id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente informado não existe.")

    raw_payload = dados.model_dump()
    criar_no_github = bool(raw_payload.pop("criar_no_github", False))
    github_repo_nome = raw_payload.pop("github_repo_nome", None)
    github_template = raw_payload.pop("github_template", "fullstack")

    slug_base = github_repo_nome or raw_payload.get("titulo") or "projeto"
    raw_payload["url_homologacao"] = _normalizar_url_homologacao_nexus(raw_payload.get("url_homologacao"), slug_base)
    if raw_payload.get("url_producao") and not re.match(r"^https?://", raw_payload["url_producao"].strip(), flags=re.IGNORECASE):
        raw_payload["url_producao"] = "https://" + raw_payload["url_producao"].strip()

    projeto = Projeto(**raw_payload, organizacao_id=org.id)
    db.add(projeto)
    db.flush()

    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org.id).first())
    if criar_no_github and cfg and cfg.github_ativo and cfg.github_token:
        try:
            repo_res = github_criar_repositorio_empresa(
                token=cfg.github_token,
                org=cfg.github_org,
                repo_nome=github_repo_nome or projeto.titulo,
                descricao=projeto.descricao or f"Projeto {projeto.titulo} — Cliente {cliente.nome_empresa}",
                visibilidade=projeto.github_visibilidade or cfg.github_visibilidade_padrao or "private",
                template=github_template or "fullstack",
                empresa_nome=org.nome,
            )
            projeto.repositorio_url = repo_res["html_url"]
            projeto.github_repo_full_name = repo_res["full_name"]
            projeto.github_default_branch = repo_res["default_branch"]
            projeto.github_visibilidade = repo_res["visibilidade"]
            registrar_log(db, equipe.nome, "GITHUB_REPO_CRIADO", f"Repositório '{repo_res['full_name']}' criado no GitHub.", org_id=org.id)
        except Exception as gh_err:
            raise HTTPException(status_code=502, detail=f"Falha ao criar repositório no GitHub: {gh_err}")
    elif projeto.repositorio_url and not projeto.github_repo_full_name:
        extracted = extrair_repo_full_name(projeto.repositorio_url, cfg.github_org if cfg else None)
        if extracted:
            projeto.github_repo_full_name = extracted

    if cliente.usuario_portal_id:
        criar_notificacao(
            db,
            titulo="Novo Projeto Iniciado",
            mensagem=f"O projeto '{projeto.titulo}' já está disponível para acompanhamento no seu portal.",
            link_pagina="projects",
            usuario_id=cliente.usuario_portal_id,
            org_id=org.id,
        )
    registrar_log(db, equipe.nome, "CRIAR_PROJETO", f"Criou projeto '{projeto.titulo}'", org_id=org.id)
    db.commit()
    db.refresh(projeto)
    return projeto


@router.patch("/projetos/{projeto_id}", response_model=ProjetoOut, tags=["Projetos"])
def atualizar_projeto(
    projeto_id: int,
    dados: ProjetoUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    projeto = db.query(Projeto).filter(Projeto.id == projeto_id, Projeto.organizacao_id == equipe.organizacao_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    payload = dados.model_dump(exclude_unset=True)
    for campo, valor in payload.items():
        setattr(projeto, campo, valor)

    if payload.get("status") == "homologacao" or payload.get("aprovacao_cliente_status") == "aguardando_homologacao":
        projeto.aprovacao_cliente_status = "aguardando_homologacao"
        cliente = db.query(Cliente).filter(Cliente.id == projeto.cliente_id).first()
        if cliente and cliente.usuario_portal_id:
            criar_notificacao(
                db,
                titulo="Entrega Pronta para Homologação",
                mensagem=f"O projeto '{projeto.titulo}' foi liberado para sua validação no Portal do Cliente.",
                link_pagina="projects",
                usuario_id=cliente.usuario_portal_id,
                org_id=equipe.organizacao_id,
            )

    registrar_log(db, equipe.nome, "EDITAR_PROJETO", f"Atualizou projeto #{projeto_id}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(projeto)
    return projeto


@router.delete("/projetos/{projeto_id}", status_code=204, tags=["Projetos"])
def remover_projeto(
    projeto_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    projeto = db.query(Projeto).filter(Projeto.id == projeto_id, Projeto.organizacao_id == admin.organizacao_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_PROJETO", f"Removeu projeto '{projeto.titulo}'", org_id=admin.organizacao_id)
    db.delete(projeto)
    db.commit()


# ==================== TAREFAS ====================
@router.get("/tarefas", response_model=List[TarefaOut], tags=["Tarefas"])
def listar_todas_tarefas(
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    return db.query(Tarefa).filter(Tarefa.organizacao_id == equipe.organizacao_id).order_by(Tarefa.criado_em.desc()).all()


@router.get("/projetos/{projeto_id}/tarefas", response_model=List[TarefaOut], tags=["Tarefas"])
def listar_tarefas_projeto(
    projeto_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    proj = db.query(Projeto).filter(Projeto.id == projeto_id, Projeto.organizacao_id == usuario.organizacao_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    if usuario.perfil == "cliente":
        cli_usr = _obter_cliente_do_usuario(db, usuario)
        if not cli_usr or proj.cliente_id != cli_usr.id:
            raise HTTPException(status_code=403, detail="Acesso negado às tarefas deste projeto.")
    return db.query(Tarefa).filter(Tarefa.projeto_id == projeto_id, Tarefa.organizacao_id == usuario.organizacao_id).all()


@router.post("/tarefas", response_model=TarefaOut, status_code=201, tags=["Tarefas"])
def criar_tarefa(
    dados: TarefaCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    _verificar_modulo(org, "tarefas")
    tarefa = Tarefa(**dados.model_dump(), organizacao_id=org.id)
    db.add(tarefa)
    registrar_log(db, equipe.nome, "CRIAR_TAREFA", f"Criou tarefa '{tarefa.titulo}'", org_id=org.id)
    db.commit()
    db.refresh(tarefa)
    return tarefa


@router.patch("/tarefas/{tarefa_id}", response_model=TarefaOut, tags=["Tarefas"])
def atualizar_tarefa(
    tarefa_id: int,
    dados: TarefaUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    tarefa = db.query(Tarefa).filter(Tarefa.id == tarefa_id, Tarefa.organizacao_id == equipe.organizacao_id).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(tarefa, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_TAREFA", f"Atualizou tarefa #{tarefa_id}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(tarefa)
    return tarefa


@router.delete("/tarefas/{tarefa_id}", status_code=204, tags=["Tarefas"])
def remover_tarefa(
    tarefa_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    tarefa = db.query(Tarefa).filter(Tarefa.id == tarefa_id, Tarefa.organizacao_id == equipe.organizacao_id).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    db.delete(tarefa)
    db.commit()


# ==================== INTERAÇÕES CRM ====================
@router.get("/clientes/{cliente_id}/interacoes", response_model=List[InteracaoOut], tags=["CRM"])
def listar_interacoes(
    cliente_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    return (
        db.query(Interacao)
        .filter(Interacao.cliente_id == cliente_id, Interacao.organizacao_id == equipe.organizacao_id)
        .order_by(Interacao.data_interacao.desc())
        .all()
    )


@router.post("/interacoes", response_model=InteracaoOut, status_code=201, tags=["CRM"])
def registrar_interacao(
    dados: InteracaoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    interacao = Interacao(**dados.model_dump(), organizacao_id=usuario.organizacao_id, usuario_id=usuario.id)
    db.add(interacao)
    db.commit()
    db.refresh(interacao)
    return interacao


# ==================== FATURAS / FINANCEIRO ====================
@router.get("/faturas", response_model=List[FaturaListOut], tags=["Financeiro"])
def listar_faturas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    query = db.query(Fatura).options(defer(Fatura.comprovante_data)).filter(Fatura.organizacao_id == usuario.organizacao_id)
    if usuario.perfil == "cliente":
        query = query.join(Cliente).filter(
            (Cliente.usuario_portal_id == usuario.id) | (Cliente.email == usuario.email)
        )
    return query.order_by(Fatura.vencimento.asc()).all()


@router.get("/faturas/{fatura_id}/recibo-digital", tags=["Financeiro"])
def obter_recibo_digital_fatura(
    fatura_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    fat = db.query(Fatura).filter(
        Fatura.id == fatura_id,
        Fatura.organizacao_id == usuario.organizacao_id,
    ).first()
    if not fat:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")

    if usuario.perfil == "cliente":
        cli_usr = _obter_cliente_do_usuario(db, usuario)
        if not cli_usr or fat.cliente_id != cli_usr.id:
            raise HTTPException(status_code=403, detail="Acesso negado a esta fatura.")

    if fat.status != "pago":
        raise HTTPException(status_code=400, detail="O comprovante oficial é gerado automaticamente após a confirmação do pagamento.")

    if not fat.mp_status_detalhe and (fat.mp_order_id or fat.mp_payment_id):
        cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == fat.organizacao_id).first())
        if cfg and cfg.mp_access_token:
            try:
                info = (
                    mp_consultar_order(cfg.mp_access_token, fat.mp_order_id)
                    if fat.mp_order_id
                    else mp_consultar_pagamento(cfg.mp_access_token, fat.mp_payment_id)
                )
                if info.get("status_detail"):
                    fat.mp_status_detalhe = info.get("status_detail")
                if info.get("payment_id") and not fat.mp_payment_id:
                    fat.mp_payment_id = str(info.get("payment_id"))
                if info.get("ticket_url") and not fat.mp_checkout_url:
                    fat.mp_checkout_url = info.get("ticket_url")
                db.commit()
                db.refresh(fat)
            except Exception:
                pass

    return _gerar_dados_recibo_fatura(db, fat)


@router.get("/faturas/{fatura_id}/comprovante", tags=["Financeiro"])
def baixar_comprovante_fatura(
    fatura_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    fat = db.query(Fatura.id, Fatura.cliente_id, Fatura.comprovante_nome, Fatura.comprovante_data).filter(
        Fatura.id == fatura_id,
        Fatura.organizacao_id == usuario.organizacao_id,
    ).first()
    if not fat:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    if usuario.perfil == "cliente":
        cli_usr = _obter_cliente_do_usuario(db, usuario)
        if not cli_usr or fat.cliente_id != cli_usr.id:
            raise HTTPException(status_code=403, detail="Acesso negado a este comprovante.")
    if not fat.comprovante_data:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado.")
    return {"id": fat.id, "comprovante_nome": fat.comprovante_nome, "comprovante_data": fat.comprovante_data}


@router.post("/faturas", response_model=FaturaListOut, status_code=201, tags=["Financeiro"])
def criar_fatura(
    dados: FaturaCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    org = _get_org_or_404(db, equipe.organizacao_id)
    _verificar_modulo(org, "faturas")
    fatura = Fatura(**dados.model_dump(), organizacao_id=org.id)
    db.add(fatura)
    cliente = db.query(Cliente).filter(Cliente.id == dados.cliente_id, Cliente.organizacao_id == org.id).first()
    if cliente and cliente.usuario_portal_id:
        criar_notificacao(
            db,
            titulo="Nova Fatura Emitida",
            mensagem=f"Fatura '{fatura.descricao}' disponível no seu portal.",
            link_pagina="invoices",
            usuario_id=cliente.usuario_portal_id,
            org_id=org.id,
        )
    registrar_log(db, equipe.nome, "CRIAR_FATURA", f"Lançou fatura '{fatura.descricao}'", org_id=org.id)
    db.commit()
    db.refresh(fatura)
    return fatura


@router.patch("/faturas/{fatura_id}", response_model=FaturaListOut, tags=["Financeiro"])
def atualizar_fatura(
    fatura_id: int,
    dados: FaturaUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    fatura = db.query(Fatura).filter(Fatura.id == fatura_id, Fatura.organizacao_id == equipe.organizacao_id).first()
    if not fatura:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    was_paid = fatura.status == "pago"
    payload = dados.model_dump(exclude_unset=True)
    if payload.get("status") == "pago" and not fatura.pago_em:
        fatura.pago_em = datetime.utcnow()
    for campo, valor in payload.items():
        setattr(fatura, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_FATURA", f"Atualizou fatura #{fatura_id}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(fatura)
    if not was_paid and fatura.status == "pago":
        _notificar_pagamento_fatura_confirmado(db, fatura, background_tasks)
    return fatura


@router.delete("/faturas/{fatura_id}", status_code=204, tags=["Financeiro"])
def remover_fatura(
    fatura_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    fatura = db.query(Fatura).filter(Fatura.id == fatura_id, Fatura.organizacao_id == admin.organizacao_id).first()
    if not fatura:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    db.delete(fatura)
    db.commit()


# ==================== FOLHA DE PAGAMENTO, HOLERITES & INFORME DE RENDIMENTOS ====================
@router.get("/holerites", response_model=List[HoleriteListOut], tags=["Holerite"])
def listar_holerites(
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    query = db.query(Holerite).options(defer(Holerite.anexo_data)).filter(Holerite.organizacao_id == usuario.organizacao_id)
    if usuario.perfil != "admin":
        query = query.filter(Holerite.usuario_id == usuario.id)
    elif usuario_id:
        query = query.filter(Holerite.usuario_id == usuario_id)
    return query.order_by(Holerite.criado_em.desc()).all()


@router.get("/holerites/{holerite_id}/anexo", tags=["Holerite"])
def baixar_anexo_holerite(
    holerite_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    h = db.query(Holerite.id, Holerite.usuario_id, Holerite.anexo_nome, Holerite.anexo_data).filter(
        Holerite.id == holerite_id,
        Holerite.organizacao_id == usuario.organizacao_id,
    ).first()
    if not h or not h.anexo_data:
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    if usuario.perfil != "admin" and h.usuario_id != usuario.id:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return {"id": h.id, "anexo_nome": h.anexo_nome, "anexo_data": h.anexo_data}


@router.post("/holerites", response_model=HoleriteListOut, status_code=201, tags=["Holerite"])
def criar_holerite(
    dados: HoleriteCreate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    org = _get_org_or_404(db, admin.organizacao_id)
    _verificar_modulo(org, "holerite")
    colaborador = db.query(Usuario).filter(Usuario.id == dados.usuario_id, Usuario.organizacao_id == org.id).first()
    if not colaborador:
        raise HTTPException(status_code=404, detail="Colaborador informado não encontrado.")

    payload = dados.model_dump()
    liquido_calc = (payload["salario_base"] or 0) + (payload["proventos"] or 0) - (payload["descontos"] or 0)
    if not payload.get("valor_liquido") or payload["valor_liquido"] == 0:
        payload["valor_liquido"] = liquido_calc

    item = Holerite(**payload, organizacao_id=org.id, publicado_por=admin.nome)
    db.add(item)
    registrar_log(
        db,
        admin.nome,
        "PUBLICAR_HOLERITE",
        f"Publicou holerite ({item.competencia} - {item.tipo}) para {colaborador.nome}",
        org_id=org.id,
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/holerites/{holerite_id}", response_model=HoleriteListOut, tags=["Holerite"])
def atualizar_holerite(
    holerite_id: int,
    dados: HoleriteUpdate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    item = db.query(Holerite).filter(Holerite.id == holerite_id, Holerite.organizacao_id == admin.organizacao_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Holerite não encontrado.")

    payload = dados.model_dump(exclude_unset=True)
    for campo, valor in payload.items():
        setattr(item, campo, valor)

    if any(k in payload for k in ("salario_base", "proventos", "descontos")) and "valor_liquido" not in payload:
        item.valor_liquido = (item.salario_base or 0) + (item.proventos or 0) - (item.descontos or 0)

    registrar_log(db, admin.nome, "EDITAR_HOLERITE", f"Atualizou holerite #{holerite_id} ({item.competencia})", org_id=admin.organizacao_id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/holerites/{holerite_id}", status_code=204, tags=["Holerite"])
def remover_holerite(
    holerite_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    item = db.query(Holerite).filter(Holerite.id == holerite_id, Holerite.organizacao_id == admin.organizacao_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Holerite não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_HOLERITE", f"Removeu holerite #{holerite_id} ({item.competencia})", org_id=admin.organizacao_id)
    db.delete(item)
    db.commit()


@router.get("/informes-rendimentos", response_model=List[InformeListOut], tags=["Holerite"])
def listar_informes_rendimentos(
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    query = db.query(InformeRendimento).options(defer(InformeRendimento.anexo_data)).filter(InformeRendimento.organizacao_id == usuario.organizacao_id)
    if usuario.perfil != "admin":
        query = query.filter(InformeRendimento.usuario_id == usuario.id)
    elif usuario_id:
        query = query.filter(InformeRendimento.usuario_id == usuario_id)
    return query.order_by(InformeRendimento.ano_calendario.desc(), InformeRendimento.criado_em.desc()).all()


@router.get("/informes-rendimentos/{informe_id}/anexo", tags=["Holerite"])
def baixar_anexo_informe(
    informe_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    inf = db.query(InformeRendimento.id, InformeRendimento.usuario_id, InformeRendimento.anexo_nome, InformeRendimento.anexo_data).filter(
        InformeRendimento.id == informe_id,
        InformeRendimento.organizacao_id == usuario.organizacao_id,
    ).first()
    if not inf or not inf.anexo_data:
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    if usuario.perfil != "admin" and inf.usuario_id != usuario.id:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return {"id": inf.id, "anexo_nome": inf.anexo_nome, "anexo_data": inf.anexo_data}


@router.post("/informes-rendimentos", response_model=InformeListOut, status_code=201, tags=["Holerite"])
def criar_informe_rendimento(
    dados: InformeRendimentoCreate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    colaborador = db.query(Usuario).filter(Usuario.id == dados.usuario_id, Usuario.organizacao_id == admin.organizacao_id).first()
    if not colaborador:
        raise HTTPException(status_code=404, detail="Colaborador informado não encontrado.")

    item = InformeRendimento(**dados.model_dump(), organizacao_id=admin.organizacao_id, publicado_por=admin.nome)
    db.add(item)
    registrar_log(
        db,
        admin.nome,
        "PUBLICAR_INFORME_IR",
        f"Publicou Informe de Rendimentos ({item.ano_calendario}) para {colaborador.nome}",
        org_id=admin.organizacao_id,
    )
    db.commit()
    db.refresh(item)
    return item


@router.delete("/informes-rendimentos/{informe_id}", status_code=204, tags=["Holerite"])
def remover_informe_rendimento(
    informe_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    item = db.query(InformeRendimento).filter(InformeRendimento.id == informe_id, InformeRendimento.organizacao_id == admin.organizacao_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Informe de rendimentos não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_INFORME_IR", f"Removeu Informe de Rendimentos #{informe_id}", org_id=admin.organizacao_id)
    db.delete(item)
    db.commit()


# ==================== CBO, GESTÃO DE PONTO & CÁLCULO AUTOMÁTICO DE FOLHA ====================
def _agora_brasilia() -> datetime:
    tz_br = timezone(timedelta(hours=-3))
    return datetime.now(tz_br)


@router.get("/cbo/buscar", tags=["RH & Ponto"])
def api_buscar_cbo(
    q: Optional[str] = "",
    _: Usuario = Depends(exigir_equipe),
):
    return buscar_cbos(q or "")


@router.get("/ponto", response_model=List[RegistroPontoOut], tags=["RH & Ponto"])
def listar_registros_ponto(
    competencia: Optional[str] = None,
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    query = db.query(RegistroPonto).filter(RegistroPonto.organizacao_id == usuario.organizacao_id)
    if usuario.perfil != "admin":
        query = query.filter(RegistroPonto.usuario_id == usuario.id)
    elif usuario_id:
        query = query.filter(RegistroPonto.usuario_id == usuario_id)

    if competencia and "/" in competencia:
        try:
            mes_str, ano_str = competencia.strip().split("/")
            mes, ano = int(mes_str), int(ano_str)
            _, ult_dia = calendar.monthrange(ano, mes)
            query = query.filter(
                RegistroPonto.data_ponto >= date(ano, mes, 1),
                RegistroPonto.data_ponto <= date(ano, mes, ult_dia),
            )
        except ValueError:
            pass

    return query.order_by(RegistroPonto.data_ponto.desc(), RegistroPonto.id.desc()).all()


@router.post("/ponto/bater", response_model=RegistroPontoOut, tags=["RH & Ponto"])
def registrar_batida_ponto(
    dados: PontoBatidaRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    if usuario.perfil == "cliente":
        raise HTTPException(status_code=403, detail="Acesso restrito a colaboradores e administradores.")

    org = _get_org_or_404(db, usuario.organizacao_id)
    _verificar_modulo(org, "ponto")

    agora = _agora_brasilia()
    hoje = agora.date()
    hora_atual = dados.hora_manual.strip() if dados.hora_manual else agora.strftime("%H:%M")

    reg = (
        db.query(RegistroPonto)
        .filter(
            RegistroPonto.organizacao_id == org.id,
            RegistroPonto.usuario_id == usuario.id,
            RegistroPonto.data_ponto == hoje,
        )
        .first()
    )
    if not reg:
        reg = RegistroPonto(
            organizacao_id=org.id,
            usuario_id=usuario.id,
            data_ponto=hoje,
            tipo_dia="normal",
            status_ajuste="aprovado",
        )
        db.add(reg)

    campo = dados.tipo_batida
    if getattr(reg, campo):
        raise HTTPException(
            status_code=400,
            detail=f"A marcação '{campo.replace('_', ' ')}' já foi registrada hoje às {getattr(reg, campo)}. Utilize 'Solicitar Ajuste' caso precise corrigir.",
        )

    setattr(reg, campo, hora_atual)
    if dados.observacao:
        reg.observacao = dados.observacao.strip()
    reg.ip_registro = request.client.host if request.client else "web"

    calc = calcular_jornada_diaria(
        data_ponto=reg.data_ponto,
        entrada=reg.entrada,
        saida_almoco=reg.saida_almoco,
        retorno_almoco=reg.retorno_almoco,
        saida=reg.saida,
        carga_diaria_horas=float(usuario.carga_horaria_diaria or 8.0),
        tipo_dia=reg.tipo_dia,
    )
    reg.minutos_trabalhados = calc["minutos_trabalhados"]
    reg.minutos_extras_50 = calc["minutos_extras_50"]
    reg.minutos_extras_100 = calc["minutos_extras_100"]
    reg.minutos_atraso = calc["minutos_atraso"]
    reg.eh_feriado_ou_domingo = calc["eh_feriado_ou_domingo"]

    registrar_log(db, usuario.nome, "BATER_PONTO", f"Registrou {campo} às {hora_atual} ({hoje.isoformat()})", org_id=org.id)
    db.commit()
    db.refresh(reg)
    return reg


@router.post("/ponto/ajustes", response_model=RegistroPontoOut, tags=["RH & Ponto"])
def solicitar_ajuste_ponto(
    dados: PontoAjusteCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    if usuario.perfil == "cliente":
        raise HTTPException(status_code=403, detail="Acesso restrito à equipe.")

    org = _get_org_or_404(db, usuario.organizacao_id)
    _verificar_modulo(org, "ponto")

    reg = (
        db.query(RegistroPonto)
        .filter(
            RegistroPonto.organizacao_id == org.id,
            RegistroPonto.usuario_id == usuario.id,
            RegistroPonto.data_ponto == dados.data_ponto,
        )
        .first()
    )
    if not reg:
        reg = RegistroPonto(
            organizacao_id=org.id,
            usuario_id=usuario.id,
            data_ponto=dados.data_ponto,
            tipo_dia=dados.tipo_dia,
        )
        db.add(reg)

    ajuste_payload = {
        "entrada": dados.entrada or None,
        "saida_almoco": dados.saida_almoco or None,
        "retorno_almoco": dados.retorno_almoco or None,
        "saida": dados.saida or None,
        "tipo_dia": dados.tipo_dia,
    }

    if usuario.perfil == "admin":
        reg.entrada = ajuste_payload["entrada"]
        reg.saida_almoco = ajuste_payload["saida_almoco"]
        reg.retorno_almoco = ajuste_payload["retorno_almoco"]
        reg.saida = ajuste_payload["saida"]
        reg.tipo_dia = ajuste_payload["tipo_dia"]
        reg.status_ajuste = "aprovado"
        reg.justificativa_ajuste = dados.justificativa.strip()
        reg.ajuste_solicitado_json = None
        calc = calcular_jornada_diaria(
            data_ponto=reg.data_ponto,
            entrada=reg.entrada,
            saida_almoco=reg.saida_almoco,
            retorno_almoco=reg.retorno_almoco,
            saida=reg.saida,
            carga_diaria_horas=float(usuario.carga_horaria_diaria or 8.0),
            tipo_dia=reg.tipo_dia,
        )
        reg.minutos_trabalhados = calc["minutos_trabalhados"]
        reg.minutos_extras_50 = calc["minutos_extras_50"]
        reg.minutos_extras_100 = calc["minutos_extras_100"]
        reg.minutos_atraso = calc["minutos_atraso"]
        reg.eh_feriado_ou_domingo = calc["eh_feriado_ou_domingo"]
    else:
        reg.status_ajuste = "pendente_ajuste"
        reg.justificativa_ajuste = dados.justificativa.strip()
        reg.ajuste_solicitado_json = json.dumps(ajuste_payload, ensure_ascii=False)

    registrar_log(db, usuario.nome, "AJUSTE_PONTO", f"Solicitou ajuste de ponto em {dados.data_ponto.isoformat()}", org_id=org.id)
    db.commit()
    db.refresh(reg)
    return reg


@router.patch("/ponto/ajustes/{ponto_id}", response_model=RegistroPontoOut, tags=["RH & Ponto"])
def decidir_ajuste_ponto(
    ponto_id: int,
    dados: PontoAjusteDecisao,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    reg = db.query(RegistroPonto).filter(RegistroPonto.id == ponto_id, RegistroPonto.organizacao_id == admin.organizacao_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registro de ponto não encontrado.")

    colaborador = db.query(Usuario).filter(Usuario.id == reg.usuario_id).first()
    carga = float(colaborador.carga_horaria_diaria or 8.0) if colaborador else 8.0

    if dados.decisao == "aprovado":
        if reg.ajuste_solicitado_json:
            try:
                aj = json.loads(reg.ajuste_solicitado_json)
                reg.entrada = aj.get("entrada")
                reg.saida_almoco = aj.get("saida_almoco")
                reg.retorno_almoco = aj.get("retorno_almoco")
                reg.saida = aj.get("saida")
                reg.tipo_dia = aj.get("tipo_dia") or reg.tipo_dia
            except Exception:
                pass
        reg.status_ajuste = "aprovado"
        reg.ajuste_solicitado_json = None
        if dados.observacao_gestor:
            reg.observacao = dados.observacao_gestor.strip()

        calc = calcular_jornada_diaria(
            data_ponto=reg.data_ponto,
            entrada=reg.entrada,
            saida_almoco=reg.saida_almoco,
            retorno_almoco=reg.retorno_almoco,
            saida=reg.saida,
            carga_diaria_horas=carga,
            tipo_dia=reg.tipo_dia,
        )
        reg.minutos_trabalhados = calc["minutos_trabalhados"]
        reg.minutos_extras_50 = calc["minutos_extras_50"]
        reg.minutos_extras_100 = calc["minutos_extras_100"]
        reg.minutos_atraso = calc["minutos_atraso"]
        reg.eh_feriado_ou_domingo = calc["eh_feriado_ou_domingo"]
    else:
        reg.status_ajuste = "rejeitado"
        reg.ajuste_solicitado_json = None
        if dados.observacao_gestor:
            reg.observacao = dados.observacao_gestor.strip()

    registrar_log(
        db,
        admin.nome,
        "DECISAO_AJUSTE_PONTO",
        f"Marcou ajuste #{ponto_id} como {dados.decisao}",
        org_id=admin.organizacao_id,
    )
    db.commit()
    db.refresh(reg)
    return reg


@router.get("/folha/calcular", tags=["Holerite"])
def pre_calcular_folha_colaborador(
    usuario_id: int,
    competencia: str,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    colaborador = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.organizacao_id == admin.organizacao_id).first()
    if not colaborador:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")

    try:
        mes_str, ano_str = competencia.strip().split("/")
        mes, ano = int(mes_str), int(ano_str)
        _, ult_dia = calendar.monthrange(ano, mes)
    except ValueError:
        raise HTTPException(status_code=400, detail="Competência inválida. Use o formato MM/AAAA.")

    pontos = (
        db.query(RegistroPonto)
        .filter(
            RegistroPonto.organizacao_id == admin.organizacao_id,
            RegistroPonto.usuario_id == usuario_id,
            RegistroPonto.data_ponto >= date(ano, mes, 1),
            RegistroPonto.data_ponto <= date(ano, mes, ult_dia),
        )
        .all()
    )

    return calcular_holerite_automatico(colaborador, pontos, competencia)


@router.post("/holerites/gerar-automatico", tags=["Holerite"])
def gerar_holerite_automatico_endpoint(
    dados: GerarHoleriteAutoRequest,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    org = _get_org_or_404(db, admin.organizacao_id)
    _verificar_modulo(org, "holerite")

    try:
        mes_str, ano_str = dados.competencia.strip().split("/")
        mes, ano = int(mes_str), int(ano_str)
        _, ult_dia = calendar.monthrange(ano, mes)
    except ValueError:
        raise HTTPException(status_code=400, detail="Competência inválida. Utilize o formato MM/AAAA.")

    if dados.gerar_todos:
        colaboradores = (
            db.query(Usuario)
            .filter(Usuario.organizacao_id == org.id, Usuario.ativo == True, Usuario.perfil != "cliente")
            .order_by(Usuario.nome)
            .all()
        )
    else:
        if not dados.usuario_id:
            raise HTTPException(status_code=400, detail="Selecione um colaborador ou marque 'Gerar para toda a equipe'.")
        colab = db.query(Usuario).filter(Usuario.id == dados.usuario_id, Usuario.organizacao_id == org.id).first()
        if not colab:
            raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
        colaboradores = [colab]

    gerados = []
    dt_pag = dados.data_pagamento or date.today()

    for colab in colaboradores:
        pontos = (
            db.query(RegistroPonto)
            .filter(
                RegistroPonto.organizacao_id == org.id,
                RegistroPonto.usuario_id == colab.id,
                RegistroPonto.data_ponto >= date(ano, mes, 1),
                RegistroPonto.data_ponto <= date(ano, mes, ult_dia),
            )
            .all()
        )
        res = calcular_holerite_automatico(colab, pontos, dados.competencia.strip())

        obs_auto = (
            f"Cálculo automático via Gestão de Ponto ({res['dias_registrados_ponto']} dia(s), "
            f"Trabalhadas: {res['horas_trabalhadas_fmt']}, HE 50%: {res['horas_extras_50_fmt']}, "
            f"HE 100%: {res['horas_extras_100_fmt']})."
        )
        if dados.observacoes:
            obs_auto = f"{dados.observacoes.strip()} | {obs_auto}"

        item = Holerite(
            organizacao_id=org.id,
            usuario_id=colab.id,
            competencia=dados.competencia.strip(),
            tipo=dados.tipo,
            salario_base=res["salario_base"],
            proventos=res["proventos"],
            descricao_proventos=res["descricao_proventos"],
            descontos=res["descontos"],
            descricao_descontos=res["descricao_descontos"],
            valor_liquido=res["valor_liquido"],
            fgts_valor=res["fgts_valor"],
            data_pagamento=dt_pag,
            status=dados.status,
            observacoes=obs_auto,
            publicado_por=admin.nome,
        )
        db.add(item)
        gerados.append(item)

    registrar_log(
        db,
        admin.nome,
        "GERAR_FOLHA_AUTOMATICA",
        f"Gerou {len(gerados)} holerite(s) automático(s) da competência {dados.competencia}",
        org_id=org.id,
    )
    db.commit()
    for g in gerados:
        db.refresh(g)

    return {
        "gerados": len(gerados),
        "holerites": [HoleriteListOut.model_validate(g) for g in gerados],
    }


# ==================== MÓDULOS COMPLEMENTARES & AUDITORIA ====================
@router.get("/modulos/{modulo}", response_model=List[ModuloRegistroOut], tags=["Módulos"])
def listar_modulo(
    modulo: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    return (
        db.query(ModuloRegistro)
        .filter(ModuloRegistro.organizacao_id == usuario.organizacao_id, ModuloRegistro.modulo == modulo)
        .order_by(ModuloRegistro.criado_em.desc())
        .all()
    )


@router.post("/modulos/{modulo}", response_model=ModuloRegistroOut, status_code=201, tags=["Módulos"])
def criar_registro_modulo(
    modulo: str,
    dados: ModuloRegistroCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    item = ModuloRegistro(organizacao_id=usuario.organizacao_id, modulo=modulo, **dados.model_dump())
    db.add(item)
    registrar_log(db, usuario.nome, f"CRIAR_{modulo.upper()}", f"Criou '{item.titulo}'", org_id=usuario.organizacao_id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/modulos/{modulo}/{item_id}", status_code=204, tags=["Módulos"])
def remover_registro_modulo(
    modulo: str,
    item_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    item = db.query(ModuloRegistro).filter(
        ModuloRegistro.id == item_id,
        ModuloRegistro.organizacao_id == equipe.organizacao_id,
        ModuloRegistro.modulo == modulo,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    db.delete(item)
    db.commit()


@router.get("/auditoria", response_model=List[LogAuditoriaOut], tags=["Auditoria"])
def listar_auditoria(
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    return db.query(LogAuditoria).filter(LogAuditoria.organizacao_id == equipe.organizacao_id).order_by(LogAuditoria.criado_em.desc()).limit(100).all()



from schemas import (
    PedidoDominioCreate, PedidoDominioOut,
    MercadoPagoCobrarRequest, MercadoPagoPayoutLoteRequest,
    IdeFileWriteRequest, IdeFileDeleteRequest, IdeBranchCreateRequest,
    ProjetoDeployRequest,
)
from integrations import (
    DEFAULT_TLD_PRICING,
    get_tld_pricing,
    normalizar_dominio_busca,
    pesquisar_dominios_com_sugestoes,
    mp_criar_pagamento_pix,
    mp_criar_order_pix,
    mp_criar_cobranca_pix_unificada,
    mp_criar_checkout_pro,
    mp_consultar_pagamento,
    mp_consultar_order,
    mp_validar_assinatura_webhook,
    mp_enviar_pix_colaborador,
    registrar_dominio_no_provedor,
    provisionar_dominio_vercel,
    verificar_status_dns_vercel,
    slugify_repo_name,
    extrair_repo_full_name,
    github_testar_conexao,
    github_criar_repositorio_empresa,
    github_listar_arvore_repositorio,
    github_ler_arquivo,
    github_salvar_arquivo,
    github_excluir_arquivo,
    github_criar_branch,
    vercel_disparar_deploy_projeto,
    vercel_listar_deploys_projeto,
)



def _aplicar_env_fallback_integracoes(cfg: Optional[ConfiguracaoEmpresa]) -> Optional[ConfiguracaoEmpresa]:
    """Permite usar variáveis de ambiente da Vercel (MP_ACCESS_TOKEN, MP_PUBLIC_KEY, etc.) caso não preenchidas no painel."""
    if not cfg:
        return cfg
    env_token = (os.getenv("MP_ACCESS_TOKEN") or "").strip()
    env_pub = (os.getenv("MP_PUBLIC_KEY") or "").strip()
    env_wh = (os.getenv("MP_WEBHOOK_SECRET") or "").strip()
    env_tipo = (os.getenv("MP_API_TIPO") or "").strip().lower()
    env_amb = (os.getenv("MP_AMBIENTE") or "").strip().lower()

    if not cfg.mp_access_token and env_token:
        cfg.mp_access_token = env_token
        cfg.mp_ativo = True
    if not cfg.mp_public_key and env_pub:
        cfg.mp_public_key = env_pub
    if not cfg.mp_webhook_secret and env_wh:
        cfg.mp_webhook_secret = env_wh
    if env_tipo in ("orders", "payments") and not cfg.mp_api_tipo:
        cfg.mp_api_tipo = env_tipo
    if env_amb in ("sandbox", "producao") and not cfg.mp_ambiente:
        cfg.mp_ambiente = env_amb

    if not cfg.registrar_api_user and os.getenv("REGISTRAR_API_USER"):
        cfg.registrar_api_user = os.getenv("REGISTRAR_API_USER").strip()
    if not cfg.registrar_api_key and os.getenv("REGISTRAR_API_KEY"):
        cfg.registrar_api_key = os.getenv("REGISTRAR_API_KEY").strip()
    if not cfg.vercel_token and os.getenv("VERCEL_TOKEN"):
        cfg.vercel_token = os.getenv("VERCEL_TOKEN").strip()
    if not cfg.github_token and os.getenv("GITHUB_TOKEN"):
        cfg.github_token = os.getenv("GITHUB_TOKEN").strip()
        cfg.github_ativo = True
    if not cfg.github_org and os.getenv("GITHUB_ORG"):
        cfg.github_org = os.getenv("GITHUB_ORG").strip()
    if not cfg.vercel_project_id and os.getenv("VERCEL_PROJECT_ID"):
        cfg.vercel_project_id = os.getenv("VERCEL_PROJECT_ID").strip()
    return cfg


def _executar_ativacao_dominio_pago(db: Session, pedido: PedidoDominio, cfg: ConfiguracaoEmpresa):
    """Registra o domínio no provedor, aponta DNS/SSL na Vercel, cria Ativo + Contrato Anual e notifica."""
    if pedido.status == "ativo":
        return pedido

    pedido.status = "registrando"
    db.flush()

    try:
        reg_res = registrar_dominio_no_provedor(
            provedor=cfg.registrar_provedor if cfg else "sandbox",
            api_user=cfg.registrar_api_user if cfg else None,
            api_key=cfg.registrar_api_key if cfg else None,
            client_ip=cfg.registrar_client_ip if cfg else None,
            dominio=pedido.dominio,
            anos=pedido.anos,
            titular_nome=pedido.titular_nome,
            titular_email=pedido.titular_email,
            titular_telefone=pedido.titular_telefone,
        )
        pedido.registrar_order_id = reg_res.get("order_id")
        pedido.registrar_resposta_json = json.dumps(reg_res, ensure_ascii=False)

        vercel_res = provisionar_dominio_vercel(
            vercel_token=cfg.vercel_token if cfg else os.getenv("VERCEL_TOKEN"),
            project_id=cfg.vercel_project_id if cfg else os.getenv("VERCEL_PROJECT_ID"),
            team_id=cfg.vercel_team_id if cfg else os.getenv("VERCEL_TEAM_ID"),
            dominio=pedido.dominio,
        )
        pedido.dns_status = vercel_res.get("dns_status", "aguardando_propagacao")
        pedido.expira_em = date.today() + timedelta(days=365 * max(1, pedido.anos))
        pedido.status = "ativo"

        # 1. Registra no Cofre de Ativos & Domínios
        ativo = AtivoInfra(
            organizacao_id=pedido.organizacao_id,
            cliente_id=pedido.cliente_id,
            tipo="dominio",
            nome=pedido.dominio,
            provedor=(cfg.registrar_provedor or "Nexus Domains").upper(),
            url_acesso=f"https://{pedido.dominio}",
            valor_renovacao=pedido.valor_venda,
            data_vencimento=pedido.expira_em,
            status="ativo",
            observacoes=f"Pedido {pedido.codigo} | Ordem Registrador: {pedido.registrar_order_id}",
        )
        db.add(ativo)
        db.flush()
        pedido.ativo_id = ativo.id

        # 2. Cria Contrato Recorrente para controle de renovação anual
        if pedido.cliente_id:
            contrato = ContratoRecorrente(
                organizacao_id=pedido.organizacao_id,
                cliente_id=pedido.cliente_id,
                titulo=f"Renovação Anual Domínio — {pedido.dominio}",
                valor_mensal=round(float(pedido.valor_venda) / 12.0, 2),
                dia_vencimento=min(28, date.today().day),
                data_inicio=date.today(),
                status="ativo",
                descricao=f"Renovação automática anual ({pedido.valor_venda}/ano) - Pedido {pedido.codigo}",
            )
            db.add(contrato)
            db.flush()
            pedido.contrato_id = contrato.id

        # 3. Vincula automaticamente ao Portal SaaS Enterprise se solicitado
        if pedido.vincular_portal_saas and pedido.usuario_id:
            usr = db.query(Usuario).filter(Usuario.id == pedido.usuario_id).first()
            if usr:
                org_usr = db.query(Organizacao).filter(Organizacao.id == usr.organizacao_id).first()
                if org_usr and (org_usr.is_master or (org_usr.plano or "").lower() == "enterprise"):
                    org_usr.dominio_customizado = pedido.dominio

        criar_notificacao(
            db,
            f"Domínio Ativado: {pedido.dominio}",
            f"O domínio {pedido.dominio} foi registrado automaticamente ({pedido.registrar_order_id}) e enviado para emissão SSL.",
            "ativos",
            pedido.usuario_id,
            "equipe",
            org_id=pedido.organizacao_id,
        )
    except Exception as exc:
        pedido.status = "erro_registro"
        pedido.registrar_resposta_json = json.dumps({"erro": str(exc)}, ensure_ascii=False)
        criar_notificacao(
            db,
            f"Falha no Registro Automático: {pedido.dominio}",
            f"Pagamento confirmado, mas houve falha na API do registrador: {exc}",
            "ativos",
            None,
            "admin",
            org_id=pedido.organizacao_id,
        )
    return pedido


def _processar_checkout_dominio(
    db: Session,
    org: Organizacao,
    dados: PedidoDominioCreate,
    base_url: str,
    usuario_logado: Optional[Usuario] = None,
) -> PedidoDominio:
    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org.id).first())
    if not cfg or not cfg.mp_ativo or not cfg.mp_access_token:
        raise HTTPException(status_code=400, detail="Gateway Mercado Pago não habilitado no painel administrativo.")

    try:
        dominio_norm, _, ext = normalizar_dominio_busca(dados.dominio)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    pricing = get_tld_pricing(cfg.dominio_precos_json)
    tld_info = pricing.get(ext, {"custo": 50.0, "venda": 99.90})
    valor_total = round(float(tld_info["venda"]) * dados.anos, 2)
    custo_total = round(float(tld_info["custo"]) * dados.anos, 2)

    cliente = None
    if usuario_logado:
        cliente = _garantir_cliente_para_portal(db, usuario_logado)
    if not cliente:
        cliente = db.query(Cliente).filter(Cliente.organizacao_id == org.id, Cliente.email == dados.titular_email).first()
    if not cliente:
        cliente = Cliente(
            organizacao_id=org.id,
            nome_empresa=dados.titular_nome.strip(),
            contato_nome=dados.titular_nome.strip(),
            email=dados.titular_email,
            telefone=dados.titular_telefone,
            documento=dados.titular_documento,
            status_funil="ativo",
            origem="Registro de Domínios",
        )
        db.add(cliente)
        db.flush()

    seq = (db.query(func.count(PedidoDominio.id)).scalar() or 0) + 1
    codigo = f"DOM-{date.today().year}-{seq:05d}"

    fatura = Fatura(
        organizacao_id=org.id,
        cliente_id=cliente.id,
        descricao=f"Registro de Domínio {dominio_norm} ({dados.anos} ano(s))",
        valor=valor_total,
        status="pendente",
        forma_pagamento="Mercado Pago PIX" if dados.metodo_pagamento == "pix" else "Mercado Pago Checkout",
        vencimento=date.today() + timedelta(days=1),
    )
    db.add(fatura)
    db.flush()

    pedido = PedidoDominio(
        organizacao_id=org.id,
        codigo=codigo,
        cliente_id=cliente.id,
        usuario_id=usuario_logado.id if usuario_logado else None,
        dominio=dominio_norm,
        extensao=ext,
        anos=dados.anos,
        titular_nome=dados.titular_nome.strip(),
        titular_documento=dados.titular_documento,
        titular_email=dados.titular_email,
        titular_telefone=dados.titular_telefone,
        preco_custo=custo_total,
        valor_venda=valor_total,
        status="aguardando_pagamento",
        dns_status="pendente",
        vincular_portal_saas=dados.vincular_portal_saas,
        fatura_id=fatura.id,
    )
    db.add(pedido)
    db.flush()

    clean_base = base_url.rstrip("/")
    webhook_url = f"{clean_base}/api/webhooks/mercadopago?org_id={org.id}"
    ext_ref = f"DOMINIO-{pedido.id}"

    try:
        if dados.metodo_pagamento == "pix":
            mp_res = mp_criar_cobranca_pix_unificada(
                access_token=cfg.mp_access_token,
                api_tipo=getattr(cfg, "mp_api_tipo", "orders"),
                valor=valor_total,
                descricao=f"Domínio {dominio_norm} ({dados.anos} ano) - {codigo}",
                external_reference=ext_ref,
                pagador_email=dados.titular_email,
                pagador_nome=dados.titular_nome,
                notification_url=webhook_url,
            )
            pedido.mp_order_id = mp_res.get("order_id")
            pedido.mp_payment_id = mp_res.get("payment_id")
            pedido.mp_qr_code = mp_res.get("qr_code")
            pedido.mp_qr_code_base64 = mp_res.get("qr_code_base64")
            pedido.mp_checkout_url = mp_res.get("ticket_url")
            fatura.mp_order_id = mp_res.get("order_id")
            fatura.mp_payment_id = mp_res.get("payment_id")
            fatura.mp_qr_code = mp_res.get("qr_code")
            fatura.mp_qr_code_base64 = mp_res.get("qr_code_base64")
        else:
            back_page = f"{clean_base}/app/portal.html" if usuario_logado else f"{clean_base}/index.html"
            mp_res = mp_criar_checkout_pro(
                access_token=cfg.mp_access_token,
                titulo=f"Registro de Domínio {dominio_norm} ({dados.anos} ano)",
                valor=valor_total,
                external_reference=ext_ref,
                pagador_email=dados.titular_email,
                back_url_base=back_page,
                notification_url=webhook_url,
                ambiente=getattr(cfg, "mp_ambiente", "producao"),
            )
            pedido.mp_checkout_url = mp_res["init_point"]
            fatura.mp_preference_id = mp_res["preference_id"]
            fatura.mp_checkout_url = mp_res["init_point"]
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc))

    db.commit()
    db.refresh(pedido)
    return pedido


# ==================== PESQUISA & VENDA AUTOMÁTICA DE DOMÍNIOS ====================
@router.get("/public/dominios/precos", tags=["Domínios"])
def obter_tabela_precos_dominios(req: Request, db: Session = Depends(get_db)):
    org = _resolver_org_por_request(req, db)
    cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org.id).first()
    pricing = get_tld_pricing(cfg.dominio_precos_json if cfg else None)
    return {
        "mp_ativo": bool(cfg and cfg.mp_ativo and cfg.mp_access_token),
        "extensoes": [
            {"extensao": ext, "label": info.get("label", ext), "venda": info.get("venda", 99.9), "destaque": bool(info.get("destaque", False))}
            for ext, info in pricing.items()
            if info.get("ativo", True)
        ],
    }


@router.get("/public/dominios/pesquisar", tags=["Domínios"])
def pesquisar_dominio_publico(q: str, req: Request, db: Session = Depends(get_db)):
    org = _resolver_org_por_request(req, db)
    cfg = db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org.id).first()
    pricing = get_tld_pricing(cfg.dominio_precos_json if cfg else None)
    try:
        return pesquisar_dominios_com_sugestoes(q, pricing)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/public/dominios/checkout", response_model=PedidoDominioOut, status_code=201, tags=["Domínios"])
def checkout_dominio_automatico(
    dados: PedidoDominioCreate,
    req: Request,
    db: Session = Depends(get_db),
):
    org = _resolver_org_por_request(req, db)
    return _processar_checkout_dominio(db, org, dados, str(req.base_url), usuario_logado=None)


@router.post("/portal/dominios/checkout", response_model=PedidoDominioOut, status_code=201, tags=["Domínios"])
def checkout_dominio_portal_cliente(
    dados: PedidoDominioCreate,
    req: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    org = _get_org_or_404(db, usuario.organizacao_id)
    return _processar_checkout_dominio(db, org, dados, str(req.base_url), usuario_logado=usuario)


@router.get("/public/dominios/pedidos/{codigo}/status", response_model=PedidoDominioOut, tags=["Domínios"])
def verificar_status_pedido_dominio(codigo: str, db: Session = Depends(get_db)):
    pedido = db.query(PedidoDominio).filter(PedidoDominio.codigo == codigo).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido de domínio não encontrado.")

    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == pedido.organizacao_id).first())
    if pedido.status == "aguardando_pagamento" and cfg and cfg.mp_access_token:
        info = {"status": "pending"}
        if pedido.mp_order_id:
            info = mp_consultar_order(cfg.mp_access_token, pedido.mp_order_id)
        elif pedido.mp_payment_id:
            info = mp_consultar_pagamento(cfg.mp_access_token, pedido.mp_payment_id)

        if info.get("status") == "approved":
            if pedido.fatura_id:
                fat = db.query(Fatura).filter(Fatura.id == pedido.fatura_id).first()
                if fat and fat.status != "pago":
                    fat.status = "pago"
                    fat.pago_em = datetime.utcnow()
            _executar_ativacao_dominio_pago(db, pedido, cfg)
            db.commit()
            db.refresh(pedido)

    return pedido


@router.get("/dominios/pedidos", response_model=List[PedidoDominioOut], tags=["Domínios"])
def listar_pedidos_dominios(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    q = db.query(PedidoDominio).filter(PedidoDominio.organizacao_id == usuario.organizacao_id)
    if usuario.perfil == "cliente":
        cli = _obter_cliente_do_usuario(db, usuario)
        q = q.filter(or_(PedidoDominio.usuario_id == usuario.id, PedidoDominio.cliente_id == (cli.id if cli else -1)))
    return q.order_by(PedidoDominio.criado_em.desc()).all()


@router.post("/dominios/pedidos/{pedido_id}/verificar-dns", tags=["Domínios"])
def verificar_dns_pedido_dominio(pedido_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    pedido = db.query(PedidoDominio).filter(PedidoDominio.id == pedido_id, PedidoDominio.organizacao_id == usuario.organizacao_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Domínio não encontrado.")
    if usuario.perfil == "cliente":
        cli_usr = _obter_cliente_do_usuario(db, usuario)
        if pedido.usuario_id != usuario.id and (not cli_usr or pedido.cliente_id != cli_usr.id):
            raise HTTPException(status_code=403, detail="Acesso negado a este domínio.")
    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == usuario.organizacao_id).first())
    res = verificar_status_dns_vercel(
        vercel_token=cfg.vercel_token if cfg else os.getenv("VERCEL_TOKEN"),
        project_id=cfg.vercel_project_id if cfg else os.getenv("VERCEL_PROJECT_ID"),
        team_id=cfg.vercel_team_id if cfg else os.getenv("VERCEL_TEAM_ID"),
        dominio=pedido.dominio,
    )
    pedido.dns_status = res["dns_status"]
    db.commit()
    return {"dominio": pedido.dominio, **res}


# ==================== MERCADO PAGO: FATURAS (ORDERS & PAYMENTS), WEBHOOK & PAYOUTS RH ====================
@router.post("/faturas/{fatura_id}/mercadopago", response_model=FaturaOut, tags=["Mercado Pago"])
def gerar_cobranca_mercadopago_fatura(
    fatura_id: int,
    dados: MercadoPagoCobrarRequest,
    req: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    fat = db.query(Fatura).filter(Fatura.id == fatura_id, Fatura.organizacao_id == usuario.organizacao_id).first()
    if not fat:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    if usuario.perfil == "cliente":
        cli_usr = _obter_cliente_do_usuario(db, usuario)
        if not cli_usr or fat.cliente_id != cli_usr.id:
            raise HTTPException(status_code=403, detail="Acesso negado a esta fatura.")
    if fat.status == "pago":
        return fat

    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == usuario.organizacao_id).first())
    if not cfg or not cfg.mp_ativo or not cfg.mp_access_token:
        raise HTTPException(status_code=400, detail="Configure e ative o Mercado Pago em Empresa & Permissões > Integrações.")

    cli = db.query(Cliente).filter(Cliente.id == fat.cliente_id).first()
    pagador_email = cli.email if cli else usuario.email
    pagador_nome = cli.nome_empresa if cli else usuario.nome
    base_url = str(req.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/webhooks/mercadopago?org_id={usuario.organizacao_id}"
    ext_ref = f"FATURA-{fat.id}"

    try:
        if dados.metodo == "pix":
            mp_res = mp_criar_cobranca_pix_unificada(
                access_token=cfg.mp_access_token,
                api_tipo=getattr(cfg, "mp_api_tipo", "orders"),
                valor=float(fat.valor),
                descricao=fat.descricao,
                external_reference=ext_ref,
                pagador_email=pagador_email,
                pagador_nome=pagador_nome,
                notification_url=webhook_url,
            )
            fat.forma_pagamento = "Mercado Pago PIX"
            fat.mp_order_id = mp_res.get("order_id")
            fat.mp_payment_id = mp_res.get("payment_id")
            fat.mp_qr_code = mp_res.get("qr_code")
            fat.mp_qr_code_base64 = mp_res.get("qr_code_base64")
            fat.mp_checkout_url = mp_res.get("ticket_url")
        else:
            mp_res = mp_criar_checkout_pro(
                access_token=cfg.mp_access_token,
                titulo=fat.descricao,
                valor=float(fat.valor),
                external_reference=ext_ref,
                pagador_email=pagador_email,
                back_url_base=f"{base_url}/app/portal.html",
                notification_url=webhook_url,
                ambiente=getattr(cfg, "mp_ambiente", "producao"),
            )
            fat.forma_pagamento = "Mercado Pago Checkout"
            fat.mp_preference_id = mp_res["preference_id"]
            fat.mp_checkout_url = mp_res["init_point"]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    db.commit()
    db.refresh(fat)
    return fat


@router.get("/faturas/{fatura_id}/mercadopago/status", response_model=FaturaListOut, tags=["Mercado Pago"])
def verificar_status_pagamento_fatura_mp(
    fatura_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    fat = db.query(Fatura).filter(Fatura.id == fatura_id, Fatura.organizacao_id == usuario.organizacao_id).first()
    if not fat:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    if usuario.perfil == "cliente":
        cli_usr = _obter_cliente_do_usuario(db, usuario)
        if not cli_usr or fat.cliente_id != cli_usr.id:
            raise HTTPException(status_code=403, detail="Acesso negado a esta fatura.")
    if fat.status == "pago":
        return fat

    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == usuario.organizacao_id).first())
    if cfg and cfg.mp_access_token and (fat.mp_order_id or fat.mp_payment_id):
        info = (
            mp_consultar_order(cfg.mp_access_token, fat.mp_order_id)
            if fat.mp_order_id
            else mp_consultar_pagamento(cfg.mp_access_token, fat.mp_payment_id)
        )
        if info.get("status") == "approved":
            fat.status = "pago"
            fat.mp_status_detalhe = info.get("status_detail")
            if info.get("payment_id") and not fat.mp_payment_id:
                fat.mp_payment_id = str(info.get("payment_id"))
            if info.get("ticket_url") and not fat.mp_checkout_url:
                fat.mp_checkout_url = info.get("ticket_url")
            fat.pago_em = datetime.utcnow()
            ped_loja = db.query(PedidoLoja).filter(PedidoLoja.fatura_gerada_id == fat.id).first()
            if ped_loja:
                ped_loja.status = "pago"
            db.commit()
            db.refresh(fat)
            _notificar_pagamento_fatura_confirmado(db, fat, background_tasks)

    return fat


@router.post("/webhooks/mercadopago", tags=["Mercado Pago"])
async def webhook_mercadopago(req: Request, background_tasks: BackgroundTasks, org_id: int = 1, db: Session = Depends(get_db)):
    body = await req.json() if req.headers.get("content-type", "").startswith("application/json") else {}
    data_id = str((body.get("data") or {}).get("id") or req.query_params.get("data.id") or req.query_params.get("id") or "")
    topic = str(body.get("type") or req.query_params.get("type") or req.query_params.get("topic") or "").lower()

    if not data_id:
        return {"received": True}

    is_order_event = topic == "order" or data_id.upper().startswith("ORD")
    if topic and topic not in ("order", "payment", "merchant_order") and not is_order_event:
        return {"received": True}

    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org_id).first())
    if not cfg or not cfg.mp_access_token:
        return {"received": False, "reason": "mp_not_configured"}

    if not mp_validar_assinatura_webhook(
        req.headers.get("x-signature"),
        req.headers.get("x-request-id"),
        data_id,
        cfg.mp_webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="Assinatura HMAC Mercado Pago inválida.")

    info = (
        mp_consultar_order(cfg.mp_access_token, data_id)
        if is_order_event
        else mp_consultar_pagamento(cfg.mp_access_token, data_id)
    )
    if info.get("status") != "approved":
        return {"received": True, "status": info.get("status")}

    ext_ref = str(info.get("external_reference") or "")
    if ext_ref.startswith(("DOMINIO-", "DOMINIO:")):
        sep = "-" if "DOMINIO-" in ext_ref else ":"
        dom_id = int(ext_ref.split(sep, 1)[1])
        pedido = db.query(PedidoDominio).filter(PedidoDominio.id == dom_id).first()
        if pedido:
            if pedido.fatura_id:
                fat = db.query(Fatura).filter(Fatura.id == pedido.fatura_id).first()
                if fat and fat.status != "pago":
                    fat.status = "pago"
                    fat.pago_em = datetime.utcnow()
            _executar_ativacao_dominio_pago(db, pedido, cfg)
            db.commit()
    elif ext_ref.startswith(("FATURA-", "FATURA:")):
        sep = "-" if "FATURA-" in ext_ref else ":"
        fat_id = int(ext_ref.split(sep, 1)[1])
        fat = db.query(Fatura).filter(Fatura.id == fat_id).first()
        if fat and fat.status != "pago":
            fat.status = "pago"
            if is_order_event:
                fat.mp_order_id = str(data_id)
            else:
                fat.mp_payment_id = str(data_id)
            fat.mp_status_detalhe = info.get("status_detail")
            if info.get("payment_id") and not fat.mp_payment_id:
                fat.mp_payment_id = str(info.get("payment_id"))
            if info.get("ticket_url") and not fat.mp_checkout_url:
                fat.mp_checkout_url = info.get("ticket_url")
            fat.pago_em = datetime.utcnow()
            ped_loja = db.query(PedidoLoja).filter(PedidoLoja.fatura_gerada_id == fat.id).first()
            if ped_loja:
                ped_loja.status = "pago"
            criar_notificacao(
                db,
                f"Pagamento Recebido: {fat.descricao}",
                f"Fatura #{fat.id} ({fat.valor}) liquidada automaticamente via Mercado Pago.",
                "faturas",
                None,
                "equipe",
                org_id=fat.organizacao_id,
            )
            db.commit()
            db.refresh(fat)
            _notificar_pagamento_fatura_confirmado(db, fat, background_tasks)

    return {"received": True, "processed": ext_ref}


@router.post("/holerites/{holerite_id}/pagar-mercadopago", response_model=HoleriteOut, tags=["Mercado Pago"])
def pagar_holerite_via_mercadopago(
    holerite_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    hol = db.query(Holerite).filter(Holerite.id == holerite_id, Holerite.organizacao_id == admin.organizacao_id).first()
    if not hol:
        raise HTTPException(status_code=404, detail="Holerite não encontrado.")
    if hol.mp_payout_status == "approved":
        return hol

    colab = db.query(Usuario).filter(Usuario.id == hol.usuario_id).first()
    if not colab or not colab.pix_chave:
        raise HTTPException(status_code=400, detail=f"Cadastre a Chave PIX de {colab.nome if colab else 'colaborador'} antes de disparar o pagamento.")

    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == admin.organizacao_id).first())
    if not cfg or not cfg.mp_ativo or not cfg.mp_access_token:
        raise HTTPException(status_code=400, detail="Configure e ative o Mercado Pago em Empresa & Permissões > Integrações.")

    try:
        res = mp_enviar_pix_colaborador(
            access_token=cfg.mp_access_token,
            valor=float(hol.valor_liquido),
            pix_tipo=colab.pix_tipo or "cpf",
            pix_chave=colab.pix_chave,
            favorecido_nome=colab.nome,
            favorecido_cpf=colab.cpf,
            descricao=f"Folha {hol.competencia} - {hol.tipo} ({colab.nome})",
            external_reference=f"HOLERITE-{hol.id}-{hol.competencia.replace('/', '')}",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    hol.status = "pago"
    hol.data_pagamento = date.today()
    hol.mp_payout_id = res["payout_id"]
    hol.mp_payout_status = res["status"]
    registrar_log(
        db,
        admin.nome,
        "PAGAMENTO_FOLHA_MP",
        f"Pagou holerite #{hol.id} ({colab.nome} - R$ {hol.valor_liquido}) via PIX Mercado Pago ({res['payout_id']})",
        org_id=admin.organizacao_id,
    )
    db.commit()
    db.refresh(hol)
    return hol



# ==================== GITHUB ENTERPRISE, DEPLOYS VERCEL & CLOUD IDE (CODESPACES) ====================
@router.post("/integracoes/github/testar", tags=["DevOps & IDE"])
def testar_conexao_github_endpoint(
    payload: dict,
    equipe: Usuario = Depends(exigir_equipe),
):
    try:
        return github_testar_conexao(payload.get("github_token", ""), payload.get("github_org", ""))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/projetos/{projeto_id}/github/provisionar", response_model=ProjetoOut, tags=["DevOps & IDE"])
def provisionar_github_projeto_existente(
    projeto_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    projeto = db.query(Projeto).filter(Projeto.id == projeto_id, Projeto.organizacao_id == equipe.organizacao_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == equipe.organizacao_id).first())
    if not cfg or not cfg.github_token:
        raise HTTPException(status_code=400, detail="Configure o Token do GitHub em Empresa & Permissões > Integrações.")

    modo = (payload.get("modo") or "criar").strip()
    if modo == "vincular":
        full_name = extrair_repo_full_name(payload.get("repo_url_ou_slug"), cfg.github_org)
        if not full_name:
            raise HTTPException(status_code=400, detail="Informe um repositório válido (ex.: Nexus-Code-Brasil/meu-projeto).")
        projeto.github_repo_full_name = full_name
        projeto.repositorio_url = f"https://github.com/{full_name}"
        projeto.github_default_branch = (payload.get("branch") or "main").strip()
    else:
        org_obj = db.query(Organizacao).filter(Organizacao.id == equipe.organizacao_id).first()
        try:
            repo_res = github_criar_repositorio_empresa(
                token=cfg.github_token,
                org=cfg.github_org,
                repo_nome=payload.get("repo_nome") or projeto.titulo,
                descricao=projeto.descricao or "",
                visibilidade=payload.get("visibilidade") or cfg.github_visibilidade_padrao or "private",
                template=payload.get("template") or "fullstack",
                empresa_nome=org_obj.nome if org_obj else "Nexus Code Brasil",
            )
        except Exception as gh_err:
            raise HTTPException(status_code=502, detail=f"Falha ao criar repositório no GitHub: {gh_err}")
        projeto.repositorio_url = repo_res["html_url"]
        projeto.github_repo_full_name = repo_res["full_name"]
        projeto.github_default_branch = repo_res["default_branch"]
        projeto.github_visibilidade = repo_res["visibilidade"]

    registrar_log(db, equipe.nome, "GITHUB_VINCULADO", f"Repositório {projeto.github_repo_full_name} vinculado ao Projeto #{projeto.id}", org_id=equipe.organizacao_id)
    db.commit()
    db.refresh(projeto)
    return projeto


@router.post("/projetos/{projeto_id}/deploy", tags=["DevOps & IDE"])
def disparar_deploy_projeto_endpoint(
    projeto_id: int,
    dados: ProjetoDeployRequest,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    projeto = db.query(Projeto).filter(Projeto.id == projeto_id, Projeto.organizacao_id == equipe.organizacao_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == equipe.organizacao_id).first())
    if not cfg or not cfg.vercel_token:
        raise HTTPException(status_code=400, detail="Configure o Vercel API Token em Empresa & Permissões > Integrações.")

    full_name = projeto.github_repo_full_name or extrair_repo_full_name(projeto.repositorio_url, cfg.github_org)
    if not full_name:
        raise HTTPException(status_code=400, detail="Este projeto ainda não possui um repositório GitHub vinculado.")

    branch = dados.branch or projeto.github_default_branch or "main"
    try:
        dep = vercel_disparar_deploy_projeto(
            vercel_token=cfg.vercel_token,
            team_id=cfg.vercel_team_id,
            project_slug=full_name.split("/")[-1],
            github_repo_full_name=full_name,
            github_token=cfg.github_token,
            branch=branch,
            target=dados.target,
            existing_vercel_project_id=projeto.vercel_project_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    projeto.github_repo_full_name = full_name
    projeto.vercel_project_id = dep.get("vercel_project_id") or projeto.vercel_project_id
    projeto.ultimo_deploy_status = dep.get("status", "BUILDING")
    projeto.ultimo_deploy_em = datetime.utcnow()

    staging_url = _normalizar_url_homologacao_nexus(projeto.url_homologacao, full_name.split("/")[-1])
    projeto.url_homologacao = staging_url
    staging_host = re.sub(r"^https?://", "", staging_url, flags=re.IGNORECASE).split("/")[0]
    if staging_host.endswith(".nexuscodebrasil.com.br") and projeto.vercel_project_id:
        try:
            provisionar_dominio_vercel(cfg.vercel_token, projeto.vercel_project_id, cfg.vercel_team_id, staging_host)
        except Exception:
            pass

    if dados.target == "production":
        if projeto.url_producao and projeto.vercel_project_id:
            prod_host = re.sub(r"^https?://", "", projeto.url_producao, flags=re.IGNORECASE).split("/")[0]
            if prod_host and "." in prod_host and not prod_host.endswith(".vercel.app"):
                try:
                    provisionar_dominio_vercel(cfg.vercel_token, projeto.vercel_project_id, cfg.vercel_team_id, prod_host)
                except Exception:
                    pass
        elif not projeto.url_producao and dep.get("url"):
            projeto.url_producao = dep["url"]

    registrar_log(db, equipe.nome, "DEPLOY_VERCEL", f"Disparou deploy ({dados.target}) de {full_name}@{branch}", org_id=equipe.organizacao_id)
    db.commit()
    return {"ok": True, "deploy": dep, "projeto_id": projeto.id}


@router.get("/projetos/{projeto_id}/deploys", tags=["DevOps & IDE"])
def listar_deploys_projeto_endpoint(
    projeto_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    projeto = db.query(Projeto).filter(Projeto.id == projeto_id, Projeto.organizacao_id == equipe.organizacao_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == equipe.organizacao_id).first())
    full_name = projeto.github_repo_full_name or extrair_repo_full_name(projeto.repositorio_url, cfg.github_org if cfg else None)
    return vercel_listar_deploys_projeto(
        vercel_token=cfg.vercel_token if cfg else None,
        team_id=cfg.vercel_team_id if cfg else None,
        vercel_project_id=projeto.vercel_project_id,
        github_token=cfg.github_token if cfg else None,
        github_repo_full_name=full_name,
    )


def _obter_contexto_ide_projeto(db: Session, projeto_id: int, org_id: int):
    projeto = db.query(Projeto).filter(Projeto.id == projeto_id, Projeto.organizacao_id == org_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    cfg = _aplicar_env_fallback_integracoes(db.query(ConfiguracaoEmpresa).filter(ConfiguracaoEmpresa.organizacao_id == org_id).first())
    if not cfg or not cfg.github_token:
        raise HTTPException(status_code=400, detail="Token do GitHub não configurado em Empresa & Permissões > Integrações.")
    full_name = projeto.github_repo_full_name or extrair_repo_full_name(projeto.repositorio_url, cfg.github_org)
    if not full_name:
        raise HTTPException(status_code=400, detail="Repositório GitHub não vinculado a este projeto.")
    return projeto, cfg, full_name


@router.get("/projetos/{projeto_id}/ide/tree", tags=["DevOps & IDE"])
def ide_obter_arvore_projeto(
    projeto_id: int,
    branch: Optional[str] = None,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    projeto, cfg, full_name = _obter_contexto_ide_projeto(db, projeto_id, equipe.organizacao_id)
    try:
        tree_info = github_listar_arvore_repositorio(cfg.github_token, full_name, branch or projeto.github_default_branch or "main")
        return {
            "projeto": {
                "id": projeto.id,
                "titulo": projeto.titulo,
                "status": projeto.status,
                "url_producao": projeto.url_producao,
                "url_homologacao": projeto.url_homologacao,
                "ultimo_deploy_status": projeto.ultimo_deploy_status,
            },
            **tree_info,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/projetos/{projeto_id}/ide/file", tags=["DevOps & IDE"])
def ide_ler_arquivo_projeto(
    projeto_id: int,
    path: str,
    branch: str = "main",
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    _, cfg, full_name = _obter_contexto_ide_projeto(db, projeto_id, equipe.organizacao_id)
    try:
        return github_ler_arquivo(cfg.github_token, full_name, path, branch)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.put("/projetos/{projeto_id}/ide/file", tags=["DevOps & IDE"])
@router.post("/projetos/{projeto_id}/ide/file", tags=["DevOps & IDE"])
def ide_salvar_arquivo_projeto(
    projeto_id: int,
    dados: IdeFileWriteRequest,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    _, cfg, full_name = _obter_contexto_ide_projeto(db, projeto_id, equipe.organizacao_id)
    try:
        res = github_salvar_arquivo(
            token=cfg.github_token,
            full_name=full_name,
            path=dados.path,
            content=dados.content,
            message=dados.message or f"feat({dados.path}): commit via Nexus Code Studio por {equipe.nome}",
            branch=dados.branch or "main",
            sha=dados.sha,
        )
        registrar_log(db, equipe.nome, "IDE_COMMIT", f"Commit em {full_name}/{dados.path} ({res.get('commit_sha')})", org_id=equipe.organizacao_id)
        db.commit()
        return res
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.delete("/projetos/{projeto_id}/ide/file", tags=["DevOps & IDE"])
def ide_excluir_arquivo_projeto(
    projeto_id: int,
    dados: IdeFileDeleteRequest,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    _, cfg, full_name = _obter_contexto_ide_projeto(db, projeto_id, equipe.organizacao_id)
    try:
        res = github_excluir_arquivo(cfg.github_token, full_name, dados.path, dados.sha, dados.message, dados.branch or "main")
        registrar_log(db, equipe.nome, "IDE_DELETE_FILE", f"Removeu {full_name}/{dados.path}", org_id=equipe.organizacao_id)
        db.commit()
        return res
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/projetos/{projeto_id}/ide/branch", tags=["DevOps & IDE"])
def ide_criar_branch_projeto(
    projeto_id: int,
    dados: IdeBranchCreateRequest,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    _, cfg, full_name = _obter_contexto_ide_projeto(db, projeto_id, equipe.organizacao_id)
    try:
        res = github_criar_branch(cfg.github_token, full_name, dados.new_branch, dados.from_branch or "main")
        registrar_log(db, equipe.nome, "IDE_NEW_BRANCH", f"Criou branch '{res['branch']}' em {full_name}", org_id=equipe.organizacao_id)
        db.commit()
        return res
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

# ==================== END NEW ROUTES ====================

app.include_router(router)
