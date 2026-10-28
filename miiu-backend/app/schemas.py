"""Formatos de entrada e saida da API (Pydantic v2).

Os enums sao serializados pelo valor ("validada", "buraco"), que e o que o
aplicativo e o painel exibem e enviam.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ClasseOcorrencia, StatusOcorrencia

ROTULOS_CLASSE = {
    ClasseOcorrencia.BURACO: "Buraco na via",
    ClasseOcorrencia.CALCADA_DANIFICADA: "Calçada danificada",
}


# ------------------------------------------------------------------ cidadao

class OcorrenciaCriada(BaseModel):
    protocolo: str
    status: StatusOcorrencia
    classe_informada: ClasseOcorrencia
    classe_detectada: ClasseOcorrencia | None
    confianca: float | None
    criado_em: datetime
    mensagem: str


class EventoHistorico(BaseModel):
    status: StatusOcorrencia
    em: datetime


class OcorrenciaPublica(BaseModel):
    protocolo: str
    status: StatusOcorrencia
    classe_informada: ClasseOcorrencia
    classe_detectada: ClasseOcorrencia | None
    classe_final: ClasseOcorrencia
    confianca: float | None
    latitude: float
    longitude: float
    descricao: str | None
    criado_em: datetime
    atualizado_em: datetime
    historico: list[EventoHistorico]
    imagem_url: str


class PontoMapa(BaseModel):
    """Ocorrencia ativa no mapa publico. Sem descricao nem imagem: o mapa e
    aberto a qualquer pessoa e o texto livre pode conter dado pessoal."""

    protocolo: str
    classe: ClasseOcorrencia
    status: StatusOcorrencia
    latitude: float
    longitude: float
    raio_m: int
    criado_em: datetime


class DispositivoEntrada(BaseModel):
    fcm_token: str | None = Field(default=None, max_length=255)
    notificacoes_habilitadas: bool | None = None


class DispositivoSaida(BaseModel):
    device_id: uuid.UUID
    notificacoes_habilitadas: bool
    fcm_registrado: bool
    modo_push: str


class ConsultaProximidade(BaseModel):
    device_id: uuid.UUID
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    # incerteza horizontal informada pelo GPS do aparelho, em metros
    precisao_m: float | None = Field(default=None, ge=0)


class Alerta(BaseModel):
    protocolo: str
    classe: ClasseOcorrencia
    status: StatusOcorrencia
    distancia_m: float
    latitude: float
    longitude: float
    raio_m: int
    mensagem: str
    canal: str


class RespostaProximidade(BaseModel):
    alertas: list[Alerta]
    ignorada: bool = False
    motivo: str | None = None
    verificado_em: datetime


# ------------------------------------------------------------------ painel

class Login(BaseModel):
    senha: str = Field(min_length=1, max_length=200)


class TokenSaida(BaseModel):
    token: str
    expira_em: datetime


class OcorrenciaResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    protocolo: str
    status: StatusOcorrencia
    classe_informada: ClasseOcorrencia
    classe_detectada: ClasseOcorrencia | None
    classe_validada: ClasseOcorrencia | None
    classe_final: ClasseOcorrencia
    confianca: float | None
    latitude: float
    longitude: float
    raio_m: int
    criado_em: datetime
    atualizado_em: datetime


class ListaOcorrencias(BaseModel):
    total: int
    itens: list[OcorrenciaResumo]


class EventoAuditoria(BaseModel):
    acao: str
    detalhe: dict | None
    criado_em: datetime


class PossivelDuplicata(BaseModel):
    id: uuid.UUID
    protocolo: str
    status: StatusOcorrencia
    distancia_m: float
    criado_em: datetime


class OcorrenciaDetalhe(OcorrenciaResumo):
    descricao: str | None
    deteccoes: list[dict] | None
    modelo_versao: str | None
    imagem_url: str
    auditoria: list[EventoAuditoria]
    possiveis_duplicatas: list[PossivelDuplicata]
    notificacoes_enviadas: int
    transicoes_permitidas: list[StatusOcorrencia]


class MudancaStatus(BaseModel):
    status: StatusOcorrencia
    # na validacao: a classe decidida pelo gestor (padrao: a melhor disponivel)
    classe_validada: ClasseOcorrencia | None = None
    observacao: str | None = Field(default=None, max_length=500)
    raio_m: int | None = Field(default=None, ge=10)


class ContagemDia(BaseModel):
    dia: str
    total: int


class Estatisticas(BaseModel):
    total: int
    por_status: dict[str, int]
    por_classe: dict[str, int]
    por_dia: list[ContagemDia]
    # proporcao das ocorrencias classificadas sem passar pela triagem humana
    taxa_automacao: float | None
    # entre as validadas que tinham deteccao: modelo acertou a classe do gestor
    concordancia_modelo: float | None
    # entre as validadas: cidadao informou a mesma classe decidida pelo gestor
    concordancia_cidadao: float | None
    validadas_avaliadas: int
    confianca_media: float | None
    tempo_medio_triagem_h: float | None
    tempo_medio_resolucao_h: float | None
    notificacoes_enviadas: int
    notificacoes_por_canal: dict[str, int]
    distancia_media_alerta_m: float | None
    dispositivos_ativos_7d: int
