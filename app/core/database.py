"""
Configuracao do SQLAlchemy e gerenciamento de sessoes.

Fornece:
- engine: conexao com o banco (SQLite local / PostgreSQL producao)
- SessionLocal: fabrica de sessoes
- Base: classe declarativa para todos os models
- get_db(): dependency injection para rotas FastAPI
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# SQLite nao suporta pool_size — detectar automaticamente
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs = {"pool_pre_ping": True}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Classe base declarativa para todos os modelos SQLAlchemy do sistema."""
    pass


def get_db():
    """Fornece uma sessao de banco de dados por requisicao (Dependency Injection).

    Uso tipico em rotas FastAPI:
        def minha_rota(db: Session = Depends(get_db)):
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
