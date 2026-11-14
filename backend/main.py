import os
from contextlib import asynccontextmanager
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
import calendar
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
)
from payroll_engine import (
    buscar_cbos,
    calcular_jornada_diaria,
    calcular_holerite_automatico,
)
from auth import (
    SECRET_KEY, ALGORITHM,
    gerar_hash_senha, verificar_senha, criar_token_acesso,
    get_usuario_atual, get_usuario_db, exigir_equipe, exigir_admin,
)

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")


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


def registrar_log(db: Session, usuario_nome: str, acao: str, detalhes: str):
    db.add(LogAuditoria(usuario_nome=usuario_nome, acao=acao, detalhes=detalhes[:250]))


def criar_notificacao(
    db: Session,
    titulo: str,
    mensagem: str,
    link_pagina: str = "dashboard",
    usuario_id: Optional[int] = None,
    perfil_destino: Optional[str] = None,
):
    db.add(
        Notificacao(
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
        .filter((Cliente.usuario_portal_id == usuario.id) | (Cliente.email == usuario.email))
        .first()
    )


def _garantir_cliente_para_portal(db: Session, usuario: Usuario) -> Cliente:
    cliente = _obter_cliente_do_usuario(db, usuario)
    if cliente:
        if not cliente.usuario_portal_id:
            cliente.usuario_portal_id = usuario.id
        return cliente
    cliente = Cliente(
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

    admin_user = db.query(Usuario).filter(Usuario.perfil == "admin", Usuario.ativo == True).first()
    hoje = date.today()
    entrega = hoje + timedelta(days=int(prop.prazo_dias or 30))

    projeto = Projeto(
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
                    projeto_id=projeto.id,
                    cliente_id=prop.cliente_id,
                    descricao=f"{prop.titulo} — Parcela {p_idx + 1}/{n_parcelas} ({prop.codigo})",
                    valor=Decimal(str(max(0, val_atual))),
                    status="pendente",
                    forma_pagamento="PIX",
                    vencimento=venc,
                )
            )

    cliente = db.query(Cliente).filter(Cliente.id == prop.cliente_id).first()
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
    )
    return projeto


_db_ready = False

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
                conn.execute(text("SELECT 1 FROM produtos_loja LIMIT 1"))
                conn.execute(text("SELECT 1 FROM pedidos_loja LIMIT 1"))
                conn.execute(text("SELECT 1 FROM configuracoes_empresa LIMIT 1"))
            _db_ready = True
            return
        except Exception:
            pass

    _run_full_schema_sync()

    db = SessionLocal()
    try:
        if not db.query(ConfiguracaoEmpresa.id).first():
            db.add(
                ConfiguracaoEmpresa(
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

        if not db.query(ProdutoLoja.id).first():
            db.add_all([
                ProdutoLoja(
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
                nome="Administrador Nexus",
                email="admin@nexuscode.com",
                senha_hash=gerar_hash_senha("Nexus@2026"),
                perfil="admin",
                ativo=True,
            )
            db.add(admin)
            db.flush()

            cliente_demo = Cliente(
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
                Tarefa(projeto_id=projeto_demo.id, responsavel_id=admin.id, titulo="Levantamento de requisitos e arquitetura da plataforma", status="concluida"),
                Tarefa(projeto_id=projeto_demo.id, responsavel_id=admin.id, titulo="Homologação do portal corporativo com o cliente", status="fazendo"),
            ])
            registrar_log(db, "Sistema", "INIT", "Ambiente corporativo Nexus Code Enterprise inicializado.")
            db.commit()
        _db_ready = True
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_db_initialized()
    yield


app = FastAPI(
    title=os.getenv("APP_NAME", "Nexus Code Enterprise ERP & CRM"),
    version="2.2.0",
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
        "sistema": "Nexus Code Enterprise ERP & CRM API",
        "versao": "2.2.0",
        "regiao": os.getenv("VERCEL_REGION", "local"),
    }


@router.post("/admin/sync-db", tags=["Status"])
def forcar_migracao_banco(_: Usuario = Depends(exigir_admin)):
    ensure_db_initialized(force_sync=True)
    return {"ok": True, "message": "Estrutura de tabelas e colunas sincronizada com sucesso."}


# ==================== AUTENTICAÇÃO ====================
@router.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = (
        db.query(Usuario)
        .options(defer(Usuario.foto_url), defer(Usuario.resumo_profissional))
        .filter(Usuario.email == dados.email)
        .first()
    )
    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas. Verifique o e-mail e a senha informados.")
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Conta desativada. Entre em contato com o administrador.")

    token = criar_token_acesso({"sub": str(usuario.id), "perfil": usuario.perfil, "nome": usuario.nome, "email": usuario.email})
    return {"access_token": token, "token_type": "bearer", "usuario": usuario}


@router.post("/auth/register", response_model=TokenResponse, status_code=201, tags=["Auth"])
def registrar_conta(dados: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(Usuario.id).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=400, detail="Este endereço de e-mail já está vinculado a uma conta.")

    novo = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=gerar_hash_senha(dados.senha),
        perfil="cliente",
        ativo=True,
    )
    db.add(novo)
    db.flush()

    cliente_existente = db.query(Cliente).filter(Cliente.email == novo.email).first()
    if cliente_existente:
        if not cliente_existente.usuario_portal_id:
            cliente_existente.usuario_portal_id = novo.id
    else:
        db.add(
            Cliente(
                usuario_portal_id=novo.id,
                nome_empresa=novo.nome,
                contato_nome=novo.nome,
                email=novo.email,
                status_funil="lead",
                origem="Cadastro Portal do Cliente",
            )
        )

    registrar_log(db, novo.nome, "CADASTRO", f"Nova conta de cliente criada: {novo.email}")
    db.commit()
    db.refresh(novo)

    token = criar_token_acesso({"sub": str(novo.id), "perfil": novo.perfil, "nome": novo.nome, "email": novo.email})
    return {"access_token": token, "token_type": "bearer", "usuario": novo}


@router.post("/auth/forgot-password", tags=["Auth"])
def recuperar_senha(dados: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if usuario and usuario.ativo:
        reset_token = jwt.encode(
            {"sub": str(usuario.id), "exp": datetime.utcnow() + timedelta(minutes=20), "type": "reset"},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        link = f"https://www.nexuscodebrasil.com.br/login.html?reset_token={reset_token}"
        corpo_email = f"""
        <div style="font-family: Arial, sans-serif; color: #0A1D37;">
            <h2 style="color: #00B4D8;">Recuperação de Senha</h2>
            <p>Olá, {usuario.nome}.</p>
            <p>Recebemos uma solicitação para redefinir sua senha na plataforma Nexus Code Brasil.</p>
            <p><a href="{link}" style="background-color: #00B4D8; color: #0A1D37; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold;">Redefinir Minha Senha</a></p>
            <p style="font-size:12px; color:#64748b;">O link expira em 20 minutos. Caso não tenha solicitado, ignore este e-mail.</p>
        </div>
        """
        background_tasks.add_task(enviar_email, usuario.email, "Redefinição de Senha - Nexus Code Brasil", corpo_email)
        registrar_log(db, usuario.nome, "RECUPERAR_SENHA", f"Token de recuperação gerado para {usuario.email}")
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
    registrar_log(db, usuario.nome, "REDEFINIR_SENHA", "Senha redefinida via link seguro.")
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

    registrar_log(db, usuario.nome, "EDITAR_PERFIL", "Atualizou dados cadastrais, currículo e consentimento LGPD.")
    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("/auth/me", response_model=UsuarioOut, tags=["Auth"])
def perfil_logado(usuario: Usuario = Depends(get_usuario_db)):
    return usuario


# ==================== SOLICITAÇÕES DE ORÇAMENTO (SITE & PORTAL -> CRM) ====================
@router.post("/public/orcamentos", status_code=201, tags=["Orçamentos"])
def receber_solicitacao_site(dados: SolicitacaoPublicCreate, db: Session = Depends(get_db)):
    if dados.website:
        return {"message": "Solicitação recebida com sucesso."}

    tipo_map = {
        "web": "Desenvolvimento Web",
        "mobile": "Aplicativo Mobile",
        "system": "Sistema Personalizado",
        "ecommerce": "E-commerce",
        "other": "Outro",
    }
    tipo_legivel = tipo_map.get(dados.tipo_projeto or "", dados.tipo_projeto or "Não especificado")

    cliente = db.query(Cliente).filter(Cliente.email == dados.email).first()
    if not cliente:
        cliente = Cliente(
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
    )

    registrar_log(
        db,
        dados.nome.strip(),
        "SOLICITACAO_SITE",
        f"Nova solicitação de orçamento ({tipo_legivel}) de {dados.email}",
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
    )
    registrar_log(db, usuario.nome, "SOLICITACAO_PORTAL", f"Solicitou novo projeto via portal: {dados.titulo}")
    db.commit()
    db.refresh(sol)
    return sol


@router.get("/orcamentos", response_model=List[SolicitacaoOut], tags=["Orçamentos"])
def listar_solicitacoes(
    status_solicitacao: Optional[str] = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    query = db.query(SolicitacaoOrcamento)
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
        .filter(SolicitacaoOrcamento.email == usuario.email)
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
    sol = db.query(SolicitacaoOrcamento).filter(SolicitacaoOrcamento.id == orcamento_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    sol.resposta = dados.resposta.strip()
    sol.status = dados.status
    sol.respondido_por = equipe.nome
    sol.respondido_em = datetime.utcnow()

    if sol.cliente_id:
        cliente = db.query(Cliente).filter(Cliente.id == sol.cliente_id).first()
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
                )
        db.add(Interacao(
            cliente_id=sol.cliente_id,
            usuario_id=equipe.id,
            tipo="proposta",
            resumo=f"Resposta enviada por {equipe.nome}: {sol.resposta}",
        ))

    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; color: #0A1D37;">
        <h2 style="color: #00B4D8;">Olá, {sol.nome}.</h2>
        <p>A equipe da <b>Nexus Code Brasil</b> respondeu à sua solicitação de projeto ({sol.tipo_projeto}):</p>
        <div style="padding: 15px; border-left: 4px solid #00B4D8; background-color: #f8fafc; margin-bottom: 20px;">
            {sol.resposta.replace(chr(10), '<br>')}
        </div>
        <p>Acesse o Portal do Cliente para acompanhar o status e interagir com nossa equipe.</p>
    </div>
    """
    background_tasks.add_task(enviar_email, sol.email, f"Retorno: {sol.tipo_projeto} - Nexus Code", corpo_email)

    registrar_log(db, equipe.nome, "RESPONDER_ORCAMENTO", f"Respondeu solicitação #{sol.id} ({sol.nome})")
    db.commit()
    db.refresh(sol)
    return sol


@router.patch("/orcamentos/{orcamento_id}", response_model=SolicitacaoOut, tags=["Orçamentos"])
def atualizar_solicitacao(
    orcamento_id: int,
    dados: SolicitacaoUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    sol = db.query(SolicitacaoOrcamento).filter(SolicitacaoOrcamento.id == orcamento_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    payload = dados.model_dump(exclude_unset=True)
    for campo, valor in payload.items():
        setattr(sol, campo, valor)

    registrar_log(db, equipe.nome, "EDITAR_ORCAMENTO", f"Atualizou solicitação #{sol.id}")
    db.commit()
    db.refresh(sol)
    return sol


@router.delete("/orcamentos/{orcamento_id}", status_code=204, tags=["Orçamentos"])
def remover_solicitacao(
    orcamento_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    sol = db.query(SolicitacaoOrcamento).filter(SolicitacaoOrcamento.id == orcamento_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    registrar_log(db, equipe.nome, "EXCLUIR_ORCAMENTO", f"Removeu solicitação #{sol.id} ({sol.nome})")
    db.delete(sol)
    db.commit()


# ==================== BOOTSTRAP CONSOLIDADO DE ALTA VELOCIDADE ====================
@router.get("/bootstrap", tags=["Dashboard"])
def bootstrap_painel(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    clientes = db.query(Cliente).order_by(Cliente.criado_em.desc()).all()
    usuarios = (
        db.query(Usuario)
        .options(defer(Usuario.foto_url), defer(Usuario.resumo_profissional))
        .order_by(Usuario.nome)
        .all()
    )
    projetos = db.query(Projeto).order_by(Projeto.criado_em.desc()).all()
    orcamentos = db.query(SolicitacaoOrcamento).order_by(SolicitacaoOrcamento.criado_em.desc()).all()
    tarefas = db.query(Tarefa).order_by(Tarefa.criado_em.desc()).all()
    propostas = db.query(PropostaComercial).order_by(PropostaComercial.criado_em.desc()).all()
    despesas = db.query(Despesa).order_by(Despesa.vencimento.asc()).all()
    contratos = db.query(ContratoRecorrente).order_by(ContratoRecorrente.criado_em.desc()).all()
    apontamentos = db.query(ApontamentoHora).order_by(ApontamentoHora.data_trabalho.desc(), ApontamentoHora.id.desc()).all()
    chamados = db.query(ChamadoSuporte).order_by(ChamadoSuporte.criado_em.desc()).all()
    ativos = db.query(AtivoInfra).order_by(AtivoInfra.data_vencimento.asc().nullslast()).all()
    empresa_cfg = db.query(ConfiguracaoEmpresa).first()

    notificacoes = (
        db.query(Notificacao)
        .filter(
            or_(
                Notificacao.usuario_id == usuario.id,
                Notificacao.perfil_destino == "equipe",
                Notificacao.perfil_destino == usuario.perfil,
            )
        )
        .order_by(Notificacao.criado_em.desc())
        .limit(25)
        .all()
    )

    agg = db.execute(
        text("""
            SELECT
                COALESCE((SELECT SUM(valor) FROM faturas WHERE status = 'pago'), 0) AS receita_paga,
                COALESCE((SELECT SUM(valor) FROM faturas WHERE status IN ('pendente', 'atrasado')), 0) AS receita_pendente,
                COALESCE((SELECT COUNT(*) FROM registros_ponto WHERE status_ajuste = 'pendente_ajuste'), 0) AS ponto_pendentes
        """)
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

    holerite_q = db.query(Holerite).options(defer(Holerite.anexo_data))
    informe_q = db.query(InformeRendimento).options(defer(InformeRendimento.anexo_data))
    if usuario.perfil != "admin":
        holerite_q = holerite_q.filter(Holerite.usuario_id == usuario.id)
        informe_q = informe_q.filter(InformeRendimento.usuario_id == usuario.id)

    holerites = holerite_q.order_by(Holerite.criado_em.desc()).all()
    informes = informe_q.order_by(InformeRendimento.ano_calendario.desc(), InformeRendimento.criado_em.desc()).all()
    produtos_loja = db.query(ProdutoLoja).order_by(ProdutoLoja.ordem.asc(), ProdutoLoja.id.asc()).all()
    pedidos_loja = db.query(PedidoLoja).order_by(PedidoLoja.criado_em.desc()).limit(50).all()

    return {
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
        "holerites": [HoleriteListOut.model_validate(h) for h in holerites],
        "informes": [InformeListOut.model_validate(i) for i in informes],
        "produtos_loja": [ProdutoLojaOut.model_validate(pl) for pl in produtos_loja],
        "pedidos_loja": [PedidoLojaOut.model_validate(ped) for ped in pedidos_loja],
    }


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
    cliente = _obter_cliente_do_usuario(db, usuario)
    empresa_cfg = db.query(ConfiguracaoEmpresa).first()

    orcamentos = (
        db.query(SolicitacaoOrcamento)
        .filter(SolicitacaoOrcamento.email == usuario.email)
        .order_by(SolicitacaoOrcamento.criado_em.desc())
        .all()
    )

    projetos = []
    tarefas = []
    faturas = []
    propostas = []
    chamados = []

    if cliente:
        projetos = db.query(Projeto).filter(Projeto.cliente_id == cliente.id).order_by(Projeto.criado_em.desc()).all()
        proj_ids = [p.id for p in projetos]
        if proj_ids:
            tarefas = db.query(Tarefa).filter(Tarefa.projeto_id.in_(proj_ids)).order_by(Tarefa.id.asc()).all()
        faturas = (
            db.query(Fatura)
            .options(defer(Fatura.comprovante_data))
            .filter(Fatura.cliente_id == cliente.id)
            .order_by(Fatura.vencimento.asc())
            .all()
        )
        propostas = db.query(PropostaComercial).filter(PropostaComercial.cliente_id == cliente.id).order_by(PropostaComercial.criado_em.desc()).all()
        chamados = db.query(ChamadoSuporte).filter(ChamadoSuporte.cliente_id == cliente.id).order_by(ChamadoSuporte.criado_em.desc()).all()

    notificacoes = (
        db.query(Notificacao)
        .filter(
            or_(
                Notificacao.usuario_id == usuario.id,
                Notificacao.perfil_destino == "cliente",
            )
        )
        .order_by(Notificacao.criado_em.desc())
        .limit(25)
        .all()
    )

    pagamento_info = {
        "empresa": empresa_cfg.razao_social if empresa_cfg else "Nexus Code Brasil Tecnologia Ltda",
        "cnpj": empresa_cfg.cnpj if empresa_cfg else "",
        "banco": empresa_cfg.banco_nome if empresa_cfg else "",
        "agencia": empresa_cfg.agencia if empresa_cfg else "",
        "conta": empresa_cfg.conta if empresa_cfg else "",
        "chave_pix": empresa_cfg.chave_pix if empresa_cfg else "contato@nexuscodebrasil.com.br",
        "titular_pix": empresa_cfg.titular_pix if empresa_cfg else "Nexus Code Brasil",
    }

    return {
        "cliente": ClienteOut.model_validate(cliente) if cliente else None,
        "projetos": [ProjetoOut.model_validate(p) for p in projetos],
        "tarefas": [TarefaOut.model_validate(t) for t in tarefas],
        "faturas": [FaturaListOut.model_validate(f) for f in faturas],
        "propostas": [PropostaOut.model_validate(pr) for pr in propostas],
        "orcamentos": [SolicitacaoOut.model_validate(o) for o in orcamentos],
        "chamados": [ChamadoOut.model_validate(ch) for ch in chamados],
        "notificacoes": [NotificacaoOut.model_validate(n) for n in notificacoes],
        "pagamento_info": pagamento_info,
    }


@router.post("/portal/propostas/{proposta_id}/decidir", response_model=PropostaOut, tags=["Portal Cliente"])
def cliente_decidir_proposta(
    proposta_id: int,
    dados: PropostaDecisaoCliente,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_db),
):
    cliente = _obter_cliente_do_usuario(db, usuario)
    prop = db.query(PropostaComercial).filter(PropostaComercial.id == proposta_id).first()
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
        )
    else:
        criar_notificacao(
            db,
            titulo=f"Retorno na Proposta {prop.codigo}",
            mensagem=f"{cliente.nome_empresa} marcou a proposta como '{dados.decisao}'.",
            link_pagina="propostas",
            perfil_destino="equipe",
        )

    registrar_log(db, usuario.nome, "DECISAO_PROPOSTA", f"Marcou proposta {prop.codigo} como {dados.decisao}")
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
    proj = db.query(Projeto).filter(Projeto.id == projeto_id).first()
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
    )
    registrar_log(db, usuario.nome, "HOMOLOGAR_PROJETO", f"Homologou projeto #{proj.id}: {dados.decisao}")
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
    fat = db.query(Fatura).filter(Fatura.id == fatura_id).first()
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
    )
    registrar_log(db, usuario.nome, "COMPROVANTE_FATURA", f"Enviou comprovante na fatura #{fat.id}")
    db.commit()
    db.refresh(fat)
    return fat


# ==================== PROPOSTAS COMERCIAIS ====================
@router.get("/propostas", response_model=List[PropostaOut], tags=["Propostas"])
def listar_propostas(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    return db.query(PropostaComercial).order_by(PropostaComercial.criado_em.desc()).all()


@router.post("/propostas", response_model=PropostaOut, status_code=201, tags=["Propostas"])
def criar_proposta(
    dados: PropostaCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    cliente = db.query(Cliente).filter(Cliente.id == dados.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    seq = (db.query(func.count(PropostaComercial.id)).scalar() or 0) + 1
    codigo = f"PROP-{date.today().year}-{seq:03d}"

    prop = PropostaComercial(
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
            )
        if cliente.email:
            background_tasks.add_task(
                enviar_email,
                cliente.email,
                f"Proposta Comercial {codigo} — Nexus Code Brasil",
                f"<p>Olá, <b>{cliente.contato_nome}</b>. Sua proposta comercial <b>{codigo} ({prop.titulo})</b> já está disponível para análise e aprovação digital no Portal do Cliente.</p>",
            )

    registrar_log(db, equipe.nome, "CRIAR_PROPOSTA", f"Criou proposta {codigo} para {cliente.nome_empresa}")
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
    prop = db.query(PropostaComercial).filter(PropostaComercial.id == proposta_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(prop, campo, valor)

    if prop.status == "aprovada" and not prop.projeto_gerado_id:
        _converter_proposta_em_projeto(db, prop, equipe.nome)

    registrar_log(db, equipe.nome, "EDITAR_PROPOSTA", f"Atualizou proposta {prop.codigo}")
    db.commit()
    db.refresh(prop)
    return prop


@router.post("/propostas/{proposta_id}/aprovar", response_model=PropostaOut, tags=["Propostas"])
def aprovar_e_converter_proposta(
    proposta_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    prop = db.query(PropostaComercial).filter(PropostaComercial.id == proposta_id).first()
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
    prop = db.query(PropostaComercial).filter(PropostaComercial.id == proposta_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")
    registrar_log(db, equipe.nome, "EXCLUIR_PROPOSTA", f"Removeu proposta {prop.codigo}")
    db.delete(prop)
    db.commit()


# ==================== FINANCEIRO: DESPESAS, MRR, DRE & WEBHOOK ====================
@router.get("/despesas", response_model=List[DespesaOut], tags=["Financeiro"])
def listar_despesas(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    return db.query(Despesa).order_by(Despesa.vencimento.asc()).all()


@router.post("/despesas", response_model=DespesaOut, status_code=201, tags=["Financeiro"])
def criar_despesa(
    dados: DespesaCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    desp = Despesa(**dados.model_dump())
    if desp.status == "pago":
        desp.pago_em = datetime.utcnow()
    db.add(desp)
    registrar_log(db, equipe.nome, "CRIAR_DESPESA", f"Lançou despesa '{desp.descricao}' ({desp.valor})")
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
    desp = db.query(Despesa).filter(Despesa.id == despesa_id).first()
    if not desp:
        raise HTTPException(status_code=404, detail="Despesa não encontrada.")
    payload = dados.model_dump(exclude_unset=True)
    if payload.get("status") == "pago" and not desp.pago_em:
        desp.pago_em = datetime.utcnow()
    for campo, valor in payload.items():
        setattr(desp, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_DESPESA", f"Atualizou despesa #{despesa_id}")
    db.commit()
    db.refresh(desp)
    return desp


@router.delete("/despesas/{despesa_id}", status_code=204, tags=["Financeiro"])
def remover_despesa(
    despesa_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    desp = db.query(Despesa).filter(Despesa.id == despesa_id).first()
    if not desp:
        raise HTTPException(status_code=404, detail="Despesa não encontrada.")
    db.delete(desp)
    db.commit()


@router.get("/contratos-recorrentes", response_model=List[ContratoRecorrenteOut], tags=["Financeiro"])
def listar_contratos_recorrentes(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    return db.query(ContratoRecorrente).order_by(ContratoRecorrente.criado_em.desc()).all()


@router.post("/contratos-recorrentes", response_model=ContratoRecorrenteOut, status_code=201, tags=["Financeiro"])
def criar_contrato_recorrente(
    dados: ContratoRecorrenteCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    ct = ContratoRecorrente(**dados.model_dump())
    db.add(ct)
    registrar_log(db, equipe.nome, "CRIAR_CONTRATO_MRR", f"Criou assinatura recorrente '{ct.titulo}'")
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
    ct = db.query(ContratoRecorrente).filter(ContratoRecorrente.id == contrato_id).first()
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
    ct = db.query(ContratoRecorrente).filter(ContratoRecorrente.id == contrato_id).first()
    if not ct:
        raise HTTPException(status_code=404, detail="Contrato recorrente não encontrado.")
    db.delete(ct)
    db.commit()


@router.post("/contratos-recorrentes/gerar-faturas-mes", tags=["Financeiro"])
def gerar_faturas_recorrentes_mes(
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    hoje = date.today()
    comp = f"{hoje.month:02d}/{hoje.year}"
    ativos = db.query(ContratoRecorrente).filter(ContratoRecorrente.status == "ativo").all()
    geradas = 0

    for ct in ativos:
        if ct.ultima_geracao == comp:
            continue
        proj_id = ct.projeto_id
        if not proj_id:
            proj = db.query(Projeto).filter(Projeto.cliente_id == ct.cliente_id).first()
            if not proj:
                proj = Projeto(
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

    registrar_log(db, equipe.nome, "FATURAMENTO_MRR", f"Gerou {geradas} fatura(s) recorrente(s) da competência {comp}")
    db.commit()
    return {"competencia": comp, "faturas_geradas": geradas}


@router.get("/financeiro/dre", tags=["Financeiro"])
def obter_dre_gerencial(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    faturas = db.query(Fatura.valor, Fatura.status, Fatura.vencimento).all()
    despesas = db.query(Despesa.valor, Despesa.status, Despesa.categoria, Despesa.vencimento).all()
    holerites = db.query(Holerite.valor_liquido, Holerite.competencia).filter(Holerite.status == "pago").all()
    mrr_mensal = float(db.query(func.coalesce(func.sum(ContratoRecorrente.valor_mensal), 0)).filter(ContratoRecorrente.status == "ativo").scalar() or 0)

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
    fatura_id = req.query_params.get("fatura_id")
    status_pg = req.query_params.get("status")
    if not fatura_id or not status_pg:
        raise HTTPException(status_code=400, detail="Parâmetros fatura_id e status são obrigatórios.")

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

        cliente = db.query(Cliente).filter(Cliente.id == fatura.cliente_id).first()
        if cliente and cliente.email:
            background_tasks.add_task(
                enviar_email,
                cliente.email,
                f"Recibo de Pagamento - {fatura.descricao}",
                f"<p>Olá, <b>{cliente.contato_nome}</b>. Confirmamos o recebimento de <b>R$ {fatura.valor}</b> referente a <b>{fatura.descricao}</b>.</p>",
            )
        registrar_log(db, "Webhook Gateway", "BAIXA_FATURA_AUTO", f"Fatura #{fatura.id} compensada automaticamente.")
        db.commit()

    return {"ok": True, "fatura_id": fatura.id, "status": fatura.status}


# ==================== LOJA VIRTUAL (SITE -> CRM & FATURAMENTO) ====================
@router.post("/public/loja/pedidos", response_model=PedidoLojaOut, status_code=201, tags=["Loja"])
def registrar_pedido_loja(dados: PedidoLojaCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.email == dados.email_comprador).first()
    if not cliente:
        cliente = Cliente(
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

    cfg = db.query(ConfiguracaoEmpresa).first()
    background_tasks.add_task(
        enviar_email,
        pedido.email_comprador,
        f"Pedido {pedido.codigo} - Nexus Code Store",
        f"<p>Olá, <b>{pedido.nome_comprador}</b>. Seu pedido <b>{pedido.codigo}</b> (R$ {pedido.valor_total}) foi registrado. Chave PIX: <b>{cfg.chave_pix if cfg else 'contato@nexuscodebrasil.com.br'}</b>.</p>",
    )
    criar_notificacao(db, "Novo Pedido na Loja", f"Pedido {pedido.codigo} (R$ {pedido.valor_total}) registrado.", "invoices", None, "equipe")
    registrar_log(db, pedido.nome_comprador, "NOVO_PEDIDO_LOJA", f"Pedido {pedido.codigo} criado.")
    db.commit()
    db.refresh(pedido)
    return pedido


@router.get("/pedidos-loja", response_model=List[PedidoLojaOut], tags=["Loja"])
def listar_pedidos_loja(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    return db.query(PedidoLoja).order_by(PedidoLoja.criado_em.desc()).all()


@router.patch("/pedidos-loja/{pedido_id}", response_model=PedidoLojaOut, tags=["Loja"])
def atualizar_pedido_loja(pedido_id: int, dados: PedidoLojaUpdate, db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    ped = db.query(PedidoLoja).filter(PedidoLoja.id == pedido_id).first()
    if not ped:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    ped.status = dados.status
    registrar_log(db, equipe.nome, "EDITAR_PEDIDO_LOJA", f"Atualizou pedido {ped.codigo} para {dados.status}")
    db.commit()
    db.refresh(ped)
    return ped


# ==================== VITRINE PÚBLICA & CATÁLOGO DA LOJA (SITE <-> PAINEL) ====================
_SITE_CONFIG_CACHE = {"data": None, "ts": 0.0}


def _slugify_produto(texto: str) -> str:
    norm = unicodedata.normalize("NFKD", texto or "produto").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", norm.lower()).strip("-")
    return slug or "produto"


@router.get("/public/site-config", tags=["Site & Loja"])
def obter_configuracao_publica_site(db: Session = Depends(get_db)):
    now_ts = datetime.utcnow().timestamp()
    if _SITE_CONFIG_CACHE["data"] is not None and (now_ts - _SITE_CONFIG_CACHE["ts"]) < 30:
        return _SITE_CONFIG_CACHE["data"]

    cfg = db.query(ConfiguracaoEmpresa).first()
    produtos = (
        db.query(ProdutoLoja)
        .filter(ProdutoLoja.ativo == True)
        .order_by(ProdutoLoja.ordem.asc(), ProdutoLoja.id.asc())
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
    }
    _SITE_CONFIG_CACHE["data"] = payload
    _SITE_CONFIG_CACHE["ts"] = now_ts
    return payload


@router.get("/loja/produtos", response_model=List[ProdutoLojaOut], tags=["Site & Loja"])
def listar_produtos_loja_admin(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    return db.query(ProdutoLoja).order_by(ProdutoLoja.ordem.asc(), ProdutoLoja.id.asc()).all()


@router.post("/loja/produtos", response_model=ProdutoLojaOut, status_code=201, tags=["Site & Loja"])
def criar_produto_loja(
    dados: ProdutoLojaCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    base_slug = _slugify_produto(dados.slug or dados.nome)
    slug = base_slug
    idx = 2
    while db.query(ProdutoLoja.id).filter(ProdutoLoja.slug == slug).first():
        slug = f"{base_slug}-{idx}"
        idx += 1

    payload = dados.model_dump()
    payload["slug"] = slug
    prod = ProdutoLoja(**payload)
    db.add(prod)
    registrar_log(db, equipe.nome, "CRIAR_PRODUTO_LOJA", f"Adicionou produto '{prod.nome}' na loja do site")
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
    prod = db.query(ProdutoLoja).filter(ProdutoLoja.id == produto_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(prod, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_PRODUTO_LOJA", f"Atualizou produto '{prod.nome}' (#{produto_id})")
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
    prod = db.query(ProdutoLoja).filter(ProdutoLoja.id == produto_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_PRODUTO_LOJA", f"Removeu produto '{prod.nome}'")
    db.delete(prod)
    db.commit()
    _SITE_CONFIG_CACHE["data"] = None


# ==================== TIMESHEET & RENTABILIDADE DE PROJETOS ====================
@router.get("/timesheet", response_model=List[ApontamentoHoraOut], tags=["Timesheet"])
def listar_apontamentos_horas(
    projeto_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    q = db.query(ApontamentoHora)
    if projeto_id:
        q = q.filter(ApontamentoHora.projeto_id == projeto_id)
    return q.order_by(ApontamentoHora.data_trabalho.desc(), ApontamentoHora.id.desc()).all()


@router.post("/timesheet", response_model=ApontamentoHoraOut, status_code=201, tags=["Timesheet"])
def registrar_apontamento_hora(
    dados: ApontamentoHoraCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    target_uid = dados.usuario_id if (equipe.perfil == "admin" and dados.usuario_id) else equipe.id
    colab = db.query(Usuario.id, Usuario.salario_base, Usuario.carga_horaria_diaria).filter(Usuario.id == target_uid).first()
    if not colab:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")

    sal = float(colab.salario_base or 0)
    carga = float(colab.carga_horaria_diaria or 8.0)
    divisor = 220.0 if abs(carga - 8.0) < 0.01 else max(1.0, carga * 27.5)
    custo_hora = round(sal / divisor, 2) if sal > 0 else 50.0

    ap = ApontamentoHora(
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
    registrar_log(db, equipe.nome, "APONTAR_HORAS", f"Registrou {dados.horas}h no projeto #{dados.projeto_id}")
    db.commit()
    db.refresh(ap)
    return ap


@router.delete("/timesheet/{apontamento_id}", status_code=204, tags=["Timesheet"])
def remover_apontamento_hora(
    apontamento_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    ap = db.query(ApontamentoHora).filter(ApontamentoHora.id == apontamento_id).first()
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
def listar_chamados_equipe(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    return db.query(ChamadoSuporte).order_by(ChamadoSuporte.criado_em.desc()).all()


@router.post("/chamados", response_model=ChamadoOut, status_code=201, tags=["Chamados"])
def criar_chamado_equipe(
    dados: ChamadoCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    if not dados.cliente_id:
        raise HTTPException(status_code=400, detail="Selecione o cliente vinculado ao chamado.")
    cliente = db.query(Cliente).filter(Cliente.id == dados.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    seq = (db.query(func.count(ChamadoSuporte.id)).scalar() or 0) + 1
    protocolo = f"CHM-{date.today().year}-{seq:04d}"

    ch = ChamadoSuporte(
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
    registrar_log(db, equipe.nome, "ABRIR_CHAMADO", f"Abriu chamado {protocolo} ({ch.titulo})")
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
    ch = db.query(ChamadoSuporte).filter(ChamadoSuporte.id == chamado_id).first()
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
        )

    registrar_log(db, equipe.nome, "RESPONDER_CHAMADO", f"Respondeu no chamado {ch.protocolo}")
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
    ch = db.query(ChamadoSuporte).filter(ChamadoSuporte.id == chamado_id).first()
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
    ch = db.query(ChamadoSuporte).filter(ChamadoSuporte.id == chamado_id).first()
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
    protocolo = f"CHM-{date.today().year}-{seq:04d}"

    sla_map = {"critica": 4, "alta": 8, "media": 24, "baixa": 48}
    ch = ChamadoSuporte(
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
    )
    registrar_log(db, usuario.nome, "ABRIR_CHAMADO_PORTAL", f"Cliente abriu chamado {protocolo}")
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
    ch = db.query(ChamadoSuporte).filter(ChamadoSuporte.id == chamado_id).first()
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
    )
    db.commit()
    db.refresh(ch)
    return ch


# ==================== ATIVOS, DOMÍNIOS & CRON DE VENCIMENTOS ====================
@router.get("/ativos", response_model=List[AtivoInfraOut], tags=["Infraestrutura"])
def listar_ativos_infra(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    return db.query(AtivoInfra).order_by(AtivoInfra.data_vencimento.asc().nullslast()).all()


@router.post("/ativos", response_model=AtivoInfraOut, status_code=201, tags=["Infraestrutura"])
def criar_ativo_infra(
    dados: AtivoInfraCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    ativo = AtivoInfra(**dados.model_dump())
    db.add(ativo)
    registrar_log(db, equipe.nome, "CRIAR_ATIVO", f"Cadastrou ativo '{ativo.nome}' ({ativo.tipo})")
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
    ativo = db.query(AtivoInfra).filter(AtivoInfra.id == ativo_id).first()
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
    ativo = db.query(AtivoInfra).filter(AtivoInfra.id == ativo_id).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    db.delete(ativo)
    db.commit()


@router.get("/cron/verificar-vencimentos", tags=["Infraestrutura"])
def cron_verificar_vencimentos(db: Session = Depends(get_db)):
    hoje = date.today()
    ativos = db.query(AtivoInfra).filter(AtivoInfra.status.in_(["ativo", "vencendo"])).all()
    notificados = 0
    for a in ativos:
        if not a.data_vencimento:
            continue
        delta = (a.data_vencimento - hoje).days
        if delta < 0 and a.status != "expirado":
            a.status = "expirado"
            criar_notificacao(db, f"Ativo Expirado: {a.nome}", f"O ativo {a.tipo} expirou em {a.data_vencimento}.", "ativos", None, "equipe")
            notificados += 1
        elif delta in (30, 15, 5):
            a.status = "vencendo"
            criar_notificacao(db, f"Renovação Próxima: {a.nome}", f"O ativo {a.tipo} vence em {delta} dias ({a.data_vencimento}).", "ativos", None, "equipe")
            notificados += 1
    db.commit()
    return {"ok": True, "ativos_alertados": notificados}


# ==================== REEMBOLSOS (RH AVANÇADO) ====================
@router.get("/reembolsos", response_model=List[ReembolsoOut], tags=["RH"])
def listar_reembolsos(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    query = db.query(ReembolsoDespesa)
    if usuario.perfil != "admin":
        query = query.filter(ReembolsoDespesa.usuario_id == usuario.id)
    return query.order_by(ReembolsoDespesa.criado_em.desc()).all()


@router.post("/reembolsos", response_model=ReembolsoOut, status_code=201, tags=["RH"])
def solicitar_reembolso(dados: ReembolsoCreate, db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    r = ReembolsoDespesa(**dados.model_dump(), usuario_id=equipe.id)
    db.add(r)
    criar_notificacao(db, "Nova Solicitação de Reembolso", f"{equipe.nome} solicitou R$ {r.valor} para {r.descricao}.", "despesas", None, "admin")
    registrar_log(db, equipe.nome, "SOLICITAR_REEMBOLSO", f"Solicitou reembolso de R$ {r.valor}")
    db.commit()
    db.refresh(r)
    return r


@router.patch("/reembolsos/{reembolso_id}", response_model=ReembolsoOut, tags=["RH"])
def julgar_reembolso(reembolso_id: int, dados: ReembolsoUpdate, db: Session = Depends(get_db), admin: Usuario = Depends(exigir_admin)):
    r = db.query(ReembolsoDespesa).filter(ReembolsoDespesa.id == reembolso_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reembolso não encontrado.")
    r.status = dados.status
    if dados.observacoes_gestor:
        r.observacoes_gestor = dados.observacoes_gestor
    if dados.status == "aprovado" and not r.despesa_gerada_id:
        desp = Despesa(
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
    criar_notificacao(db, f"Reembolso {dados.status.capitalize()}", f"Sua solicitação de R$ {r.valor} foi {dados.status}.", "dashboard", r.usuario_id, None)
    registrar_log(db, admin.nome, "JULGAR_REEMBOLSO", f"Marcou reembolso #{r.id} como {dados.status}")
    db.commit()
    db.refresh(r)
    return r


# ==================== CONFIGURAÇÕES DA EMPRESA & PERMISSÕES ====================
@router.get("/empresa", response_model=ConfiguracaoEmpresaOut, tags=["Empresa"])
def obter_configuracoes_empresa(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    cfg = db.query(ConfiguracaoEmpresa).first()
    if not cfg:
        cfg = ConfiguracaoEmpresa(permissoes_json=json.dumps(DEFAULT_PERMISSOES))
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
    cfg = db.query(ConfiguracaoEmpresa).first()
    if not cfg:
        cfg = ConfiguracaoEmpresa()
        db.add(cfg)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(cfg, campo, valor)
    cfg.atualizado_em = datetime.utcnow()
    registrar_log(db, admin.nome, "CONFIG_EMPRESA", "Atualizou parâmetros institucionais, bancários e permissões.")
    db.commit()
    _SITE_CONFIG_CACHE["data"] = None
    db.refresh(cfg)
    return cfg


# ==================== CENTRAL DE NOTIFICAÇÕES ====================
@router.patch("/notificacoes/{notif_id}/lida", tags=["Notificações"])
def marcar_notificacao_lida(
    notif_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    n = db.query(Notificacao).filter(Notificacao.id == notif_id).first()
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
            or_(Notificacao.usuario_id == usuario.id, Notificacao.perfil_destino == "cliente"),
            Notificacao.lida == False,
        ).update({"lida": True}, synchronize_session=False)
    else:
        db.query(Notificacao).filter(
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
def listar_usuarios(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    return (
        db.query(Usuario)
        .options(defer(Usuario.foto_url), defer(Usuario.resumo_profissional))
        .order_by(Usuario.nome)
        .all()
    )


@router.post("/usuarios", response_model=UsuarioListOut, status_code=201, tags=["Usuários"])
def criar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    if db.query(Usuario.id).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")
    cargo_final = dados.cargo or dados.cbo_descricao
    novo = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=gerar_hash_senha(dados.senha),
        perfil=dados.perfil,
        ativo=dados.ativo,
        cpf=dados.cpf,
        cargo=cargo_final,
        cbo_codigo=dados.cbo_codigo,
        cbo_descricao=dados.cbo_descricao,
        tipo_contrato=dados.tipo_contrato or "clt_fixo",
        data_nascimento=dados.data_nascimento,
        data_contratacao=dados.data_contratacao,
        data_fim_contrato=dados.data_fim_contrato,
        carga_horaria_diaria=dados.carga_horaria_diaria if dados.carga_horaria_diaria is not None else 8.00,
        horario_entrada=dados.horario_entrada or "08:00",
        horario_saida=dados.horario_saida or "17:00",
        dependentes_irrf=dados.dependentes_irrf or 0,
        vale_transporte=bool(dados.vale_transporte),
        valor_vt_mensal=dados.valor_vt_mensal or 0,
        salario_base=dados.salario_base or 0,
        telefone=dados.telefone,
    )
    db.add(novo)
    registrar_log(db, admin.nome, "CRIAR_USUARIO", f"Criou usuário {novo.email} ({novo.perfil})")
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
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    payload = dados.model_dump(exclude_unset=True)
    if "senha" in payload:
        usuario.senha_hash = gerar_hash_senha(payload.pop("senha"))
    for campo, valor in payload.items():
        setattr(usuario, campo, valor)

    registrar_log(db, admin.nome, "EDITAR_USUARIO", f"Atualizou usuário #{usuario_id}")
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
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_USUARIO", f"Removeu usuário {usuario.email}")
    db.delete(usuario)
    db.commit()


# ==================== CLIENTES / LEADS ====================
@router.get("/clientes", response_model=List[ClienteOut], tags=["Clientes"])
def listar_clientes(
    status_funil: Optional[str] = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    query = db.query(Cliente)
    if status_funil:
        query = query.filter(Cliente.status_funil == status_funil)
    return query.order_by(Cliente.criado_em.desc()).all()


@router.post("/clientes", response_model=ClienteOut, status_code=201, tags=["Clientes"])
def criar_cliente(
    dados: ClienteCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    cliente = Cliente(**dados.model_dump())
    db.add(cliente)
    registrar_log(db, equipe.nome, "CRIAR_CLIENTE", f"Cadastrou {cliente.nome_empresa}")
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
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(cliente, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_CLIENTE", f"Atualizou cliente #{cliente_id}")
    db.commit()
    db.refresh(cliente)
    return cliente


@router.delete("/clientes/{cliente_id}", status_code=204, tags=["Clientes"])
def remover_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_CLIENTE", f"Removeu cliente {cliente.nome_empresa}")
    db.delete(cliente)
    db.commit()


# ==================== PROJETOS ====================
@router.get("/projetos", response_model=List[ProjetoOut], tags=["Projetos"])
def listar_projetos(
    status_projeto: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    query = db.query(Projeto)
    if usuario.perfil == "cliente":
        query = query.join(Cliente).filter(
            (Cliente.usuario_portal_id == usuario.id) | (Cliente.email == usuario.email)
        )
    if status_projeto:
        query = query.filter(Projeto.status == status_projeto)
    return query.order_by(Projeto.criado_em.desc()).all()


@router.post("/projetos", response_model=ProjetoOut, status_code=201, tags=["Projetos"])
def criar_projeto(
    dados: ProjetoCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    cliente = db.query(Cliente).filter(Cliente.id == dados.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente informado não existe.")
    projeto = Projeto(**dados.model_dump())
    db.add(projeto)
    if cliente.usuario_portal_id:
        criar_notificacao(
            db,
            titulo="Novo Projeto Iniciado",
            mensagem=f"O projeto '{projeto.titulo}' já está disponível para acompanhamento no seu portal.",
            link_pagina="projects",
            usuario_id=cliente.usuario_portal_id,
        )
    registrar_log(db, equipe.nome, "CRIAR_PROJETO", f"Criou projeto '{projeto.titulo}'")
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
    projeto = db.query(Projeto).filter(Projeto.id == projeto_id).first()
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
            )

    registrar_log(db, equipe.nome, "EDITAR_PROJETO", f"Atualizou projeto #{projeto_id}")
    db.commit()
    db.refresh(projeto)
    return projeto


@router.delete("/projetos/{projeto_id}", status_code=204, tags=["Projetos"])
def remover_projeto(
    projeto_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    projeto = db.query(Projeto).filter(Projeto.id == projeto_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_PROJETO", f"Removeu projeto '{projeto.titulo}'")
    db.delete(projeto)
    db.commit()


# ==================== TAREFAS ====================
@router.get("/tarefas", response_model=List[TarefaOut], tags=["Tarefas"])
def listar_todas_tarefas(
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    return db.query(Tarefa).order_by(Tarefa.criado_em.desc()).all()


@router.get("/projetos/{projeto_id}/tarefas", response_model=List[TarefaOut], tags=["Tarefas"])
def listar_tarefas_projeto(
    projeto_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_usuario_atual),
):
    return db.query(Tarefa).filter(Tarefa.projeto_id == projeto_id).all()


@router.post("/tarefas", response_model=TarefaOut, status_code=201, tags=["Tarefas"])
def criar_tarefa(
    dados: TarefaCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    tarefa = Tarefa(**dados.model_dump())
    db.add(tarefa)
    registrar_log(db, equipe.nome, "CRIAR_TAREFA", f"Criou tarefa '{tarefa.titulo}'")
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
    tarefa = db.query(Tarefa).filter(Tarefa.id == tarefa_id).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(tarefa, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_TAREFA", f"Atualizou tarefa #{tarefa_id}")
    db.commit()
    db.refresh(tarefa)
    return tarefa


@router.delete("/tarefas/{tarefa_id}", status_code=204, tags=["Tarefas"])
def remover_tarefa(
    tarefa_id: int,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    tarefa = db.query(Tarefa).filter(Tarefa.id == tarefa_id).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    db.delete(tarefa)
    db.commit()


# ==================== INTERAÇÕES CRM ====================
@router.get("/clientes/{cliente_id}/interacoes", response_model=List[InteracaoOut], tags=["CRM"])
def listar_interacoes(
    cliente_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    return (
        db.query(Interacao)
        .filter(Interacao.cliente_id == cliente_id)
        .order_by(Interacao.data_interacao.desc())
        .all()
    )


@router.post("/interacoes", response_model=InteracaoOut, status_code=201, tags=["CRM"])
def registrar_interacao(
    dados: InteracaoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    interacao = Interacao(**dados.model_dump(), usuario_id=usuario.id)
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
    query = db.query(Fatura).options(defer(Fatura.comprovante_data))
    if usuario.perfil == "cliente":
        query = query.join(Cliente).filter(
            (Cliente.usuario_portal_id == usuario.id) | (Cliente.email == usuario.email)
        )
    return query.order_by(Fatura.vencimento.asc()).all()


@router.get("/faturas/{fatura_id}/comprovante", tags=["Financeiro"])
def baixar_comprovante_fatura(
    fatura_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_usuario_atual),
):
    fat = db.query(Fatura.id, Fatura.comprovante_nome, Fatura.comprovante_data).filter(Fatura.id == fatura_id).first()
    if not fat or not fat.comprovante_data:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado.")
    return {"id": fat.id, "comprovante_nome": fat.comprovante_nome, "comprovante_data": fat.comprovante_data}


@router.post("/faturas", response_model=FaturaListOut, status_code=201, tags=["Financeiro"])
def criar_fatura(
    dados: FaturaCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    fatura = Fatura(**dados.model_dump())
    db.add(fatura)
    cliente = db.query(Cliente).filter(Cliente.id == dados.cliente_id).first()
    if cliente and cliente.usuario_portal_id:
        criar_notificacao(
            db,
            titulo="Nova Fatura Emitida",
            mensagem=f"Fatura '{fatura.descricao}' disponível no seu portal.",
            link_pagina="invoices",
            usuario_id=cliente.usuario_portal_id,
        )
    registrar_log(db, equipe.nome, "CRIAR_FATURA", f"Lançou fatura '{fatura.descricao}'")
    db.commit()
    db.refresh(fatura)
    return fatura


@router.patch("/faturas/{fatura_id}", response_model=FaturaListOut, tags=["Financeiro"])
def atualizar_fatura(
    fatura_id: int,
    dados: FaturaUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    fatura = db.query(Fatura).filter(Fatura.id == fatura_id).first()
    if not fatura:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    payload = dados.model_dump(exclude_unset=True)
    if payload.get("status") == "pago" and not fatura.pago_em:
        fatura.pago_em = datetime.utcnow()
    for campo, valor in payload.items():
        setattr(fatura, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_FATURA", f"Atualizou fatura #{fatura_id}")
    db.commit()
    db.refresh(fatura)
    return fatura


@router.delete("/faturas/{fatura_id}", status_code=204, tags=["Financeiro"])
def remover_fatura(
    fatura_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    fatura = db.query(Fatura).filter(Fatura.id == fatura_id).first()
    if not fatura:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    db.delete(fatura)
    db.commit()


# ==================== FOLHA DE PAGAMENTO, HOLERITES & INFORME DE RENDIMENTOS ====================
@router.get("/holerites", response_model=List[HoleriteListOut], tags=["Holerite"])
def listar_holerites(
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    query = db.query(Holerite).options(defer(Holerite.anexo_data))
    if usuario.perfil != "admin":
        query = query.filter(Holerite.usuario_id == usuario.id)
    elif usuario_id:
        query = query.filter(Holerite.usuario_id == usuario_id)
    return query.order_by(Holerite.criado_em.desc()).all()


@router.get("/holerites/{holerite_id}/anexo", tags=["Holerite"])
def baixar_anexo_holerite(
    holerite_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    h = db.query(Holerite.id, Holerite.usuario_id, Holerite.anexo_nome, Holerite.anexo_data).filter(Holerite.id == holerite_id).first()
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
    colaborador = db.query(Usuario).filter(Usuario.id == dados.usuario_id).first()
    if not colaborador:
        raise HTTPException(status_code=404, detail="Colaborador informado não encontrado.")

    payload = dados.model_dump()
    liquido_calc = (payload["salario_base"] or 0) + (payload["proventos"] or 0) - (payload["descontos"] or 0)
    if not payload.get("valor_liquido") or payload["valor_liquido"] == 0:
        payload["valor_liquido"] = liquido_calc

    item = Holerite(**payload, publicado_por=admin.nome)
    db.add(item)
    registrar_log(
        db,
        admin.nome,
        "PUBLICAR_HOLERITE",
        f"Publicou holerite ({item.competencia} - {item.tipo}) para {colaborador.nome}",
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
    item = db.query(Holerite).filter(Holerite.id == holerite_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Holerite não encontrado.")

    payload = dados.model_dump(exclude_unset=True)
    for campo, valor in payload.items():
        setattr(item, campo, valor)

    if any(k in payload for k in ("salario_base", "proventos", "descontos")) and "valor_liquido" not in payload:
        item.valor_liquido = (item.salario_base or 0) + (item.proventos or 0) - (item.descontos or 0)

    registrar_log(db, admin.nome, "EDITAR_HOLERITE", f"Atualizou holerite #{holerite_id} ({item.competencia})")
    db.commit()
    db.refresh(item)
    return item


@router.delete("/holerites/{holerite_id}", status_code=204, tags=["Holerite"])
def remover_holerite(
    holerite_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    item = db.query(Holerite).filter(Holerite.id == holerite_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Holerite não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_HOLERITE", f"Removeu holerite #{holerite_id} ({item.competencia})")
    db.delete(item)
    db.commit()


@router.get("/informes-rendimentos", response_model=List[InformeListOut], tags=["Holerite"])
def listar_informes_rendimentos(
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    query = db.query(InformeRendimento).options(defer(InformeRendimento.anexo_data))
    if usuario.perfil != "admin":
        query = query.filter(InformeRendimento.usuario_id == usuario.id)
    elif usuario_id:
        query = query.filter(InformeRendimento.usuario_id == usuario_id)
    return query.order_by(InformeRendimento.ano_calendario.desc(), InformeRendimento.criado_em.desc()).all()


@router.get("/informes-rendimentos/{informe_id}/anexo", tags=["Holerite"])
def baixar_anexo_informe(
    informe_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    inf = db.query(InformeRendimento.id, InformeRendimento.usuario_id, InformeRendimento.anexo_nome, InformeRendimento.anexo_data).filter(InformeRendimento.id == informe_id).first()
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
    colaborador = db.query(Usuario).filter(Usuario.id == dados.usuario_id).first()
    if not colaborador:
        raise HTTPException(status_code=404, detail="Colaborador informado não encontrado.")

    item = InformeRendimento(**dados.model_dump(), publicado_por=admin.nome)
    db.add(item)
    registrar_log(
        db,
        admin.nome,
        "PUBLICAR_INFORME_IR",
        f"Publicou Informe de Rendimentos ({item.ano_calendario}) para {colaborador.nome}",
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
    item = db.query(InformeRendimento).filter(InformeRendimento.id == informe_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Informe de rendimentos não encontrado.")
    registrar_log(db, admin.nome, "EXCLUIR_INFORME_IR", f"Removeu Informe de Rendimentos #{informe_id}")
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
    query = db.query(RegistroPonto)
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

    agora = _agora_brasilia()
    hoje = agora.date()
    hora_atual = dados.hora_manual.strip() if dados.hora_manual else agora.strftime("%H:%M")

    reg = (
        db.query(RegistroPonto)
        .filter(RegistroPonto.usuario_id == usuario.id, RegistroPonto.data_ponto == hoje)
        .first()
    )
    if not reg:
        reg = RegistroPonto(
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

    registrar_log(db, usuario.nome, "BATER_PONTO", f"Registrou {campo} às {hora_atual} ({hoje.isoformat()})")
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

    reg = (
        db.query(RegistroPonto)
        .filter(RegistroPonto.usuario_id == usuario.id, RegistroPonto.data_ponto == dados.data_ponto)
        .first()
    )
    if not reg:
        reg = RegistroPonto(
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

    registrar_log(db, usuario.nome, "AJUSTE_PONTO", f"Solicitou ajuste de ponto em {dados.data_ponto.isoformat()}")
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
    reg = db.query(RegistroPonto).filter(RegistroPonto.id == ponto_id).first()
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
    )
    db.commit()
    db.refresh(reg)
    return reg


@router.get("/folha/calcular", tags=["Holerite"])
def pre_calcular_folha_colaborador(
    usuario_id: int,
    competencia: str,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_admin),
):
    colaborador = db.query(Usuario).filter(Usuario.id == usuario_id).first()
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
    try:
        mes_str, ano_str = dados.competencia.strip().split("/")
        mes, ano = int(mes_str), int(ano_str)
        _, ult_dia = calendar.monthrange(ano, mes)
    except ValueError:
        raise HTTPException(status_code=400, detail="Competência inválida. Utilize o formato MM/AAAA.")

    if dados.gerar_todos:
        colaboradores = (
            db.query(Usuario)
            .filter(Usuario.ativo == True, Usuario.perfil != "cliente")
            .order_by(Usuario.nome)
            .all()
        )
    else:
        if not dados.usuario_id:
            raise HTTPException(status_code=400, detail="Selecione um colaborador ou marque 'Gerar para toda a equipe'.")
        colab = db.query(Usuario).filter(Usuario.id == dados.usuario_id).first()
        if not colab:
            raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
        colaboradores = [colab]

    gerados = []
    dt_pag = dados.data_pagamento or date.today()

    for colab in colaboradores:
        pontos = (
            db.query(RegistroPonto)
            .filter(
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
    _: Usuario = Depends(get_usuario_atual),
):
    return (
        db.query(ModuloRegistro)
        .filter(ModuloRegistro.modulo == modulo)
        .order_by(ModuloRegistro.criado_em.desc())
        .all()
    )


@router.post("/modulos/{modulo}", response_model=ModuloRegistroOut, status_code=201, tags=["Módulos"])
def criar_registro_modulo(
    modulo: str,
    dados: ModuloRegistroCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    item = ModuloRegistro(modulo=modulo, **dados.model_dump())
    db.add(item)
    registrar_log(db, usuario.nome, f"CRIAR_{modulo.upper()}", f"Criou '{item.titulo}'")
    db.commit()
    db.refresh(item)
    return item


@router.delete("/modulos/{modulo}/{item_id}", status_code=204, tags=["Módulos"])
def remover_registro_modulo(
    modulo: str,
    item_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    item = db.query(ModuloRegistro).filter(ModuloRegistro.id == item_id, ModuloRegistro.modulo == modulo).first()
    if not item:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    db.delete(item)
    db.commit()


@router.get("/auditoria", response_model=List[LogAuditoriaOut], tags=["Auditoria"])
def listar_auditoria(
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    return db.query(LogAuditoria).order_by(LogAuditoria.criado_em.desc()).limit(100).all()


app.include_router(router)
