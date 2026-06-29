"""
Teste do Seedance 2.0 Fast (fal.ai) com a foto do Mestre Leme.

Muito mais barato que o Wan 2.7 ($0,022/s vs $0,10/s) e com lip-sync nativo
(audio sincronizado fonema a fonema), em vez de depender de uma "voz"
genérica mal ajustada como no teste anterior.

Uso:
  pip install fal-client python-dotenv
  FAL_KEY já configurado no .env
  python seedance_test.py
"""

import os
import sys
import urllib.request
from pathlib import Path

import fal_client
from dotenv import load_dotenv

REFERENCE_PHOTO = Path(__file__).parent / "Mestre Leme.png"
OUTPUT_DIR = Path(__file__).parent / "wan_clips"
MODEL_ID = "bytedance/seedance-2.0/reference-to-video"  # Standard (nao Fast)

# Sintaxe do Seedance: referencia a imagem enviada como "@Image1" dentro do
# prompt (em vez de um campo separado de reference_image_urls como no Wan).
TEST_PROMPT = (
    "@Image1 Locked static camera, chest-up shot. A stocky Brazilian man "
    "matching the reference image exactly, wearing a canary-yellow Brazil "
    "jersey, standing right outside a stadium, blurred crowd of fans and "
    "stadium floodlight towers softly out of focus behind him (shallow "
    "depth of field), him in sharp, crisp, in-focus detail. One single "
    "controlled gesture: he slowly raises a fist toward the camera while "
    "speaking in Brazilian Portuguese, clearly: 'Meu povo! Vai, Brasil!'"
)


def main():
    load_dotenv()
    if not os.environ.get("FAL_KEY"):
        sys.exit("FAL_KEY não encontrado no .env nem nas variáveis de ambiente.")

    if not REFERENCE_PHOTO.exists():
        sys.exit(f"Foto de referência não encontrada: {REFERENCE_PHOTO}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"Enviando foto de referência ({REFERENCE_PHOTO.name})...")
    photo_url = fal_client.upload_file(str(REFERENCE_PHOTO))
    print(f"  URL: {photo_url}")

    print("\nGerando clipe de teste (Seedance 2.0 Fast, 8s, 720p)...")

    def on_update(update):
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                print(f"  [log] {log['message']}")

    result = fal_client.subscribe(
        MODEL_ID,
        arguments={
            "prompt": TEST_PROMPT,
            "image_urls": [photo_url],
            "duration": 4,
            "resolution": "720p",
            "aspect_ratio": "16:9",
            "generate_audio": True,
        },
        with_logs=True,
        on_queue_update=on_update,
    )

    video_url = result["video"]["url"]
    print(f"\nVídeo gerado: {video_url}")

    out_path = OUTPUT_DIR / "teste_seedance2_standard_4s_ambiente_aberto.mp4"
    print(f"Baixando para {out_path}...")
    urllib.request.urlretrieve(video_url, out_path)
    print(f"\nPronto! Clipe salvo em: {out_path}")
    print(f"Seed usada (pra reproduzir): {result.get('seed')}")


if __name__ == "__main__":
    main()
