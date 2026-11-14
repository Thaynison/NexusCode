import os
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import Base, engine, get_db, SessionLocal
from models import (
    Usuario, Cliente, SolicitacaoOrcamento, Projeto,
    Tarefa, Interacao, Fatura, ModuloRegistro, LogAuditoria
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
    ModuloRegistroCreate, ModuloRegistroOut, LogAuditoriaOut,
)
from auth import (
    gerar_hash_senha, verificar_senha, criar_token_acesso,
    get_usuario_atual, get_usuario_db, exigir_equipe, exigir_admin,
)

load_dotenv()


def registrar_log(db: Session, usuario_nome: str, acao: str, detalhes: str):
    db.add(LogAuditoria(usuario_nome=usuario_nome, acao=acao, detalhes=detalhes[:250]))


_db_ready = False


def ensure_db_initialized():
    global _db_ready
    if _db_ready:
        return
    db = SessionLocal()
    try:
        # Caminho rápido: se a tabela já existe e possui usuário, evita 10 consultas de catálogo
        has_user = db.query(Usuario.id).first()
        if has_user:
            _db_ready = True
            return
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()

    Base.metadata.create_all(bind=engine)
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
    # Não permitir que o usuário altere o próprio perfil de acesso ou status via este endpoint
    payload.pop("perfil", None)
    payload.pop("ativo", None)

    if "senha" in payload:
        usuario.senha_hash = gerar_hash_senha(payload.pop("senha"))
    
    for campo, valor in payload.items():
        setattr(usuario, campo, valor)

    if not usuario.termos_aceitos_em:
        usuario.termos_aceitos_em = datetime.utcnow()

    registrar_log(db, usuario.nome, "EDITAR_PERFIL", "O usuário atualizou seus próprios dados cadastrais.")
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
    _: Usuario = Depends(exigir_equipe),
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

    kpi = {
        "total_clientes": len(clientes),
        "leads_abertos": leads_abertos,
        "solicitacoes_novas": solicitacoes_novas,
        "projetos_ativos": projetos_ativos,
        "tarefas_pendentes": tarefas_pendentes,
        "receita_paga": float(receita_paga),
        "receita_pendente": float(receita_pendente),
    }

    return {
        "kpi": kpi,
        "clientes": [ClienteOut.model_validate(c) for c in clientes],
        "usuarios": [UsuarioOut.model_validate(u) for u in usuarios],
        "projetos": [ProjetoOut.model_validate(p) for p in projetos],
        "orcamentos": [SolicitacaoOut.model_validate(o) for o in orcamentos],
        "tarefas": [TarefaOut.model_validate(t) for t in tarefas],
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
    novo = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=gerar_hash_senha(dados.senha),
        perfil=dados.perfil,
        ativo=dados.ativo,
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
