"""Registro do aparelho (token FCM) e verificacao de proximidade (geofencing)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import obter_sessao
from app.dependencias import obter_notificador
from app.models import Dispositivo
from app.schemas import (
    Alerta, ConsultaProximidade, DispositivoEntrada, DispositivoSaida, RespostaProximidade,
)
from app.servicos.geocerca import verificar_proximidade
from app.servicos.notificacoes import Notificador

rotas = APIRouter(tags=["cidadão"])


@rotas.put("/dispositivos/{device_id}", response_model=DispositivoSaida)
def registrar_dispositivo(
    device_id: uuid.UUID,
    entrada: DispositivoEntrada,
    sessao: Session = Depends(obter_sessao),
    notificador: Notificador = Depends(obter_notificador),
):
    """Cria ou atualiza o aparelho. Campos omitidos não são alterados."""
    valores = entrada.model_dump(exclude_unset=True)
    comando = insert(Dispositivo).values(device_id=device_id, **valores)
    comando = comando.on_conflict_do_update(
        index_elements=[Dispositivo.device_id],
        set_={**valores, "atualizado_em": func.now()},
    )
    sessao.execute(comando)
    sessao.commit()

    d = sessao.get(Dispositivo, device_id, populate_existing=True)
    return DispositivoSaida(
        device_id=d.device_id,
        notificacoes_habilitadas=d.notificacoes_habilitadas,
        fcm_registrado=bool(d.fcm_token),
        modo_push=notificador.modo,
    )


@rotas.post("/geofence/checar", response_model=RespostaProximidade)
def checar_proximidade(
    consulta: ConsultaProximidade,
    sessao: Session = Depends(obter_sessao),
    notificador: Notificador = Depends(obter_notificador),
):
    """Alerta proativo: devolve (e envia por push) os alertas das geocercas
    em que o aparelho acabou de entrar. Cada alerta é entregue uma única vez."""
    r = verificar_proximidade(
        sessao, notificador, consulta.device_id,
        consulta.latitude, consulta.longitude, consulta.precisao_m,
    )
    return RespostaProximidade(
        alertas=[Alerta(**vars(a)) for a in r.alertas],
        ignorada=r.ignorada,
        motivo=r.motivo,
        verificado_em=r.verificado_em,
    )
