"""
Integração com D-ID para geração do vídeo do Mestre Leme.
Usa a API /talks (plano Lite), com voz Microsoft pt-BR.
"""

import os
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

DID_API = "https://api.d-id.com"
AVATAR_NAME = "Crespao"
VOICE_ID = "pt-BR-AntonioNeural"
POLL_INTERVAL = 5
POLL_TIMEOUT = 300

# Imagem padrão usada quando nenhuma foto personalizada for fornecida
DEFAULT_SOURCE_URL = "https://d-id-public-bucket.s3.us-west-2.amazonaws.com/alice.jpg"


def _headers(api_key: str) -> dict:
    """D-ID aceita a chave bruta no formato 'Basic {key}'."""
    token = api_key if api_key.lower().startswith(("basic ", "bearer ")) else f"Basic {api_key}"
    return {
        "Authorization": token,
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
        raise RuntimeError(f"D-ID API erro {e.code}: {error_body}") from e


def _get_presenter_url(api_key: str) -> str | None:
    """Tenta encontrar a imagem do Crespao em /scenes/avatars."""
    try:
        result = _request("GET", f"{DID_API}/scenes/avatars", api_key)
        avatars = result if isinstance(result, list) else result.get("avatars", [])
        print(f"  Avatares em /scenes/avatars: {len(avatars)}")
        for av in avatars:
            if AVATAR_NAME.lower() in av.get("name", "").lower():
                url = av.get("image_url") or av.get("thumbnail_url") or av.get("url")
                if url:
                    print(f"  Encontrou '{av.get('name')}': {url[:60]}...")
                    return url
        if avatars:
            names = [av.get("name", "?") for av in avatars]
            print(f"  '{AVATAR_NAME}' não encontrado. Disponíveis: {names}")
    except RuntimeError as e:
        print(f"  /scenes/avatars erro: {e}")
    return None


def _create_talks_video(script: str, source_url: str, api_key: str, output_path: str) -> str:
    """Cria vídeo via /talks com voz Microsoft pt-BR e aguarda conclusão."""
    print(f"  Criando vídeo via /talks (voz: {VOICE_ID})...")
    talk = _request("POST", f"{DID_API}/talks", api_key, {
        "source_url": source_url,
        "script": {
            "type": "text",
            "input": script,
            "provider": {
                "type": "microsoft",
                "voice_id": VOICE_ID,
            },
        },
        "config": {"fluent": True, "pad_audio": 0.5, "stitch": True},
    })
    talk_id = talk.get("id")
    if not talk_id:
        raise RuntimeError(f"D-ID não retornou ID: {talk}")
    print(f"  ID: {talk_id}, aguardando processamento...")
    return _poll_and_download(f"{DID_API}/talks/{talk_id}", talk_id, api_key, output_path)


def _poll_and_download(status_url: str, job_id: str, api_key: str, output_path: str) -> str:
    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        status = _request("GET", status_url, api_key)
        state = status.get("status")
        print(f"  Status: {state} ({elapsed}s)")
        if state == "done":
            video_url = status.get("result_url")
            if not video_url:
                raise RuntimeError("D-ID retornou done mas sem result_url")
            print("  Baixando vídeo...")
            urllib.request.urlretrieve(video_url, output_path)
            size_kb = Path(output_path).stat().st_size // 1024
            print(f"  Vídeo salvo: {output_path} ({size_kb} KB)")
            return output_path
        if state == "error":
            raise RuntimeError(f"D-ID erro: {status}")
    raise TimeoutError(f"D-ID não terminou em {POLL_TIMEOUT}s")


def create_bulletin_video(script: str, api_key: str, output_path: str = "bulletin.mp4",
                          email: str = "", source_url: str = "") -> str:
    """
    Gera o vídeo do Mestre Leme via D-ID /talks API (plano Lite).
    1. Se source_url fornecida (DID_SOURCE_URL secret), usa direto.
    2. Tenta encontrar imagem do Crespao em /scenes/avatars.
    3. Fallback: usa alice.jpg padrão do D-ID.
    """
    # 1. URL de imagem fornecida diretamente via secret
    if source_url:
        print(f"  Usando imagem personalizada: {source_url[:60]}...")
        return _create_talks_video(script, source_url, api_key, output_path)

    # 2. Busca avatar Crespao na conta
    presenter_url = _get_presenter_url(api_key)
    if presenter_url:
        return _create_talks_video(script, presenter_url, api_key, output_path)

    # 3. Fallback: imagem padrão D-ID
    print(f"  Usando imagem padrão D-ID (alice.jpg)...")
    return _create_talks_video(script, DEFAULT_SOURCE_URL, api_key, output_path)


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("DID_API_KEY")
    if not api_key:
        print("DID_API_KEY não encontrada no .env")
        sys.exit(1)
    script_test = (
        "E aí, meu povo! Sou o Mestre Leme, direto do boteco mais honesto do Brasil! "
        "Isso aqui é só um teste do Boletim do Bolão dos Lemes. "
        "Se esse vídeo chegou até você, o sistema tá funcionando! Saúde!"
    )
    path = create_bulletin_video(script_test, api_key, "test_bulletin.mp4")
    print(f"\nTeste concluído: {path}")
