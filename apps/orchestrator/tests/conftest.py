
# Ensure the orchestrator package is importable in tests
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orchestrator.db import Base


@pytest.fixture
def db_session(tmp_path):
    """In-memory SQLite session for unit tests that need DB access.
    Uses a file-backed SQLite in tmp to match SQLAlchemy behavior for create_all.
    """
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

