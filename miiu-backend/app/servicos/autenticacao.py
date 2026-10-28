"""Autenticacao do painel de gestao (decisao 2.1: senha unica).

O gestor troca a senha por um token assinado com HMAC-SHA256, valido por
TOKEN_VALIDADE_HORAS. O token carrega apenas a data de expiracao; a
assinatura impede que seja forjado ou prorrogado. So a biblioteca padrao do
Python e usada.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import config


def _segredo() -> bytes:
    if config.SEGREDO_TOKEN:
        return config.SEGREDO_TOKEN.encode()
    return hashlib.sha256(f"miiu-painel:{config.ADMIN_SENHA}".encode()).digest()


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def _de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def senha_confere(senha: str) -> bool:
    return secrets.compare_digest(senha.encode(), config.ADMIN_SENHA.encode())


def emitir_token(agora: float | None = None) -> tuple[str, int]:
    expira = int((agora or time.time()) + config.TOKEN_VALIDADE_HORAS * 3600)
    carga = _b64(json.dumps({"exp": expira, "papel": "gestor"}).encode())
    assinatura = _b64(hmac.new(_segredo(), carga.encode(), hashlib.sha256).digest())
    return f"{carga}.{assinatura}", expira


def token_valido(token: str, agora: float | None = None) -> bool:
    try:
        carga, assinatura = token.split(".")
        esperada = _b64(hmac.new(_segredo(), carga.encode(), hashlib.sha256).digest())
        if not secrets.compare_digest(assinatura, esperada):
            return False
        dados = json.loads(_de_b64(carga))
        return dados.get("papel") == "gestor" and dados["exp"] > (agora or time.time())
    except (ValueError, KeyError, TypeError):
        return False


_bearer = HTTPBearer(auto_error=False)


def exigir_gestor(credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    """Dependencia das rotas /admin."""
    if credenciais is None or not token_valido(credenciais.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token do painel ausente, invalido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
