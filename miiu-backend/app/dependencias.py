"""Dependencias compartilhadas pelas rotas.

O classificador e o notificador sao criados uma unica vez na inicializacao
(ciclo_de_vida em main.py) e guardados em app.state. Os testes substituem
estas funcoes por versoes falsas via app.dependency_overrides.
"""

from fastapi import Request

from app.servicos.classificador import Classificador
from app.servicos.notificacoes import Notificador


def obter_classificador(request: Request) -> Classificador:
    return request.app.state.classificador


def obter_notificador(request: Request) -> Notificador:
    return request.app.state.notificador
