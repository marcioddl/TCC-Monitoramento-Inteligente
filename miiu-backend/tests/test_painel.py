"""Painel de gestao: autenticacao, listagem, transicoes e indicadores."""

import uuid

from app.enums import ClasseOcorrencia
from tests.conftest import LAT0, LON0, deslocar_norte, reportar, validar

B, C = ClasseOcorrencia.BURACO, ClasseOcorrencia.CALCADA_DANIFICADA


def _id(cliente, admin, protocolo):
    r = cliente.get("/admin/ocorrencias", params={"busca": protocolo}, headers=admin)
    return r.json()["itens"][0]["id"]


def test_rotas_do_painel_exigem_token(cliente):
    assert cliente.get("/admin/ocorrencias").status_code == 401
    assert cliente.get("/admin/estatisticas").status_code == 401
    cabecalho = {"Authorization": "Bearer token.falso"}
    assert cliente.get("/admin/ocorrencias", headers=cabecalho).status_code == 401


def test_login_com_senha_errada(cliente):
    assert cliente.post("/admin/login", json={"senha": "chute"}).status_code == 401


def test_listagem_com_filtros(cliente, admin, classificador):
    classificador.programar(B, 0.9)
    reportar(cliente, classe="buraco")
    classificador.programar(C, 0.2)
    reportar(cliente, classe="calcada_danificada")

    todas = cliente.get("/admin/ocorrencias", headers=admin).json()
    assert todas["total"] == 2

    triagem = cliente.get(
        "/admin/ocorrencias", params={"status": ["em_triagem"]}, headers=admin
    ).json()
    assert triagem["total"] == 1
    assert triagem["itens"][0]["classe_final"] == "calcada_danificada"

    varios = cliente.get(
        "/admin/ocorrencias", params={"status": ["em_triagem", "classificada"]}, headers=admin
    ).json()
    assert varios["total"] == 2

    so_buraco = cliente.get("/admin/ocorrencias", params={"classe": "buraco"}, headers=admin).json()
    assert so_buraco["total"] == 1


def test_fluxo_completo_ate_resolucao(cliente, admin, classificador):
    classificador.programar(B, 0.9)
    protocolo = reportar(cliente).json()["protocolo"]
    oid = _id(cliente, admin, protocolo)

    detalhe = cliente.get(f"/admin/ocorrencias/{oid}", headers=admin).json()
    assert set(detalhe["transicoes_permitidas"]) == {"em_triagem", "validada", "rejeitada"}

    for proximo in ("validada", "em_atendimento", "resolvida"):
        r = cliente.patch(
            f"/admin/ocorrencias/{oid}/status",
            json={"status": proximo, "observacao": f"passo {proximo}"},
            headers=admin,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == proximo

    final = cliente.get(f"/admin/ocorrencias/{oid}", headers=admin).json()
    assert final["classe_validada"] == "buraco"
    assert final["transicoes_permitidas"] == []
    assert [e["acao"] for e in final["auditoria"]].count("mudanca_status") == 3

    publico = cliente.get(f"/ocorrencias/{protocolo}").json()
    assert [h["status"] for h in publico["historico"]] == [
        "recebida", "classificada", "validada", "em_atendimento", "resolvida",
    ]


def test_transicao_invalida_retorna_409(cliente, admin, classificador):
    classificador.programar(B, 0.9)
    oid = _id(cliente, admin, reportar(cliente).json()["protocolo"])
    r = cliente.patch(f"/admin/ocorrencias/{oid}/status", json={"status": "resolvida"}, headers=admin)
    assert r.status_code == 409


def test_gestor_corrige_a_classe_na_triagem(cliente, admin, classificador):
    classificador.programar(C, 0.4)  # modelo inseguro e divergente
    protocolo = reportar(cliente, classe="buraco").json()["protocolo"]
    corpo = validar(cliente, admin, protocolo, classe="buraco")
    assert corpo["classe_validada"] == "buraco"
    assert corpo["classe_final"] == "buraco"
    assert corpo["classe_detectada"] == "calcada_danificada"  # preservada para metricas


def test_possivel_duplicata(cliente, admin, classificador):
    classificador.programar(B, 0.9)
    p1 = reportar(cliente).json()["protocolo"]
    lat, lon = deslocar_norte(LAT0, LON0, 12)
    reportar(cliente, lat=lat, lon=lon)
    lat, lon = deslocar_norte(LAT0, LON0, 300)
    reportar(cliente, lat=lat, lon=lon)

    detalhe = cliente.get(f"/admin/ocorrencias/{_id(cliente, admin, p1)}", headers=admin).json()
    assert len(detalhe["possiveis_duplicatas"]) == 1
    assert 10 < detalhe["possiveis_duplicatas"][0]["distancia_m"] < 14


def test_estatisticas(cliente, admin, classificador):
    classificador.programar(B, 0.9)
    validar(cliente, admin, reportar(cliente, classe="buraco").json()["protocolo"])

    classificador.programar(B, 0.3)  # triagem; gestor decide que e calcada
    validar(cliente, admin, reportar(cliente, classe="calcada_danificada").json()["protocolo"],
            classe="calcada_danificada")

    classificador.programar(C, 0.8)
    reportar(cliente, classe="calcada_danificada")  # fica classificada

    e = cliente.get("/admin/estatisticas", headers=admin).json()
    assert e["total"] == 3
    assert e["por_status"]["validada"] == 2
    assert e["por_status"]["classificada"] == 1
    assert e["por_classe"] == {"buraco": 1, "calcada_danificada": 2}
    assert e["taxa_automacao"] == round(2 / 3, 4)
    assert e["validadas_avaliadas"] == 2
    assert e["concordancia_modelo"] == 0.5     # acertou 1 de 2
    assert e["concordancia_cidadao"] == 1.0
    assert sum(d["total"] for d in e["por_dia"]) == 3
    assert e["tempo_medio_triagem_h"] is not None


def test_exportacao_csv(cliente, admin, classificador):
    classificador.programar(B, 0.9)
    protocolo = reportar(cliente).json()["protocolo"]
    r = cliente.get("/admin/exportar.csv", headers=admin)
    assert r.status_code == 200
    linhas = r.content.decode("utf-8-sig").strip().splitlines()
    assert linhas[0].startswith("protocolo;status")
    assert protocolo in linhas[1]


def test_ocorrencia_inexistente_no_painel(cliente, admin):
    assert cliente.get(f"/admin/ocorrencias/{uuid.uuid4()}", headers=admin).status_code == 404
