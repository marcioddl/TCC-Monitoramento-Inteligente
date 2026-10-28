"""tabelas"""

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ClasseOcorrencia, StatusOcorrencia


class Ocorrencia(Base):
    __tablename__ = "ocorrencia"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    protocolo: Mapped[str] = mapped_column(String(24), unique=True, index=True)

    classe_informada: Mapped[ClasseOcorrencia] = mapped_column(
        Enum(ClasseOcorrencia, name="classe_ocorrencia")
    )
    classe_detectada: Mapped[ClasseOcorrencia | None] = mapped_column(
        Enum(ClasseOcorrencia, name="classe_ocorrencia"), nullable=True
    )
    confianca: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Decisao do gestor na validacao. Fica separada da classe detectada para
    # permitir medir, em producao, a concordancia entre modelo e gestor.
    classe_validada: Mapped[ClasseOcorrencia | None] = mapped_column(
        Enum(ClasseOcorrencia, name="classe_ocorrencia"), nullable=True
    )
    # Caixas devolvidas pelo YOLO: [{classe, confianca, caixa: [x1,y1,x2,y2]}]
    # com coordenadas normalizadas entre 0 e 1
    deteccoes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    modelo_versao: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[StatusOcorrencia] = mapped_column(
        Enum(StatusOcorrencia, name="status_ocorrencia"),
        default=StatusOcorrencia.RECEBIDA,
        index=True,
    )

    # geography em WGS 84: distancias saem diretamente em metros
    geom: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True)
    )
    raio_m: Mapped[int] = mapped_column(Integer, default=100)

    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    imagem_path: Mapped[str] = mapped_column(String(255))
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    notificacoes = relationship("NotificacaoEnviada", back_populates="ocorrencia")
    auditorias = relationship("Auditoria", back_populates="ocorrencia")

    @property
    def classe_final(self) -> ClasseOcorrencia:
        """Melhor informacao disponivel: gestor, depois modelo, depois cidadao."""
        return self.classe_validada or self.classe_detectada or self.classe_informada


class Dispositivo(Base):
    """Substitui a entidade de usuario. O identificador e gerado pelo
    aplicativo na primeira execucao e persistido localmente."""

    __tablename__ = "dispositivo"

    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    fcm_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notificacoes_habilitadas: Mapped[bool] = mapped_column(Boolean, default=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NotificacaoEnviada(Base):
    """A restricao de unicidade abaixo e a deduplicacao de alertas: o banco
    impede que o mesmo dispositivo receba duas vezes o alerta da mesma
    ocorrencia, sem depender de logica de aplicacao."""

    __tablename__ = "notificacao_enviada"
    __table_args__ = (
        UniqueConstraint("ocorrencia_id", "device_id", name="uq_notificacao_ocorrencia_device"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ocorrencia_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ocorrencia.id", ondelete="CASCADE")
    )
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    enviada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Distancia entre o dispositivo e a ocorrencia no momento do disparo.
    # A posicao do dispositivo em si nao e armazenada (LGPD).
    distancia_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    # "fcm" quando o push saiu pelo Firebase; "app" quando o alerta foi
    # entregue apenas na resposta da consulta (app em primeiro plano)
    canal: Mapped[str] = mapped_column(String(16), default="app", server_default="app")

    ocorrencia = relationship("Ocorrencia", back_populates="notificacoes")


class Auditoria(Base):
    """Rastreabilidade das alteracoes de estado das ocorrencias."""

    __tablename__ = "auditoria"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ocorrencia_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ocorrencia.id", ondelete="CASCADE"), index=True
    )
    acao: Mapped[str] = mapped_column(String(50))
    detalhe: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ocorrencia = relationship("Ocorrencia", back_populates="auditorias")
