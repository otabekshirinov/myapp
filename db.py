# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

def _normalize_url(url: str) -> str:
    """Делаем URL совместимым с SQLAlchemy + psycopg (v3) и добавляем sslmode при необходимости."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    # добавим sslmode=require, если его нет
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url

# Только из ENV (не хардкодим секреты)
DB_URL = os.getenv("DATABASE_URL", "")
if not DB_URL:
    raise RuntimeError("DATABASE_URL is not set. Укажите переменную окружения с DSN Neon.")

DB_URL = _normalize_url(DB_URL)

engine = create_engine(
    DB_URL,
    future=True,
    pool_pre_ping=True,   # авто-переподключение
    pool_recycle=300,     # раз в 5 мин обновляем соединение
    pool_size=int(os.getenv("DB_POOL_SIZE", 3)),      # чуть скромнее для фритира
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 2)),
    echo=os.getenv("SQL_ECHO", "0") == "1",
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)
