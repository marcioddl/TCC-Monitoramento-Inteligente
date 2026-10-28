"""Caminhos e classes compartilhados pelos scripts de ML.

A ordem de CLASSES define os indices do YOLO (0 = buraco, 1 = calcada) e
precisa ser a mesma usada no backend (app/enums.py, pelos nomes).
"""

import unicodedata
from pathlib import Path

ML = Path(__file__).resolve().parents[1]          # .../miiu/ml
PROJETO = ML.parent                                 # .../miiu
BACKEND = PROJETO / "miiu-backend"

RAW = ML / "raw"
WORK = ML / "work"
DATASET = ML / "dataset"
RUNS = ML / "runs"
RESULTADOS = ML / "resultados"

MODELO_BACKEND = BACKEND / "modelos" / "miiu_yolov8.pt"

CLASSES = ["buraco", "calcada_danificada"]
INDICE = {nome: i for i, nome in enumerate(CLASSES)}

EXTENSOES = {".jpg", ".jpeg", ".png"}
SEMENTE = 42


def normalizar_nome(nome: str) -> str:
    """'Calçada Danificada' -> 'calcada_danificada'"""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return "_".join(sem_acento.lower().replace("-", " ").split())


def grupo_da_imagem(nome_arquivo: str) -> str:
    """Identifica a foto original de uma imagem exportada pelo Roboflow.

    'pothole_umat__images155_jpg.rf.bbc54c....jpg' -> 'pothole_umat__images155_jpg'

    As versoes aumentadas da mesma foto so diferem no hash depois de '.rf.'.
    Fotos proprias (sem '.rf.') formam um grupo cada.
    """
    if ".rf." in nome_arquivo:
        return nome_arquivo.split(".rf.")[0]
    return Path(nome_arquivo).stem


def ler_rotulos(caminho: Path) -> list[int]:
    """Indices de classe de cada caixa de um arquivo de rotulos YOLO."""
    if not caminho.is_file():
        return []
    indices = []
    for linha in caminho.read_text().splitlines():
        partes = linha.split()
        if len(partes) >= 5:
            try:
                indices.append(int(partes[0]))
            except ValueError:
                pass
    return indices
