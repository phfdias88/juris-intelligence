"""
Configuracao global dos testes.

Cria um banco SQLite em memoria para cada sessao de testes,
substituindo o banco real. Garante isolamento total.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.celery_app import celery_app
from app.main import app

# Banco em memoria para testes
SQLALCHEMY_TEST_URL = "sqlite:///./test.db"

engine_test = create_engine(
    SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Cria todas as tabelas antes dos testes e remove depois."""
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)

    # Forcar Celery em modo eager (sincrono) nos testes
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )

    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture()
def db():
    """Fornece uma sessao de banco limpa para cada teste."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture()
def client():
    """Fornece um TestClient do FastAPI com banco de teste."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def cnj_unico():
    """Gera um numero CNJ unico para cada teste."""
    n = uuid.uuid4().int % 9999999
    return f"{n:07d}-00.2024.8.26.0100"
