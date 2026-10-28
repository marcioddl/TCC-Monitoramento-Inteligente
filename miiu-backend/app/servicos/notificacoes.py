"""Envio de notificacoes push pelo Firebase Cloud Messaging (FCM).

Com FIREBASE_CREDENCIAIS apontando para o JSON da conta de servico, as
mensagens saem pelo FCM. Sem ele, o notificador opera em modo simulado:
registra o envio no log e devolve "nao enviado", e o aplicativo mostra o
alerta a partir da propria resposta da consulta de proximidade. Assim o
mecanismo de geofencing pode ser demonstrado e testado sem um projeto
Firebase configurado.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("miiu.notificacoes")


@dataclass
class ResultadoEnvio:
    enviado: bool
    token_invalido: bool = False
    erro: str = ""


class Notificador:
    modo = "simulado"

    def enviar(self, token: str, titulo: str, corpo: str, dados: dict[str, str]) -> ResultadoEnvio:
        log.info("[simulado] push para %s...: %s | %s", token[:12], titulo, corpo)
        return ResultadoEnvio(enviado=False, erro="modo simulado")


class NotificadorFCM(Notificador):
    modo = "fcm"

    def __init__(self, credenciais: Path):
        import firebase_admin
        from firebase_admin import credentials, messaging

        self._messaging = messaging
        # Reutiliza o app se ele ja tiver sido inicializado (ex.: reload do uvicorn)
        try:
            self._app = firebase_admin.get_app("miiu")
        except ValueError:
            self._app = firebase_admin.initialize_app(
                credentials.Certificate(str(credenciais)), name="miiu"
            )

    def enviar(self, token: str, titulo: str, corpo: str, dados: dict[str, str]) -> ResultadoEnvio:
        m = self._messaging
        mensagem = m.Message(
            token=token,
            notification=m.Notification(title=titulo, body=corpo),
            # o FCM exige que todos os valores de "data" sejam strings
            data={k: str(v) for k, v in dados.items()},
            android=m.AndroidConfig(priority="high"),
        )
        try:
            m.send(mensagem, app=self._app)
            return ResultadoEnvio(enviado=True)
        except (m.UnregisteredError, m.SenderIdMismatchError) as e:
            return ResultadoEnvio(enviado=False, token_invalido=True, erro=str(e))
        except Exception as e:  # rede, cota, credencial
            log.warning("falha no envio FCM: %s", e)
            return ResultadoEnvio(enviado=False, erro=str(e))


def carregar_notificador(caminho_credenciais: str) -> Notificador:
    if not caminho_credenciais:
        log.info("FIREBASE_CREDENCIAIS vazio: notificacoes em modo simulado")
        return Notificador()
    arquivo = Path(caminho_credenciais)
    if not arquivo.is_file():
        log.warning("credenciais do Firebase nao encontradas em %s; modo simulado", arquivo)
        return Notificador()
    try:
        notificador = NotificadorFCM(arquivo)
    except ImportError:
        log.warning("firebase-admin nao instalado; modo simulado")
        return Notificador()
    except Exception:
        log.exception("falha ao iniciar o Firebase; modo simulado")
        return Notificador()
    log.info("notificacoes push via FCM ativas")
    return notificador
