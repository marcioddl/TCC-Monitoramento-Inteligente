# MIIU · Backend (FastAPI + PostgreSQL/PostGIS)

API que recebe os reportes do aplicativo, classifica a foto com o YOLOv8,
registra a ocorrência no PostGIS, dispara os alertas de proximidade
(geofencing + Firebase Cloud Messaging) e atende o painel de gestão.

## Como rodar (Windows, PowerShell)

Pré-requisitos: Docker Desktop aberto e Python 3.13. O PostgreSQL nativo do
Windows precisa estar parado, senão disputa a porta 5432.

```powershell
cd C:\Users\"Marcio Felipe"\miiu\miiu-backend

docker compose up -d                 # sobe o banco (PostGIS 16-3.4)
.\.venv\Scripts\Activate.ps1         # ativa o ambiente virtual
pip install -r requirements.txt      # instala as novas dependências
alembic upgrade head                 # aplica a migração 0002
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Documentação interativa: http://localhost:8000/docs
- Painel de gestão: http://localhost:8000/painel (senha = `ADMIN_SENHA` do `.env`)
- App do cidadão na web: http://localhost:8000/app/ (depois do `flutter build web`, veja o README do app)
- Saúde do sistema: http://localhost:8000/health

`--host 0.0.0.0` deixa o celular da mesma rede Wi-Fi acessar a API pelo IP do
computador. Na primeira vez o Windows pergunta se libera o Python no firewall:
libere para **redes privadas**.

O seu `.env` antigo continua válido: todas as opções novas têm valor padrão.
Veja o `.env.example` para o que pode ser ajustado.

## Testes automatizados

Com o Docker do banco no ar e o venv ativo:

```powershell
pytest
```

São 44 testes que rodam contra um PostGIS real, num banco separado
(`miiu_test`, criado sozinho). O esquema é criado pelas próprias migrações,
então elas também são testadas. Os testes cobrem: classificação e triagem
(confiança, divergência cidadão × modelo, falha do modelo), remoção de EXIF
e orientação da foto, validações de entrada, limite de reportes, protocolo e
histórico, máquina de estados, autenticação do painel, indicadores, CSV e o
geofencing (dentro/fora do raio, deduplicação inclusive com 8 requisições
simultâneas, autor não é alertado, GPS impreciso, FCM e token inválido, raio
personalizado, ordenação por distância, mapa público).

## Simulação de cenário (objetivo específico 4)

Com a API rodando, em outro terminal:

```powershell
python scripts\simular_cenario.py --senha SUA_ADMIN_SENHA
python scripts\simular_cenario.py --senha SUA_ADMIN_SENHA --ruido-gps 8      # com erro de GPS
python scripts\simular_cenario.py --senha SUA_ADMIN_SENHA --imagens ..\ml\dataset\test\images
```

Cria ocorrências a distâncias conhecidas de um trajeto de 1,5 km no centro
de Teresina, valida pelo painel e faz um pedestre virtual percorrer o
trajeto (ida e volta). Compara alertas esperados × recebidos (precisão e
recall do mecanismo), mede a distância no disparo, confirma que nenhum alerta
se repete e mede a latência de cada verificação. Os resultados ficam em
`resultados_simulacao\<data_hora>\` (CSV e JSON). Os registros criados levam
`[SIMULACAO]` na descrição.

Resultado da execução de referência (raio 100 m, leituras a cada 10 m):
VP = 5, FP = 0, FN = 0, VN = 6 (precisão e recall de 100%), disparo entre
90,0 e 99,6 m, 0 alertas repetidos e latência média de 8,6 ms.

## Endpoints

| Método | Rota | Quem usa | O que faz |
|---|---|---|---|
| POST | `/ocorrencias` | app | Reporte: foto + latitude/longitude + classe (multipart) |
| GET | `/ocorrencias/{protocolo}` | app | Acompanhamento pelo protocolo, com histórico |
| GET | `/ocorrencias/{protocolo}/imagem` | app, painel | Foto (sem metadados) |
| GET | `/ocorrencias/mapa` | app | Ocorrências ativas ao redor de um ponto (sem descrição) |
| PUT | `/dispositivos/{device_id}` | app | Registra o aparelho e o token FCM |
| POST | `/geofence/checar` | app | Verificação de proximidade; devolve e envia os alertas |
| POST | `/admin/login` | painel | Troca a senha por um token (12 h) |
| GET | `/admin/ocorrencias` | painel | Lista com filtros (status, classe, período, busca) |
| GET | `/admin/ocorrencias/{id}` | painel | Detalhe: detecções, auditoria, possíveis duplicatas |
| PATCH | `/admin/ocorrencias/{id}/status` | painel | Transição de status (validar, rejeitar, resolver...) |
| GET | `/admin/estatisticas` | painel | Indicadores (automação, concordância, tempos, alertas) |
| GET | `/admin/exportar.csv` | painel | Todas as ocorrências em CSV |
| GET | `/health` | todos | Banco, PostGIS, migração, modelo e modo do push |

## Como as peças se encaixam (capítulo 4 da monografia)

**Percepção e reporte** (`app/rotas/cidadao.py`). A foto é decodificada e
regravada como JPEG novo (`app/servicos/imagens.py`). Isso valida o conteúdo,
aplica a orientação do EXIF (senão a foto em pé chega deitada ao modelo) e
descarta todos os metadados, inclusive o GPS embutido e o modelo do celular.
O sistema não tem login: o aparelho é um UUID e o cidadão recebe um protocolo
(`MIIU-2026-7K3QXA`, alfabeto Base32 de Crockford, sem I, L, O e U).

**Recepção e triagem** (`app/servicos/ocorrencias.py`). O YOLOv8 roda no
próprio backend (`app/servicos/classificador.py`), carregado uma vez na
inicialização. A ocorrência recebe a classe da caixa de maior confiança. Vai
direto para o gestor como `classificada` se a confiança passar do limiar
(`INFERENCIA_LIMIAR`, 0,50) e o modelo concordar com o cidadão; caso
contrário vai para `em_triagem`, com o motivo registrado (confiança baixa,
divergência, nenhuma detecção ou modelo indisponível). Sem o arquivo do
modelo a API continua funcionando e tudo vai para a triagem humana.

**Registro geoespacial**. Ponto em `geography(POINT, 4326)` com índice GiST.
No tipo geography as distâncias saem direto em metros, sobre o elipsoide.

**Alerta proativo** (`app/servicos/geocerca.py`). Cada ocorrência validada ou
em atendimento é uma geocerca de `raio_m` metros (100 por padrão). O app
envia a posição; uma única consulta espacial encontra as geocercas em que o
aparelho está e que ainda não o alertaram. A deduplicação é garantida pelo
banco (restrição única ocorrência + aparelho, `INSERT ... ON CONFLICT DO
NOTHING`). A posição do aparelho não é gravada (LGPD), só a distância no
disparo. A consulta usa duas condições `ST_DWithin`: uma com raio constante
(1.000 m), que permite ao PostgreSQL usar o índice, e outra com o raio de cada
geocerca. Medido com 50 mil ocorrências: 8 ms com o índice contra 2,7 s sem
ele (varredura completa).

**Gestão e resolução** (`app/rotas/admin.py`). Transições validadas pela
máquina de estados (`app/enums.py`), cada uma registrada na auditoria com
observação. A classe decidida pelo gestor fica em `classe_validada`, separada
da `classe_detectada`, o que permite medir em uso a concordância entre o
modelo e o gestor (indicador do painel).

## Modelo de visão computacional

O backend procura os pesos em `modelos/miiu_yolov8.pt` (configurável em
`MODELO_PATH`). O script `ml/scripts/treinar.py` copia o melhor modelo para lá
ao fim do treinamento. Depois, reinicie o uvicorn. O `/health` mostra a
versão carregada (nome + 8 primeiros caracteres do SHA-256 dos pesos), e cada
ocorrência guarda a versão que a classificou.

## Notificações push (Firebase Cloud Messaging)

Sem configuração, as notificações ficam em **modo simulado**: o alerta é
entregue na resposta da verificação e o app o mostra quando está aberto.
Para enviar push de verdade:

1. No [console do Firebase](https://console.firebase.google.com), crie um
   projeto e adicione o app Android (pacote `br.uespi.miiu.miiu_app`).
2. Em Configurações do projeto > Contas de serviço, clique em
   "Gerar nova chave privada" e salve o JSON em
   `miiu-backend\firebase-credenciais.json` (o `.gitignore` já impede que ele
   vá para o GitHub).
3. No `.env`: `FIREBASE_CREDENCIAIS=firebase-credenciais.json`
4. Reinicie o uvicorn; o `/health` passa a mostrar `"notificacoes": "fcm"`.
5. No app, rode o `flutterfire configure` (veja o README do app).

## Estrutura

```
app/
  main.py              aplicação, CORS, painel em /painel, /health
  config.py            opções do .env
  models.py            tabelas (SQLAlchemy + GeoAlchemy2)
  schemas.py           formatos de entrada e saída (Pydantic)
  enums.py             classes, status e transições permitidas
  rotas/               cidadao.py, dispositivos.py, admin.py
  servicos/            regras de negócio (uma responsabilidade por arquivo)
migrations/versions/   0001 esquema inicial, 0002 validação e alertas
tests/                 44 testes (pytest)
scripts/               simular_cenario.py
modelos/               pesos do YOLOv8 (não versionados)
uploads/               fotos recebidas (não versionadas)
```

O arquivo `app/consolidar.py` é uma cópia antiga do script de dataset e não é
usado pela API: a versão atual está em `ml/scripts/consolidar.py`, então ele
pode ser apagado.
