"""
Integração com D-ID Expressives API (V4) para geração do vídeo do Mestre Leme.
Usa /expressives endpoint com avatar_id e sentiment_id.
"""

import base64
import os
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

DID_API = "https://api.d-id.com"
AVATAR_NAME = "Mestre_Leme"
POLL_INTERVAL = 5
POLL_TIMEOUT = 300

# Sentimentos preferidos para o Mestre Leme (animado, botequeiro)
PREFERRED_SENTIMENTS = ["excited", "friendly", "professional", "empathetic"]


def _build_auth(api_key: str, email: str = "") -> str:
    """
    D-ID API key do dashboard já vem como base64(email:raw_key).
    Basta adicionar o prefixo 'Basic '.
    Se a chave for crua (sem colon no decoded), constrói com email.
    """
    if api_key.lower().startswith(("basic ", "bearer ")):
        return api_key
    try:
        decoded = base64.b64decode(api_key + "==").decode("utf-8", errors="replace")
        if ":" in decoded:
            return f"Basic {api_key}"
    except Exception:
        pass
    if email:
        encoded = base64.b64encode(f"{email}:{api_key}".encode()).decode()
        return f"Basic {encoded}"
    return f"Basic {api_key}"


def _headers(api_key: str, email: str = "") -> dict:
    return {
        "Authorization": _build_auth(api_key, email),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request(method: str, url: str, api_key: str, email: str = "", body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers=_headers(api_key, email),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"D-ID API erro {e.code}: {error_body}") from e


def get_avatar_and_sentiment(api_key: str, email: str = "") -> tuple[str, str]:
    """
    Lista avatares em /expressives/avatars, encontra o Mestre_Leme
    e retorna (avatar_id, sentiment_id).
    """
    result = _request("GET", f"{DID_API}/expressives/avatars", api_key, email)
    avatars = result if isinstance(result, list) else result.get("avatars", [])

    for av in avatars:
        name = av.get("name", "")
        if AVATAR_NAME.lower() in name.lower():
            avatar_id = av.get("id")
            sentiments = av.get("sentiments", [])
            print(f"  Avatar '{name}' (id={avatar_id}) encontrado.")

            sentiment_id = None
            for pref in PREFERRED_SENTIMENTS:
                for snt in sentiments:
                    if pref in snt.get("name", "").lower():
                        sentiment_id = snt.get("id")
                        print(f"  Sentiment: {snt.get('name')} (id={sentiment_id})")
                        break
                if sentiment_id:
                    break
            if not sentiment_id and sentiments:
                sentiment_id = sentiments[0].get("id")
                print(f"  Sentiment (1º disponível): {sentiments[0].get('name')} (id={sentiment_id})")

            if avatar_id and sentiment_id:
                return avatar_id, sentiment_id

    names = [av.get("name", "?") for av in avatars]
    raise RuntimeError(
        f"Avatar '{AVATAR_NAME}' não encontrado no D-ID. "
        f"Avatares disponíveis: {names}. "
        f"Crie um avatar com esse nome no D-ID Studio ou ajuste AVATAR_NAME em video_creator.py."
    )


def create_bulletin_video(script: str, api_key: str, output_path: str = "bulletin.mp4",
                          email: str = "") -> str:
    """
    Gera o vídeo do Mestre Leme via D-ID Expressives API.
    Retorna o caminho do arquivo de vídeo baixado.
    """
    avatar_id, sentiment_id = get_avatar_and_sentiment(api_key, email)

    print("  Criando vídeo no D-ID (expressives)...")
    expressive = _request("POST", f"{DID_API}/expressives", api_key, email, {
        "avatar_id": avatar_id,
        "sentiment_id": sentiment_id,
        "script": {
            "type": "text",
            "input": script,
        },
    })

    exp_id = expressive.get("id")
    if not exp_id:
        raise RuntimeError(f"D-ID não retornou ID do vídeo: {expressive}")
    print(f"  Vídeo criado (id={exp_id}), aguardando processamento...")

    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        status = _request("GET", f"{DID_API}/expressives/{exp_id}", api_key, email)
        state = status.get("status")
        print(f"  Status: {state} ({elapsed}s)")
        if state == "done":
            video_url = status.get("result_url")
            if not video_url:
                raise RuntimeError("D-ID retornou done mas sem result_url")
            break
        if state == "error":
            raise RuntimeError(f"D-ID erro ao gerar vídeo: {status}")
    else:
        raise TimeoutError(f"D-ID não terminou o vídeo em {POLL_TIMEOUT}s")

    print("  Baixando vídeo...")
    urllib.request.urlretrieve(video_url, output_path)
    size_kb = Path(output_path).stat().st_size // 1024
    print(f"  Vídeo salvo: {output_path} ({size_kb} KB)")
    return output_path


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("DID_API_KEY")
    email = os.getenv("DID_EMAIL", "")
    if not api_key:
        print("DID_API_KEY não encontrada no .env")
        sys.exit(1)
    script_test = (
        "E aí, meu povo! Sou o Mestre Leme, direto do boteco mais honesto do Brasil! "
        "Isso aqui é só um teste do Boletim do Bolão dos Lemes. "
        "Se esse vídeo chegou até você, o sistema tá funcionando! Saúde!"
    )
    path = create_bulletin_video(script_test, api_key, "test_bulletin.mp4", email)
    print(f"\nTeste concluído: {path}")
