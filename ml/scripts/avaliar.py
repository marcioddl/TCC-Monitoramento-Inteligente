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
    python ml/scripts/avaliar.py --pasta ml/work/teresina --nome generalizacao_teresina

Com --pasta, avalia uma pasta com images/ e labels/ em vez de uma particao
do dataset. Serve para o teste de generalizacao: medir o modelo em imagens
de Teresina antes de elas entrarem no treino.

Resultados em ml/resultados/<nome>/ (JSON, CSVs e graficos). O previsoes.csv
traz tambem o brilho medio de cada imagem (0 a 255), para separar as fotos
noturnas na analise.
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageStat

from comum import CLASSES, DATASET, EXTENSOES, MODELO_BACKEND, RESULTADOS, ler_rotulos

NENHUMA = "nenhuma"


def f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if (p + r) else 0.0


def brilho(caminho: Path) -> float:
    """Luminancia media (0 = preto, 255 = branco); fotos noturnas ficam baixas."""
    try:
        with Image.open(caminho) as im:
            cinza = im.convert("L")
            cinza.thumbnail((256, 256))
            return round(ImageStat.Stat(cinza).mean[0], 1)
    except OSError:
        return -1.0


def origem_da_imagem(nome: str) -> str:
    """'proprias__foto.jpg' -> 'proprias' (prefixo gravado pelo consolidar.py)."""
    return nome.split("__", 1)[0] if "__" in nome else "-"


def ler_particao(pasta: Path) -> list[tuple[Path, str]]:
    """(imagem, classe verdadeira) de uma pasta images/ com labels/ ao lado;
    'negativa' se a imagem nao tem caixas."""
    if not pasta.is_dir():
        raise SystemExit(f"pasta de imagens nao encontrada: {pasta}")
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
        previsoes.append({"imagem": img.name, "origem": origem_da_imagem(img.name),
                          "verdade": verdade, "previsto": classe,
                          "confianca": round(confianca, 4), "brilho": brilho(img)})

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

    # acertos por fonte (prefixo do arquivo), no limiar do backend
    por_origem: dict[str, Counter] = defaultdict(Counter)
    for p in previsoes:
        c = por_origem[p["origem"]]
        if p["verdade"] == "negativa":
            c["negativas"] += 1
            c["alarmes"] += p["previsto"] != NENHUMA and p["confianca"] >= args.limiar
        else:
            c["positivas"] += 1
            c["acertos"] += p["previsto"] == p["verdade"]
            c["automaticas"] += p["previsto"] == p["verdade"] and p["confianca"] >= args.limiar

    resumo = {
        "imagens": len(previsoes), "positivas": len(positivas), "negativas": len(negativas),
        "acuracia": round(acertos / len(positivas), 4) if positivas else None,
        "f1_macro": round(macro_f1, 4),
        "por_classe": por_classe,
        "matriz": {v: {p: matriz[v][p] for p in CLASSES + [NENHUMA]} for v in CLASSES},
        "limiar_backend": args.limiar,
        "no_limiar_backend": linha_limiar,
        "por_origem": {o: dict(c) for o, c in sorted(por_origem.items())},
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
    parser.add_argument("--pasta", default=None,
                        help="avaliar uma pasta com images/ e labels/ (ex.: ml/work/teresina) "
                             "em vez de uma particao do dataset")
    parser.add_argument("--nome", default=None)
    args = parser.parse_args()

    pesos = Path(args.pesos)
    if not pesos.is_file():
        raise SystemExit(f"arquivo nao encontrado: {pesos}")
    agora = f"{datetime.now():%Y%m%d_%H%M}"
    if args.pasta:
        pasta = Path(args.pasta).resolve()
        if not (pasta / "images").is_dir():
            raise SystemExit(f"a pasta precisa ter images/ e labels/: {pasta}")
        alvo, particao = pasta.name, "test"
    else:
        dados = Path(args.dados)
        if not dados.is_file():
            raise SystemExit(f"arquivo nao encontrado: {dados}")
        pasta, alvo, particao = dados.parent / args.particao, args.particao, args.particao

    saida = RESULTADOS / (args.nome or f"{pesos.stem}_{alvo}_{agora}")
    saida.mkdir(parents=True, exist_ok=True)
    if args.pasta:
        # data.yaml provisorio com todas as particoes apontando para a pasta
        dados = saida / "dados_pasta.yaml"
        nomes = "\n".join(f"  {i}: {nome}" for i, nome in enumerate(CLASSES))
        dados.write_text(
            f"path: {pasta.as_posix()}\ntrain: images\nval: images\ntest: images\n"
            f"names:\n{nomes}\n",
            encoding="utf-8",
        )

    from ultralytics import YOLO

    modelo = YOLO(str(pesos))

    print(f"avaliando {pesos} em '{alvo}'...")
    deteccao = metricas_deteccao(modelo, dados, particao, args, saida)
    itens = ler_particao(pasta / "images")
    ocorrencia, tabela_limiar, previsoes = metricas_ocorrencia(modelo, itens, args)

    relatorio = {
        "pesos": str(pesos), "avaliado": alvo, "pasta": str(pasta),
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
    print(f"{'DETECCAO (' + alvo + ')':<26}precisao  recall    F1    mAP@50  mAP@50:95")
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

    print(f"\n  {'origem':<22}{'positivas':>10}{'acertos':>9}{'automaticas':>13}"
          f"{'negativas':>11}{'alarmes':>9}")
    for origem, c in ocorrencia["por_origem"].items():
        print(f"  {origem:<22}{c.get('positivas', 0):>10}{c.get('acertos', 0):>9}"
              f"{c.get('automaticas', 0):>13}{c.get('negativas', 0):>11}{c.get('alarmes', 0):>9}")
    print(f"  (automaticas e alarmes com confianca >= {args.limiar:.2f}, o limiar do backend)")

    print(f"\n{'limiar':>8}{'automacao':>11}{'precisao_auto':>15}{'para_triagem':>14}{'alarmes_neg':>13}")
    for t in tabela_limiar:
        marca = "  <- backend" if abs(t["limiar"] - args.limiar) < 1e-9 else ""
        auto = f"{t['automacao']:.3f}" if t["automacao"] is not None else "-"
        prec = f"{t['precisao_automatica']:.3f}" if t["precisao_automatica"] is not None else "-"
        print(f"{t['limiar']:>8.2f}{auto:>11}{prec:>15}{t['para_triagem']:>14}"
              f"{t['alarmes_em_negativas']:>13}{marca}")
    print(f"alarmes_neg: imagens sem defeito (de {ocorrencia['negativas']}) com deteccao acima do limiar")

    print(f"\nresultados gravados em {saida}")


if __name__ == "__main__":
    main()
