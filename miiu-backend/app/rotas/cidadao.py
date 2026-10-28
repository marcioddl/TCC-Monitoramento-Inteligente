"""Rotas usadas pelo aplicativo do cidadao (sem login: o protocolo e a chave)."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import config
from app.database import obter_sessao
from app.dependencias import obter_classificador
from app.enums import ClasseOcorrencia, StatusOcorrencia
from app.models import Auditoria, Ocorrencia
from app.schemas import EventoHistorico, OcorrenciaCriada, OcorrenciaPublica, PontoMapa
from app.servicos import geo
from app.servicos.classificador import Classificador
from app.servicos.imagens import (
    ImagemGrandeDemais, ImagemInvalida, caminho_absoluto, ler_com_limite,
)
from app.servicos.ocorrencias import LimiteExcedido, criar_ocorrencia
from app.servicos.protocolo import normalizar_protocolo

rotas = APIRouter(prefix="/ocorrencias", tags=["cidadão"])

MENSAGENS = {
    StatusOcorrencia.CLASSIFICADA: (
        "Ocorrência registrada e classificada automaticamente. "
        "Ela será conferida pela equipe de gestão."
    ),
    StatusOcorrencia.EM_TRIAGEM: (
        "Ocorrência registrada. Ela passará por uma análise da equipe de gestão."
    ),
}

STATUS_PUBLICOS_NO_MAPA = (StatusOcorrencia.VALIDADA, StatusOcorrencia.EM_ATENDIMENTO)


def imagem_url(protocolo: str) -> str:
    return f"/ocorrencias/{protocolo}/imagem"


# desempate de eventos gravados no mesmo instante
ORDEM_ACOES = {"criacao": 0, "classificacao": 1, "mudanca_status": 2}


def eventos_ordenados(sessao: Session, ocorrencia_id) -> list[Auditoria]:
    eventos = sessao.scalars(
        select(Auditoria).where(Auditoria.ocorrencia_id == ocorrencia_id)
    ).all()
    return sorted(eventos, key=lambda e: (e.criado_em, ORDEM_ACOES.get(e.acao, 9)))


def _buscar_por_protocolo(sessao: Session, protocolo: str):
    linha = sessao.execute(
        select(Ocorrencia, geo.latitude, geo.longitude).where(
            Ocorrencia.protocolo == normalizar_protocolo(protocolo)
        )
    ).first()
    if linha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "protocolo não encontrado")
    return linha


@rotas.post("", response_model=OcorrenciaCriada, status_code=status.HTTP_201_CREATED)
def reportar(
    imagem: UploadFile = File(..., description="Fotografia da ocorrência (JPEG ou PNG)"),
    latitude: float = Form(..., ge=-90, le=90),
    longitude: float = Form(..., ge=-180, le=180),
    classe_informada: ClasseOcorrencia = Form(...),
    device_id: uuid.UUID = Form(...),
    descricao: str | None = Form(None, max_length=500),
    precisao_m: float | None = Form(None, ge=0),
    sessao: Session = Depends(obter_sessao),
    classificador: Classificador = Depends(obter_classificador),
):
    """Percepção e reporte: recebe a foto georreferenciada e a classifica."""
    if latitude == 0 and longitude == 0:
        # (0, 0) e o valor tipico de GPS que ainda nao obteve posicao
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "coordenadas inválidas (0, 0)")

    try:
        dados = ler_com_limite(imagem.file, config.UPLOAD_MAX_MB * 1024 * 1024)
        ocorrencia = criar_ocorrencia(
            sessao,
            dados_imagem=dados,
            latitude=latitude,
            longitude=longitude,
            classe_informada=classe_informada,
            descricao=descricao,
            device_id=device_id,
            precisao_m=precisao_m,
            classificador=classificador,
        )
    except ImagemGrandeDemais as e:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(e)) from e
    except ImagemInvalida as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    except LimiteExcedido as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(e)) from e

    return OcorrenciaCriada(
        protocolo=ocorrencia.protocolo,
        status=ocorrencia.status,
        classe_informada=ocorrencia.classe_informada,
        classe_detectada=ocorrencia.classe_detectada,
        confianca=ocorrencia.confianca,
        criado_em=ocorrencia.criado_em,
        mensagem=MENSAGENS.get(ocorrencia.status, "Ocorrência registrada."),
    )


@rotas.get("/mapa", response_model=list[PontoMapa])
def mapa_publico(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    raio_m: int = Query(3000, ge=50, le=20000),
    limite: int = Query(300, ge=1, le=1000),
    sessao: Session = Depends(obter_sessao),
):
    """Ocorrências ativas (validadas ou em atendimento) ao redor de um ponto."""
    aqui = geo.ponto(latitude, longitude)
    linhas = sessao.execute(
        select(Ocorrencia, geo.latitude, geo.longitude)
        .where(
            Ocorrencia.status.in_(STATUS_PUBLICOS_NO_MAPA),
            func.ST_DWithin(Ocorrencia.geom, aqui, raio_m),
        )
        .order_by(func.ST_Distance(Ocorrencia.geom, aqui))
        .limit(limite)
    ).all()
    return [
        PontoMapa(
            protocolo=o.protocolo, classe=o.classe_final, status=o.status,
            latitude=lat, longitude=lon, raio_m=o.raio_m, criado_em=o.criado_em,
        )
        for o, lat, lon in linhas
    ]


@rotas.get("/{protocolo}", response_model=OcorrenciaPublica)
def consultar(protocolo: str, sessao: Session = Depends(obter_sessao)):
    """Acompanhamento pelo cidadão a partir do número de protocolo."""
    o, lat, lon = _buscar_por_protocolo(sessao, protocolo)

    historico = []
    for ev in eventos_ordenados(sessao, o.id):
        if ev.acao == "criacao":
            historico.append(EventoHistorico(status=StatusOcorrencia.RECEBIDA, em=ev.criado_em))
        elif ev.acao in ("classificacao", "mudanca_status") and ev.detalhe:
            historico.append(EventoHistorico(
                status=StatusOcorrencia(ev.detalhe["para"]), em=ev.criado_em
            ))

    return OcorrenciaPublica(
        protocolo=o.protocolo,
        status=o.status,
        classe_informada=o.classe_informada,
        classe_detectada=o.classe_detectada,
        classe_final=o.classe_final,
        confianca=o.confianca,
        latitude=lat,
        longitude=lon,
        descricao=o.descricao,
        criado_em=o.criado_em,
        atualizado_em=o.atualizado_em,
        historico=historico,
        imagem_url=imagem_url(o.protocolo),
    )


@rotas.get("/{protocolo}/imagem", response_class=FileResponse)
def imagem(protocolo: str, sessao: Session = Depends(obter_sessao)):
    o, _, _ = _buscar_por_protocolo(sessao, protocolo)
    arquivo = caminho_absoluto(Path(config.UPLOAD_DIR), o.imagem_path)
    if arquivo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "imagem não encontrada")
    return FileResponse(arquivo, media_type="image/jpeg")
