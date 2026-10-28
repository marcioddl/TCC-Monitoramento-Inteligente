"""Infraestrutura dos testes.

Os testes rodam contra um PostgreSQL/PostGIS de verdade, num banco separado
(miiu_test) criado automaticamente no mesmo servidor do Docker. Consultas
espaciais nao podem ser testadas em SQLite: o geofencing depende do PostGIS.

O esquema e criado pelas proprias migracoes do Alembic, o que tambem testa
as migracoes. Antes de cada teste as tabelas sao esvaziadas.

Uso (com o Docker do banco no ar):   pytest
"""

import io
import math
import os
import tempfile
import uuid
from pathlib import Path

# As variaveis precisam existir antes de qualquer import de app.*
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://miiu:miiu_dev@localhost:5432/miiu_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="miiu_uploads_")
os.environ["ADMIN_SENHA"] = "senha-de-teste"
os.environ["SEGREDO_TOKEN"] = ""
os.environ["MODELO_PATH"] = "nao_existe.pt"
os.environ["FIREBASE_CREDENCIAIS"] = ""
os.environ["PAINEL_DIR"] = "nao_existe"
os.environ["LIMITE_REPORTES_HORA"] = "5"
os.environ["INFERENCIA_LIMIAR"] = "0.5"
os.environ["GEOFENCE_RAIO_PADRAO"] = "100"

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config as ConfigAlembic  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


def _garantir_banco_de_teste():
    url = make_url(TEST_DATABASE_URL)
    with psycopg.connect(
        host=url.host, port=url.port or 5432, user=url.username,
        password=url.password, dbname="postgres", autocommit=True,
    ) as conexao:
        existe = conexao.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
        ).fetchone()
        if not existe:
            conexao.execute(f'CREATE DATABASE "{url.database}"')


@pytest.fixture(scope="session", autouse=True)
def esquema():
    _garantir_banco_de_teste()

    from app.database import engine

    with engine.begin() as conexao:
        conexao.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conexao.execute(text("CREATE SCHEMA public"))

    cfg = ConfigAlembic(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "migrations"))
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def tabelas_vazias(esquema):
    from app.database import engine

    with engine.begin() as conexao:
        conexao.execute(text(
            "TRUNCATE ocorrencia, dispositivo, notificacao_enviada, auditoria CASCADE"
        ))
    yield


# ------------------------------------------------------------------ dubles

from app.enums import ClasseOcorrencia  # noqa: E402
from app.servicos.classificador import (  # noqa: E402
    Classificador, Deteccao, ResultadoClassificacao,
)
from app.servicos.notificacoes import Notificador, ResultadoEnvio  # noqa: E402


class ClassificadorFalso(Classificador):
    """Devolve o resultado programado no teste, sem rodar o YOLO."""

    disponivel = True
    versao = "falso@00000000"

    def __init__(self):
        self.proximo: ResultadoClassificacao | None = None
        self.levantar_erro = False

    def programar(self, classe: ClasseOcorrencia | None, confianca: float = 0.9):
        if classe is None:
            self.proximo = ResultadoClassificacao(None, 0.0, [], self.versao)
            return
        self.proximo = ResultadoClassificacao(
            classe, confianca,
            [Deteccao(classe.value, confianca, [0.1, 0.2, 0.5, 0.6])],
            self.versao, tempo_ms=12.3,
        )

    def classificar(self, imagem):
        if self.levantar_erro:
            raise RuntimeError("falha simulada na inferencia")
        return self.proximo


class NotificadorFalso(Notificador):
    """Registra os envios em memoria, como se o FCM tivesse aceitado."""

    modo = "fcm"

    def __init__(self):
        self.enviados: list[dict] = []
        self.token_invalido = False

    def enviar(self, token, titulo, corpo, dados):
        self.enviados.append({"token": token, "titulo": titulo, "corpo": corpo, "dados": dados})
        if self.token_invalido:
            return ResultadoEnvio(enviado=False, token_invalido=True, erro="UNREGISTERED")
        return ResultadoEnvio(enviado=True)


@pytest.fixture
def classificador():
    return ClassificadorFalso()


@pytest.fixture
def notificador():
    return NotificadorFalso()


@pytest.fixture
def cliente(classificador, notificador):
    from app.dependencias import obter_classificador, obter_notificador
    from app.main import app

    app.dependency_overrides[obter_classificador] = lambda: classificador
    app.dependency_overrides[obter_notificador] = lambda: notificador
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def token(cliente) -> str:
    r = cliente.post("/admin/login", json={"senha": "senha-de-teste"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def admin(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ utilidades

# Centro de Teresina (Praca da Liberdade, aproximadamente)
LAT0, LON0 = -5.0892, -42.8016


def deslocar_norte(lat: float, lon: float, metros: float) -> tuple[float, float]:
    """Ponto a `metros` ao norte. Usa o comprimento do grau de latitude no
    elipsoide WGS 84, o mesmo usado pelo PostGIS no tipo geography."""
    phi = math.radians(lat)
    m_por_grau = 111132.954 - 559.822 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
    return lat + metros / m_por_grau, lon


def jpeg(largura=800, altura=600, exif: dict | None = None, cor=(128, 128, 128)) -> bytes:
    imagem = Image.new("RGB", (largura, altura), cor)
    buffer = io.BytesIO()
    if exif:
        dados = Image.Exif()
        for tag, valor in exif.items():
            dados[tag] = valor
        imagem.save(buffer, "JPEG", exif=dados.tobytes())
    else:
        imagem.save(buffer, "JPEG")
    return buffer.getvalue()


def reportar(
    cliente,
    *,
    lat=LAT0,
    lon=LON0,
    classe="buraco",
    device_id=None,
    imagem: bytes | None = None,
    descricao="buraco grande na faixa da direita",
    precisao_m=8.0,
):
    dados = {
        "latitude": str(lat),
        "longitude": str(lon),
        "classe_informada": classe,
        "device_id": str(device_id or uuid.uuid4()),
        "descricao": descricao,
    }
    if precisao_m is not None:
        dados["precisao_m"] = str(precisao_m)
    return cliente.post(
        "/ocorrencias",
        data=dados,
        files={"imagem": ("foto.jpg", imagem or jpeg(), "image/jpeg")},
    )


def validar(cliente, admin, protocolo: str, classe: str | None = None) -> dict:
    """Leva uma ocorrencia recem-criada ate VALIDADA pelo painel."""
    lista = cliente.get("/admin/ocorrencias", params={"busca": protocolo}, headers=admin).json()
    oid = lista["itens"][0]["id"]
    corpo = {"status": "validada"}
    if classe:
        corpo["classe_validada"] = classe
    r = cliente.patch(f"/admin/ocorrencias/{oid}/status", json=corpo, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()
