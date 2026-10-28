"""Indicadores do painel de gestao.

Alem dos totais, calcula metricas que servem a avaliacao do sistema em uso:
a taxa de automacao (ocorrencias que dispensaram triagem humana) e a
concordancia entre a classe sugerida pelo modelo, a informada pelo cidadao e
a decidida pelo gestor.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import config
from app.enums import StatusOcorrencia
from app.models import Auditoria, Dispositivo, NotificacaoEnviada, Ocorrencia
from app.schemas import ContagemDia, Estatisticas

classe_final = func.coalesce(
    Ocorrencia.classe_validada, Ocorrencia.classe_detectada, Ocorrencia.classe_informada
)


def _um_se(condicao):
    return case((condicao, 1.0), else_=0.0)


def _media(valor) -> float | None:
    return round(float(valor), 4) if valor is not None else None


def _horas_ate(sessao: Session, destinos: list[str]) -> float | None:
    """Tempo medio, em horas, entre o reporte e a primeira mudanca para um
    dos estados de destino."""
    primeira = (
        select(
            Auditoria.ocorrencia_id,
            func.min(Auditoria.criado_em).label("quando"),
        )
        .where(
            Auditoria.acao == "mudanca_status",
            Auditoria.detalhe["para"].astext.in_(destinos),
        )
        .group_by(Auditoria.ocorrencia_id)
        .subquery()
    )
    segundos = sessao.scalar(
        select(func.avg(func.extract("epoch", primeira.c.quando - Ocorrencia.criado_em)))
        .join(primeira, primeira.c.ocorrencia_id == Ocorrencia.id)
    )
    return round(float(segundos) / 3600, 2) if segundos is not None else None


def calcular(sessao: Session, dias: int = 30) -> Estatisticas:
    total = sessao.scalar(select(func.count()).select_from(Ocorrencia)) or 0

    por_status = {s.value: 0 for s in StatusOcorrencia}
    for status, n in sessao.execute(
        select(Ocorrencia.status, func.count()).group_by(Ocorrencia.status)
    ):
        por_status[status.value] = n

    por_classe = {
        (classe.value if hasattr(classe, "value") else str(classe).lower()): n
        for classe, n in sessao.execute(
            select(classe_final, func.count()).group_by(classe_final)
        )
    }

    # serie diaria no fuso local, preenchendo os dias sem reporte com zero
    dia_local = func.date(func.timezone(config.FUSO_HORARIO, Ocorrencia.criado_em))
    inicio = datetime.now(timezone.utc) - timedelta(days=dias)
    contagens = dict(sessao.execute(
        select(dia_local, func.count())
        .where(Ocorrencia.criado_em >= inicio)
        .group_by(dia_local)
    ).all())
    hoje = sessao.scalar(select(func.date(func.timezone(config.FUSO_HORARIO, func.now()))))
    if contagens:
        hoje = max(hoje, max(contagens))
    por_dia = [
        ContagemDia(dia=d.isoformat(), total=contagens.get(d, 0))
        for d in (hoje - timedelta(days=i) for i in range(dias - 1, -1, -1))
    ]

    # taxa de automacao: classificadas direto / todas que passaram pelo modelo
    classificacoes = select(Auditoria.detalhe["para"].astext.label("para")).where(
        Auditoria.acao == "classificacao"
    ).subquery()
    automacao = sessao.execute(
        select(
            func.count(),
            func.sum(case((classificacoes.c.para == "classificada", 1), else_=0)),
        ).select_from(classificacoes)
    ).one()
    taxa_automacao = (automacao[1] / automacao[0]) if automacao[0] else None

    validadas = Ocorrencia.classe_validada.is_not(None)
    concord = sessao.execute(
        select(
            func.count(),
            func.avg(_um_se(Ocorrencia.classe_detectada == Ocorrencia.classe_validada))
            .filter(Ocorrencia.classe_detectada.is_not(None)),
            func.avg(_um_se(Ocorrencia.classe_informada == Ocorrencia.classe_validada)),
        ).where(validadas, Ocorrencia.status != StatusOcorrencia.REJEITADA)
    ).one()

    confianca_media = sessao.scalar(select(func.avg(Ocorrencia.confianca)))

    notificacoes = sessao.scalar(select(func.count()).select_from(NotificacaoEnviada)) or 0
    por_canal = dict(sessao.execute(
        select(NotificacaoEnviada.canal, func.count()).group_by(NotificacaoEnviada.canal)
    ).all())
    distancia_media = sessao.scalar(select(func.avg(NotificacaoEnviada.distancia_m)))

    sete_dias = datetime.now(timezone.utc) - timedelta(days=7)
    ativos = sessao.scalar(
        select(func.count()).select_from(Dispositivo).where(Dispositivo.atualizado_em >= sete_dias)
    ) or 0

    return Estatisticas(
        total=total,
        por_status=por_status,
        por_classe=por_classe,
        por_dia=por_dia,
        taxa_automacao=_media(taxa_automacao),
        concordancia_modelo=_media(concord[1]),
        concordancia_cidadao=_media(concord[2]),
        validadas_avaliadas=concord[0] or 0,
        confianca_media=_media(confianca_media),
        tempo_medio_triagem_h=_horas_ate(sessao, ["validada", "rejeitada"]),
        tempo_medio_resolucao_h=_horas_ate(sessao, ["resolvida"]),
        notificacoes_enviadas=notificacoes,
        notificacoes_por_canal=por_canal,
        distancia_media_alerta_m=round(float(distancia_media), 1) if distancia_media else None,
        dispositivos_ativos_7d=ativos,
    )
