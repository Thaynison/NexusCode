import os
from datetime import datetime, timedelta
from types import SimpleNamespace
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario, Organizacao

load_dotenv()

_RAW_SECRET = (os.getenv("SECRET_KEY") or "").strip()
if not _RAW_SECRET or _RAW_SECRET == "chave_insegura_altere_no_env":
    if os.getenv("VERCEL") or os.getenv("ENV") == "production":
        raise RuntimeError("CRÍTICO: Defina uma variável de ambiente SECRET_KEY forte em produção.")
    _RAW_SECRET = "dev_only_nexus_ephemeral_secret_change_me_2026"

SECRET_KEY = _RAW_SECRET
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def gerar_hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha_plana, senha_hash)


def criar_token_acesso(dados: dict, expires_minutes: int | None = None) -> str:
    payload = dados.copy()
    payload.setdefault("type", "access")
    expira = datetime.utcnow() + timedelta(minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expira})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decodificar_identidade_jwt(token: str) -> SimpleNamespace:
    credenciais_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") == "reset":
            raise credenciais_exc
        user_id = payload.get("sub")
        perfil = payload.get("perfil")
        if user_id is None or perfil is None:
            raise credenciais_exc
        return SimpleNamespace(
            id=int(user_id),
            organizacao_id=int(payload.get("org_id") or 1),
            is_master=bool(payload.get("is_master", False)),
            perfil=perfil,
            nome=payload.get("nome", "Usuário"),
            email=payload.get("email", ""),
            ativo=True,
        )
    except (JWTError, ValueError, TypeError):
        raise credenciais_exc


def get_usuario_db(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    ident = _decodificar_identidade_jwt(token)
    usuario = db.query(Usuario).filter(Usuario.id == ident.id).first()
    if not usuario or not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida, revogada ou usuário desativado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    org = db.query(Organizacao).filter(Organizacao.id == usuario.organizacao_id).first()
    if org and not org.is_master and org.status_assinatura == "suspenso":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A assinatura deste portal está suspensa. Entre em contato com o suporte para reativação.",
        )
    return usuario


def get_usuario_atual(
    usuario: Usuario = Depends(get_usuario_db),
) -> Usuario:
    return usuario


def exigir_equipe(usuario: Usuario = Depends(get_usuario_db)) -> Usuario:
    if usuario.perfil not in ("admin", "colaborador"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito à equipe interna.",
        )
    return usuario


def exigir_admin(usuario: Usuario = Depends(get_usuario_db)) -> Usuario:
    if usuario.perfil != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return usuario


def exigir_master_admin(
    usuario: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
) -> Usuario:
    org = db.query(Organizacao).filter(Organizacao.id == usuario.organizacao_id).first()
    if not org or not org.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recurso exclusivo da organização proprietária (Nexus Code Master).",
        )
    return usuario
