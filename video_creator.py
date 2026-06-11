"""
Integração com HeyGen para geração do vídeo do Mestre Leme.
"""

import os
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

HEYGEN_API = "https://api.heygen.com"
AVATAR_NAME = "Crespao"
POLL_INTERVAL = 10
POLL_TIMEOUT = 600

# Fundo padrão: azul-escuro estilizado (pode ser sobrescrito via source_url com URL de imagem)
DEFAULT_BACKGROUND = {"type": "color", "value": "#0d1b2a"}


def _headers(api_key: str) -> dict:
    return {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request(method: str, url: str, api_key: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=_headers(api_key), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HeyGen API erro {e.code}: {error_body}") from e


def _get_avatar(api_key: str) -> str:
    """Retorna avatar_id do AVATAR_NAME ou do primeiro avatar disponível."""
    result = _request("GET", f"{HEYGEN_API}/v2/avatars", api_key)
    avatars = result.get("data", {}).get("avatars", [])
    print(f"  Avatares disponíveis: {len(avatars)}")
    for av in avatars:
        if AVATAR_NAME.lower() in av.get("avatar_name", "").lower():
            aid = av["avatar_id"]
            print(f"  Avatar: '{av['avatar_name']}' (id={aid})")
            return aid
    if not avatars:
        raise RuntimeError("Nenhum avatar disponível no HeyGen")
    av = avatars[0]
    print(f"  '{AVATAR_NAME}' não encontrado. Usando '{av['avatar_name']}' como fallback.")
    return av["avatar_id"]


def _get_voice(api_key: str) -> str:
    """Retorna voice_id masculino em português BR."""
    result = _request("GET", f"{HEYGEN_API}/v2/voices", api_key)
    voices = result.get("data", {}).get("voices", [])

    # Prioridade: masculino + português BR
    for v in voices:
        lang = v.get("language", "").lower()
        gender = v.get("gender", "").lower()
        if ("portuguese" in lang or "brazil" in lang or "pt-br" in lang) and gender == "male":
            print(f"  Voz: '{v['name']}' [{v['language']}] (id={v['voice_id']})")
            return v["voice_id"]

    # Sem filtro de gênero
    for v in voices:
        lang = v.get("language", "").lower()
        if "portuguese" in lang or "brazil" in lang or "pt-br" in lang:
            print(f"  Voz (sem filtro gênero): '{v['name']}' (id={v['voice_id']})")
            return v["voice_id"]

    if not voices:
        raise RuntimeError("Nenhuma voz disponível no HeyGen")
    v = voices[0]
    print(f"  Voz fallback: '{v['name']}' (id={v['voice_id']})")
    return v["voice_id"]


def _build_background(source_url: str) -> dict:
    """Monta o objeto background: imagem (URL) ou cor padrão."""
    if source_url and source_url.startswith("http"):
        return {"type": "image", "url": source_url}
    return DEFAULT_BACKGROUND


def _create_video(script: str, avatar_id: str, voice_id: str,
                  background: dict, api_key: str, output_path: str) -> str:
    print("  Criando vídeo no HeyGen...")
    body = {
        "video_inputs": [{
            "character": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal",
            },
            "voice": {
                "type": "text",
                "input_text": script,
                "voice_id": voice_id,
                "speed": 1.0,
            },
            "background": background,
        }],
        "dimension": {"width": 1280, "height": 720},
    }
    result = _request("POST", f"{HEYGEN_API}/v2/video/generate", api_key, body)
    video_id = result.get("data", {}).get("video_id")
    if not video_id:
        raise RuntimeError(f"HeyGen não retornou video_id: {result}")
    print(f"  video_id: {video_id}, processando...")
    return _poll_and_download(video_id, api_key, output_path)


def _poll_and_download(video_id: str, api_key: str, output_path: str) -> str:
    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        result = _request("GET", f"{HEYGEN_API}/v1/video_status.get?video_id={video_id}", api_key)
        data = result.get("data", {})
        state = data.get("status")
        print(f"  Status: {state} ({elapsed}s)")
        if state == "completed":
            video_url = data.get("video_url")
            if not video_url:
                raise RuntimeError("HeyGen: completed mas sem video_url")
            print("  Baixando vídeo...")
            urllib.request.urlretrieve(video_url, output_path)
            size_kb = Path(output_path).stat().st_size // 1024
            print(f"  Vídeo salvo: {output_path} ({size_kb} KB)")
            return output_path
        if state == "failed":
            raise RuntimeError(f"HeyGen falhou: {data}")
    raise TimeoutError(f"HeyGen não terminou em {POLL_TIMEOUT}s")


def create_bulletin_video(script: str, api_key: str, output_path: str = "bulletin.mp4",
                          source_url: str = "") -> str:
    """
    Gera o vídeo do Mestre Leme via HeyGen API.
    source_url: URL de imagem usada como background (opcional).
    """
    print("  Buscando avatar e voz no HeyGen...")
    avatar_id = _get_avatar(api_key)
    voice_id = _get_voice(api_key)
    background = _build_background(source_url)
    print(f"  Background: {background['type']}")
    return _create_video(script, avatar_id, voice_id, background, api_key, output_path)


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("HEYGEN_API_KEY", "").strip()
    if not api_key:
        print("HEYGEN_API_KEY não encontrada no .env")
        sys.exit(1)
    script_test = (
        "E aí, meu povo! Sou o Mestre Leme, direto do boteco mais honesto do Brasil! "
        "Isso aqui é só um teste do Boletim do Bolão dos Lemes. "
        "Se esse vídeo chegou até você, o sistema tá funcionando! Saúde!"
    )
    path = create_bulletin_video(script_test, api_key, "test_bulletin.mp4")
    print(f"\nTeste concluído: {path}")
