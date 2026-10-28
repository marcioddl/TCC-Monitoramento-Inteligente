"""Validacao pelo gestor, deteccoes do modelo e metricas dos alertas

Acrescenta a ocorrencia a classe decidida pelo gestor (separada da classe
detectada, para medir a concordancia entre modelo e gestor), as caixas
devolvidas pelo YOLO e a versao do modelo que as produziu. Na tabela de
notificacoes, registra a distancia no momento do disparo e o canal de entrega.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # o tipo ja existe desde a 0001; create_type=False evita recria-lo
    classe = postgresql.ENUM(
        "BURACO", "CALCADA_DANIFICADA", name="classe_ocorrencia", create_type=False
    )

    op.add_column("ocorrencia", sa.Column("classe_validada", classe, nullable=True))
    op.add_column("ocorrencia", sa.Column("deteccoes", postgresql.JSONB(), nullable=True))
    op.add_column("ocorrencia", sa.Column("modelo_versao", sa.String(64), nullable=True))

    op.add_column(
        "notificacao_enviada", sa.Column("distancia_m", sa.Float(), nullable=True)
    )
    op.add_column(
        "notificacao_enviada",
        sa.Column("canal", sa.String(16), nullable=False, server_default="app"),
    )


def downgrade() -> None:
    op.drop_column("notificacao_enviada", "canal")
    op.drop_column("notificacao_enviada", "distancia_m")
    op.drop_column("ocorrencia", "modelo_versao")
    op.drop_column("ocorrencia", "deteccoes")
    op.drop_column("ocorrencia", "classe_validada")
