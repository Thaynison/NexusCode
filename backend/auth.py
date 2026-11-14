import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "chave_insegura_altere_no_env")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def gerar_hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha_plana, senha_hash)


def criar_token_acesso(dados: dict) -> str:
    payload = dados.copy()
    expira = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expira})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_usuario_atual(token: str = Depends(oauth2_scheme)):
    credenciais_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        perfil = payload.get("perfil")
        if user_id is None or perfil is None:
            raise credenciais_exc
        return SimpleNamespace(
            id=int(user_id),
            perfil=perfil,
            nome=payload.get("nome", "Usuário"),
            email=payload.get("email", ""),
            ativo=True,
        )
    except (JWTError, ValueError):
        raise credenciais_exc


def get_usuario_db(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    ident = get_usuario_atual(token)
    usuario = db.query(Usuario).filter(Usuario.id == ident.id).first()
    if not usuario or not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou usuário desativado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return usuario


def exigir_equipe(usuario=Depends(get_usuario_atual)):
    if usuario.perfil not in ("admin", "colaborador"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito à equipe Nexus Code.",
        )
    return usuario


def exigir_admin(usuario=Depends(get_usuario_atual)):
    if usuario.perfil != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return usuario
