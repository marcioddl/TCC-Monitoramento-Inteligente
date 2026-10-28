"""Alerta proativo: geocercas de 100 m em torno das ocorrencias validadas."""

import threading
import uuid

from sqlalchemy import func, select

from app.enums import ClasseOcorrencia
from tests.conftest import LAT0, LON0, deslocar_norte, reportar, validar

B = ClasseOcorrencia.BURACO


def checar(cliente, aparelho, lat, lon, precisao_m=5.0):
    r = cliente.post("/geofence/checar", json={
        "device_id": str(aparelho), "latitude": lat, "longitude": lon, "precisao_m": precisao_m,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _ocorrencia_validada(cliente, admin, classificador, lat=LAT0, lon=LON0, autor=None):
    classificador.programar(B, 0.9)
    protocolo = reportar(cliente, lat=lat, lon=lon, device_id=autor).json()["protocolo"]
    validar(cliente, admin, protocolo)
    return protocolo


def test_alerta_dentro_do_raio_e_silencio_fora(cliente, admin, classificador):
    protocolo = _ocorrencia_validada(cliente, admin, classificador)
    pedestre = uuid.uuid4()

    longe = checar(cliente, pedestre, *deslocar_norte(LAT0, LON0, 110))
    assert longe["alertas"] == []

    perto = checar(cliente, pedestre, *deslocar_norte(LAT0, LON0, 90))
    assert len(perto["alertas"]) == 1
    alerta = perto["alertas"][0]
    assert alerta["protocolo"] == protocolo
    assert 89 < alerta["distancia_m"] < 91
    assert alerta["mensagem"] == "Buraco na via a 90 m de você"


def test_alerta_e_entregue_uma_unica_vez(cliente, admin, classificador):
    _ocorrencia_validada(cliente, admin, classificador)
    pedestre = uuid.uuid4()
    ponto = deslocar_norte(LAT0, LON0, 40)

    assert len(checar(cliente, pedestre, *ponto)["alertas"]) == 1
    assert checar(cliente, pedestre, *ponto)["alertas"] == []
    # outro aparelho no mesmo lugar recebe o seu proprio alerta
    assert len(checar(cliente, uuid.uuid4(), *ponto)["alertas"]) == 1


def test_deduplicacao_resiste_a_requisicoes_simultaneas(cliente, admin, classificador):
    _ocorrencia_validada(cliente, admin, classificador)
    pedestre = uuid.uuid4()
    ponto = deslocar_norte(LAT0, LON0, 20)
    checar(cliente, pedestre, *deslocar_norte(LAT0, LON0, 500))  # registra o aparelho

    respostas = []

    def disparar():
        respostas.append(checar(cliente, pedestre, *ponto))

    threads = [threading.Thread(target=disparar) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(len(r["alertas"]) for r in respostas) == 1

    from app.database import SessaoLocal
    from app.models import NotificacaoEnviada

    with SessaoLocal() as s:
        assert s.scalar(select(func.count()).select_from(NotificacaoEnviada)) == 1


def test_somente_ocorrencias_validadas_ou_em_atendimento_alertam(cliente, admin, classificador):
    classificador.programar(B, 0.9)
    reportar(cliente)                                   # classificada, nao validada
    classificador.programar(B, 0.1)
    reportar(cliente, lat=deslocar_norte(LAT0, LON0, 5)[0])  # em triagem

    pedestre = uuid.uuid4()
    assert checar(cliente, pedestre, LAT0, LON0)["alertas"] == []


def test_resolvida_ou_rejeitada_nao_alerta(cliente, admin, classificador):
    protocolo = _ocorrencia_validada(cliente, admin, classificador)
    oid = cliente.get("/admin/ocorrencias", params={"busca": protocolo}, headers=admin).json()["itens"][0]["id"]

    em_atendimento = uuid.uuid4()
    cliente.patch(f"/admin/ocorrencias/{oid}/status", json={"status": "em_atendimento"}, headers=admin)
    assert len(checar(cliente, em_atendimento, LAT0, LON0)["alertas"]) == 1

    cliente.patch(f"/admin/ocorrencias/{oid}/status", json={"status": "resolvida"}, headers=admin)
    assert checar(cliente, uuid.uuid4(), LAT0, LON0)["alertas"] == []


def test_autor_do_reporte_nao_recebe_alerta_da_propria_ocorrencia(cliente, admin, classificador):
    autor = uuid.uuid4()
    _ocorrencia_validada(cliente, admin, classificador, autor=autor)
    assert checar(cliente, autor, LAT0, LON0)["alertas"] == []


def test_gps_impreciso_e_ignorado(cliente, admin, classificador):
    _ocorrencia_validada(cliente, admin, classificador)
    r = checar(cliente, uuid.uuid4(), LAT0, LON0, precisao_m=400)
    assert r["ignorada"] is True
    assert r["motivo"] == "precisao_gps_insuficiente"
    assert r["alertas"] == []


def test_aparelho_com_notificacoes_desligadas(cliente, admin, classificador):
    _ocorrencia_validada(cliente, admin, classificador)
    aparelho = uuid.uuid4()
    cliente.put(f"/dispositivos/{aparelho}", json={"notificacoes_habilitadas": False})
    r = checar(cliente, aparelho, LAT0, LON0)
    assert r["ignorada"] is True and r["alertas"] == []


def test_push_pelo_fcm_quando_o_aparelho_tem_token(cliente, admin, classificador, notificador):
    _ocorrencia_validada(cliente, admin, classificador)
    aparelho = uuid.uuid4()
    r = cliente.put(f"/dispositivos/{aparelho}", json={"fcm_token": "token-fcm-de-teste"})
    assert r.json() == {
        "device_id": str(aparelho), "notificacoes_habilitadas": True,
        "fcm_registrado": True, "modo_push": "fcm",
    }

    alerta = checar(cliente, aparelho, LAT0, LON0)["alertas"][0]
    assert alerta["canal"] == "fcm"
    assert notificador.enviados[0]["token"] == "token-fcm-de-teste"
    assert notificador.enviados[0]["dados"]["tipo"] == "geocerca"


def test_token_fcm_invalido_e_descartado(cliente, admin, classificador, notificador):
    _ocorrencia_validada(cliente, admin, classificador)
    aparelho = uuid.uuid4()
    cliente.put(f"/dispositivos/{aparelho}", json={"fcm_token": "token-velho"})
    notificador.token_invalido = True

    alerta = checar(cliente, aparelho, LAT0, LON0)["alertas"][0]
    assert alerta["canal"] == "app"  # o app ainda recebe pela resposta
    r = cliente.put(f"/dispositivos/{aparelho}", json={})
    assert r.json()["fcm_registrado"] is False


def test_raio_personalizado_pelo_gestor(cliente, admin, classificador):
    classificador.programar(B, 0.9)
    protocolo = reportar(cliente).json()["protocolo"]
    oid = cliente.get("/admin/ocorrencias", params={"busca": protocolo}, headers=admin).json()["itens"][0]["id"]
    cliente.patch(f"/admin/ocorrencias/{oid}/status",
                  json={"status": "validada", "raio_m": 250}, headers=admin)

    assert len(checar(cliente, uuid.uuid4(), *deslocar_norte(LAT0, LON0, 200))["alertas"]) == 1


def test_varias_geocercas_vem_ordenadas_pela_distancia(cliente, admin, classificador):
    longe = _ocorrencia_validada(cliente, admin, classificador, *deslocar_norte(LAT0, LON0, 80))
    perto = _ocorrencia_validada(cliente, admin, classificador, *deslocar_norte(LAT0, LON0, 30))
    alertas = checar(cliente, uuid.uuid4(), LAT0, LON0)["alertas"]
    assert [a["protocolo"] for a in alertas] == [perto, longe]


def test_mapa_publico_so_mostra_ativas_e_sem_descricao(cliente, admin, classificador):
    validada = _ocorrencia_validada(cliente, admin, classificador)
    classificador.programar(B, 0.9)
    reportar(cliente, lat=deslocar_norte(LAT0, LON0, 50)[0])  # so classificada
    _ocorrencia_validada(cliente, admin, classificador, *deslocar_norte(LAT0, LON0, 9000))

    pontos = cliente.get("/ocorrencias/mapa", params={
        "latitude": LAT0, "longitude": LON0, "raio_m": 2000,
    }).json()
    assert [p["protocolo"] for p in pontos] == [validada]
    assert "descricao" not in pontos[0]
