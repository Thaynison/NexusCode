import os
from urllib.parse import quote_plus, urlparse, urlunparse, parse_qsl, urlencode
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

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

    if raw_url.startswith("postgres://"):
        raw_url = "postgresql+psycopg2://" + raw_url[len("postgres://"):]
    elif raw_url.startswith("postgresql://"):
        raw_url = "postgresql+psycopg2://" + raw_url[len("postgresql://"):]

    parsed = urlparse(raw_url)
    query_params = dict(parse_qsl(parsed.query))
    query_params.pop("channel_binding", None)

    is_local = parsed.hostname in ("127.0.0.1", "localhost")
    if not is_local and "sslmode" not in query_params:
        query_params["sslmode"] = "require"

    new_query = urlencode(query_params)
    return urlunparse(parsed._replace(query=new_query))


DATABASE_URL = _build_neon_database_url()
IS_VERCEL = bool(os.getenv("VERCEL"))

# Conexão persistente otimizada com TCP keepalive: evita round-trips extras de SELECT 1 (pool_pre_ping)
# e reaproveita o handshake TLS dentro da instância Vercel em gru1 (São Paulo).
engine = create_engine(
    DATABASE_URL,
    pool_size=3 if IS_VERCEL else 6,
    max_overflow=4 if IS_VERCEL else 10,
    pool_timeout=10,
    pool_recycle=45,
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 12,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
