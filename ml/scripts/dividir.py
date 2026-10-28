"""Divide o dataset consolidado em treino, validacao e teste (70/20/10)
sem vazamento de dados.

O problema: o Roboflow exporta varias versoes aumentadas da mesma foto, por
exemplo images155_jpg.rf.bbc5....jpg e images155_jpg.rf.eed5....jpg. Se uma
vai para o treino e a outra para o teste, o modelo e avaliado numa foto que
ja viu, e as metricas ficam infladas. No dataset do MIIU sao cerca de quatro
versoes por foto original.

Regras aplicadas:

1. A unidade da divisao e o GRUPO (a foto original), nunca o arquivo.
2. Estratificacao por (classe predominante do grupo, origem): cada fonte
   contribui com 70/20/10 dos seus grupos, inclusive as fotos proprias.
3. Em validacao e teste fica UMA imagem por grupo: as demais versoes
   aumentadas sao redundantes e distorceriam o tamanho real da amostra
   (desligue com --manter-aumentos).
4. Verificacao final: nenhum grupo e nenhum SHA-256 aparece em mais de uma
   particao.
5. Rotulos so no formato de deteccao (classe x y largura altura). Algumas
   fontes do Roboflow trazem poligonos de segmentacao, as vezes misturados
   com caixas no mesmo arquivo, e o YOLO descarta esses arquivos mistos.
   Cada poligono e convertido na caixa que o envolve.

Uso (a partir da pasta miiu/):

    python ml/scripts/dividir.py

Le todas as pastas de ml/work/ e grava ml/dataset/ (apagado e recriado),
com data.yaml, divisao.csv e resumo.txt.
"""

import argparse
import csv
import hashlib
import random
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from comum import CLASSES, DATASET, EXTENSOES, SEMENTE, WORK, grupo_da_imagem, ler_rotulos

PARTICOES = ("train", "val", "test")
PROPORCOES = {"train": 0.70, "val": 0.20, "test": 0.10}


@dataclass
class Imagem:
    caminho: Path
    rotulo: Path
    origem: str
    sha256: str
    caixas: list[int]


@dataclass
class Grupo:
    chave: str
    origem: str
    imagens: list[Imagem] = field(default_factory=list)

    @property
    def classe(self) -> str:
        """Classe predominante entre as caixas do grupo, ou 'negativa'."""
        contagem = Counter(i for img in self.imagens for i in img.caixas)
        if not contagem:
            return "negativa"
        return CLASSES[contagem.most_common(1)[0][0]]


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def carregar_grupos() -> list[Grupo]:
    grupos: dict[str, Grupo] = {}
    pastas = sorted(p for p in WORK.iterdir() if (p / "images").is_dir())
    if not pastas:
        raise SystemExit(f"nenhuma pasta consolidada em {WORK}; rode consolidar.py antes")

    for pasta in pastas:
        manifesto = {}
        if (pasta / "manifesto.csv").is_file():
            with open(pasta / "manifesto.csv", encoding="utf-8") as f:
                manifesto = {linha["arquivo"]: linha for linha in csv.DictReader(f)}

        for img in sorted((pasta / "images").iterdir()):
            if img.suffix.lower() not in EXTENSOES:
                continue
            info = manifesto.get(img.name, {})
            origem = info.get("origem") or img.name.split("__")[0]
            rotulo = pasta / "labels" / f"{img.stem}.txt"
            chave = f"{pasta.name}/{grupo_da_imagem(img.name)}"
            grupo = grupos.setdefault(chave, Grupo(chave, origem))
            grupo.imagens.append(Imagem(
                caminho=img, rotulo=rotulo, origem=origem,
                sha256=info.get("sha256") or sha256(img),
                caixas=ler_rotulos(rotulo),
            ))
        print(f"lida: {pasta.name:<22} {sum(1 for _ in (pasta / 'images').iterdir()):>5} imagens")
    return list(grupos.values())


def sortear_particoes(grupos: list[Grupo], semente: int) -> dict[str, str]:
    """Distribui os grupos de cada estrato (classe, origem) em 70/20/10."""
    estratos: dict[tuple[str, str], list[Grupo]] = defaultdict(list)
    for g in grupos:
        estratos[(g.classe, g.origem)].append(g)

    destino: dict[str, str] = {}
    sorteio = random.Random(semente)
    for chave in sorted(estratos):
        membros = sorted(estratos[chave], key=lambda g: g.chave)
        sorteio.shuffle(membros)
        n = len(membros)
        n_teste = round(n * PROPORCOES["test"]) if n >= 3 else 0
        n_val = round(n * PROPORCOES["val"]) if n >= 3 else 0
        if n >= 3:
            n_teste, n_val = max(n_teste, 1), max(n_val, 1)
        for i, g in enumerate(membros):
            if i < n_teste:
                destino[g.chave] = "test"
            elif i < n_teste + n_val:
                destino[g.chave] = "val"
            else:
                destino[g.chave] = "train"
    return destino


def normalizar_rotulo(caminho: Path) -> tuple[str, int, bool]:
    """Devolve o rotulo so com caixas, quantos poligonos foram convertidos e
    se o arquivo original misturava poligonos e caixas."""
    linhas, convertidos, caixas_originais = [], 0, 0
    for linha in caminho.read_text().splitlines():
        partes = linha.split()
        if len(partes) == 5:
            linhas.append(" ".join(partes))
            caixas_originais += 1
            continue
        coords = partes[1:]
        if len(partes) < 7 or len(coords) % 2:
            continue  # linha malformada
        try:
            xs = [min(max(float(v), 0.0), 1.0) for v in coords[0::2]]
            ys = [min(max(float(v), 0.0), 1.0) for v in coords[1::2]]
        except ValueError:
            continue
        largura, altura = max(xs) - min(xs), max(ys) - min(ys)
        if largura <= 0 or altura <= 0:
            continue
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        linhas.append(f"{partes[0]} {cx:.6f} {cy:.6f} {largura:.6f} {altura:.6f}")
        convertidos += 1
    texto = "\n".join(linhas) + ("\n" if linhas else "")
    return texto, convertidos, bool(convertidos and caixas_originais)


def main() -> None:
    parser = argparse.ArgumentParser(description="Divisao 70/20/10 sem vazamento")
    parser.add_argument("--semente", type=int, default=SEMENTE)
    parser.add_argument("--manter-aumentos", action="store_true",
                        help="manter todas as versoes aumentadas tambem em val e test")
    args = parser.parse_args()

    grupos = carregar_grupos()
    destino = sortear_particoes(grupos, args.semente)

    if DATASET.exists():
        shutil.rmtree(DATASET)
    for p in PARTICOES:
        (DATASET / p / "images").mkdir(parents=True)
        (DATASET / p / "labels").mkdir(parents=True)

    linhas = []
    descartadas = Counter()
    poligonos = Counter()  # linhas convertidas e arquivos que misturavam formatos
    sha_por_particao: dict[str, str] = {}
    resumo = {p: {"imagens": 0, "grupos": 0, "negativas": 0,
                  "instancias": Counter(), "origens": Counter(), "classes": Counter()}
              for p in PARTICOES}

    for g in sorted(grupos, key=lambda g: g.chave):
        particao = destino[g.chave]
        imagens = sorted(g.imagens, key=lambda i: i.caminho.name)
        if particao != "train" and not args.manter_aumentos:
            descartadas[particao] += len(imagens) - 1
            imagens = imagens[:1]

        r = resumo[particao]
        r["grupos"] += 1
        r["classes"][g.classe] += 1
        for img in imagens:
            anterior = sha_por_particao.setdefault(img.sha256, particao)
            if anterior != particao:
                raise SystemExit(f"VAZAMENTO: {img.caminho.name} em {anterior} e {particao}")

            shutil.copy2(img.caminho, DATASET / particao / "images" / img.caminho.name)
            if img.rotulo.is_file():
                texto, convertidos, misturava = normalizar_rotulo(img.rotulo)
                (DATASET / particao / "labels" / img.rotulo.name).write_text(texto)
                poligonos["linhas"] += convertidos
                poligonos["arquivos"] += bool(convertidos)
                poligonos["mistos"] += misturava
            else:
                (DATASET / particao / "labels" / f"{img.caminho.stem}.txt").write_text("")

            r["imagens"] += 1
            r["origens"][img.origem] += 1
            r["negativas"] += not img.caixas
            for i in img.caixas:
                r["instancias"][CLASSES[i]] += 1
            linhas.append({
                "arquivo": img.caminho.name, "particao": particao, "grupo": g.chave,
                "classe_grupo": g.classe, "origem": img.origem,
                "caixas": len(img.caixas), "sha256": img.sha256,
            })

    with open(DATASET / "divisao.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)

    nomes = "\n".join(f"  {i}: {nome}" for i, nome in enumerate(CLASSES))
    (DATASET / "data.yaml").write_text(
        f"# Gerado por ml/scripts/dividir.py (semente {args.semente})\n"
        f"path: {DATASET.as_posix()}\n"
        "train: train/images\nval: val/images\ntest: test/images\n"
        f"names:\n{nomes}\n",
        encoding="utf-8",
    )

    total_grupos = len(grupos)
    total_imagens = sum(len(g.imagens) for g in grupos)
    saida = [
        "=" * 66,
        "DIVISAO DO DATASET (por grupo de foto original, sem vazamento)",
        "=" * 66,
        f"imagens consolidadas: {total_imagens}   fotos originais (grupos): {total_grupos}"
        f"   media de versoes por foto: {total_imagens / max(total_grupos, 1):.2f}",
        "",
        f"{'particao':<8}{'grupos':>8}{'imagens':>9}{'negativas':>11}"
        + "".join(f"{c[:14]:>16}" for c in CLASSES),
    ]
    for p in PARTICOES:
        r = resumo[p]
        saida.append(
            f"{p:<8}{r['grupos']:>8}{r['imagens']:>9}{r['negativas']:>11}"
            + "".join(f"{r['instancias'][c]:>16}" for c in CLASSES)
        )
    saida.append("\n(colunas das classes = numero de caixas/instancias)")
    saida.append("\ngrupos por classe predominante:")
    for p in PARTICOES:
        saida.append(f"  {p:<6} {dict(sorted(resumo[p]['classes'].items()))}")
    saida.append("\nimagens por origem:")
    for p in PARTICOES:
        saida.append(f"  {p:<6} {dict(sorted(resumo[p]['origens'].items()))}")
    if descartadas:
        saida.append(
            f"\nversoes aumentadas fora da avaliacao: val {descartadas['val']}, "
            f"test {descartadas['test']} (use --manter-aumentos para incluir)"
        )
    if poligonos["linhas"]:
        saida.append(
            f"\npoligonos convertidos em caixas: {poligonos['linhas']} linhas em "
            f"{poligonos['arquivos']} arquivos ({poligonos['mistos']} misturavam poligono e caixa)"
        )
    saida.append("\nverificacao: nenhum grupo e nenhum SHA-256 em mais de uma particao. OK")
    saida.append(f"\ndata.yaml: {DATASET / 'data.yaml'}")

    texto = "\n".join(saida)
    (DATASET / "resumo.txt").write_text(texto + "\n", encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
