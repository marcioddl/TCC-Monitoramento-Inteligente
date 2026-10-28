"""Consolida as fontes brutas (ml/raw) em ml/work/<destino>.

Generaliza o script de consolidacao usado na construcao do dataset publico:
mesmas regras (resolucao minima, deduplicacao por SHA-256, remapeamento de
indices, prefixo de proveniencia e manifesto.csv), agora para qualquer
classe e para as fotos proprias capturadas em Teresina.

Uso (a partir da pasta miiu/):

    python ml/scripts/consolidar.py buraco
    python ml/scripts/consolidar.py calcada_danificada
    python ml/scripts/consolidar.py proprias

Fotos proprias: rotule no Roboflow com as classes "buraco" e
"calcada_danificada", exporte no formato YOLOv8 e descompacte em
ml/raw/proprias/. O mapeamento e feito pelo NOME da classe lido do
data.yaml, entao a ordem das classes no Roboflow nao importa.
"""

import argparse
import csv
import hashlib
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

from comum import CLASSES, EXTENSOES, INDICE, RAW, WORK, normalizar_nome

LADO_MINIMO = 512

# destino -> lista de (subpasta em ml/raw, proveniencia, licenca, mapa de indices)
# Mapa None = ler os nomes do data.yaml e mapear pelo nome.
FONTES = {
    "buraco": [
        ("buraco/pothole_yeeun", "roboflow:yeeun-kim-fyvoj/pothole-vhmow", "CC BY 4.0",
         {0: INDICE["buraco"]}),
        ("buraco/pothole_umat", "roboflow:umat/pothole-abpqz", "CC BY 4.0",
         {0: INDICE["buraco"]}),
        # pothole_bradwyer fica de fora: licenca ODbL v1.0 (decisao de escopo)
    ],
    "calcada_danificada": [
        ("calcada/sidewalk_meliss", "roboflow:meliss-workspace-oniq8/damaged-sidewalk",
         "CC BY 4.0", {0: INDICE["calcada_danificada"]}),
        ("calcada/sidewalk_objdet", "roboflow:objectdetection-xkyum/sidewalk-gbw7n",
         "CC BY 4.0", {0: INDICE["calcada_danificada"]}),
    ],
    "proprias": [
        ("proprias", "captura propria (Teresina-PI)", "propria", None),
    ],
}


def hash_arquivo(caminho: Path) -> str:
    """SHA-256 do conteudo bruto: arquivos identicos batem mesmo com nomes
    diferentes, que e o caso de datasets forkados."""
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def achar_label(img: Path) -> Path | None:
    """O label fica em ../labels/ com o mesmo nome-base e extensao .txt."""
    candidato = img.parent.parent / "labels" / (img.stem + ".txt")
    return candidato if candidato.exists() else None


def listar_imagens(base: Path):
    """Aceita a estrutura do Roboflow (train|valid|test/images) e a plana (images/)."""
    pastas = [base / p / "images" for p in ("train", "valid", "test")] + [base / "images"]
    for pasta in pastas:
        if pasta.is_dir():
            for img in sorted(pasta.iterdir()):
                if img.suffix.lower() in EXTENSOES:
                    yield img


def mapa_pelos_nomes(base: Path) -> dict[int, int | None]:
    """Le 'names' do data.yaml e traduz para os indices do sistema."""
    yaml = base / "data.yaml"
    if not yaml.is_file():
        raise SystemExit(f"data.yaml nao encontrado em {base}")
    texto = yaml.read_text(encoding="utf-8")

    nomes: list[str] = []
    lista = re.search(r"^names:\s*\[(.*?)\]", texto, re.MULTILINE | re.DOTALL)
    if lista:  # names: ['buraco', 'calcada_danificada']
        nomes = [n.strip().strip("'\"") for n in lista.group(1).split(",") if n.strip()]
    else:      # names:\n- buraco\n- calcada   ou   names:\n  0: buraco
        bloco = re.search(r"^names:\s*\n((?:\s+.*\n?)+)", texto, re.MULTILINE)
        for linha in (bloco.group(1).splitlines() if bloco else []):
            linha = linha.strip()
            if linha.startswith("- "):
                nomes.append(linha[2:].strip().strip("'\""))
            elif ":" in linha:
                nomes.append(linha.split(":", 1)[1].strip().strip("'\""))

    mapa = {i: INDICE.get(normalizar_nome(n)) for i, n in enumerate(nomes)}
    print(f"classes do data.yaml: {dict(enumerate(nomes))}")
    print(f"mapeamento para o sistema: {mapa}  (None = descartada)")
    return mapa


def nome_curto(subpasta: str) -> str:
    """'calcada/sidewalk_meliss' -> 'sidewalk_meliss'"""
    return subpasta.split("/")[-1]


def consolidar(destino: str) -> None:
    fontes = FONTES[destino]
    if not any((RAW / sub).is_dir() for sub, *_ in fontes):
        raise SystemExit(f"nenhuma fonte de '{destino}' encontrada em {RAW}; nada foi alterado")

    saida = WORK / destino
    if saida.exists():
        shutil.rmtree(saida)
    (saida / "images").mkdir(parents=True)
    (saida / "labels").mkdir(parents=True)

    vistos: dict[str, str] = {}
    stats = defaultdict(Counter)
    resolucoes = Counter()
    classes_originais = defaultdict(Counter)
    caixas_por_classe = Counter()
    linhas_manifesto = []

    for subpasta, proveniencia, licenca, mapa in fontes:
        base = RAW / subpasta
        rotulo = nome_curto(subpasta)

        if not base.is_dir():
            print(f"[aviso] pasta nao encontrada, pulando: {base}")
            continue
        if mapa is None:
            mapa = mapa_pelos_nomes(base)

        for img in listar_imagens(base):
            stats[rotulo]["encontradas"] += 1

            try:
                with Image.open(img) as im:
                    largura, altura = im.size
            except Exception:
                stats[rotulo]["ilegiveis"] += 1
                continue
            resolucoes[f"{largura}x{altura}"] += 1

            if min(largura, altura) < LADO_MINIMO:
                stats[rotulo]["descartadas_resolucao"] += 1
                continue

            h = hash_arquivo(img)
            if h in vistos:
                stats[rotulo]["descartadas_duplicata"] += 1
                continue
            vistos[h] = img.name

            label = achar_label(img)
            if label is None:
                stats[rotulo]["sem_label"] += 1
                continue

            linhas_saida = []
            for linha in label.read_text().splitlines():
                partes = linha.split()
                if len(partes) < 5:
                    continue
                try:
                    original = int(partes[0])
                except ValueError:
                    continue
                classes_originais[rotulo][original] += 1
                if original not in mapa:
                    stats[rotulo]["caixas_indice_desconhecido"] += 1
                    continue
                if mapa[original] is None:
                    stats[rotulo]["caixas_descartadas"] += 1
                    continue
                partes[0] = str(mapa[original])
                caixas_por_classe[CLASSES[mapa[original]]] += 1
                linhas_saida.append(" ".join(partes))

            novo_nome = f"{rotulo}__{img.name}"
            shutil.copy2(img, saida / "images" / novo_nome)
            (saida / "labels" / f"{rotulo}__{img.stem}.txt").write_text(
                "\n".join(linhas_saida) + ("\n" if linhas_saida else "")
            )

            if not linhas_saida:
                stats[rotulo]["negativas"] += 1
            stats[rotulo]["aceitas"] += 1
            linhas_manifesto.append({
                "arquivo": novo_nome, "origem": rotulo, "proveniencia": proveniencia,
                "licenca": licenca, "largura": largura, "altura": altura,
                "caixas": len(linhas_saida), "sha256": h,
            })

    manifesto = saida / "manifesto.csv"
    with open(manifesto, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=[
            "arquivo", "origem", "proveniencia", "licenca",
            "largura", "altura", "caixas", "sha256",
        ])
        escritor.writeheader()
        escritor.writerows(linhas_manifesto)

    print("\n" + "=" * 62)
    print(f"CONSOLIDACAO: {destino}")
    print("=" * 62)
    for subpasta, *_ in fontes:
        c = stats[nome_curto(subpasta)]
        if not c:
            continue
        print(f"\n{nome_curto(subpasta)}")
        for chave in ("encontradas", "descartadas_resolucao", "descartadas_duplicata",
                      "sem_label", "ilegiveis", "aceitas", "negativas",
                      "caixas_descartadas", "caixas_indice_desconhecido"):
            print(f"  {chave.replace('_', ' '):<28}{c[chave]:>6}")

    total = len(linhas_manifesto)
    instancias = sum(caixas_por_classe.values())
    print("\n" + "-" * 62)
    print(f"TOTAL DE IMAGENS ACEITAS   {total:>6}")
    print(f"TOTAL DE INSTANCIAS        {instancias:>6}  {dict(caixas_por_classe)}")
    if total:
        print(f"MEDIA DE CAIXAS POR IMAGEM {instancias / total:>9.2f}")
    print("\nresolucoes mais comuns:")
    for res, n in resolucoes.most_common(8):
        print(f"  {res:>12}  {n}")
    print(f"\nsaida:      {saida}")
    print(f"manifesto:  {manifesto}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("destino", choices=sorted(FONTES))
    consolidar(parser.parse_args().destino)
