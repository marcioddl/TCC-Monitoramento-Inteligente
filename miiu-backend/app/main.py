"""Aplicacao FastAPI do MIIU."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import obter_sessao


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # Espaco para carregar o modelo YOLO uma unica vez, na atividade 13.
    yield


app = FastAPI(
    title="MIIU API",
    description=(
        "Backend do Monitoramento Inteligente de Infraestrutura Urbana. "
        "Recebe ocorrencias georreferenciadas, classifica automaticamente por "
        "visao computacional e dispara alertas de proximidade por geofencing."
    ),
    version="0.1.0",
    lifespan=ciclo_de_vida,
)


TABELAS_ESPERADAS = {"ocorrencia", "dispositivo", "notificacao_enviada", "auditoria"}


@app.get("/health", tags=["infraestrutura"])
def health(sessao: Session = Depends(obter_sessao)):
    try:
        sessao.execute(text("SELECT 1"))
        postgis = sessao.execute(text("SELECT PostGIS_Version()")).scalar()

        encontradas = {
            linha[0]
            for linha in sessao.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            ))
        }

        try:
            revisao = sessao.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
        except Exception:
            revisao = None

        faltando = sorted(TABELAS_ESPERADAS - encontradas)

        return {
            "status": "ok" if not faltando else "esquema_incompleto",
            "banco": "conectado",
            "postgis": postgis,
            "migracao": revisao,
            "tabelas": sorted(encontradas & TABELAS_ESPERADAS),
            "tabelas_faltando": faltando,
            "dica": None if not faltando else "rode: alembic upgrade head",
        }
    except Exception as e:
        return {"status": "degradado", "banco": "indisponivel", "erro": str(e)}