"""
Integração com D-ID para geração do vídeo do Mestre Leme.
Tenta V4 Expressives API (/expressives) primeiro (plano Pro+).
Fallback para /talks API (plano Lite) com imagem estática.
"""

import os
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

DID_API = "https://api.d-id.com"
AVATAR_NAME = "Crespao"
VOICE_ID = "pt-BR-HumbertoNeural"
POLL_INTERVAL = 5
POLL_TIMEOUT = 300

PREFERRED_SENTIMENTS = ["excited", "friendly", "professional", "empathetic"]

# Imagem padrão quando nenhuma foto personalizada for fornecida
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


# ---------------------------------------------------------------------------
# V4 Expressives API (plano Pro+)
# ---------------------------------------------------------------------------

def _pick_sentiment(sentiments: list[dict]) -> str | None:
    # A API D-ID usa o campo "sentiment" (não "name")
    for pref in PREFERRED_SENTIMENTS:
        for snt in sentiments:
            label = snt.get("sentiment", snt.get("name", "")).lower()
            if pref in label:
                print(f"  Sentiment: {snt.get('sentiment')} ({snt.get('id')})")
                return snt.get("id")
    if sentiments:
        label = sentiments[0].get("sentiment", sentiments[0].get("name", "?"))
        print(f"  Sentiment (1º): {label} ({sentiments[0].get('id')})")
        return sentiments[0].get("id")
    return None


def _get_expressive_avatar(api_key: str) -> tuple[str, str | None] | None:
    """Busca avatar V4 pelo nome AVATAR_NAME. Retorna (avatar_id, sentiment_id) ou None."""
    try:
        result = _request("GET", f"{DID_API}/expressives/avatars", api_key)
        avatars = result if isinstance(result, list) else result.get("avatars", [])
        print(f"  V4 avatares encontrados: {len(avatars)}")
        for av in avatars:
            if AVATAR_NAME.lower() in av.get("name", "").lower():
                avatar_id = av.get("id")
                sentiment_id = _pick_sentiment(av.get("sentiments", []))
                print(f"  Avatar '{av.get('name')}' (id={avatar_id})")
                return avatar_id, sentiment_id
        if avatars:
            names = [av.get("name", "?") for av in avatars]
            print(f"  '{AVATAR_NAME}' não encontrado. Disponíveis: {names}")
            # Usa o primeiro avatar disponível como fallback
            av = avatars[0]
            avatar_id = av.get("id")
            sentiment_id = _pick_sentiment(av.get("sentiments", []))
            print(f"  Usando avatar '{av.get('name')}' como fallback")
            return avatar_id, sentiment_id
    except RuntimeError as e:
        print(f"  Expressives não disponível: {e}")
    return None


def _create_expressive_video(script: str, avatar_id: str, sentiment_id: str | None,
                              api_key: str, output_path: str) -> str:
    """Cria vídeo via /expressives (plano Pro+) com voz pt-BR."""
    print("  Criando vídeo via /expressives...")
    body: dict = {
        "avatar_id": avatar_id,
        "script": {
            "type": "text",
            "input": script,
            "provider": {
                "type": "microsoft",
                "voice_id": VOICE_ID,
            },
        },
    }
    if sentiment_id:
        body["sentiment_id"] = sentiment_id
    exp = _request("POST", f"{DID_API}/expressives", api_key, body)
    exp_id = exp.get("id")
    if not exp_id:
        raise RuntimeError(f"D-ID não retornou ID: {exp}")
    print(f"  ID: {exp_id}, aguardando...")
    return _poll_and_download(f"{DID_API}/expressives/{exp_id}", exp_id, api_key, output_path)


# ---------------------------------------------------------------------------
# /talks API (plano Lite — fallback)
# ---------------------------------------------------------------------------

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
    except RuntimeError as e:
        print(f"  /scenes/avatars erro: {e}")
    return None


def _create_talks_video(script: str, source_url: str, api_key: str, output_path: str) -> str:
    """Cria vídeo via /talks com voz Microsoft pt-BR."""
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
    print(f"  ID: {talk_id}, aguardando...")
    return _poll_and_download(f"{DID_API}/talks/{talk_id}", talk_id, api_key, output_path)


# ---------------------------------------------------------------------------
# Polling + download
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def create_bulletin_video(script: str, api_key: str, output_path: str = "bulletin.mp4",
                          source_url: str = "") -> str:
    """
    Gera o vídeo do Mestre Leme via D-ID.
    1. Tenta /expressives com o avatar Crespao (plano Pro+)
    2. Se DID_SOURCE_URL fornecida, usa /talks com essa imagem
    3. Tenta /scenes/avatars para encontrar imagem do Crespao
    4. Fallback: /talks com alice.jpg
    """
    # Tenta V4 Expressives (plano Pro+)
    expressive = _get_expressive_avatar(api_key)
    if expressive:
        avatar_id, sentiment_id = expressive
        try:
            return _create_expressive_video(script, avatar_id, sentiment_id, api_key, output_path)
        except RuntimeError as e:
            print(f"  Expressives falhou: {e} — tentando /talks...")

    # Fallback /talks
    image_url = source_url
    if not image_url:
        image_url = _get_presenter_url(api_key) or DEFAULT_SOURCE_URL

    return _create_talks_video(script, image_url, api_key, output_path)


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
