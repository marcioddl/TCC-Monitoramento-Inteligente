"""Regras de negocio do ciclo de vida das ocorrencias.

Ciclo (capitulo 4 da monografia):

  Percepcao e reporte  -> o cidadao fotografa; o app captura o GPS
  Recepcao e triagem   -> o YOLO sugere a classe; baixa confianca ou
                          divergencia com o cidadao vai para triagem humana
  Registro geoespacial -> ponto gravado em geography com indice GiST
  Alerta proativo      -> validada, a ocorrencia vira uma geocerca de raio_m
  Gestao e resolucao   -> o gestor conduz ate resolvida ou rejeitada

Toda mudanca de estado gera um registro na tabela de auditoria.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import config
from app.enums import ClasseOcorrencia, StatusOcorrencia, transicao_valida
from app.models import Auditoria, Ocorrencia
from app.servicos import geo
from app.servicos.classificador import Classificador, ResultadoClassificacao
from app.servicos.imagens import processar_e_salvar
from app.servicos.protocolo import gerar_protocolo

log = logging.getLogger("miiu.ocorrencias")


class LimiteExcedido(Exception):
    pass


class TransicaoInvalida(Exception):
    pass


@dataclass
class Decisao:
    status: StatusOcorrencia
    motivo: str


def decidir_status(
    classe_informada: ClasseOcorrencia,
    resultado: ResultadoClassificacao | None,
    limiar: float,
) -> Decisao:
    """Recepcao e triagem: decide se a ocorrencia precisa de olho humano."""
    if resultado is None:
        return Decisao(StatusOcorrencia.EM_TRIAGEM, "modelo_indisponivel")
    if resultado.classe is None:
        return Decisao(StatusOcorrencia.EM_TRIAGEM, "sem_deteccao")
    if resultado.confianca < limiar:
        return Decisao(StatusOcorrencia.EM_TRIAGEM, "baixa_confianca")
    if resultado.classe != classe_informada:
        return Decisao(StatusOcorrencia.EM_TRIAGEM, "divergencia_cidadao_modelo")
    return Decisao(StatusOcorrencia.CLASSIFICADA, "confianca_acima_do_limiar")


def registrar(sessao: Session, ocorrencia_id: uuid.UUID, acao: str, detalhe: dict | None = None):
    # Horario do Python, nao o now() do banco: dentro de uma transacao o
    # now() e constante, e eventos da mesma requisicao ficariam empatados
    sessao.add(Auditoria(
        ocorrencia_id=ocorrencia_id, acao=acao, detalhe=detalhe,
        criado_em=datetime.now(timezone.utc),
    ))


def verificar_limite(sessao: Session, device_id: uuid.UUID) -> None:
    uma_hora = datetime.now(timezone.utc) - timedelta(hours=1)
    recentes = sessao.scalar(
        select(func.count()).select_from(Ocorrencia).where(
            Ocorrencia.device_id == device_id, Ocorrencia.criado_em >= uma_hora
        )
    )
    if recentes >= config.LIMITE_REPORTES_HORA:
        raise LimiteExcedido(
            f"limite de {config.LIMITE_REPORTES_HORA} reportes por hora atingido"
        )


def _protocolo_unico(sessao: Session) -> str:
    for _ in range(10):
        protocolo = gerar_protocolo()
        existe = sessao.scalar(select(Ocorrencia.id).where(Ocorrencia.protocolo == protocolo))
        if existe is None:
            return protocolo
    raise RuntimeError("nao foi possivel gerar um protocolo unico")


def criar_ocorrencia(
    sessao: Session,
    *,
    dados_imagem: bytes,
    latitude: float,
    longitude: float,
    classe_informada: ClasseOcorrencia,
    descricao: str | None,
    device_id: uuid.UUID,
    precisao_m: float | None,
    classificador: Classificador,
) -> Ocorrencia:
    verificar_limite(sessao, device_id)

    pasta = Path(config.UPLOAD_DIR)
    salva = processar_e_salvar(dados_imagem, pasta, config.IMAGEM_LADO_MAX)

    try:
        try:
            resultado = classificador.classificar(salva.imagem)
        except Exception:
            # Falha de inferencia nao pode perder o reporte do cidadao
            log.exception("falha na inferencia; ocorrencia vai para triagem")
            resultado = None

        decisao = decidir_status(classe_informada, resultado, config.INFERENCIA_LIMIAR)

        ocorrencia = Ocorrencia(
            id=uuid.uuid4(),
            protocolo=_protocolo_unico(sessao),
            classe_informada=classe_informada,
            classe_detectada=resultado.classe if resultado else None,
            confianca=resultado.confianca if resultado and resultado.classe else None,
            deteccoes=resultado.deteccoes_json() if resultado else None,
            modelo_versao=resultado.modelo_versao if resultado else None,
            status=decisao.status,
            geom=geo.ponto_para_gravar(latitude, longitude),
            raio_m=config.GEOFENCE_RAIO_PADRAO,
            descricao=(descricao or "").strip() or None,
            imagem_path=salva.caminho_relativo,
            device_id=device_id,
        )
        sessao.add(ocorrencia)
        sessao.flush()

        registrar(sessao, ocorrencia.id, "criacao", {
            "status": StatusOcorrencia.RECEBIDA.value,
            "precisao_gps_m": precisao_m,
            "imagem": {"largura": salva.largura, "altura": salva.altura},
        })
        registrar(sessao, ocorrencia.id, "classificacao", {
            "de": StatusOcorrencia.RECEBIDA.value,
            "para": decisao.status.value,
            "motivo": decisao.motivo,
            "limiar": config.INFERENCIA_LIMIAR,
            "classe_detectada": resultado.classe.value if resultado and resultado.classe else None,
            "confianca": resultado.confianca if resultado else None,
            "caixas": len(resultado.deteccoes) if resultado else 0,
            "tempo_inferencia_ms": resultado.tempo_ms if resultado else None,
            "modelo": resultado.modelo_versao if resultado else classificador.motivo,
        })
        sessao.commit()
    except Exception:
        sessao.rollback()
        (pasta / salva.caminho_relativo).unlink(missing_ok=True)
        raise

    sessao.refresh(ocorrencia)
    return ocorrencia


def mudar_status(
    sessao: Session,
    ocorrencia: Ocorrencia,
    novo: StatusOcorrencia,
    *,
    classe_validada: ClasseOcorrencia | None = None,
    observacao: str | None = None,
    raio_m: int | None = None,
) -> Ocorrencia:
    atual = ocorrencia.status
    if not transicao_valida(atual, novo):
        raise TransicaoInvalida(f"transicao nao permitida: {atual.value} -> {novo.value}")

    if novo == StatusOcorrencia.VALIDADA:
        ocorrencia.classe_validada = classe_validada or ocorrencia.classe_final
    elif classe_validada is not None:
        ocorrencia.classe_validada = classe_validada

    if raio_m is not None:
        ocorrencia.raio_m = min(raio_m, config.GEOFENCE_RAIO_MAX)

    ocorrencia.status = novo
    registrar(sessao, ocorrencia.id, "mudanca_status", {
        "de": atual.value,
        "para": novo.value,
        "classe_validada": ocorrencia.classe_validada.value if ocorrencia.classe_validada else None,
        "observacao": observacao,
        "raio_m": ocorrencia.raio_m,
    })
    sessao.commit()
    sessao.refresh(ocorrencia)
    return ocorrencia
