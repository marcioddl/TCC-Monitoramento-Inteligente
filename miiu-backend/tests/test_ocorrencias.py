"""Percepcao e reporte, recepcao e triagem, acompanhamento por protocolo."""

import uuid
from pathlib import Path

from PIL import Image

from app.config import config
from app.enums import ClasseOcorrencia
from tests.conftest import LAT0, LON0, jpeg, reportar

B, C = ClasseOcorrencia.BURACO, ClasseOcorrencia.CALCADA_DANIFICADA


def _arquivo_da_ocorrencia(cliente, admin, protocolo) -> Path:
    item = cliente.get("/admin/ocorrencias", params={"busca": protocolo}, headers=admin).json()
    from app.database import SessaoLocal
    from app.models import Ocorrencia

    with SessaoLocal() as s:
        o = s.get(Ocorrencia, uuid.UUID(item["itens"][0]["id"]))
        return Path(config.UPLOAD_DIR) / o.imagem_path


def test_health(cliente):
    r = cliente.get("/health").json()
    assert r["status"] == "ok"
    assert r["migracao"] == "0002"
    assert r["postgis"]


def test_reporte_com_alta_confianca_e_classificado(cliente, classificador):
    classificador.programar(B, 0.91)
    r = reportar(cliente, classe="buraco")
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["status"] == "classificada"
    assert corpo["classe_detectada"] == "buraco"
    assert corpo["confianca"] == 0.91
    assert corpo["protocolo"].startswith("MIIU-")


def test_reporte_com_baixa_confianca_vai_para_triagem(cliente, classificador):
    classificador.programar(B, 0.31)
    r = reportar(cliente)
    assert r.json()["status"] == "em_triagem"


def test_divergencia_entre_cidadao_e_modelo_vai_para_triagem(cliente, classificador):
    classificador.programar(C, 0.97)
    r = reportar(cliente, classe="buraco")
    assert r.json()["status"] == "em_triagem"
    assert r.json()["classe_detectada"] == "calcada_danificada"


def test_sem_modelo_ou_com_falha_na_inferencia_o_reporte_nao_se_perde(cliente, classificador):
    classificador.proximo = None
    assert reportar(cliente).json()["status"] == "em_triagem"

    classificador.levantar_erro = True
    r = reportar(cliente)
    assert r.status_code == 201
    assert r.json()["status"] == "em_triagem"


def test_exif_e_removido_e_orientacao_aplicada(cliente, admin, classificador):
    classificador.programar(B)
    # 0x010F fabricante, 0x0110 modelo da camera, 0x0112 orientacao (6 = girar 90)
    foto = jpeg(800, 600, exif={0x010F: "Fabricante", 0x0110: "Celular X", 0x0112: 6})
    protocolo = reportar(cliente, imagem=foto).json()["protocolo"]

    arquivo = _arquivo_da_ocorrencia(cliente, admin, protocolo)
    with Image.open(arquivo) as salva:
        assert len(salva.getexif()) == 0
        assert salva.size == (600, 800)  # deitada no arquivo, em pe no resultado


def test_imagem_grande_e_reduzida(cliente, admin, classificador):
    classificador.programar(B)
    protocolo = reportar(cliente, imagem=jpeg(4000, 3000)).json()["protocolo"]
    with Image.open(_arquivo_da_ocorrencia(cliente, admin, protocolo)) as salva:
        assert max(salva.size) == config.IMAGEM_LADO_MAX


def test_arquivo_que_nao_e_imagem_e_recusado(cliente):
    r = cliente.post(
        "/ocorrencias",
        data={"latitude": LAT0, "longitude": LON0, "classe_informada": "buraco",
              "device_id": str(uuid.uuid4())},
        files={"imagem": ("foto.jpg", b"isto nao e uma imagem", "image/jpeg")},
    )
    assert r.status_code == 422


def test_imagem_acima_do_limite_e_recusada(cliente, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_MAX_MB", 0)
    r = reportar(cliente)
    assert r.status_code == 413


def test_coordenadas_invalidas(cliente):
    assert reportar(cliente, lat=91).status_code == 422
    assert reportar(cliente, lon=-181).status_code == 422
    assert reportar(cliente, lat=0, lon=0).status_code == 422


def test_classe_fora_do_escopo_e_recusada(cliente):
    assert reportar(cliente, classe="poste_danificado").status_code == 422


def test_limite_de_reportes_por_hora(cliente, classificador):
    classificador.programar(B)
    aparelho = uuid.uuid4()
    for _ in range(config.LIMITE_REPORTES_HORA):
        assert reportar(cliente, device_id=aparelho).status_code == 201
    assert reportar(cliente, device_id=aparelho).status_code == 429
    # outro aparelho nao e afetado
    assert reportar(cliente).status_code == 201


def test_consulta_por_protocolo_com_historico(cliente, admin, classificador):
    classificador.programar(B, 0.88)
    protocolo = reportar(cliente).json()["protocolo"]

    r = cliente.get(f"/ocorrencias/{protocolo.lower()}")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["protocolo"] == protocolo
    assert [h["status"] for h in corpo["historico"]] == ["recebida", "classificada"]
    assert abs(corpo["latitude"] - LAT0) < 1e-9
    assert abs(corpo["longitude"] - LON0) < 1e-9

    imagem = cliente.get(corpo["imagem_url"])
    assert imagem.status_code == 200
    assert imagem.headers["content-type"] == "image/jpeg"


def test_protocolo_inexistente(cliente):
    assert cliente.get("/ocorrencias/MIIU-2026-ZZZZZZ").status_code == 404
    assert cliente.get("/ocorrencias/MIIU-2026-ZZZZZZ/imagem").status_code == 404


def test_auditoria_registra_criacao_e_classificacao(cliente, admin, classificador):
    classificador.programar(B, 0.77)
    protocolo = reportar(cliente, precisao_m=6.5).json()["protocolo"]
    oid = cliente.get("/admin/ocorrencias", params={"busca": protocolo}, headers=admin).json()["itens"][0]["id"]
    detalhe = cliente.get(f"/admin/ocorrencias/{oid}", headers=admin).json()

    acoes = [e["acao"] for e in detalhe["auditoria"]]
    assert acoes == ["criacao", "classificacao"]
    criacao, classificacao = detalhe["auditoria"]
    assert criacao["detalhe"]["precisao_gps_m"] == 6.5
    assert classificacao["detalhe"]["motivo"] == "confianca_acima_do_limiar"
    assert classificacao["detalhe"]["modelo"] == "falso@00000000"
    assert detalhe["deteccoes"][0]["classe"] == "buraco"
    assert detalhe["modelo_versao"] == "falso@00000000"
