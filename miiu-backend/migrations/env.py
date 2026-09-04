from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import config as cfg_app
from app.database import Base
import app.models  # noqa: F401  -- registra as tabelas no metadata

config = context.config
config.set_main_option("sqlalchemy.url", cfg_app.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def excluir_tabelas_do_postgis(objeto, nome, tipo, reflexo, comparado):
    """O PostGIS cria tabelas proprias (spatial_ref_sys). Elas nao devem
    entrar nas migracoes autogeradas."""
    if tipo == "table" and nome in {"spatial_ref_sys"}:
        return False
    return True


def rodar_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=excluir_tabelas_do_postgis,
    )
    with context.begin_transaction():
        context.run_migrations()


def rodar_online() -> None:
    conectavel = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with conectavel.connect() as conexao:
        context.configure(
            connection=conexao,
            target_metadata=target_metadata,
            include_object=excluir_tabelas_do_postgis,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    rodar_offline()
else:
    rodar_online()
