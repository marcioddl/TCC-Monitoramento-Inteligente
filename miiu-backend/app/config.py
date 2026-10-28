"""Configuracao lida de variaveis de ambiente (arquivo .env).

Todos os campos, exceto DATABASE_URL, tem valor padrao. Assim um .env antigo
continua valido quando novas opcoes sao adicionadas.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str

    # --- painel de gestao (decisao 2.1: senha unica, sem cadastro de usuarios)
    ADMIN_SENHA: str = "123456"
    # Segredo que assina os tokens do painel. Vazio = derivado da ADMIN_SENHA,
    # o que faz a troca de senha invalidar todos os tokens ja emitidos.
    SEGREDO_TOKEN: str = ""
    TOKEN_VALIDADE_HORAS: int = 12

    # --- imagens
    UPLOAD_DIR: str = "uploads"
    UPLOAD_MAX_MB: int = 10
    # Imagens com o maior lado acima disto (em pixels) sao reduzidas
    IMAGEM_LADO_MAX: int = 1920

    # --- geofencing
    GEOFENCE_RAIO_PADRAO: int = 100
    # Teto do raio de uma geocerca; tambem limita a busca no indice espacial
    GEOFENCE_RAIO_MAX: int = 1000
    # Leituras de GPS com incerteza maior que isto sao ignoradas
    GEOFENCE_PRECISAO_MAX_M: float = 150.0
    # Ocorrencias da mesma classe a menos disto aparecem como possivel
    # duplicata no painel
    RAIO_DUPLICATA_M: int = 30

    # --- visao computacional
    INFERENCIA_LIMIAR: float = 0.50
    MODELO_PATH: str = "modelos/miiu_yolov8.pt"
    MODELO_IMGSZ: int = 640
    # Confianca minima para uma caixa entrar no resultado da inferencia
    MODELO_CONF_MIN: float = 0.10

    # --- notificacoes push (vazio = modo simulado, sem Firebase)
    FIREBASE_CREDENCIAIS: str = ""

    # --- protecao contra abuso
    LIMITE_REPORTES_HORA: int = 10

    # Fuso usado para agrupar os indicadores por dia (Teresina = UTC-3)
    FUSO_HORARIO: str = "America/Fortaleza"

    # --- web
    # Origens liberadas no CORS, separadas por virgula
    CORS_ORIGENS: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Pasta do painel React compilado (npm run build), servido em /painel
    PAINEL_DIR: str = "../painel/dist"
    # Pasta do app do cidadao compilado para a web, servido em /app
    # (flutter build web --release --base-href /app/)
    APP_WEB_DIR: str = "../miiu-app/build/web"


config = Config()
