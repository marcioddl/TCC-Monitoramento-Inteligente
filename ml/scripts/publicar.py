"""Publica no backend o melhor modelo de uma execucao de treinamento.

O treinar.py ja publica sozinho ao terminar. Este script serve para escolher
outra execucao depois, por exemplo o YOLOv8m treinado com --nao-publicar,
mantendo os metadados (JSON ao lado do .pt) coerentes com o modelo publicado.

Uso (a partir da pasta miiu/):

    python ml/scripts/publicar.py ml/runs/miiu_yolov8m_20261028_0909

Depois, reinicie o uvicorn.
"""

import argparse
import csv
import json
import platform
import shutil
from datetime import datetime
from pathlib import Path

from comum import MODELO_BACKEND


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica o best.pt de uma execucao")
    parser.add_argument("execucao", help="pasta da execucao em ml/runs/")
    args = parser.parse_args()

    pasta = Path(args.execucao).resolve()
    pesos = pasta / "weights" / "best.pt"
    resultados = pasta / "results.csv"
    if not pesos.is_file() or not resultados.is_file():
        raise SystemExit(f"execucao incompleta: preciso de {pesos} e {resultados}")

    import yaml

    parametros = yaml.safe_load((pasta / "args.yaml").read_text(encoding="utf-8"))
    with open(resultados, encoding="utf-8") as f:
        epocas = [{k.strip(): v.strip() for k, v in linha.items()} for linha in csv.DictReader(f)]

    # o best.pt do Ultralytics e a epoca de maior "fitness", dominada pelo mAP@50:95
    melhor = max(epocas, key=lambda e: float(e["metrics/mAP50-95(B)"]))
    metricas = {
        chave: round(float(melhor[chave]), 4)
        for chave in ("metrics/precision(B)", "metrics/recall(B)",
                      "metrics/mAP50(B)", "metrics/mAP50-95(B)")
    }

    gpu = None
    try:
        import torch

        versao_torch = torch.__version__
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
    except ImportError:
        versao_torch = None

    MODELO_BACKEND.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pesos, MODELO_BACKEND)
    metadados = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "execucao": str(pasta),
        "pesos_iniciais": parametros.get("model"),
        "dados": parametros.get("data"),
        "parametros": {
            "epocas": parametros.get("epochs"), "paciencia": parametros.get("patience"),
            "imgsz": parametros.get("imgsz"), "batch": parametros.get("batch"),
            "fracao": parametros.get("fraction"), "semente": parametros.get("seed"),
            "otimizador": parametros.get("optimizer"),
        },
        "epocas_executadas": len(epocas),
        "melhor_epoca": int(float(melhor["epoch"])),
        "metricas_validacao": metricas,
        "ambiente": {"python": platform.python_version(), "torch": versao_torch, "gpu": gpu},
    }
    MODELO_BACKEND.with_suffix(".json").write_text(
        json.dumps(metadados, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"publicado: {pesos}")
    print(f"       em: {MODELO_BACKEND}")
    print(f"melhor epoca {metadados['melhor_epoca']} de {len(epocas)}: {metricas}")
    print("reinicie o uvicorn para carregar o novo modelo.")


if __name__ == "__main__":
    main()
