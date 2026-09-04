"""Conexao com o banco e sessao do SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import config

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
SessaoLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def obter_sessao() -> Iterator[Session]:
    """Dependencia do FastAPI: abre e fecha a sessao por requisicao."""
    sessao = SessaoLocal()
    try:
        yield sessao
    finally:
        sessao.close()
