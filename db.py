# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Загружаем переменные окружения из .env (если есть)
load_dotenv()

# Берём строку подключения из .env (рекомендуется), иначе используем дефолт ниже
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://neondb_owner:npg_bRgMocauH25U@ep-curly-bird-a228n5ay-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"
)

# Создаём engine
engine = create_engine(
    DB_URL,
    future=True,
    echo=True,          # включи для дебага; можно выключить в проде
    pool_pre_ping=True  # безопаснее для облака (reconnect при разрыве)
)

# Фабрика сессий
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    # Чуть меньше шансов словить DetachedInstanceError при рендеринге шаблонов
    expire_on_commit=False
)

# База для моделей
Base = declarative_base()
