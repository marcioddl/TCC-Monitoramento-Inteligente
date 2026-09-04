import enum


class ClasseOcorrencia(str, enum.Enum):
    BURACO = "buraco"
    CALCADA_DANIFICADA = "calcada_danificada"


class StatusOcorrencia(str, enum.Enum):
    RECEBIDA = "recebida"
    CLASSIFICADA = "classificada"
    EM_TRIAGEM = "em_triagem"
    VALIDADA = "validada"
    EM_ATENDIMENTO = "em_atendimento"
    RESOLVIDA = "resolvida"
    REJEITADA = "rejeitada"

TRANSICOES = {
    StatusOcorrencia.RECEBIDA: {StatusOcorrencia.CLASSIFICADA, StatusOcorrencia.EM_TRIAGEM},
    StatusOcorrencia.CLASSIFICADA: {StatusOcorrencia.VALIDADA, StatusOcorrencia.EM_TRIAGEM, StatusOcorrencia.REJEITADA},
    StatusOcorrencia.EM_TRIAGEM: {StatusOcorrencia.VALIDADA, StatusOcorrencia.REJEITADA},
    StatusOcorrencia.VALIDADA: {StatusOcorrencia.EM_ATENDIMENTO, StatusOcorrencia.REJEITADA},
    StatusOcorrencia.EM_ATENDIMENTO: {StatusOcorrencia.RESOLVIDA},
    StatusOcorrencia.RESOLVIDA: set(),
    StatusOcorrencia.REJEITADA: set(),
}


def transicao_valida(atual: StatusOcorrencia, novo: StatusOcorrencia) -> bool:
    return novo in TRANSICOES.get(atual, set())
