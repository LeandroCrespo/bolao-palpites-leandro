"""
Teste do Veo 3.1 Fast (via fal.ai) com referencia de imagem -- o mesmo
modelo Veo que ja conheciamos, mas agora com suporte a imagem de
referencia no tier "fast" (na API direta do Google isso nao era possivel).

Mesma cena de teste do Seedance (ambiente aberto, frente do estadio) pra
comparar lado a lado.

Uso:
  pip install fal-client python-dotenv
  FAL_KEY ja configurado no .env
  python veo31_fal_test.py
"""

import os
import sys
import urllib.request
from pathlib import Path

import fal_client
from dotenv import load_dotenv

REFERENCE_PHOTO = Path(__file__).parent / "Mestre Leme.png"
OUTPUT_DIR = Path(__file__).parent / "wan_clips"
MODEL_ID = "fal-ai/veo3.1/fast/reference-to-video"

TEST_PROMPT = (
    "Locked static camera, chest-up shot. A stocky Brazilian man matching "
    "the reference image exactly, wearing a canary-yellow Brazil jersey, "
    "standing right outside a stadium, blurred crowd of fans and stadium "
    "floodlight towers softly out of focus behind him (shallow depth of "
    "field), him in sharp, crisp, in-focus detail. One single controlled "
    "gesture: he slowly raises a fist toward the camera. He says in "
    "Portuguese: 'Meu povo! Vai, Brasil!'"
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

    print("\nGerando clipe de teste (Veo 3.1 Fast, 4s, 720p, com áudio)...")

    def on_update(update):
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                print(f"  [log] {log['message']}")

    result = fal_client.subscribe(
        MODEL_ID,
        arguments={
            "prompt": TEST_PROMPT,
            "image_urls": [photo_url],
            "duration": "8s",
            "resolution": "720p",
            "aspect_ratio": "16:9",
            "generate_audio": True,
        },
        with_logs=True,
        on_queue_update=on_update,
    )

    video_url = result["video"]["url"]
    print(f"\nVídeo gerado: {video_url}")

    out_path = OUTPUT_DIR / "teste_veo31_fal_v2_idioma_corrigido.mp4"
    print(f"Baixando para {out_path}...")
    urllib.request.urlretrieve(video_url, out_path)
    print(f"\nPronto! Clipe salvo em: {out_path}")


if __name__ == "__main__":
    main()
