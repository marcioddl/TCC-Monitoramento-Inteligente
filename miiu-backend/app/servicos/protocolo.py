"""Geracao e normalizacao do numero de protocolo.

O protocolo substitui o login do cidadao (decisao de escopo): e o unico
identificador que ele recebe e usa para acompanhar a ocorrencia. Formato:

    MIIU-2026-7K3QXA

O sufixo usa o alfabeto Base32 de Crockford, que exclui I, L, O e U para
evitar confusao na leitura e na digitacao. Seis caracteres dao 32^6, cerca
de um bilhao de combinacoes por ano, o que torna inviavel adivinhar o
protocolo de outra pessoa.
"""

import re
import secrets
from datetime import datetime, timezone

ALFABETO = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
TAMANHO_SUFIXO = 6
PADRAO = re.compile(r"^MIIU-\d{4}-[0-9A-HJKMNP-TV-Z]{6}$")

# Caracteres que o cidadao pode digitar por engano no lugar dos validos
TROCAS = str.maketrans({"O": "0", "I": "1", "L": "1"})


def gerar_protocolo(agora: datetime | None = None) -> str:
    ano = (agora or datetime.now(timezone.utc)).year
    sufixo = "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO_SUFIXO))
    return f"MIIU-{ano}-{sufixo}"


def normalizar_protocolo(texto: str) -> str:
    """Aceita minusculas, espacos e as trocas comuns de Crockford.

    'miiu 2026 7k3qxa' -> 'MIIU-2026-7K3QXA'
    """
    limpo = re.sub(r"[\s_\-]+", "", texto.strip().upper())
    if limpo.startswith("MIIU"):
        limpo = limpo[4:]
    if len(limpo) != 4 + TAMANHO_SUFIXO:
        return texto.strip().upper()
    ano, sufixo = limpo[:4], limpo[4:].translate(TROCAS)
    return f"MIIU-{ano}-{sufixo}"


def protocolo_valido(texto: str) -> bool:
    return bool(PADRAO.match(texto))
