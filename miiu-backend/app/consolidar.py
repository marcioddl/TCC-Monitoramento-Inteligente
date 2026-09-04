import csv
import hashlib
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

# ---------------------------------------------------------------- configuracao

RAIZ = Path(__file__).resolve().parent

CLASSE = "calcada_danificada"
INDICE_CLASSE = 1          # esquema final: 0=buraco 1=calcada 2=descarte
LADO_MINIMO = 512

# Cada fonte: (subpasta, proveniencia, licenca, mapa de indices)
#
# O mapa traduz o indice original -> indice final. Use None para descartar
# uma classe que nao pertence ao escopo.
FONTES = [
    (
        "calcada/sidewalk_meliss",
        "roboflow:meliss-workspace-oniq8/damaged-sidewalk",
        "CC BY 4.0",
        # 0 = crack
        {0: INDICE_CLASSE},
    ),
    (
        "calcada/sidewalk_objdet",
        "roboflow:objectdetection-xkyum/sidewalk-gbw7n",
        "CC BY 4.0",
        # 0 = damage-qnnD
        {0: INDICE_CLASSE},
    ),
]

SAIDA = RAIZ.parent / "work" / CLASSE

EXTENSOES = {".jpg", ".jpeg", ".png"}

# ---------------------------------------------------------------------- funcoes


def hash_arquivo(caminho: Path) -> str:
    """SHA-256 do conteudo bruto. Arquivos identicos batem mesmo com nomes
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
    for particao in ("train", "valid", "test"):
        pasta = base / particao / "images"
        if not pasta.is_dir():
            continue
        for img in sorted(pasta.iterdir()):
            if img.suffix.lower() in EXTENSOES:
                yield img


def nome_curto(subpasta: str) -> str:
    """'calcada/sidewalk_meliss' -> 'sidewalk_meliss'"""
    return subpasta.split("/")[-1]


# -------------------------------------------------------------------- execucao


def main() -> None:
    (SAIDA / "images").mkdir(parents=True, exist_ok=True)
    (SAIDA / "labels").mkdir(parents=True, exist_ok=True)

    vistos: dict[str, str] = {}
    stats = defaultdict(Counter)
    resolucoes = Counter()
    classes_originais = defaultdict(Counter)
    linhas_manifesto = []
    instancias = 0

    for subpasta, proveniencia, licenca, mapa in FONTES:
        base = RAIZ / subpasta
        rotulo = nome_curto(subpasta)

        if not base.is_dir():
            print(f"[aviso] pasta nao encontrada, pulando: {subpasta}")
            continue

        for img in listar_imagens(base):
            stats[rotulo]["encontradas"] += 1

            # --- resolucao
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

            # --- duplicata
            h = hash_arquivo(img)
            if h in vistos:
                stats[rotulo]["descartadas_duplicata"] += 1
                continue
            vistos[h] = img.name

            # --- label correspondente
            label = achar_label(img)
            if label is None:
                stats[rotulo]["sem_label"] += 1
                continue

            # --- remapeamento dos indices
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

                destino = mapa[original]
                if destino is None:
                    stats[rotulo]["caixas_descartadas"] += 1
                    continue

                partes[0] = str(destino)
                linhas_saida.append(" ".join(partes))

            novo_nome = f"{rotulo}__{img.name}"
            shutil.copy2(img, SAIDA / "images" / novo_nome)

            instancias += len(linhas_saida)
            destino_label = SAIDA / "labels" / f"{rotulo}__{img.stem}.txt"
            destino_label.write_text(
                "\n".join(linhas_saida) + ("\n" if linhas_saida else "")
            )

            if not linhas_saida:
                stats[rotulo]["negativas"] += 1

            stats[rotulo]["aceitas"] += 1
            linhas_manifesto.append({
                "arquivo": novo_nome,
                "origem": rotulo,
                "proveniencia": proveniencia,
                "licenca": licenca,
                "largura": largura,
                "altura": altura,
                "caixas": len(linhas_saida),
                "sha256": h,
            })

    # --- manifesto
    manifesto = SAIDA / "manifesto.csv"
    with open(manifesto, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=[
            "arquivo", "origem", "proveniencia", "licenca",
            "largura", "altura", "caixas", "sha256",
        ])
        escritor.writeheader()
        escritor.writerows(linhas_manifesto)

    # --- relatorio
    print("\n" + "=" * 62)
    print(f"CONSOLIDACAO DA CLASSE: {CLASSE}  (indice final {INDICE_CLASSE})")
    print("=" * 62)

    for subpasta, _, _, _ in FONTES:
        rotulo = nome_curto(subpasta)
        c = stats[rotulo]
        if not c:
            continue
        print(f"\n{rotulo}")
        print(f"  encontradas               {c['encontradas']:>6}")
        print(f"  descartadas resolucao     {c['descartadas_resolucao']:>6}")
        print(f"  descartadas duplicata     {c['descartadas_duplicata']:>6}")
        print(f"  sem label                 {c['sem_label']:>6}")
        print(f"  ilegiveis                 {c['ilegiveis']:>6}")
        print(f"  ACEITAS                   {c['aceitas']:>6}")
        print(f"    (destas, negativas)     {c['negativas']:>6}")
        print(f"  caixas descartadas (mapa) {c['caixas_descartadas']:>6}")
        print(f"  caixas indice desconhec.  {c['caixas_indice_desconhecido']:>6}")
        if classes_originais[rotulo]:
            distrib = ", ".join(
                f"{k}:{v}" for k, v in sorted(classes_originais[rotulo].items())
            )
            print(f"  indices originais vistos  {distrib}")

    total = sum(stats[nome_curto(s)]["aceitas"] for s, _, _, _ in FONTES)
    print("\n" + "-" * 62)
    print(f"TOTAL DE IMAGENS ACEITAS   {total:>6}")
    print(f"TOTAL DE INSTANCIAS        {instancias:>6}")
    if total:
        print(f"MEDIA DE CAIXAS POR IMAGEM {instancias / total:>9.2f}")

    print("\nresolucoes mais comuns encontradas:")
    for res, n in resolucoes.most_common(8):
        print(f"  {res:>12}  {n}")

    print(f"\nsaida:      {SAIDA}")
    print(f"manifesto:  {manifesto}")


if __name__ == "__main__":
    main()