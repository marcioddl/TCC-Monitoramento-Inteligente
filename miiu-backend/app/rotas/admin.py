"""Rotas do painel de gestao. Todas, exceto o login, exigem o token."""

import csv
import io
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import config
from app.database import obter_sessao
from app.enums import TRANSICOES, ClasseOcorrencia, StatusOcorrencia
from app.models import NotificacaoEnviada, Ocorrencia
from app.rotas.cidadao import eventos_ordenados, imagem_url
from app.schemas import (
    Estatisticas, EventoAuditoria, ListaOcorrencias, Login, MudancaStatus,
    OcorrenciaDetalhe, OcorrenciaResumo, PossivelDuplicata, TokenSaida,
)
from app.servicos import estatisticas, geo
from app.servicos.autenticacao import emitir_token, exigir_gestor, senha_confere
from app.servicos.ocorrencias import TransicaoInvalida, mudar_status

publico = APIRouter(prefix="/admin", tags=["painel"])
rotas = APIRouter(prefix="/admin", tags=["painel"], dependencies=[Depends(exigir_gestor)])


@publico.post("/login", response_model=TokenSaida)
def login(entrada: Login):
    if not senha_confere(entrada.senha):
        time.sleep(0.5)  # encarece tentativas de forca bruta
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "senha incorreta")
    token, expira = emitir_token()
    return TokenSaida(token=token, expira_em=datetime.fromtimestamp(expira, timezone.utc))


def _resumo(o: Ocorrencia, lat: float, lon: float) -> dict:
    return dict(
        id=o.id, protocolo=o.protocolo, status=o.status,
        classe_informada=o.classe_informada, classe_detectada=o.classe_detectada,
        classe_validada=o.classe_validada, classe_final=o.classe_final,
        confianca=o.confianca, latitude=lat, longitude=lon, raio_m=o.raio_m,
        criado_em=o.criado_em, atualizado_em=o.atualizado_em,
    )


def _filtros(
    status_: list[StatusOcorrencia] | None,
    classe: ClasseOcorrencia | None,
    desde: datetime | None,
    ate: datetime | None,
    busca: str | None,
):
    condicoes = []
    if status_:
        condicoes.append(Ocorrencia.status.in_(status_))
    if classe:
        condicoes.append(func.coalesce(
            Ocorrencia.classe_validada, Ocorrencia.classe_detectada, Ocorrencia.classe_informada
        ) == classe)
    if desde:
        condicoes.append(Ocorrencia.criado_em >= desde)
    if ate:
        condicoes.append(Ocorrencia.criado_em <= ate)
    if busca:
        termo = f"%{busca.strip()}%"
        condicoes.append(or_(
            Ocorrencia.protocolo.ilike(termo), Ocorrencia.descricao.ilike(termo)
        ))
    return condicoes


@rotas.get("/ocorrencias", response_model=ListaOcorrencias)
def listar(
    status_: list[StatusOcorrencia] | None = Query(None, alias="status"),
    classe: ClasseOcorrencia | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    busca: str | None = Query(None, max_length=100),
    limite: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    sessao: Session = Depends(obter_sessao),
):
    """Lista filtrada; `status` pode ser repetido (?status=em_triagem&status=classificada)."""
    condicoes = _filtros(status_, classe, desde, ate, busca)
    total = sessao.scalar(select(func.count()).select_from(Ocorrencia).where(*condicoes))
    linhas = sessao.execute(
        select(Ocorrencia, geo.latitude, geo.longitude)
        .where(*condicoes)
        .order_by(Ocorrencia.criado_em.desc())
        .limit(limite)
        .offset(offset)
    ).all()
    return ListaOcorrencias(
        total=total, itens=[OcorrenciaResumo(**_resumo(o, la, lo)) for o, la, lo in linhas]
    )


def _carregar(sessao: Session, ocorrencia_id: uuid.UUID):
    linha = sessao.execute(
        select(Ocorrencia, geo.latitude, geo.longitude).where(Ocorrencia.id == ocorrencia_id)
    ).first()
    if linha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ocorrência não encontrada")
    return linha


def _detalhe(sessao: Session, ocorrencia_id: uuid.UUID) -> OcorrenciaDetalhe:
    o, lat, lon = _carregar(sessao, ocorrencia_id)

    aqui = geo.ponto(lat, lon)
    distancia = func.ST_Distance(Ocorrencia.geom, aqui)
    vizinhas = sessao.execute(
        select(Ocorrencia.id, Ocorrencia.protocolo, Ocorrencia.status,
               Ocorrencia.criado_em, distancia.label("d"))
        .where(
            Ocorrencia.id != o.id,
            Ocorrencia.status != StatusOcorrencia.REJEITADA,
            func.coalesce(Ocorrencia.classe_validada, Ocorrencia.classe_detectada,
                          Ocorrencia.classe_informada) == o.classe_final,
            func.ST_DWithin(Ocorrencia.geom, aqui, config.RAIO_DUPLICATA_M),
        )
        .order_by(distancia)
        .limit(10)
    ).all()

    enviadas = sessao.scalar(
        select(func.count()).select_from(NotificacaoEnviada)
        .where(NotificacaoEnviada.ocorrencia_id == o.id)
    )

    return OcorrenciaDetalhe(
        **_resumo(o, lat, lon),
        descricao=o.descricao,
        deteccoes=o.deteccoes,
        modelo_versao=o.modelo_versao,
        imagem_url=imagem_url(o.protocolo),
        auditoria=[
            EventoAuditoria(acao=e.acao, detalhe=e.detalhe, criado_em=e.criado_em)
            for e in eventos_ordenados(sessao, o.id)
        ],
        possiveis_duplicatas=[
            PossivelDuplicata(id=v.id, protocolo=v.protocolo, status=v.status,
                              distancia_m=round(v.d, 1), criado_em=v.criado_em)
            for v in vizinhas
        ],
        notificacoes_enviadas=enviadas,
        transicoes_permitidas=sorted(TRANSICOES[o.status], key=lambda s: list(StatusOcorrencia).index(s)),
    )


@rotas.get("/ocorrencias/{ocorrencia_id}", response_model=OcorrenciaDetalhe)
def detalhar(ocorrencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao)):
    return _detalhe(sessao, ocorrencia_id)


@rotas.patch("/ocorrencias/{ocorrencia_id}/status", response_model=OcorrenciaDetalhe)
def alterar_status(
    ocorrencia_id: uuid.UUID,
    entrada: MudancaStatus,
    sessao: Session = Depends(obter_sessao),
):
    """Gestão e resolução: aplica uma transição permitida e registra na auditoria."""
    o, _, _ = _carregar(sessao, ocorrencia_id)
    try:
        mudar_status(
            sessao, o, entrada.status,
            classe_validada=entrada.classe_validada,
            observacao=entrada.observacao,
            raio_m=entrada.raio_m,
        )
    except TransicaoInvalida as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return _detalhe(sessao, ocorrencia_id)


@rotas.get("/estatisticas", response_model=Estatisticas)
def indicadores(
    dias: int = Query(30, ge=7, le=365),
    sessao: Session = Depends(obter_sessao),
):
    return estatisticas.calcular(sessao, dias)


@rotas.get("/exportar.csv")
def exportar_csv(sessao: Session = Depends(obter_sessao)):
    """Todas as ocorrências em CSV (separador ;), para análise em planilha."""
    linhas = sessao.execute(
        select(Ocorrencia, geo.latitude, geo.longitude).order_by(Ocorrencia.criado_em)
    ).all()

    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow([
        "protocolo", "status", "classe_informada", "classe_detectada", "classe_validada",
        "confianca", "latitude", "longitude", "raio_m", "modelo_versao",
        "criado_em", "atualizado_em",
    ])
    for o, lat, lon in linhas:
        escritor.writerow([
            o.protocolo, o.status.value, o.classe_informada.value,
            o.classe_detectada.value if o.classe_detectada else "",
            o.classe_validada.value if o.classe_validada else "",
            f"{o.confianca:.4f}" if o.confianca is not None else "",
            f"{lat:.6f}", f"{lon:.6f}", o.raio_m, o.modelo_versao or "",
            o.criado_em.isoformat(), o.atualizado_em.isoformat(),
        ])

    return StreamingResponse(
        iter(["﻿" + saida.getvalue()]),  # BOM: o Excel reconhece o UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ocorrencias_miiu.csv"'},
    )
