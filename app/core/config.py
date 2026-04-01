"""
Configuracoes centrais da aplicacao.

Carrega variaveis de ambiente via .env e expoe como objeto tipado.
Todos os modulos importam 'settings' daqui — e uma unica fonte de verdade.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuracoes globais carregadas de variaveis de ambiente."""

    # ── Aplicacao ────────────────────────────────
    APP_NAME: str = "Juris Intelligence API"
    APP_VERSION: str = "0.2.0"
    DEBUG: bool = True

    # ── Banco de Dados ─────────────────────────────
    # SQLite para desenvolvimento local, PostgreSQL para producao (Docker)
    DATABASE_URL: str = "sqlite:///./juris_intelligence.db"

    # ── Redis (Broker do Celery + Cache) ─────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Celery ───────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── JWT / Autenticacao ───────────────────────
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── LLM / IA (preparado para integracao) ─────
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 4096

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
