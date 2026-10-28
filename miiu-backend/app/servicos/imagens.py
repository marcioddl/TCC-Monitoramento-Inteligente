"""Validacao, anonimizacao e armazenamento das fotografias enviadas.

Toda imagem e decodificada e regravada como JPEG novo. Isso tem tres efeitos:

1. valida o conteudo de verdade (o content-type enviado pelo cliente nao e
   confiavel);
2. descarta todos os metadados EXIF, incluindo coordenadas GPS embutidas,
   modelo e numero de serie da camera e data da captura (LGPD: so a
   localizacao informada explicitamente pelo aplicativo e armazenada);
3. aplica antes a orientacao do EXIF, para que a foto tirada com o celular
   na vertical nao chegue deitada ao modelo de visao computacional.
"""

import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

FORMATOS_ACEITOS = {"JPEG", "PNG", "WEBP", "MPO"}  # MPO: JPEG de algumas cameras
QUALIDADE_JPEG = 90


class ImagemInvalida(ValueError):
    """Conteudo que nao e uma imagem suportada."""


class ImagemGrandeDemais(ValueError):
    """Arquivo acima do limite configurado."""


@dataclass
class ImagemProcessada:
    imagem: Image.Image      # pronta para a inferencia (RGB, orientada)
    caminho_relativo: str    # relativo ao UPLOAD_DIR, gravado no banco
    largura: int
    altura: int
    bytes_gravados: int


def ler_com_limite(arquivo, limite_bytes: int) -> bytes:
    """Le o upload sem carregar mais do que o limite na memoria."""
    dados = arquivo.read(limite_bytes + 1)
    if len(dados) > limite_bytes:
        raise ImagemGrandeDemais(f"imagem acima de {limite_bytes // (1024 * 1024)} MB")
    if not dados:
        raise ImagemInvalida("arquivo vazio")
    return dados


def processar_e_salvar(dados: bytes, pasta_upload: Path, lado_max: int) -> ImagemProcessada:
    try:
        with Image.open(io.BytesIO(dados)) as bruta:
            formato = bruta.format
            if formato not in FORMATOS_ACEITOS:
                raise ImagemInvalida(f"formato nao suportado: {formato}")
            bruta.load()
            imagem = ImageOps.exif_transpose(bruta)
    except ImagemInvalida:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ImagemInvalida("o arquivo enviado nao e uma imagem valida") from e

    if imagem.mode != "RGB":
        imagem = imagem.convert("RGB")

    if max(imagem.size) > lado_max:
        imagem.thumbnail((lado_max, lado_max), Image.Resampling.LANCZOS)

    # Garante que nenhum metadado herdado do arquivo original seja regravado
    imagem.info = {}

    agora = datetime.now(timezone.utc)
    relativo = Path(f"{agora:%Y}") / f"{agora:%m}" / f"{uuid.uuid4().hex}.jpg"
    destino = pasta_upload / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)

    # Sem o parametro exif, o Pillow grava o JPEG sem nenhum metadado
    buffer = io.BytesIO()
    imagem.save(buffer, format="JPEG", quality=QUALIDADE_JPEG, optimize=True)
    destino.write_bytes(buffer.getvalue())

    return ImagemProcessada(
        imagem=imagem,
        caminho_relativo=relativo.as_posix(),
        largura=imagem.width,
        altura=imagem.height,
        bytes_gravados=buffer.tell(),
    )


def caminho_absoluto(pasta_upload: Path, relativo: str) -> Path | None:
    """Resolve o caminho gravado no banco sem permitir escapar da pasta."""
    raiz = pasta_upload.resolve()
    alvo = (raiz / relativo).resolve()
    if raiz not in alvo.parents or not alvo.is_file():
        return None
    return alvo
