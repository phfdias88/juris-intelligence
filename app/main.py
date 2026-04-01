"""
Entrypoint da aplicacao FastAPI.

Para iniciar:
    uvicorn app.main:app --reload

Para iniciar o worker Celery (em outro terminal):
    celery -A app.core.celery_app worker --loglevel=info --pool=solo
"""

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import Base, engine

# Importa models para garantir que o SQLAlchemy os registre antes do create_all
from app.domains.shared import models as _shared_models  # noqa: F401

# Cria tabelas no banco (em producao, usar Alembic migrations exclusivamente)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API de Inteligencia Juridica Avancada — "
        "Jurimetria Preditiva, Gestao de Testemunhas, Litigation Finance"
    ),
)

# ── Registrar routers dos dominios ───────────────
from app.domains.shared.router import router as processos_router
from app.domains.litigation_finance.router import router as litfin_router
from app.domains.legal_intelligence.router import router as legal_router
from app.domains.jurimetrics.router import router as jurimetrics_router
from app.domains.agent_system.router import router as agents_router

app.include_router(processos_router, prefix="/api/v1")
app.include_router(litfin_router, prefix="/api/v1")
app.include_router(legal_router, prefix="/api/v1")
app.include_router(jurimetrics_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health_check():
    """Endpoint de verificacao de saude da API."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "services": {
            "database": "postgresql",
            "broker": "redis",
            "worker": "celery",
        },
    }
