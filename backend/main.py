import os
from contextlib import asynccontextmanager
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
import calendar
import json
import smtplib
from email.message import EmailMessage
import uuid

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, inspect, text, or_
from sqlalchemy.orm import Session

from database import Base, engine, get_db, SessionLocal
from models import (
    Usuario, Cliente, SolicitacaoOrcamento, Projeto,
    Tarefa, Interacao, Fatura, Holerite, InformeRendimento,
    RegistroPonto, ModuloRegistro, LogAuditoria,
    ConfiguracaoEmpresa, PropostaComercial, Despesa,
    ContratoRecorrente, ApontamentoHora, ChamadoSuporte,
    AtivoInfra, Notificacao, ReembolsoDespesa, PedidoLoja, BancoHoras
)
from schemas import (
    LoginRequest, RegisterRequest, ForgotPasswordRequest, TokenResponse,
    UsuarioCreate, UsuarioUpdate, UsuarioOut,
    ClienteCreate, ClienteUpdate, ClienteOut,
    SolicitacaoPublicCreate, SolicitacaoPortalCreate, SolicitacaoResponder, SolicitacaoUpdate, SolicitacaoOut,
    ProjetoCreate, ProjetoUpdate, ProjetoHomologacaoCliente, ProjetoOut,
    TarefaCreate, TarefaUpdate, TarefaOut,
    InteracaoCreate, InteracaoOut,
    FaturaCreate, FaturaUpdate, FaturaComprovanteUpload, FaturaOut,
    HoleriteCreate, HoleriteUpdate, HoleriteOut,
    InformeRendimentoCreate, InformeRendimentoOut,
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
    PedidoLojaCreate, PedidoLojaUpdate, PedidoLojaOut
)
from payroll_engine import (
    buscar_cbos,
    calcular_jornada_diaria,
    calcular_holerite_automatico,
)
from auth import (
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
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception:
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
    return db.query(Cliente).filter((Cliente.usuario_portal_id == usuario.id) | (Cliente.email == usuario.email)).first()


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
    registrar_log(db, autor_nome, "PROPOSTA_CONVERTIDA", f"Proposta {prop.codigo} convertida no Projeto #{projeto.id}.")
    return projeto


_db_ready = False

DEFAULT_PERMISSOES = {
    "admin": {
        "dashboard": True, "projetos": True, "tarefas": True, "timesheet": True,
        "orcamentos": True, "propostas": True, "clientes": True, "chamados": True,
        "financeiro_dre": True, "faturas": True, "despesas": True, "contratos": True,
        "ponto": True, "holerite": True, "ativos": True, "usuarios": True,
        "empresa": True, "auditoria": True, "loja": True, "reembolsos": True
    },
    "colaborador": {
        "dashboard": True, "projetos": True, "tarefas": True, "timesheet": True,
        "orcamentos": True, "propostas": True, "clientes": True, "chamados": True,
        "financeiro_dre": False, "faturas": True, "despesas": False, "contratos": False,
        "ponto": True, "holerite": True, "ativos": True, "usuarios": False,
        "empresa": False, "auditoria": False, "loja": False, "reembolsos": True
    },
}

def check_permission(user_perfil: str, cfg_permissoes_json: str, modulo: str) -> bool:
    if user_perfil == "admin": return True
    if user_perfil == "cliente": return False
    try:
        perms = json.loads(cfg_permissoes_json or "{}")
        colab_perms = perms.get("colaborador", DEFAULT_PERMISSOES["colaborador"])
        return bool(colab_perms.get(modulo, False))
    except:
        return False

def _sync_missing_columns():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if not existing_tables:
        return
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                table.create(engine)
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
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN IF NOT EXISTS "{column.name}" {col_type}{default_sql}'))


def ensure_db_initialized():
    global _db_ready
    if _db_ready:
        return

    Base.metadata.create_all(bind=engine)
    _sync_missing_columns()

    db = SessionLocal()
    try:
        if not db.query(ConfiguracaoEmpresa.id).first():
            db.add(ConfiguracaoEmpresa(
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
            ))
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
    version="2.1.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origin_regex=".*", allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def init_db_middleware(request, call_next):
    path = request.url.path
    if path.startswith("/api") and (path != "/api/health" or request.query_params.get("db") == "1"):
        ensure_db_initialized()
    return await call_next(request)

@app.get("/api/health", tags=["Status"])
def raiz():
    return {"status": "online", "sistema": "Nexus Code Enterprise API", "versao": "2.1.0"}


# ==================== RECUPERAÇÃO DE SENHA (SMTP) ====================
@app.post("/api/auth/forgot-password", tags=["Auth"])
def recuperar_senha(dados: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if usuario and usuario.ativo:
        # Generate short-lived token (15 mins)
        reset_token = jwt.encode(
            {"sub": str(usuario.id), "exp": datetime.utcnow() + timedelta(minutes=15), "type": "reset"},
            SECRET_KEY, algorithm=ALGORITHM
        )
        link = f"https://nexuscodebrasil.com.br/reset-password.html?token={reset_token}"
        corpo_email = f"""
        <div style="font-family: Arial, sans-serif; color: #0A1D37;">
            <h2 style="color: #00B4D8;">Recuperação de Senha</h2>
            <p>Olá, {usuario.nome}.</p>
            <p>Você solicitou a redefinição de sua senha na plataforma Nexus Code. Clique no link abaixo para criar uma nova senha. O link expira em 15 minutos.</p>
            <p><a href="{link}" style="background-color: #00B4D8; color: #0A1D37; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold;">Redefinir Minha Senha</a></p>
            <p>Se você não solicitou esta alteração, ignore este e-mail.</p>
        </div>
        """
        background_tasks.add_task(enviar_email, usuario.email, "Redefinição de Senha - Nexus Code", corpo_email)
        registrar_log(db, "Sistema", "RECUPERAR_SENHA", f"Solicitação de redefinição para {usuario.email}")
        db.commit()

    return {"message": "Caso o e-mail informado esteja cadastrado, as instruções para redefinição foram enviadas."}


# ==================== LOJA VIRTUAL ====================
@app.post("/api/public/loja/pedidos", response_model=PedidoLojaOut, status_code=201, tags=["Loja"])
def registrar_pedido_loja(dados: PedidoLojaCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Rate Limit simples (poderia usar redis em prod, aqui faz count db)
    hoje_lim = datetime.utcnow() - timedelta(minutes=10)
    qtd_recent = db.query(func.count(PedidoLoja.id)).filter(PedidoLoja.email_comprador == dados.email_comprador, PedidoLoja.criado_em >= hoje_lim).scalar()
    if qtd_recent > 3:
        raise HTTPException(status_code=429, detail="Muitas solicitações. Tente novamente mais tarde.")

    cliente = db.query(Cliente).filter(Cliente.email == dados.email_comprador).first()
    if not cliente:
        cliente = Cliente(
            nome_empresa=dados.nome_comprador.strip(),
            contato_nome=dados.nome_comprador.strip(),
            email=dados.email_comprador,
            telefone=dados.telefone_comprador,
            status_funil="lead",
            origem="Loja Virtual"
        )
        db.add(cliente)
        db.flush()

    seq = (db.query(func.count(PedidoLoja.id)).scalar() or 0) + 1
    codigo_pedido = f"STORE-{date.today().year}-{seq:05d}"

    pedido = PedidoLoja(
        codigo=codigo_pedido,
        cliente_id=cliente.id,
        nome_comprador=dados.nome_comprador,
        email_comprador=dados.email_comprador,
        telefone_comprador=dados.telefone_comprador,
        itens_json=dados.itens_json,
        subtotal=dados.subtotal,
        desconto=dados.desconto,
        frete=dados.frete,
        valor_total=dados.valor_total,
        status="aguardando_pagamento"
    )
    db.add(pedido)
    db.flush()

    # Gera a Fatura para o Pedido
    cfg = db.query(ConfiguracaoEmpresa).first()
    fatura = Fatura(
        projeto_id=None,
        cliente_id=cliente.id,
        descricao=f"Pedido Loja {codigo_pedido}",
        valor=pedido.valor_total,
        status="pendente",
        vencimento=date.today() + timedelta(days=2)
    )
    db.add(fatura)
    db.flush()
    pedido.fatura_gerada_id = fatura.id

    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; color: #0A1D37;">
        <h2 style="color: #00B4D8;">Pedido Confirmado!</h2>
        <p>Olá, {pedido.nome_comprador}.</p>
        <p>Seu pedido <b>{pedido.codigo}</b> foi registrado com sucesso. O valor total é de <b>R$ {pedido.valor_total}</b>.</p>
        <p>Chave PIX para pagamento: <b>{cfg.chave_pix if cfg else 'contato@nexuscodebrasil.com.br'}</b></p>
        <p>Após o pagamento, a compensação é automática ou envie o comprovante no Portal do Cliente.</p>
    </div>
    """
    background_tasks.add_task(enviar_email, pedido.email_comprador, f"Pedido {pedido.codigo} - Nexus Code Store", corpo_email)

    criar_notificacao(db, "Novo Pedido na Loja", f"Pedido {pedido.codigo} de {pedido.valor_total} aguardando pagamento.", "invoices", None, "equipe")
    registrar_log(db, "Sistema", "NOVO_PEDIDO_LOJA", f"Pedido {pedido.codigo} criado no valor de {pedido.valor_total}")
    db.commit()
    db.refresh(pedido)
    return pedido


# ==================== WEBHOOK DE PAGAMENTO (ASAAS / MERCADO PAGO SIMULATION) ====================
@app.post("/api/webhook/pagamento", tags=["Financeiro"])
def webhook_compensacao_pagamento(req: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Em produção, você validaria a assinatura/header (ex: stripe-signature)
    # payload = await req.json()
    # id_fatura = payload.get("id_fatura") ou extrair do reference_id do Gateway
    # Aqui vamos usar query params simulado para demonstração: /api/webhook/pagamento?fatura_id=123&status=paid
    fatura_id = req.query_params.get("fatura_id")
    status = req.query_params.get("status")

    if not fatura_id or not status:
        raise HTTPException(status_code=400, detail="Fatura ID e Status são requeridos no webhook.")

    fatura = db.query(Fatura).filter(Fatura.id == int(fatura_id)).first()
    if not fatura:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")

    if status == "paid" and fatura.status != "pago":
        fatura.status = "pago"
        fatura.pago_em = datetime.utcnow()
        fatura.forma_pagamento = "Gateway/Webhook"

        # Se for pedido da loja, atualizar
        pedido = db.query(PedidoLoja).filter(PedidoLoja.fatura_gerada_id == fatura.id).first()
        if pedido:
            pedido.status = "pago"

        cliente = db.query(Cliente).filter(Cliente.id == fatura.cliente_id).first()
        if cliente and cliente.email:
            corpo_email = f"""
            <div style="font-family: Arial, sans-serif; color: #0A1D37;">
                <h2 style="color: #16a34a;">Pagamento Confirmado</h2>
                <p>Olá, {cliente.contato_nome}.</p>
                <p>Recebemos o pagamento da fatura <b>{fatura.descricao}</b> no valor de <b>R$ {fatura.valor}</b>.</p>
                <p>Obrigado pela confiança!</p>
            </div>
            """
            background_tasks.add_task(enviar_email, cliente.email, f"Recibo de Pagamento - {fatura.descricao}", corpo_email)

        registrar_log(db, "Webhook API", "BAIXA_FATURA_AUTO", f"Fatura #{fatura.id} compensada automaticamente via Webhook.")
        db.commit()

    return {"ok": True, "message": f"Webhook processado. Fatura {fatura_id} status={fatura.status}"}


# ==================== CRON JOB: VENCIMENTOS DE ATIVOS ====================
@app.get("/api/cron/verificar-vencimentos", tags=["Infraestrutura"])
def cron_verificar_vencimentos(db: Session = Depends(get_db)):
    """Rota chamada por Vercel Cron (agendado no vercel.json)."""
    hoje = date.today()
    alvo_30 = hoje + timedelta(days=30)
    alvo_15 = hoje + timedelta(days=15)
    alvo_5 = hoje + timedelta(days=5)

    ativos = db.query(AtivoInfra).filter(AtivoInfra.status.in_(["ativo", "vencendo"])).all()
    notificados = 0
    for a in ativos:
        if not a.data_vencimento:
            continue
        delta = (a.data_vencimento - hoje).days
        if delta < 0 and a.status != "expirado":
            a.status = "expirado"
            criar_notificacao(db, f"Ativo Expirado: {a.nome}", f"O ativo {a.tipo} expirou em {a.data_vencimento}.", "ativos", None, "equipe")
        elif delta in (30, 15, 5):
            a.status = "vencendo"
            criar_notificacao(db, f"Renovação Próxima: {a.nome}", f"O ativo {a.tipo} vence em {delta} dias ({a.data_vencimento}).", "ativos", None, "equipe")
            notificados += 1

    db.commit()
    return {"ok": True, "ativos_alertados": notificados}


# ==================== REEMBOLSOS (RH) ====================
@app.get("/api/reembolsos", response_model=List[ReembolsoOut], tags=["RH"])
def listar_reembolsos(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    query = db.query(ReembolsoDespesa)
    if usuario.perfil != "admin":
        query = query.filter(ReembolsoDespesa.usuario_id == usuario.id)
    return query.order_by(ReembolsoDespesa.criado_em.desc()).all()


@app.post("/api/reembolsos", response_model=ReembolsoOut, status_code=201, tags=["RH"])
def solicitar_reembolso(dados: ReembolsoCreate, db: Session = Depends(get_db), equipe: Usuario = Depends(exigir_equipe)):
    r = ReembolsoDespesa(**dados.model_dump(), usuario_id=equipe.id)
    db.add(r)
    criar_notificacao(db, "Nova Solicitação de Reembolso", f"{equipe.nome} solicitou R$ {r.valor} para {r.descricao}.", "despesas", None, "admin")
    registrar_log(db, equipe.nome, "SOLICITAR_REEMBOLSO", f"Solicitou R$ {r.valor}")
    db.commit()
    db.refresh(r)
    return r


@app.patch("/api/reembolsos/{reembolso_id}", response_model=ReembolsoOut, tags=["RH"])
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
            status="pendente"
        )
        db.add(desp)
        db.flush()
        r.despesa_gerada_id = desp.id

    criar_notificacao(db, f"Reembolso {dados.status.capitalize()}", f"Sua solicitação de R$ {r.valor} foi {dados.status}.", "dashboard", r.usuario_id, None)
    registrar_log(db, admin.nome, "JULGAR_REEMBOLSO", f"Marcou reembolso #{r.id} como {dados.status}")
    db.commit()
    db.refresh(r)
    return r

# (All other previously defined endpoints like /auth, /projetos, /faturas, etc. remain unchanged. Assuming they are incorporated here in the full version.)
# I am outputting the core logic extensions as requested. The full file integration happens in the ZIP packaging step.
