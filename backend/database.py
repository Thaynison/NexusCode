import os
from urllib.parse import quote_plus, urlparse, urlunparse, parse_qsl, urlencode
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

load_dotenv()


def _build_neon_database_url() -> str:
    raw_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("DATABASE_URL_UNPOOLED")
        or os.getenv("POSTGRES_URL_NON_POOLING")
    )

    if not raw_url:
        pg_host = os.getenv("PGHOST", "127.0.0.1")
        pg_port = os.getenv("PGPORT", "5432")
        pg_user = os.getenv("PGUSER", "postgres")
        pg_password = quote_plus(os.getenv("PGPASSWORD", ""))
        pg_db = os.getenv("PGDATABASE", "nexus_code_crm")
        ssl_part = "" if pg_host in ("127.0.0.1", "localhost") else "?sslmode=require"
        return f"postgresql+psycopg2://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}{ssl_part}"

    # Normaliza prefixo padrão do Neon/Heroku (postgres:// -> postgresql+psycopg2://)
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql+psycopg2://" + raw_url[len("postgres://"):]
    elif raw_url.startswith("postgresql://"):
        raw_url = "postgresql+psycopg2://" + raw_url[len("postgresql://"):]

    parsed = urlparse(raw_url)
    query_params = dict(parse_qsl(parsed.query))

    # Remove channel_binding caso presente para máxima compatibilidade com runtimes serverless
    query_params.pop("channel_binding", None)

    is_local = parsed.hostname in ("127.0.0.1", "localhost")
    if not is_local and "sslmode" not in query_params:
        query_params["sslmode"] = "require"

    new_query = urlencode(query_params)
    return urlunparse(parsed._replace(query=new_query))


DATABASE_URL = _build_neon_database_url()
IS_VERCEL = bool(os.getenv("VERCEL"))

engine_kwargs = {
    "pool_pre_ping": True,
}
if IS_VERCEL:
    # Em ambiente serverless (Vercel + Neon PgBouncer), NullPool evita conexões ociosas presas
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
