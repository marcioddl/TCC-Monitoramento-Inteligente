"""Classificacao automatica das fotografias com o modelo YOLOv8 treinado.

O modelo e um detector: devolve caixas, cada uma com classe e confianca. A
ocorrencia recebe a classe da caixa de maior confianca, e essa confianca
decide se ela segue direto para o gestor ou passa antes pela triagem humana
(limiar INFERENCIA_LIMIAR).

Se o arquivo do modelo nao existir ou a biblioteca ultralytics nao estiver
instalada, a API continua funcionando: o classificador fica indisponivel e
toda ocorrencia vai para triagem humana. Isso permite desenvolver e testar o
restante do sistema antes de o treinamento terminar.
"""

import hashlib
import logging
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image

from app.enums import ClasseOcorrencia

log = logging.getLogger("miiu.classificador")


@dataclass
class Deteccao:
    classe: str
    confianca: float
    caixa: list[float]  # x1, y1, x2, y2 normalizados entre 0 e 1


@dataclass
class ResultadoClassificacao:
    classe: ClasseOcorrencia | None   # None quando nada foi detectado
    confianca: float
    deteccoes: list[Deteccao] = field(default_factory=list)
    modelo_versao: str = ""
    tempo_ms: float = 0.0

    def deteccoes_json(self) -> list[dict]:
        return [asdict(d) for d in self.deteccoes]


class Classificador:
    """Interface comum. A implementacao nula responde None (sem modelo)."""

    disponivel: bool = False
    versao: str = "indisponivel"
    motivo: str = ""

    def classificar(self, imagem: Image.Image) -> ResultadoClassificacao | None:
        return None


class ClassificadorIndisponivel(Classificador):
    def __init__(self, motivo: str):
        self.motivo = motivo


class ClassificadorYOLO(Classificador):
    disponivel = True

    def __init__(self, caminho: Path, imgsz: int = 640, conf_min: float = 0.10):
        from ultralytics import YOLO  # importado aqui: dependencia pesada

        self.modelo = YOLO(str(caminho))
        self.imgsz = imgsz
        self.conf_min = conf_min
        self.versao = f"{caminho.stem}@{_hash_curto(caminho)}"
        # A inferencia do ultralytics nao e garantidamente segura entre
        # threads, e o FastAPI atende requisicoes em paralelo
        self._trava = threading.Lock()

        # Mapeia o indice do modelo para a classe do sistema pelo nome,
        # o que torna o backend imune a uma eventual troca de ordem no
        # data.yaml do treinamento
        nomes = self.modelo.names  # {0: 'buraco', 1: 'calcada_danificada'}
        validos = {c.value for c in ClasseOcorrencia}
        self.indice_para_classe = {
            int(i): ClasseOcorrencia(nome) for i, nome in nomes.items() if nome in validos
        }
        ignoradas = sorted(set(nomes.values()) - validos)
        if ignoradas:
            log.warning("classes do modelo sem correspondencia no sistema: %s", ignoradas)

        # Aquecimento: a primeira inferencia inicializa o backend do PyTorch e
        # e bem mais lenta; fazer isso agora tira esse custo do primeiro cidadao
        self.modelo.predict(Image.new("RGB", (imgsz, imgsz)), imgsz=imgsz, verbose=False)

    def classificar(self, imagem: Image.Image) -> ResultadoClassificacao:
        with self._trava:
            resultado = self.modelo.predict(
                imagem, imgsz=self.imgsz, conf=self.conf_min, verbose=False
            )[0]

        deteccoes = []
        caixas = resultado.boxes
        if caixas is not None and len(caixas):
            for cls, conf, xyxyn in zip(
                caixas.cls.tolist(), caixas.conf.tolist(), caixas.xyxyn.tolist()
            ):
                classe = self.indice_para_classe.get(int(cls))
                if classe is None:
                    continue
                deteccoes.append(Deteccao(
                    classe=classe.value,
                    confianca=round(float(conf), 4),
                    caixa=[round(float(v), 4) for v in xyxyn],
                ))

        deteccoes.sort(key=lambda d: d.confianca, reverse=True)
        melhor = deteccoes[0] if deteccoes else None
        return ResultadoClassificacao(
            classe=ClasseOcorrencia(melhor.classe) if melhor else None,
            confianca=melhor.confianca if melhor else 0.0,
            deteccoes=deteccoes,
            modelo_versao=self.versao,
            tempo_ms=round(sum(resultado.speed.values()), 1),
        )


def carregar_classificador(caminho: str, imgsz: int, conf_min: float) -> Classificador:
    arquivo = Path(caminho)
    if not arquivo.is_file():
        motivo = f"modelo nao encontrado em {arquivo.resolve()}"
        log.warning("%s; ocorrencias irao para triagem humana", motivo)
        return ClassificadorIndisponivel(motivo)
    try:
        classificador = ClassificadorYOLO(arquivo, imgsz=imgsz, conf_min=conf_min)
    except ImportError:
        motivo = "biblioteca ultralytics nao instalada (pip install ultralytics)"
        log.warning(motivo)
        return ClassificadorIndisponivel(motivo)
    except Exception as e:  # arquivo corrompido, versao incompativel etc.
        motivo = f"falha ao carregar o modelo: {e}"
        log.exception(motivo)
        return ClassificadorIndisponivel(motivo)

    log.info("modelo carregado: %s", classificador.versao)
    return classificador


def _hash_curto(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()[:8]
