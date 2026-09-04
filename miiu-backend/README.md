# MIIU — Backend

Backend do Monitoramento Inteligente de Infraestrutura Urbana.
FastAPI + PostgreSQL/PostGIS.

## Primeira execução

Pré-requisitos: Docker Desktop rodando e Python 3.11 ou superior.

```powershell
# 1. subir o banco
docker compose up -d

# 2. criar o ambiente virtual e instalar dependências
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. configurar
copy .env.example .env

# 4. criar as tabelas
alembic upgrade head

# 5. subir a API
uvicorn app.main:app --reload
```

Depois disso, `http://localhost:8000/docs` abre a documentação interativa
e `http://localhost:8000/health` confirma a conexão com o banco.

## Comandos úteis

```powershell
docker compose up -d        # sobe o banco
docker compose down         # para, preservando os dados
docker compose down -v      # para e APAGA os dados
alembic upgrade head        # aplica as migrações
alembic downgrade -1        # desfaz a última
pytest                      # roda a suíte de testes
```

## Estrutura

```
app/
  main.py        aplicação FastAPI
  config.py      configuração por variáveis de ambiente
  database.py    conexão e sessão
  enums.py       classes de ocorrência e estados
  models.py      tabelas
  rotas/         endpoints por recurso
  servicos/      protocolo, inferência, geocerca, notificação
migrations/      versionamento do esquema (Alembic)
testes/          suíte automatizada
uploads/         imagens recebidas (fora do Git)
```

## Decisões registradas

Sem autenticação de cidadão: o acompanhamento é feito por número de
protocolo. Sem tabela de geocerca: ela é a ocorrência validada mais o campo
`raio_m`. Deduplicação de notificações garantida por restrição de unicidade
no banco. Docker apenas para o banco; a API roda nativamente.

Detalhes e justificativas no documento `Plano_Backend_MIIU.docx`.
