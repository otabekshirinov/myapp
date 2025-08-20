# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

def _normalize_url(url: str) -> str:
    """Делаем URL совместимым с SQLAlchemy + psycopg (v3)."""
    url = url.strip()
    if url.startswith("postgres://"):
        # старый префикс -> новый
        url = url.replace("postgres://", "postgresql://", 1)
    # если драйвер не указан — принудительно ставим psycopg (v3)
    if url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    # если вдруг остался psycopg2 — заменим на psycopg
    if url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    return url

# БЕРЁМ ТОЛЬКО ИЗ ENV. (Не хардкодьте секреты в коде!)
DB_URL = os.getenv("DATABASE_URL", "")
if not DB_URL:
    raise RuntimeError("DATABASE_URL is not set. Укажите переменную окружения с DSN Neon.")

DB_URL = _normalize_url(DB_URL)

engine = create_engine(
    DB_URL,
    future=True,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=os.getenv("SQL_ECHO", "0") == "1",
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)
