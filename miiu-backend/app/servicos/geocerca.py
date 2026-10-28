"""Mecanismo de geofencing (alerta proativo).

Cada ocorrencia validada (ou em atendimento) define uma geocerca circular
de raio_m metros ao redor do seu ponto, 100 m por padrao (Shevchenko; Reips,
2024). O aplicativo informa periodicamente a posicao do aparelho; o backend
verifica, numa unica consulta espacial, em quais geocercas ativas o aparelho
esta e para quais delas ainda nao avisou esse aparelho.

Decisoes de projeto:

- A posicao do aparelho e usada so nesta verificacao e nao e gravada (LGPD).
  Fica registrado apenas que o alerta X foi entregue ao aparelho Y, e a que
  distancia.
- A deduplicacao e garantida pelo banco (restricao unica ocorrencia+aparelho
  com INSERT ... ON CONFLICT DO NOTHING), inclusive sob requisicoes
  simultaneas do mesmo aparelho.
- O aparelho que reportou a ocorrencia nao e alertado sobre ela.
- Leituras de GPS imprecisas demais sao descartadas, para evitar alertas
  falsos (a precisao do geofencing depende da qualidade da localizacao).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import config
from app.enums import ClasseOcorrencia, StatusOcorrencia
from app.models import Dispositivo, NotificacaoEnviada, Ocorrencia
from app.schemas import ROTULOS_CLASSE
from app.servicos import geo
from app.servicos.notificacoes import Notificador

STATUS_ALERTAVEIS = (StatusOcorrencia.VALIDADA, StatusOcorrencia.EM_ATENDIMENTO)


@dataclass
class AlertaGerado:
    protocolo: str
    classe: ClasseOcorrencia
    status: StatusOcorrencia
    distancia_m: float
    latitude: float
    longitude: float
    raio_m: int
    mensagem: str
    canal: str


@dataclass
class ResultadoVerificacao:
    alertas: list[AlertaGerado]
    ignorada: bool = False
    motivo: str | None = None
    verificado_em: datetime | None = None


def mensagem_alerta(classe: ClasseOcorrencia, distancia_m: float) -> str:
    return f"{ROTULOS_CLASSE[classe]} a {distancia_m:.0f} m de você"


def _tocar_dispositivo(sessao: Session, device_id: uuid.UUID) -> Dispositivo:
    """Obtem o registro do aparelho, criando-o no primeiro contato."""
    insert_disp = insert(Dispositivo).values(device_id=device_id).on_conflict_do_update(
        index_elements=[Dispositivo.device_id], set_={"atualizado_em": func.now()}
    )
    sessao.execute(insert_disp)
    return sessao.get(Dispositivo, device_id, populate_existing=True)


def verificar_proximidade(
    sessao: Session,
    notificador: Notificador,
    device_id: uuid.UUID,
    lat: float,
    lon: float,
    precisao_m: float | None = None,
) -> ResultadoVerificacao:
    agora = datetime.now(timezone.utc)
    dispositivo = _tocar_dispositivo(sessao, device_id)

    if not dispositivo.notificacoes_habilitadas:
        sessao.commit()
        return ResultadoVerificacao([], True, "notificacoes_desabilitadas", agora)

    if precisao_m is not None and precisao_m > config.GEOFENCE_PRECISAO_MAX_M:
        sessao.commit()
        return ResultadoVerificacao([], True, "precisao_gps_insuficiente", agora)

    aqui = geo.ponto(lat, lon)
    distancia = func.ST_Distance(Ocorrencia.geom, aqui)
    ja_notificado = exists().where(
        NotificacaoEnviada.ocorrencia_id == Ocorrencia.id,
        NotificacaoEnviada.device_id == device_id,
    )

    consulta = (
        select(
            Ocorrencia.id, Ocorrencia.protocolo, Ocorrencia.status,
            Ocorrencia.classe_validada, Ocorrencia.classe_detectada,
            Ocorrencia.classe_informada, Ocorrencia.raio_m,
            geo.latitude.label("lat"), geo.longitude.label("lon"),
            distancia.label("distancia"),
        )
        .where(
            Ocorrencia.status.in_(STATUS_ALERTAVEIS),
            # Raio constante: permite ao PostgreSQL usar o indice GiST.
            # Com o raio vindo da propria linha (abaixo), o indice nao seria usado.
            func.ST_DWithin(Ocorrencia.geom, aqui, config.GEOFENCE_RAIO_MAX),
            func.ST_DWithin(Ocorrencia.geom, aqui, Ocorrencia.raio_m),
            Ocorrencia.device_id != device_id,
            ~ja_notificado,
        )
        .order_by(distancia)
    )

    alertas: list[AlertaGerado] = []
    for linha in sessao.execute(consulta).all():
        # Reivindica o alerta antes de enviar: se outra requisicao do mesmo
        # aparelho chegou primeiro, o insert nao retorna nada e pulamos
        reivindicado = sessao.execute(
            insert(NotificacaoEnviada)
            .values(
                id=uuid.uuid4(), ocorrencia_id=linha.id, device_id=device_id,
                distancia_m=round(linha.distancia, 1), canal="app",
            )
            .on_conflict_do_nothing(constraint="uq_notificacao_ocorrencia_device")
            .returning(NotificacaoEnviada.id)
        ).scalar()
        if reivindicado is None:
            continue

        classe = linha.classe_validada or linha.classe_detectada or linha.classe_informada
        mensagem = mensagem_alerta(classe, linha.distancia)
        canal = "app"

        if dispositivo.fcm_token:
            envio = notificador.enviar(
                dispositivo.fcm_token,
                titulo="Atenção no caminho",
                corpo=mensagem,
                dados={
                    "tipo": "geocerca",
                    "protocolo": linha.protocolo,
                    "classe": classe.value,
                    "distancia_m": f"{linha.distancia:.0f}",
                    "latitude": f"{linha.lat:.6f}",
                    "longitude": f"{linha.lon:.6f}",
                },
            )
            if envio.enviado:
                canal = "fcm"
                sessao.execute(
                    update(NotificacaoEnviada)
                    .where(NotificacaoEnviada.id == reivindicado)
                    .values(canal="fcm")
                )
            elif envio.token_invalido:
                dispositivo.fcm_token = None

        alertas.append(AlertaGerado(
            protocolo=linha.protocolo,
            classe=classe,
            status=linha.status,
            distancia_m=round(linha.distancia, 1),
            latitude=linha.lat,
            longitude=linha.lon,
            raio_m=linha.raio_m,
            mensagem=mensagem,
            canal=canal,
        ))

    sessao.commit()
    return ResultadoVerificacao(alertas, verificado_em=agora)
