"""
Teste do Wan 2.7 Reference-to-Video (fal.ai) com a foto do Mestre Leme.

Gera 1 clipe curto de teste para avaliar se o modelo mantém a identidade
do Mestre Leme numa cena nova (descrita só por texto) -- o mesmo problema
que travou no Veo 3 (fast não aceita referência, standard ficou caro).

Uso:
  pip install fal-client python-dotenv
  set FAL_KEY=... (ou colocar no .env)
  python wan27_test.py
"""

import os
import sys
from pathlib import Path

import fal_client
from dotenv import load_dotenv

REFERENCE_PHOTO = Path(__file__).parent / "Mestre Leme.png"
OUTPUT_DIR = Path(__file__).parent / "wan_clips"
MODEL_ID = "fal-ai/wan/v2.7/reference-to-video"

# Roteiro de teste: cena nova (bar perto do estádio), só por texto + a foto
# de referência -- mesmo cenário que já usamos nos prompts do Veo, pra
# comparar a qualidade direito.
TEST_PROMPT = (
    "A stocky, heavy-set Brazilian man approximately 55 years old, matching "
    "the reference photo exactly (same face, hair, beard, mustache), sharp "
    "facial detail in close focus, wearing a bright canary-yellow Brazil "
    "football jersey, standing at a lively sports bar counter, holding a "
    "glass of Brazilian draft beer (chope) with white foam, raising it "
    "toward the camera with a big warm smile. Warm amber lighting, TV "
    "screens with World Cup highlights blurred in the background, "
    "photorealistic, cinematic, high detail, sharp focus on the face. "
    "He speaks SLOWLY and CLEARLY, fully pronouncing every word, with a "
    "natural deep male voice, pausing briefly between sentences: "
    "'Meu povo! Vai, Brasil!'"
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

    print("\nGerando clipe de teste (Wan 2.7 R2V, ~8s, 720p)...")

    def on_update(update):
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                print(f"  [log] {log['message']}")

    result = fal_client.subscribe(
        MODEL_ID,
        arguments={
            "prompt": TEST_PROMPT,
            "reference_image_urls": [photo_url],
            "duration": 10,
            "resolution": "1080p",
            "aspect_ratio": "16:9",
        },
        with_logs=True,
        on_queue_update=on_update,
    )

    video_url = result["video"]["url"]
    print(f"\nVídeo gerado: {video_url}")

    out_path = OUTPUT_DIR / "teste_wan27_r2v_v2_1080p.mp4"
    print(f"Baixando para {out_path}...")
    import urllib.request
    urllib.request.urlretrieve(video_url, out_path)
    print(f"\nPronto! Clipe salvo em: {out_path}")
    print(f"Seed usada (pra reproduzir): {result.get('seed')}")


if __name__ == "__main__":
    main()
