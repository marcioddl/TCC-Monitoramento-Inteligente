"""Testes de unidade das regras puras (sem banco)."""

import time

from app.enums import ClasseOcorrencia, StatusOcorrencia, transicao_valida
from app.servicos.autenticacao import emitir_token, token_valido
from app.servicos.classificador import ResultadoClassificacao
from app.servicos.ocorrencias import decidir_status
from app.servicos.protocolo import gerar_protocolo, normalizar_protocolo, protocolo_valido

B, C = ClasseOcorrencia.BURACO, ClasseOcorrencia.CALCADA_DANIFICADA
S = StatusOcorrencia


def test_protocolo_tem_formato_valido_e_sem_caracteres_ambiguos():
    for _ in range(500):
        p = gerar_protocolo()
        assert protocolo_valido(p), p
        assert not set(p[10:]) & set("ILOU")


def test_normalizacao_do_protocolo_digitado_pelo_cidadao():
    assert normalizar_protocolo("miiu-2026-7k3qxa") == "MIIU-2026-7K3QXA"
    assert normalizar_protocolo(" miiu 2026 7k3qxa ") == "MIIU-2026-7K3QXA"
    # O e I digitados por engano no lugar de 0 e 1
    assert normalizar_protocolo("MIIU-2026-O1IL0A") == "MIIU-2026-01110A"


def test_maquina_de_estados():
    assert transicao_valida(S.CLASSIFICADA, S.VALIDADA)
    assert transicao_valida(S.EM_TRIAGEM, S.REJEITADA)
    assert transicao_valida(S.EM_ATENDIMENTO, S.RESOLVIDA)
    assert not transicao_valida(S.CLASSIFICADA, S.RESOLVIDA)
    assert not transicao_valida(S.RESOLVIDA, S.VALIDADA)
    assert not transicao_valida(S.REJEITADA, S.VALIDADA)


def test_decisao_de_triagem():
    def r(classe, conf):
        return ResultadoClassificacao(classe, conf)

    assert decidir_status(B, None, 0.5).motivo == "modelo_indisponivel"
    assert decidir_status(B, r(None, 0.0), 0.5).motivo == "sem_deteccao"
    assert decidir_status(B, r(B, 0.49), 0.5).status == S.EM_TRIAGEM
    assert decidir_status(B, r(C, 0.95), 0.5).motivo == "divergencia_cidadao_modelo"
    d = decidir_status(B, r(B, 0.50), 0.5)
    assert d.status == S.CLASSIFICADA


def test_token_do_painel_expira_e_nao_aceita_adulteracao():
    token, expira = emitir_token()
    assert token_valido(token)
    assert not token_valido(token, agora=expira + 1)

    carga, assinatura = token.split(".")
    assert not token_valido(carga + "." + assinatura[:-2] + "xx")
    assert not token_valido("lixo")
    assert not token_valido("")


def test_token_antigo_continua_valido_antes_de_expirar():
    token, _ = emitir_token(agora=time.time() - 3600)
    assert token_valido(token)
