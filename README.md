# MIIU · Monitoramento Inteligente de Infraestrutura Urbana

Sistema colaborativo de monitoramento de infraestrutura urbana: o cidadão
fotografa um problema, o YOLOv8 classifica a foto, o PostGIS registra a
ocorrência e o geofencing avisa quem passa perto das ocorrências validadas.
TCC de Ciência da Computação, UESPI, orientação do Prof. Dr. Sérgio Barros de
Sousa.

| Pasta | O que é | Como abrir |
|---|---|---|
| `miiu-backend/` | API FastAPI + PostgreSQL/PostGIS, YOLOv8, geofencing, FCM | [README](miiu-backend/README.md) |
| `painel/` | Painel de gestão React + Leaflet (já compilado) | http://localhost:8000/painel |
| `miiu-app/` | Aplicativo do cidadão em Flutter (Android e web) | [README](miiu-app/README.md) · versão web em http://localhost:8000/app/ |
| `ml/` | Dataset, divisão sem vazamento, treino e avaliação do YOLOv8 | [README](ml/README.md) |

## Ordem para colocar tudo de pé

1. **Backend**: `docker compose up -d`, `pip install -r requirements.txt`,
   `alembic upgrade head`, `uvicorn app.main:app --reload --host 0.0.0.0`,
   `pytest`.
2. **Painel**: abrir http://localhost:8000/painel.
3. **Simulação**: `python scripts\simular_cenario.py --senha ...`, que
   popula o mapa e mede o geofencing.
4. **Modelo**: `dividir.py`, `treinar.py` e `avaliar.py` em `ml/scripts`;
   reiniciar o uvicorn.
5. **App**: `flutter create ...`, `configurar_android.py`, `flutter run`.

Sem o modelo treinado e sem o Firebase o sistema já funciona de ponta a ponta:
as ocorrências vão para a triagem humana e os alertas aparecem com o app aberto.

## Mapa para a monografia (capítulo 4)

| Etapa do ciclo | Onde está no código |
|---|---|
| Percepção e reporte | `miiu-app/lib/telas/reportar.dart`, `miiu-backend/app/rotas/cidadao.py`, `app/servicos/imagens.py` |
| Recepção e triagem | `app/servicos/classificador.py`, `app/servicos/ocorrencias.py` (`decidir_status`) |
| Registro geoespacial | `app/models.py`, migrações `0001` e `0002`, `app/servicos/geo.py` |
| Alerta proativo | `app/servicos/geocerca.py`, `miiu-app/lib/servicos/geocerca.dart`, `app/servicos/notificacoes.py` |
| Gestão e resolução | `app/rotas/admin.py`, `app/enums.py`, `painel/src/componentes/Detalhe.jsx` |

| Avaliação | Ferramenta | Saída |
|---|---|---|
| Modelo (P, R, F1, mAP@50, mAP@50:95, matriz, limiar) | `ml/scripts/avaliar.py` | `ml/resultados/` |
| Geofencing (precisão, recall, distância no disparo, deduplicação, latência) | `miiu-backend/scripts/simular_cenario.py` | `resultados_simulacao/` |
| Testes funcionais (44 casos) | `pytest` em `miiu-backend/` | terminal |
| Uso real (automação, concordância, tempos) | aba Indicadores do painel | painel e CSV |

## Git

O `.gitignore` desta pasta impede que imagens, datasets, modelos e
credenciais entrem no repositório.
