"""Avalia o modelo no conjunto de TESTE (nunca visto no treino nem na validacao).

Produz dois niveis de metricas:

1. Deteccao (padrao da literatura, calculado pelo Ultralytics): precisao,
   recall, F1, mAP@50 e mAP@50:95 por classe, matriz de confusao e curvas.

2. Classificacao da ocorrencia (como o backend usa o modelo): cada foto
   recebe a classe da caixa de maior confianca. Mede acuracia, precisao,
   recall e F1 por classe (objetivo do projeto: F1 > 80%) e simula o limiar
   de triagem: para cada limiar, quantas ocorrencias seriam classificadas
   automaticamente e com que acerto. Essa tabela justifica o valor de
   INFERENCIA_LIMIAR usado no backend.

Uso (a partir da pasta miiu/):

    python ml/scripts/avaliar.py
    python ml/scripts/avaliar.py --pesos ml/runs/<execucao>/weights/best.pt

Resultados em ml/resultados/<nome>/ (JSON, CSVs e graficos).
"""

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from comum import CLASSES, DATASET, EXTENSOES, MODELO_BACKEND, RESULTADOS, ler_rotulos

NENHUMA = "nenhuma"


def f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if (p + r) else 0.0


def ler_particao(dados: Path, particao: str) -> list[tuple[Path, str]]:
    """(imagem, classe verdadeira) da particao; 'negativa' se nao ha caixas."""
    pasta = dados.parent / particao / "images"
    if not pasta.is_dir():
        raise SystemExit(f"particao nao encontrada: {pasta}")
    itens = []
    for img in sorted(pasta.iterdir()):
        if img.suffix.lower() not in EXTENSOES:
            continue
        caixas = ler_rotulos(pasta.parent / "labels" / f"{img.stem}.txt")
        verdade = CLASSES[Counter(caixas).most_common(1)[0][0]] if caixas else "negativa"
        itens.append((img, verdade))
    return itens


def metricas_deteccao(modelo, dados: Path, particao: str, args, saida: Path) -> dict:
    m = modelo.val(
        data=str(dados), split=particao, imgsz=args.imgsz, batch=args.batch,
        conf=0.001, plots=True, project=str(saida.parent), name=saida.name,
        exist_ok=True, verbose=False,
    )
    por_classe = {}
    for pos, indice in enumerate(m.box.ap_class_index):
        p, r, ap50, ap = m.box.class_result(pos)
        por_classe[CLASSES[int(indice)]] = {
            "precisao": round(float(p), 4), "recall": round(float(r), 4),
            "f1": round(f1(p, r), 4), "map50": round(float(ap50), 4),
            "map50_95": round(float(ap), 4),
        }
    geral = {
        "precisao": round(float(m.box.mp), 4), "recall": round(float(m.box.mr), 4),
        "f1": round(f1(m.box.mp, m.box.mr), 4), "map50": round(float(m.box.map50), 4),
        "map50_95": round(float(m.box.map), 4),
    }
    matriz = m.confusion_matrix.matrix.tolist()
    return {
        "geral": geral, "por_classe": por_classe,
        "matriz_confusao": {"rotulos": CLASSES + ["fundo"], "valores": matriz,
                            "observacao": "linhas = previsto, colunas = verdadeiro"},
        "tempo_ms_por_imagem": {k: round(float(v), 2) for k, v in m.speed.items()},
    }


def metricas_ocorrencia(modelo, itens, args) -> tuple[dict, list[dict], list[dict]]:
    previsoes = []
    for resultado, (img, verdade) in zip(
        modelo.predict([str(i) for i, _ in itens], imgsz=args.imgsz, conf=args.conf_min,
                       stream=True, verbose=False),
        itens,
    ):
        caixas = resultado.boxes
        if caixas is not None and len(caixas):
            melhor = int(caixas.conf.argmax())
            classe = resultado.names[int(caixas.cls[melhor])]
            confianca = float(caixas.conf[melhor])
        else:
            classe, confianca = NENHUMA, 0.0
        previsoes.append({"imagem": img.name, "verdade": verdade,
                          "previsto": classe, "confianca": round(confianca, 4)})

    positivas = [p for p in previsoes if p["verdade"] != "negativa"]
    negativas = [p for p in previsoes if p["verdade"] == "negativa"]

    matriz = {v: Counter() for v in CLASSES}
    for p in positivas:
        matriz[p["verdade"]][p["previsto"]] += 1

    por_classe = {}
    for c in CLASSES:
        vp = matriz[c][c]
        previstos_c = sum(matriz[v][c] for v in CLASSES)
        reais_c = sum(matriz[c].values())
        prec = vp / previstos_c if previstos_c else 0.0
        rec = vp / reais_c if reais_c else 0.0
        por_classe[c] = {"precisao": round(prec, 4), "recall": round(rec, 4),
                         "f1": round(f1(prec, rec), 4), "suporte": reais_c}

    acertos = sum(matriz[c][c] for c in CLASSES)
    macro_f1 = sum(v["f1"] for v in por_classe.values()) / len(CLASSES)

    # simulacao do limiar de triagem do backend
    tabela_limiar = []
    for i in range(2, 19):
        limiar = round(i * 0.05, 2)
        confiantes = [p for p in positivas if p["confianca"] >= limiar]
        corretos = [p for p in confiantes if p["previsto"] == p["verdade"]]
        alarmes = [p for p in negativas if p["confianca"] >= limiar]
        tabela_limiar.append({
            "limiar": limiar,
            "automacao": round(len(corretos) / len(positivas), 4) if positivas else None,
            "precisao_automatica": round(len(corretos) / len(confiantes), 4) if confiantes else None,
            "erros_confiantes": len(confiantes) - len(corretos),
            "para_triagem": len(positivas) - len(corretos),
            "alarmes_em_negativas": len(alarmes),
        })

    linha_limiar = next(t for t in tabela_limiar if abs(t["limiar"] - args.limiar) < 1e-9) \
        if any(abs(t["limiar"] - args.limiar) < 1e-9 for t in tabela_limiar) else None

    resumo = {
        "imagens": len(previsoes), "positivas": len(positivas), "negativas": len(negativas),
        "acuracia": round(acertos / len(positivas), 4) if positivas else None,
        "f1_macro": round(macro_f1, 4),
        "por_classe": por_classe,
        "matriz": {v: {p: matriz[v][p] for p in CLASSES + [NENHUMA]} for v in CLASSES},
        "limiar_backend": args.limiar,
        "no_limiar_backend": linha_limiar,
    }
    return resumo, tabela_limiar, previsoes


def gravar_csv(caminho: Path, linhas: list[dict]) -> None:
    if not linhas:
        return
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Avaliacao do modelo no conjunto de teste")
    parser.add_argument("--pesos", default=str(MODELO_BACKEND))
    parser.add_argument("--dados", default=str(DATASET / "data.yaml"))
    parser.add_argument("--particao", default="test", choices=["test", "val"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--conf-min", type=float, default=0.10,
                        help="confianca minima de uma caixa (igual a MODELO_CONF_MIN do backend)")
    parser.add_argument("--limiar", type=float, default=0.50,
                        help="limiar de triagem do backend (INFERENCIA_LIMIAR)")
    parser.add_argument("--nome", default=None)
    args = parser.parse_args()

    pesos, dados = Path(args.pesos), Path(args.dados)
    for arquivo in (pesos, dados):
        if not arquivo.is_file():
            raise SystemExit(f"arquivo nao encontrado: {arquivo}")

    from ultralytics import YOLO

    saida = RESULTADOS / (args.nome or f"{pesos.stem}_{args.particao}_{datetime.now():%Y%m%d_%H%M}")
    saida.mkdir(parents=True, exist_ok=True)
    modelo = YOLO(str(pesos))

    print(f"avaliando {pesos} na particao '{args.particao}'...")
    deteccao = metricas_deteccao(modelo, dados, args.particao, args, saida)
    itens = ler_particao(dados, args.particao)
    ocorrencia, tabela_limiar, previsoes = metricas_ocorrencia(modelo, itens, args)

    relatorio = {
        "pesos": str(pesos), "particao": args.particao,
        "avaliado_em": datetime.now().isoformat(timespec="seconds"),
        "deteccao": deteccao, "ocorrencia": ocorrencia,
    }
    (saida / "metricas.json").write_text(
        json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    gravar_csv(saida / "metricas_por_classe.csv", [
        {"classe": c, **{f"det_{k}": v for k, v in deteccao["por_classe"].get(c, {}).items()},
         **{f"ocor_{k}": v for k, v in ocorrencia["por_classe"][c].items()}}
        for c in CLASSES
    ])
    gravar_csv(saida / "limiar.csv", tabela_limiar)
    gravar_csv(saida / "previsoes.csv", previsoes)

    g = deteccao["geral"]
    print("\n" + "=" * 70)
    print(f"DETECCAO ({args.particao})        precisao  recall    F1    mAP@50  mAP@50:95")
    print("=" * 70)
    for nome, v in [("todas", g)] + list(deteccao["por_classe"].items()):
        print(f"{nome:<26}{v['precisao']:>9.3f}{v['recall']:>8.3f}{v['f1']:>7.3f}"
              f"{v['map50']:>9.3f}{v['map50_95']:>11.3f}")
    print(f"\ntempo por imagem (ms): {deteccao['tempo_ms_por_imagem']}")

    print("\n" + "=" * 70)
    print("CLASSIFICACAO DA OCORRENCIA (caixa de maior confianca)")
    print("=" * 70)
    print(f"imagens positivas: {ocorrencia['positivas']}   negativas: {ocorrencia['negativas']}")
    print(f"acuracia: {ocorrencia['acuracia']}   F1 macro: {ocorrencia['f1_macro']}  (meta: > 0.80)")
    for c, v in ocorrencia["por_classe"].items():
        print(f"  {c:<22} P={v['precisao']:.3f}  R={v['recall']:.3f}  F1={v['f1']:.3f}  n={v['suporte']}")
    print("\nmatriz (linhas = verdadeiro):")
    print(f"  {'':<22}" + "".join(f"{p[:12]:>14}" for p in CLASSES + [NENHUMA]))
    for v, linha in ocorrencia["matriz"].items():
        print(f"  {v:<22}" + "".join(f"{linha[p]:>14}" for p in CLASSES + [NENHUMA]))

    print("\nlimiar de triagem  automacao  precisao_auto  para_triagem")
    for t in tabela_limiar:
        marca = "  <- backend" if abs(t["limiar"] - args.limiar) < 1e-9 else ""
        auto = f"{t['automacao']:.3f}" if t["automacao"] is not None else "  -  "
        prec = f"{t['precisao_automatica']:.3f}" if t["precisao_automatica"] is not None else "  -  "
        print(f"  {t['limiar']:>6.2f}          {auto:>7}      {prec:>7}        {t['para_triagem']:>5}{marca}")

    print(f"\nresultados gravados em {saida}")


if __name__ == "__main__":
    main()
