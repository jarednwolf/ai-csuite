import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def _database_url() -> str:
    # 1) Explicit DATABASE_URL if provided
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    # 2) Compose from POSTGRES_* envs (Docker Compose path)
    host = os.getenv("POSTGRES_HOST")
    if host:
        user = os.getenv("POSTGRES_USER", "csuite")
        password = os.getenv("POSTGRES_PASSWORD", "csuite")
        db = os.getenv("POSTGRES_DB", "csuite")
        return f"postgresql+psycopg://{user}:{password}@{host}:5432/{db}"
    # 3) CI/Local fallback (keeps tests green without Postgres)
    return "sqlite:///./dev.db"

DATABASE_URL = _database_url()

# Synchronous SQLAlchemy engine/session (simple & reliable for MVP)
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()

_tables_initialized = False

def get_db():
    db = SessionLocal()
    try:
        global _tables_initialized
        if not _tables_initialized:
            # Import models to ensure metadata is populated, then create tables lazily
            from . import models  # noqa: F401
            Base.metadata.create_all(bind=engine)
            _tables_initialized = True
        yield db
    finally:
        db.close()


