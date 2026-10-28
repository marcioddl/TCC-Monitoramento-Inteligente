"""Aplicacao FastAPI do MIIU."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import config
from app.database import obter_sessao
from app.rotas import admin, cidadao, dispositivos
from app.servicos.classificador import carregar_classificador
from app.servicos.notificacoes import carregar_notificador

log = logging.getLogger("miiu")
if not log.handlers:
    _saida = logging.StreamHandler()
    _saida.setFormatter(logging.Formatter("%(levelname)s:     [%(name)s] %(message)s"))
    log.addHandler(_saida)
    log.setLevel(logging.INFO)
    log.propagate = False


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # Carregados uma unica vez: o modelo YOLO leva alguns segundos para subir
    Path(config.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    app.state.classificador = carregar_classificador(
        config.MODELO_PATH, config.MODELO_IMGSZ, config.MODELO_CONF_MIN
    )
    app.state.notificador = carregar_notificador(config.FIREBASE_CREDENCIAIS)
    yield


app = FastAPI(
    title="MIIU API",
    description=(
        "Backend do Monitoramento Inteligente de Infraestrutura Urbana. "
        "Recebe ocorrências georreferenciadas, classifica automaticamente por "
        "visão computacional e dispara alertas de proximidade por geofencing."
    ),
    version="1.0.0",
    lifespan=ciclo_de_vida,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in config.CORS_ORIGENS.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cidadao.rotas)
app.include_router(dispositivos.rotas)
app.include_router(admin.publico)
app.include_router(admin.rotas)

# Painel React compilado (npm run build), quando existir
_painel = Path(config.PAINEL_DIR)
if _painel.is_dir() and (_painel / "index.html").is_file():
    app.mount("/painel", StaticFiles(directory=_painel, html=True), name="painel")

# App do cidadao compilado para a web (flutter build web --base-href /app/),
# quando existir. Servido aqui, ele fala com a API no mesmo endereco, sem CORS.
_app_web = Path(config.APP_WEB_DIR)
if _app_web.is_dir() and (_app_web / "index.html").is_file():
    app.mount("/app", StaticFiles(directory=_app_web, html=True), name="app_web")


@app.get("/", include_in_schema=False)
def raiz():
    destino = "/painel/" if _painel.is_dir() else "/docs"
    return RedirectResponse(destino)


TABELAS_ESPERADAS = {"ocorrencia", "dispositivo", "notificacao_enviada", "auditoria"}
MIGRACAO_ATUAL = "0002"


@app.get("/health", tags=["infraestrutura"])
def health(request: Request, sessao: Session = Depends(obter_sessao)):
    classificador = request.app.state.classificador
    notificador = request.app.state.notificador
    componentes = {
        "modelo": {
            "disponivel": classificador.disponivel,
            "versao": classificador.versao,
            "observacao": classificador.motivo or None,
            "limiar": config.INFERENCIA_LIMIAR,
        },
        "notificacoes": notificador.modo,
        "geocerca_raio_padrao_m": config.GEOFENCE_RAIO_PADRAO,
    }
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
            sessao.rollback()
            revisao = None

        faltando = sorted(TABELAS_ESPERADAS - encontradas)
        desatualizado = revisao != MIGRACAO_ATUAL

        return {
            "status": "ok" if not (faltando or desatualizado) else "esquema_incompleto",
            "banco": "conectado",
            "postgis": postgis,
            "migracao": revisao,
            "tabelas": sorted(encontradas & TABELAS_ESPERADAS),
            "tabelas_faltando": faltando,
            "dica": "rode: alembic upgrade head" if faltando or desatualizado else None,
            **componentes,
        }
    except Exception as e:
        return {"status": "degradado", "banco": "indisponivel", "erro": str(e), **componentes}
