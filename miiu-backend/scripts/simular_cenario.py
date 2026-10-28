"""Simulacao de cenario de uso para avaliar o geofencing de ponta a ponta.

Executa contra a API em funcionamento, pelos mesmos endpoints usados pelo
aplicativo e pelo painel (objetivo especifico 4 da monografia):

1. Cidadaos diferentes reportam ocorrencias posicionadas a distancias
   conhecidas de um trajeto de pedestre (0 a 200 m da rota).
2. O gestor valida a maioria pelo painel; uma e resolvida, uma fica na
   triagem e uma foi reportada pelo proprio pedestre (casos que NAO devem
   alertar).
3. Um pedestre percorre o trajeto enviando a posicao a cada --passo metros.
4. O trajeto e repetido para verificar que nenhum alerta chega duas vezes.

Como a posicao de cada ocorrencia e conhecida, sabe-se de antemao quais
deveriam alertar (distancia ate a rota <= raio da geocerca). O relatorio
compara esperado x recebido (precisao e recall do mecanismo), a distancia no
momento do disparo e a latencia de cada verificacao.

Uso (com a API no ar):

    python scripts/simular_cenario.py --senha SUA_ADMIN_SENHA
    python scripts/simular_cenario.py --senha ... --imagens ../ml/dataset/test/images

Os registros criados levam "[SIMULACAO]" na descricao. Resultados em
resultados_simulacao/<data_hora>/ (CSV e JSON).
"""

import argparse
import csv
import io
import json
import math
import random
import statistics
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

# Centro de Teresina (Praca da Liberdade), ponto de partida do trajeto
LAT0, LON0 = -5.0892, -42.8016


def metros_por_grau(lat: float) -> tuple[float, float]:
    """Comprimento de 1 grau de latitude e de longitude no WGS 84."""
    phi = math.radians(lat)
    m_lat = 111132.954 - 559.822 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
    m_lon = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi) + 0.118 * math.cos(5 * phi)
    return m_lat, m_lon


def deslocar(lat: float, lon: float, leste_m: float, norte_m: float) -> tuple[float, float]:
    m_lat, m_lon = metros_por_grau(lat)
    return lat + norte_m / m_lat, lon + leste_m / m_lon


@dataclass
class Caso:
    nome: str
    ao_longo_m: float     # posicao ao longo da rota (leste)
    afastamento_m: float  # distancia perpendicular a rota (norte)
    estado: str           # validada | resolvida | triagem | autor
    classe: str
    protocolo: str = ""
    esperado: bool = False
    recebido: bool = False
    distancia_disparo_m: float | None = None
    passo_disparo: int | None = None
    alertas_repetidos: int = 0


def cenario(comprimento_m: float, raio_m: float) -> list[Caso]:
    afastamentos = [0, 25, 50, 75, 95, 105, 130, 200]
    casos = [
        Caso(f"afastada_{a}m", 150 + i * (comprimento_m - 300) / len(afastamentos), a,
             "validada", "buraco" if i % 2 == 0 else "calcada_danificada")
        for i, a in enumerate(afastamentos)
    ]
    casos += [
        Caso("resolvida_10m", comprimento_m * 0.30, 10, "resolvida", "buraco"),
        Caso("em_triagem_10m", comprimento_m * 0.55, 10, "triagem", "buraco"),
        Caso("do_proprio_pedestre_10m", comprimento_m * 0.80, 10, "autor", "calcada_danificada"),
    ]
    for c in casos:
        c.esperado = c.estado == "validada" and c.afastamento_m <= raio_m
    return casos


class Fotos:
    """Fornece fotos para os reportes: de uma pasta, ou sinteticas."""

    def __init__(self, pasta: str | None):
        self.arquivos = sorted(
            p for p in Path(pasta).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ) if pasta else []
        self.i = 0

    def proxima(self, rotulo: str) -> bytes:
        if self.arquivos:
            arquivo = self.arquivos[self.i % len(self.arquivos)]
            self.i += 1
            return arquivo.read_bytes()
        imagem = Image.new("RGB", (800, 600), (110, 110, 110))
        desenho = ImageDraw.Draw(imagem)
        desenho.ellipse((250, 200, 550, 420), fill=(40, 40, 40))
        desenho.text((20, 20), f"MIIU simulacao: {rotulo}", fill=(255, 255, 255))
        buffer = io.BytesIO()
        imagem.save(buffer, "JPEG")
        return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulacao de cenario de geofencing")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--senha", required=True, help="ADMIN_SENHA do .env do backend")
    parser.add_argument("--imagens", default=None, help="pasta com fotos (padrao: sinteticas)")
    parser.add_argument("--comprimento", type=float, default=1500, help="tamanho do trajeto (m)")
    parser.add_argument("--passo", type=float, default=10, help="distancia entre leituras (m)")
    parser.add_argument("--ruido-gps", type=float, default=0.0,
                        help="desvio padrao (m) de erro aleatorio somado a cada leitura")
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument("--saida", default="resultados_simulacao")
    args = parser.parse_args()

    sorteio = random.Random(args.semente)
    api = httpx.Client(base_url=args.api, timeout=60)

    saude = api.get("/health").json()
    if saude.get("status") != "ok":
        raise SystemExit(f"API nao esta pronta: {saude}")
    raio = float(saude.get("geocerca_raio_padrao_m", 100))
    print(f"API ok | modelo: {saude['modelo']['versao']} | push: {saude['notificacoes']} | raio: {raio:.0f} m")

    r = api.post("/admin/login", json={"senha": args.senha})
    if r.status_code != 200:
        raise SystemExit("senha do painel incorreta")
    gestor = {"Authorization": f"Bearer {r.json()['token']}"}

    pedestre = str(uuid.uuid4())
    casos = cenario(args.comprimento, raio)
    fotos = Fotos(args.imagens)

    # ---------------------------------------------------------- reportes
    print(f"\nreportando {len(casos)} ocorrencias...")
    for c in casos:
        lat, lon = deslocar(LAT0, LON0, c.ao_longo_m, c.afastamento_m)
        autor = pedestre if c.estado == "autor" else str(uuid.uuid4())
        r = api.post("/ocorrencias", data={
            "latitude": f"{lat:.7f}", "longitude": f"{lon:.7f}",
            "classe_informada": c.classe, "device_id": autor,
            "descricao": f"[SIMULACAO] {c.nome}", "precisao_m": "6",
        }, files={"imagem": ("foto.jpg", fotos.proxima(c.nome), "image/jpeg")})
        r.raise_for_status()
        c.protocolo = r.json()["protocolo"]

        busca = api.get("/admin/ocorrencias", params={"busca": c.protocolo}, headers=gestor).json()
        oid = busca["itens"][0]["id"]
        roteiro = {
            "validada": ["validada"],
            "autor": ["validada"],
            "resolvida": ["validada", "em_atendimento", "resolvida"],
            "triagem": [],
        }[c.estado]
        for proximo in roteiro:
            api.patch(f"/admin/ocorrencias/{oid}/status", headers=gestor, json={
                "status": proximo, "classe_validada": c.classe,
                "observacao": "simulacao de cenario",
            }).raise_for_status()
        if c.estado == "triagem":
            atual = api.get(f"/admin/ocorrencias/{oid}", headers=gestor).json()["status"]
            if atual == "classificada":
                api.patch(f"/admin/ocorrencias/{oid}/status", headers=gestor,
                          json={"status": "em_triagem"}).raise_for_status()
        print(f"  {c.protocolo}  {c.nome:<26} {c.estado}")

    api.put(f"/dispositivos/{pedestre}", json={"notificacoes_habilitadas": True}).raise_for_status()

    # ---------------------------------------------------------- caminhadas
    passos = int(args.comprimento // args.passo) + 1
    por_protocolo = {c.protocolo: c for c in casos}
    latencias = []
    registro_alertas = []

    for volta in (1, 2):
        print(f"\nvolta {volta}: {passos} leituras de GPS a cada {args.passo:.0f} m...")
        for i in range(passos):
            ruido_l = sorteio.gauss(0, args.ruido_gps) if args.ruido_gps else 0.0
            ruido_n = sorteio.gauss(0, args.ruido_gps) if args.ruido_gps else 0.0
            lat, lon = deslocar(LAT0, LON0, i * args.passo + ruido_l, ruido_n)
            inicio = time.perf_counter()
            resposta = api.post("/geofence/checar", json={
                "device_id": pedestre, "latitude": lat, "longitude": lon,
                "precisao_m": round(sorteio.uniform(4, 15), 1),
            })
            latencias.append((time.perf_counter() - inicio) * 1000)
            resposta.raise_for_status()
            for a in resposta.json()["alertas"]:
                c = por_protocolo.get(a["protocolo"])
                registro_alertas.append({
                    "volta": volta, "passo": i, "posicao_m": round(i * args.passo, 1),
                    "protocolo": a["protocolo"], "caso": c.nome if c else "(fora do cenario)",
                    "distancia_m": a["distancia_m"], "canal": a["canal"], "mensagem": a["mensagem"],
                })
                if c is None:
                    continue
                if volta == 1 and not c.recebido:
                    c.recebido = True
                    c.distancia_disparo_m = a["distancia_m"]
                    c.passo_disparo = i
                else:
                    c.alertas_repetidos += 1

    # ---------------------------------------------------------- avaliacao
    vp = sum(c.esperado and c.recebido for c in casos)
    fp = sum(not c.esperado and c.recebido for c in casos)
    fn = sum(c.esperado and not c.recebido for c in casos)
    vn = sum(not c.esperado and not c.recebido for c in casos)
    precisao = vp / (vp + fp) if vp + fp else None
    recall = vp / (vp + fn) if vp + fn else None
    repetidos = sum(c.alertas_repetidos for c in casos)
    disparos = [c.distancia_disparo_m for c in casos if c.distancia_disparo_m is not None]
    lat_ordenadas = sorted(latencias)

    resumo = {
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "api": args.api, "modelo": saude["modelo"]["versao"], "push": saude["notificacoes"],
        "raio_m": raio, "comprimento_m": args.comprimento, "passo_m": args.passo,
        "ruido_gps_m": args.ruido_gps, "leituras": len(latencias),
        "ocorrencias": len(casos), "esperadas": vp + fn,
        "verdadeiros_positivos": vp, "falsos_positivos": fp,
        "falsos_negativos": fn, "verdadeiros_negativos": vn,
        "precisao": precisao, "recall": recall, "alertas_repetidos": repetidos,
        "distancia_disparo_m": {
            "min": min(disparos) if disparos else None,
            "media": round(statistics.mean(disparos), 1) if disparos else None,
            "max": max(disparos) if disparos else None,
        },
        "latencia_ms": {
            "media": round(statistics.mean(latencias), 1),
            "mediana": round(statistics.median(latencias), 1),
            "p95": round(lat_ordenadas[int(0.95 * (len(lat_ordenadas) - 1))], 1),
            "max": round(max(latencias), 1),
        },
    }

    pasta = Path(args.saida) / datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(pasta / "ocorrencias.csv", "w", newline="", encoding="utf-8") as f:
        campos = list(asdict(casos[0]))
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(asdict(c) for c in casos)
    if registro_alertas:
        with open(pasta / "alertas.csv", "w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=list(registro_alertas[0]))
            escritor.writeheader()
            escritor.writerows(registro_alertas)
    with open(pasta / "latencias.csv", "w", newline="", encoding="utf-8") as f:
        f.write("leitura;latencia_ms\n")
        f.writelines(f"{i};{v:.2f}\n" for i, v in enumerate(latencias))

    print("\n" + "=" * 78)
    print(f"{'caso':<26}{'estado':<11}{'dist. rota':>11}{'esperado':>10}{'recebido':>10}{'disparo':>10}")
    print("=" * 78)
    for c in casos:
        disparo = f"{c.distancia_disparo_m:.1f} m" if c.distancia_disparo_m is not None else "-"
        print(f"{c.nome:<26}{c.estado:<11}{c.afastamento_m:>9.0f} m"
              f"{'sim' if c.esperado else 'nao':>10}{'sim' if c.recebido else 'nao':>10}{disparo:>10}")
    print("-" * 78)
    print(f"VP={vp}  FP={fp}  FN={fn}  VN={vn}   precisao={precisao}  recall={recall}")
    print(f"alertas repetidos na 2a volta (deduplicacao): {repetidos}")
    print(f"distancia no disparo: {resumo['distancia_disparo_m']}")
    print(f"latencia da verificacao (ms): {resumo['latencia_ms']}  em {len(latencias)} leituras")
    print(f"\nresultados em {pasta.resolve()}")


if __name__ == "__main__":
    main()
