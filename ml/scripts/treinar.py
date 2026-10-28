"""Treina o YOLOv8 do MIIU por transfer learning (pesos pre-treinados no COCO).

Uso (a partir da pasta miiu/, com o venv do backend ativo):

    python ml/scripts/treinar.py                      # yolov8s, 100 epocas
    python ml/scripts/treinar.py --modelo yolov8n.pt  # versao menor e mais rapida
    python ml/scripts/treinar.py --epocas 3 --fracao 0.1   # teste rapido do pipeline

Parametros padrao pensados para a RTX 4050 Laptop (6 GB): imgsz 640, batch 8,
precisao mista (AMP) e parada antecipada com paciencia de 25 epocas. Se faltar
memoria de video, reduza --batch para 4.

Ao terminar, copia best.pt para miiu-backend/modelos/miiu_yolov8.pt (onde o
backend procura o modelo) e grava ao lado um JSON com os parametros e as
metricas de validacao, para a rastreabilidade do experimento. As curvas de
perda e de mAP ficam em ml/runs/<nome>/results.png.
"""

import argparse
import json
import platform
import shutil
from datetime import datetime
from pathlib import Path

from comum import DATASET, MODELO_BACKEND, RUNS, SEMENTE


def main() -> None:
    parser = argparse.ArgumentParser(description="Treinamento do YOLOv8 do MIIU")
    parser.add_argument("--modelo", default="yolov8s.pt",
                        help="pesos iniciais (yolov8n.pt, yolov8s.pt, yolov8m.pt)")
    parser.add_argument("--dados", default=str(DATASET / "data.yaml"))
    parser.add_argument("--epocas", type=int, default=100)
    parser.add_argument("--paciencia", type=int, default=25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--dispositivo", default=None,
                        help="0 para a primeira GPU, cpu para forcar CPU (padrao: automatico)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--fracao", type=float, default=1.0,
                        help="fracao do treino a usar (ex.: 0.1 para um teste rapido)")
    parser.add_argument("--nome", default=None, help="nome da execucao em ml/runs/")
    parser.add_argument("--nao-publicar", action="store_true",
                        help="nao copiar o melhor modelo para o backend")
    args = parser.parse_args()

    dados = Path(args.dados)
    if not dados.is_file():
        raise SystemExit(f"{dados} nao existe. Rode antes: python ml/scripts/dividir.py")

    import torch
    from ultralytics import YOLO

    if args.dispositivo is None:
        args.dispositivo = 0 if torch.cuda.is_available() else "cpu"
    if args.dispositivo == "cpu":
        print("\n[aviso] treinando na CPU. Para usar a GPU instale o PyTorch com CUDA "
              "(veja ml/README.md). Na CPU, 100 epocas podem levar muitas horas.\n")
    else:
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    nome = args.nome or f"miiu_{Path(args.modelo).stem}_{datetime.now():%Y%m%d_%H%M}"
    modelo = YOLO(args.modelo)
    modelo.train(
        data=str(dados),
        epochs=args.epocas,
        patience=args.paciencia,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.dispositivo,
        workers=args.workers,
        fraction=args.fracao,
        project=str(RUNS),
        name=nome,
        exist_ok=False,
        seed=SEMENTE,
        deterministic=True,
        amp=True,
        plots=True,
        verbose=True,
    )

    melhor = Path(modelo.trainer.best)
    pasta = melhor.parent.parent
    metricas = {k: round(float(v), 4) for k, v in (modelo.trainer.metrics or {}).items()}
    print(f"\nmelhor modelo: {melhor}")
    print(f"curvas e graficos: {pasta}")
    print("metricas de validacao do melhor modelo:")
    for chave, valor in metricas.items():
        print(f"  {chave:<28} {valor}")

    if args.nao_publicar:
        return

    MODELO_BACKEND.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(melhor, MODELO_BACKEND)
    metadados = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "execucao": str(pasta),
        "pesos_iniciais": args.modelo,
        "dados": str(dados),
        "parametros": {
            "epocas": args.epocas, "paciencia": args.paciencia, "imgsz": args.imgsz,
            "batch": args.batch, "fracao": args.fracao, "semente": SEMENTE,
            "dispositivo": str(args.dispositivo),
        },
        "epocas_executadas": int(modelo.trainer.epoch) + 1,
        "metricas_validacao": metricas,
        "ambiente": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
    }
    MODELO_BACKEND.with_suffix(".json").write_text(
        json.dumps(metadados, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nmodelo publicado para o backend: {MODELO_BACKEND}")
    print("reinicie o uvicorn para carregar o novo modelo.")


if __name__ == "__main__":
    # A guarda acima e obrigatoria no Windows: os workers do DataLoader sao
    # processos novos que reimportam este arquivo.
    main()
