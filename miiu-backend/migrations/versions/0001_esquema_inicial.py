"""Esquema inicial do MIIU

A extensao PostGIS e criada antes de qualquer tabela, porque o tipo
geography da tabela de ocorrencias depende dela. O indice GiST tambem
entra aqui: deixa-lo para depois exigiria refazer a migracao.

Revision ID: 0001
Revises:
"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    classe = postgresql.ENUM(
        "BURACO", "CALCADA_DANIFICADA", name="classe_ocorrencia", create_type=False
    )
    status = postgresql.ENUM(
        "RECEBIDA", "CLASSIFICADA", "EM_TRIAGEM", "VALIDADA",
        "EM_ATENDIMENTO", "RESOLVIDA", "REJEITADA",
        name="status_ocorrencia", create_type=False,
    )
    classe.create(op.get_bind(), checkfirst=True)
    status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ocorrencia",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("protocolo", sa.String(24), nullable=False),
        sa.Column("classe_informada", classe, nullable=False),
        sa.Column("classe_detectada", classe, nullable=True),
        sa.Column("confianca", sa.Float(), nullable=True),
        sa.Column("status", status, nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geography(
                geometry_type="POINT", srid=4326, from_text="ST_GeogFromText",
                name="geography", nullable=False,
                # o GeoAlchemy2 criaria o indice sozinho, com o mesmo nome
                # usado abaixo; desligamos aqui para cria-lo explicitamente
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.Column("raio_m", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("imagem_path", sa.String(255), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ocorrencia_protocolo", "ocorrencia", ["protocolo"], unique=True)
    op.create_index("ix_ocorrencia_status", "ocorrencia", ["status"])
    op.create_index("ix_ocorrencia_device_id", "ocorrencia", ["device_id"])
    op.create_index("ix_ocorrencia_criado_em", "ocorrencia", ["criado_em"])
    # indice espacial: sem ele, toda consulta de proximidade varre a tabela
    op.create_index(
        "idx_ocorrencia_geom", "ocorrencia", ["geom"], postgresql_using="gist"
    )

    op.create_table(
        "dispositivo",
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fcm_token", sa.String(255), nullable=True),
        sa.Column("notificacoes_habilitadas", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("device_id"),
    )

    op.create_table(
        "notificacao_enviada",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ocorrencia_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enviada_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ocorrencia_id"], ["ocorrencia.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # deduplicacao garantida pelo banco
        sa.UniqueConstraint("ocorrencia_id", "device_id", name="uq_notificacao_ocorrencia_device"),
    )
    op.create_index("ix_notificacao_device_id", "notificacao_enviada", ["device_id"])

    op.create_table(
        "auditoria",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ocorrencia_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("acao", sa.String(50), nullable=False),
        sa.Column("detalhe", postgresql.JSONB(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ocorrencia_id"], ["ocorrencia.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auditoria_ocorrencia_id", "auditoria", ["ocorrencia_id"])


def downgrade() -> None:
    op.drop_table("auditoria")
    op.drop_table("notificacao_enviada")
    op.drop_table("dispositivo")
    op.drop_index("idx_ocorrencia_geom", table_name="ocorrencia")
    op.drop_table("ocorrencia")
    postgresql.ENUM(name="status_ocorrencia").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="classe_ocorrencia").drop(op.get_bind(), checkfirst=True)
