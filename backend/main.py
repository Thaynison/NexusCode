import os
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import List, Optional
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False
import calendar
import json
from datetime import timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import Base, engine, get_db, SessionLocal

from email.message import EmailMessage
import smtplib

from models import (
    Usuario, Cliente, SolicitacaoOrcamento, Projeto,
    Tarefa, Interacao, Fatura, Holerite, InformeRendimento, RegistroPonto, ModuloRegistro, LogAuditoria
)
from schemas import (
    LoginRequest, RegisterRequest, ForgotPasswordRequest, TokenResponse,
    UsuarioCreate, UsuarioUpdate, UsuarioOut,
    ClienteCreate, ClienteUpdate, ClienteOut,
    SolicitacaoPublicCreate, SolicitacaoResponder, SolicitacaoUpdate, SolicitacaoOut,
    ProjetoCreate, ProjetoUpdate, ProjetoOut,
    TarefaCreate, TarefaUpdate, TarefaOut,
    InteracaoCreate, InteracaoOut,
    FaturaCreate, FaturaUpdate, FaturaOut,
    HoleriteCreate, HoleriteUpdate, HoleriteOut,
    InformeRendimentoCreate, InformeRendimentoOut,
    PontoBatidaRequest, PontoAjusteCreate, PontoAjusteDecisao, RegistroPontoOut,
    GerarHoleriteAutoRequest,
    ModuloRegistroCreate, ModuloRegistroOut, LogAuditoriaOut,
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
        print(f"[Aviso] E-mail não enviado para {destinatario}. Configure SMTP_USER e SMTP_PASS.")
        return False
    try:
        msg = EmailMessage()
        msg['Subject'] = assunto
        msg['From'] = f"Nexus Code Brasil <{SMTP_USER}>"
        msg['To'] = destinatario
        msg.set_content(mensagem_html, subtype='html')

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[Erro SMTP] {str(e)}")
        return False

def registrar_log(db: Session, usuario_nome: str, acao: str, detalhes: str):
    db.add(LogAuditoria(usuario_nome=usuario_nome, acao=acao, detalhes=detalhes[:250]))


_db_ready = False


def _sync_missing_columns():
    """Adiciona automaticamente colunas novas em tabelas já existentes e preenche valores padrão."""
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

        # Garante preenchimento de registros legados com NULL em colunas que possuem valor padrão
        if "tarefas" in existing_tables:
            conn.execute(text("UPDATE tarefas SET prioridade = 'media' WHERE prioridade IS NULL"))
        if "usuarios" in existing_tables:
            conn.execute(text("UPDATE usuarios SET salario_base = 0 WHERE salario_base IS NULL"))
            conn.execute(text("UPDATE usuarios SET tipo_contrato = 'clt_fixo' WHERE tipo_contrato IS NULL"))
            conn.execute(text("UPDATE usuarios SET carga_horaria_diaria = 8.00 WHERE carga_horaria_diaria IS NULL"))
            conn.execute(text("UPDATE usuarios SET horario_entrada = '08:00' WHERE horario_entrada IS NULL"))
            conn.execute(text("UPDATE usuarios SET horario_saida = '17:00' WHERE horario_saida IS NULL"))
            conn.execute(text("UPDATE usuarios SET dependentes_irrf = 0 WHERE dependentes_irrf IS NULL"))
            conn.execute(text("UPDATE usuarios SET vale_transporte = FALSE WHERE vale_transporte IS NULL"))
            conn.execute(text("UPDATE usuarios SET valor_vt_mensal = 0 WHERE valor_vt_mensal IS NULL"))


def ensure_db_initialized():
    global _db_ready
    if _db_ready:
        return

    Base.metadata.create_all(bind=engine)
    _sync_missing_columns()

    db = SessionLocal()
    try:
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
                data_inicio=date.today(),
            )
            db.add(projeto_demo)
            db.flush()

            db.add_all([
                Tarefa(projeto_id=projeto_demo.id, responsavel_id=admin.id, titulo="Levantamento de requisitos e arquitetura da plataforma", status="concluida"),
                Tarefa(projeto_id=projeto_demo.id, responsavel_id=admin.id, titulo="Homologação do portal corporativo com o cliente", status="fazendo"),
            ])
            registrar_log(db, "Sistema", "INIT", "Ambiente corporativo Nexus Code inicializado.")
            db.commit()
        _db_ready = True
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_db_initialized()
    yield


app = FastAPI(
    title=os.getenv("APP_NAME", "Nexus Code CRM"),
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def init_db_middleware(request, call_next):
    path = request.url.path
    if path.startswith("/api") and (path != "/api/health" or request.query_params.get("db") == "1"):
        ensure_db_initialized()
    return await call_next(request)


@app.get("/api/health", tags=["Status"])
def raiz():
    return {
        "status": "online",
        "sistema": "Nexus Code CRM API",
        "documentacao": "/docs",
    }


# ==================== AUTENTICAÇÃO ====================
@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas. Verifique o e-mail e a senha informados.")
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Conta desativada. Entre em contato com o administrador.")

    token = criar_token_acesso({"sub": str(usuario.id), "perfil": usuario.perfil, "nome": usuario.nome, "email": usuario.email})
    return {"access_token": token, "token_type": "bearer", "usuario": usuario}


@app.post("/api/auth/register", response_model=TokenResponse, status_code=201, tags=["Auth"])
def registrar_conta(dados: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
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

    # Vincular cliente existente caso já tenha enviado solicitação de orçamento pelo site
    cliente_existente = db.query(Cliente).filter(Cliente.email == novo.email).first()
    if cliente_existente and not cliente_existente.usuario_portal_id:
        cliente_existente.usuario_portal_id = novo.id

    registrar_log(db, novo.nome, "CADASTRO", f"Nova conta de cliente criada: {novo.email}")
    db.commit()
    db.refresh(novo)

    token = criar_token_acesso({"sub": str(novo.id), "perfil": novo.perfil, "nome": novo.nome, "email": novo.email})
    return {"access_token": token, "token_type": "bearer", "usuario": novo}


@app.post("/api/auth/forgot-password", tags=["Auth"])
def recuperar_senha(dados: ForgotPasswordRequest):
    return {
        "message": "Caso o e-mail informado esteja cadastrado, enviaremos as instruções para redefinição de senha."
    }



@app.patch("/api/auth/me", response_model=UsuarioOut, tags=["Auth"])
def atualizar_meu_perfil(dados: UsuarioUpdate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_db)):
    payload = dados.model_dump(exclude_unset=True)
    # Bloqueia alteração de privilégio ou status pelo próprio usuário
    payload.pop("perfil", None)
    payload.pop("ativo", None)

    if "senha" in payload:
        nova_senha = payload.pop("senha")
        if nova_senha:
            usuario.senha_hash = gerar_hash_senha(nova_senha)

    if "email" in payload and payload["email"] and payload["email"] != usuario.email:
        if db.query(Usuario).filter(Usuario.email == payload["email"], Usuario.id != usuario.id).first():
            raise HTTPException(status_code=400, detail="Este e-mail já está em uso por outra conta.")

    for campo, valor in payload.items():
        setattr(usuario, campo, valor)

    usuario.termos_aceitos_em = datetime.utcnow()

    registrar_log(db, usuario.nome, "EDITAR_PERFIL", "Atualizou dados cadastrais, currículo e consentimento LGPD.")
    db.commit()
    db.refresh(usuario)
    return usuario

@app.get("/api/auth/me", response_model=UsuarioOut, tags=["Auth"])
def perfil_logado(usuario: Usuario = Depends(get_usuario_db)):
    return usuario


# ==================== SOLICITAÇÕES DE ORÇAMENTO (SITE -> CRM) ====================
@app.post("/api/public/orcamentos", status_code=201, tags=["Orçamentos"])
def receber_solicitacao_site(dados: SolicitacaoPublicCreate, db: Session = Depends(get_db)):
    # Proteção silenciosa contra bots (honeypot)
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

    # Localizar ou cadastrar automaticamente como Lead no CRM
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


@app.get("/api/orcamentos", response_model=List[SolicitacaoOut], tags=["Orçamentos"])
def listar_solicitacoes(
    status_solicitacao: Optional[str] = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    query = db.query(SolicitacaoOrcamento)
    if status_solicitacao:
        query = query.filter(SolicitacaoOrcamento.status == status_solicitacao)
    return query.order_by(SolicitacaoOrcamento.criado_em.desc()).all()


@app.get("/api/portal/orcamentos", response_model=List[SolicitacaoOut], tags=["Orçamentos"])
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


@app.patch("/api/orcamentos/{orcamento_id}/responder", response_model=SolicitacaoOut, tags=["Orçamentos"])
def responder_solicitacao(
    orcamento_id: int,
    dados: SolicitacaoResponder,
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
        if cliente and cliente.status_funil == "lead":
            cliente.status_funil = "proposta"
        db.add(Interacao(
            cliente_id=sol.cliente_id,
            usuario_id=equipe.id,
            tipo="proposta",
            resumo=f"Resposta enviada por {equipe.nome}: {sol.resposta}",
        ))
    
    # Enviar e-mail de resposta ao cliente
    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; color: #0A1D37;">
        <h2 style="color: #00B4D8;">Olá, {sol.nome}.</h2>
        <p>A equipe da <b>Nexus Code Brasil</b> respondeu à sua solicitação de projeto ({sol.tipo_projeto}):</p>
        <div style="padding: 15px; border-left: 4px solid #00B4D8; background-color: #f8fafc; margin-bottom: 20px;">
            {sol.resposta.replace(chr(10), '<br>')}
        </div>
        <p>Acesse o <a href="https://nexuscodebrasil.com.br/login.html" style="color: #0A1D37; font-weight: bold;">Portal do Cliente</a> para acompanhar o status e interagir com nossa equipe.</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <p style="font-size: 12px; color: #64748b;">Este é um e-mail automático da plataforma Nexus Code.</p>
    </div>
    """
    enviar_email(sol.email, f"Retorno: {sol.tipo_projeto} - Nexus Code", corpo_email)


    registrar_log(db, equipe.nome, "RESPONDER_ORCAMENTO", f"Respondeu solicitação #{sol.id} ({sol.nome})")
    db.commit()
    db.refresh(sol)
    return sol


@app.patch("/api/orcamentos/{orcamento_id}", response_model=SolicitacaoOut, tags=["Orçamentos"])
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


@app.delete("/api/orcamentos/{orcamento_id}", status_code=204, tags=["Orçamentos"])
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


# ==================== BOOTSTRAP CONSOLIDADO (1 REQUISIÇÃO) ====================
@app.get("/api/bootstrap", tags=["Dashboard"])
def bootstrap_painel(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    clientes = db.query(Cliente).order_by(Cliente.criado_em.desc()).all()
    usuarios = db.query(Usuario).order_by(Usuario.nome).all()
    projetos = db.query(Projeto).order_by(Projeto.criado_em.desc()).all()
    orcamentos = db.query(SolicitacaoOrcamento).order_by(SolicitacaoOrcamento.criado_em.desc()).all()
    tarefas = db.query(Tarefa).order_by(Tarefa.criado_em.desc()).all()

    leads_abertos = sum(1 for c in clientes if c.status_funil in ("lead", "proposta", "negociacao"))
    solicitacoes_novas = sum(1 for o in orcamentos if o.status in ("novo", "em_atendimento"))
    projetos_ativos = sum(1 for p in projetos if p.status in ("planejamento", "em_andamento", "homologacao"))
    tarefas_pendentes = sum(1 for t in tarefas if t.status != "concluida")

    receita_paga = (
        db.query(func.coalesce(func.sum(Fatura.valor), 0))
        .filter(Fatura.status == "pago")
        .scalar()
    )
    receita_pendente = (
        db.query(func.coalesce(func.sum(Fatura.valor), 0))
        .filter(Fatura.status.in_(["pendente", "atrasado"]))
        .scalar()
    )

    ponto_pendentes = db.query(func.count(RegistroPonto.id)).filter(RegistroPonto.status_ajuste == "pendente_ajuste").scalar() or 0

    kpi = {
        "total_clientes": len(clientes),
        "leads_abertos": leads_abertos,
        "solicitacoes_novas": solicitacoes_novas,
        "projetos_ativos": projetos_ativos,
        "tarefas_pendentes": tarefas_pendentes,
        "ponto_pendentes": ponto_pendentes,
        "receita_paga": float(receita_paga),
        "receita_pendente": float(receita_pendente),
    }

    holerite_q = db.query(Holerite)
    informe_q = db.query(InformeRendimento)
    if usuario.perfil != "admin":
        holerite_q = holerite_q.filter(Holerite.usuario_id == usuario.id)
        informe_q = informe_q.filter(InformeRendimento.usuario_id == usuario.id)

    holerites = holerite_q.order_by(Holerite.criado_em.desc()).all()
    informes = informe_q.order_by(InformeRendimento.ano_calendario.desc(), InformeRendimento.criado_em.desc()).all()

    return {
        "kpi": kpi,
        "clientes": [ClienteOut.model_validate(c) for c in clientes],
        "usuarios": [UsuarioOut.model_validate(u) for u in usuarios],
        "projetos": [ProjetoOut.model_validate(p) for p in projetos],
        "orcamentos": [SolicitacaoOut.model_validate(o) for o in orcamentos],
        "tarefas": [TarefaOut.model_validate(t) for t in tarefas],
        "holerites": [HoleriteOut.model_validate(h) for h in holerites],
        "informes": [InformeRendimentoOut.model_validate(i) for i in informes],
    }


# ==================== DASHBOARD / KPIS ====================
@app.get("/api/dashboard/resumo", tags=["Dashboard"])
def resumo_dashboard(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_equipe),
):
    total_clientes = db.query(func.count(Cliente.id)).scalar() or 0
    leads_abertos = (
        db.query(func.count(Cliente.id))
        .filter(Cliente.status_funil.in_(["lead", "proposta", "negociacao"]))
        .scalar() or 0
    )
    solicitacoes_novas = (
        db.query(func.count(SolicitacaoOrcamento.id))
        .filter(SolicitacaoOrcamento.status.in_(["novo", "em_atendimento"]))
        .scalar() or 0
    )
    projetos_ativos = (
        db.query(func.count(Projeto.id))
        .filter(Projeto.status.in_(["planejamento", "em_andamento", "homologacao"]))
        .scalar() or 0
    )
    tarefas_pendentes = (
        db.query(func.count(Tarefa.id))
        .filter(Tarefa.status != "concluida")
        .scalar() or 0
    )
    receita_paga = (
        db.query(func.coalesce(func.sum(Fatura.valor), 0))
        .filter(Fatura.status == "pago")
        .scalar()
    )
    receita_pendente = (
        db.query(func.coalesce(func.sum(Fatura.valor), 0))
        .filter(Fatura.status.in_(["pendente", "atrasado"]))
        .scalar()
    )

    return {
        "total_clientes": total_clientes,
        "leads_abertos": leads_abertos,
        "solicitacoes_novas": solicitacoes_novas,
        "projetos_ativos": projetos_ativos,
        "tarefas_pendentes": tarefas_pendentes,
        "receita_paga": float(receita_paga),
        "receita_pendente": float(receita_pendente),
    }


# ==================== USUÁRIOS ====================
@app.get("/api/usuarios", response_model=List[UsuarioOut], tags=["Usuários"])
def listar_usuarios(db: Session = Depends(get_db), _: Usuario = Depends(exigir_equipe)):
    return db.query(Usuario).order_by(Usuario.nome).all()


@app.post("/api/usuarios", response_model=UsuarioOut, status_code=201, tags=["Usuários"])
def criar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(exigir_admin),
):
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
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


@app.patch("/api/usuarios/{usuario_id}", response_model=UsuarioOut, tags=["Usuários"])
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


@app.delete("/api/usuarios/{usuario_id}", status_code=204, tags=["Usuários"])
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
@app.get("/api/clientes", response_model=List[ClienteOut], tags=["Clientes"])
def listar_clientes(
    status_funil: Optional[str] = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    query = db.query(Cliente)
    if status_funil:
        query = query.filter(Cliente.status_funil == status_funil)
    return query.order_by(Cliente.criado_em.desc()).all()


@app.post("/api/clientes", response_model=ClienteOut, status_code=201, tags=["Clientes"])
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


@app.patch("/api/clientes/{cliente_id}", response_model=ClienteOut, tags=["Clientes"])
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


@app.delete("/api/clientes/{cliente_id}", status_code=204, tags=["Clientes"])
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
@app.get("/api/projetos", response_model=List[ProjetoOut], tags=["Projetos"])
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


@app.post("/api/projetos", response_model=ProjetoOut, status_code=201, tags=["Projetos"])
def criar_projeto(
    dados: ProjetoCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    if not db.query(Cliente).filter(Cliente.id == dados.cliente_id).first():
        raise HTTPException(status_code=404, detail="Cliente informado não existe.")
    projeto = Projeto(**dados.model_dump())
    db.add(projeto)
    registrar_log(db, equipe.nome, "CRIAR_PROJETO", f"Criou projeto '{projeto.titulo}'")
    db.commit()
    db.refresh(projeto)
    return projeto


@app.patch("/api/projetos/{projeto_id}", response_model=ProjetoOut, tags=["Projetos"])
def atualizar_projeto(
    projeto_id: int,
    dados: ProjetoUpdate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    projeto = db.query(Projeto).filter(Projeto.id == projeto_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(projeto, campo, valor)
    registrar_log(db, equipe.nome, "EDITAR_PROJETO", f"Atualizou projeto #{projeto_id}")
    db.commit()
    db.refresh(projeto)
    return projeto


@app.delete("/api/projetos/{projeto_id}", status_code=204, tags=["Projetos"])
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
@app.get("/api/tarefas", response_model=List[TarefaOut], tags=["Tarefas"])
def listar_todas_tarefas(
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    return db.query(Tarefa).order_by(Tarefa.criado_em.desc()).all()


@app.get("/api/projetos/{projeto_id}/tarefas", response_model=List[TarefaOut], tags=["Tarefas"])
def listar_tarefas_projeto(
    projeto_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_usuario_atual),
):
    return db.query(Tarefa).filter(Tarefa.projeto_id == projeto_id).all()


@app.post("/api/tarefas", response_model=TarefaOut, status_code=201, tags=["Tarefas"])
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


@app.patch("/api/tarefas/{tarefa_id}", response_model=TarefaOut, tags=["Tarefas"])
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


@app.delete("/api/tarefas/{tarefa_id}", status_code=204, tags=["Tarefas"])
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
@app.get("/api/clientes/{cliente_id}/interacoes", response_model=List[InteracaoOut], tags=["CRM"])
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


@app.post("/api/interacoes", response_model=InteracaoOut, status_code=201, tags=["CRM"])
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
@app.get("/api/faturas", response_model=List[FaturaOut], tags=["Financeiro"])
def listar_faturas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    query = db.query(Fatura)
    if usuario.perfil == "cliente":
        query = query.join(Cliente).filter(
            (Cliente.usuario_portal_id == usuario.id) | (Cliente.email == usuario.email)
        )
    return query.order_by(Fatura.vencimento.asc()).all()


@app.post("/api/faturas", response_model=FaturaOut, status_code=201, tags=["Financeiro"])
def criar_fatura(
    dados: FaturaCreate,
    db: Session = Depends(get_db),
    equipe: Usuario = Depends(exigir_equipe),
):
    fatura = Fatura(**dados.model_dump())
    db.add(fatura)
    registrar_log(db, equipe.nome, "CRIAR_FATURA", f"Lançou fatura '{fatura.descricao}'")
    db.commit()
    db.refresh(fatura)
    return fatura


@app.patch("/api/faturas/{fatura_id}", response_model=FaturaOut, tags=["Financeiro"])
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


@app.delete("/api/faturas/{fatura_id}", status_code=204, tags=["Financeiro"])
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
@app.get("/api/holerites", response_model=List[HoleriteOut], tags=["Holerite"])
def listar_holerites(
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    query = db.query(Holerite)
    if usuario.perfil != "admin":
        query = query.filter(Holerite.usuario_id == usuario.id)
    elif usuario_id:
        query = query.filter(Holerite.usuario_id == usuario_id)
    return query.order_by(Holerite.criado_em.desc()).all()


@app.post("/api/holerites", response_model=HoleriteOut, status_code=201, tags=["Holerite"])
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


@app.patch("/api/holerites/{holerite_id}", response_model=HoleriteOut, tags=["Holerite"])
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


@app.delete("/api/holerites/{holerite_id}", status_code=204, tags=["Holerite"])
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


@app.get("/api/informes-rendimentos", response_model=List[InformeRendimentoOut], tags=["Holerite"])
def listar_informes_rendimentos(
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    query = db.query(InformeRendimento)
    if usuario.perfil != "admin":
        query = query.filter(InformeRendimento.usuario_id == usuario.id)
    elif usuario_id:
        query = query.filter(InformeRendimento.usuario_id == usuario_id)
    return query.order_by(InformeRendimento.ano_calendario.desc(), InformeRendimento.criado_em.desc()).all()


@app.post("/api/informes-rendimentos", response_model=InformeRendimentoOut, status_code=201, tags=["Holerite"])
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


@app.delete("/api/informes-rendimentos/{informe_id}", status_code=204, tags=["Holerite"])
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


@app.get("/api/cbo/buscar", tags=["RH & Ponto"])
def api_buscar_cbo(
    q: Optional[str] = "",
    _: Usuario = Depends(exigir_equipe),
):
    return buscar_cbos(q or "")


@app.get("/api/ponto", response_model=List[RegistroPontoOut], tags=["RH & Ponto"])
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


@app.post("/api/ponto/bater", response_model=RegistroPontoOut, tags=["RH & Ponto"])
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


@app.post("/api/ponto/ajustes", response_model=RegistroPontoOut, tags=["RH & Ponto"])
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


@app.patch("/api/ponto/ajustes/{ponto_id}", response_model=RegistroPontoOut, tags=["RH & Ponto"])
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


@app.get("/api/folha/calcular", tags=["Holerite"])
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


@app.post("/api/holerites/gerar-automatico", tags=["Holerite"])
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
        "holerites": [HoleriteOut.model_validate(g) for g in gerados],
    }


# ==================== MÓDULOS COMPLEMENTARES & AUDITORIA ====================
@app.get("/api/modulos/{modulo}", response_model=List[ModuloRegistroOut], tags=["Módulos"])
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


@app.post("/api/modulos/{modulo}", response_model=ModuloRegistroOut, status_code=201, tags=["Módulos"])
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


@app.delete("/api/modulos/{modulo}/{item_id}", status_code=204, tags=["Módulos"])
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


@app.get("/api/auditoria", response_model=List[LogAuditoriaOut], tags=["Auditoria"])
def listar_auditoria(
    db: Session = Depends(get_db),
    _: Usuario = Depends(exigir_equipe),
):
    return db.query(LogAuditoria).order_by(LogAuditoria.criado_em.desc()).limit(100).all()
