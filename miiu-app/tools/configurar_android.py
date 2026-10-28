"""Ajusta o projeto Android gerado pelo `flutter create` para o MIIU.

Rode UMA vez, depois do flutter create (pode repetir sem problema):

    python tools/configurar_android.py

O que faz:
- AndroidManifest.xml: permissoes de internet, localizacao (inclusive em
  segundo plano via servico em primeiro plano), notificacoes e wake lock;
  libera HTTP sem TLS (o backend local roda em http://IP:8000); nome "MIIU";
  e declara a intencao de camera usada pelo image_picker.
- build.gradle(.kts): minSdk de pelo menos 23, exigido pelo Firebase.
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MANIFESTO = RAIZ / "android" / "app" / "src" / "main" / "AndroidManifest.xml"

PERMISSOES = [
    "android.permission.INTERNET",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.FOREGROUND_SERVICE",
    "android.permission.FOREGROUND_SERVICE_LOCATION",
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.WAKE_LOCK",
]

INTENCAO_CAMERA = (
    '        <intent>\n'
    '            <action android:name="android.media.action.IMAGE_CAPTURE"/>\n'
    '        </intent>\n'
)


def ajustar_manifesto() -> None:
    if not MANIFESTO.is_file():
        sys.exit(
            f"Nao encontrei {MANIFESTO}.\n"
            "Rode antes, dentro da pasta miiu-app:\n"
            "  flutter create --org br.uespi.miiu --project-name miiu_app --platforms android ."
        )
    texto = MANIFESTO.read_text(encoding="utf-8")

    faltando = [p for p in PERMISSOES if f'android:name="{p}"' not in texto]
    if faltando:
        linhas = "".join(f'    <uses-permission android:name="{p}"/>\n' for p in faltando)
        texto = re.sub(r"(<manifest[^>]*>\s*\n)", lambda m: m.group(1) + linhas, texto, count=1)

    def ajustar_application(m: re.Match) -> str:
        tag = m.group(0)
        tag = re.sub(r'android:label="[^"]*"', 'android:label="MIIU"', tag)
        if "usesCleartextTraffic" not in tag:
            tag = tag.replace("<application", '<application\n        android:usesCleartextTraffic="true"', 1)
        return tag

    texto = re.sub(r"<application[^>]*>", ajustar_application, texto, count=1)

    if "android.media.action.IMAGE_CAPTURE" not in texto:
        if "<queries>" in texto:
            texto = texto.replace("<queries>\n", "<queries>\n" + INTENCAO_CAMERA, 1)
        else:
            texto = texto.replace(
                "</manifest>", "    <queries>\n" + INTENCAO_CAMERA + "    </queries>\n</manifest>", 1
            )

    MANIFESTO.write_text(texto, encoding="utf-8")
    print(f"ok  {MANIFESTO.relative_to(RAIZ)}")
    for p in faltando:
        print(f"    + {p}")


def ajustar_gradle() -> None:
    app = RAIZ / "android" / "app"
    kts, groovy = app / "build.gradle.kts", app / "build.gradle"
    if kts.is_file():
        texto = kts.read_text(encoding="utf-8")
        novo = re.sub(r"minSdk\s*=\s*flutter\.minSdkVersion", "minSdk = maxOf(23, flutter.minSdkVersion)", texto)
        alvo = kts
    elif groovy.is_file():
        texto = groovy.read_text(encoding="utf-8")
        novo = re.sub(r"minSdkVersion\s+flutter\.minSdkVersion", "minSdkVersion Math.max(23, flutter.minSdkVersion)", texto)
        alvo = groovy
    else:
        print("[aviso] build.gradle do app nao encontrado; ajuste o minSdk para 23 manualmente")
        return
    if novo != texto:
        alvo.write_text(novo, encoding="utf-8")
        print(f"ok  {alvo.relative_to(RAIZ)}: minSdk >= 23")
    elif "maxOf(23" in texto or "Math.max(23" in texto:
        print(f"ok  {alvo.relative_to(RAIZ)}: minSdk ja ajustado")
    else:
        print(f"[aviso] nao reconheci a linha do minSdk em {alvo.name}; garanta minSdk 23 ou maior")


if __name__ == "__main__":
    ajustar_manifesto()
    ajustar_gradle()
    print("\nPronto. Agora: flutter pub get && flutter run")
