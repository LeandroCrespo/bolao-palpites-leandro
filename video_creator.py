"""
Integração com D-ID para geração do vídeo do Mestre Leme.
Busca o avatar pelo nome no D-ID, cria o vídeo e baixa o arquivo final.
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
VOICE_ID = "pt-BR-AntonioNeural"
POLL_INTERVAL = 5
POLL_TIMEOUT = 300


def _build_auth(api_key: str, email: str = "") -> str:
    """
    D-ID usa HTTP Basic Auth: Basic base64(email:api_key).
    Se DID_EMAIL estiver definido, constrói o header completo.
    Caso contrário, tenta usar api_key diretamente (para quem já armazenou
    o valor pré-codificado).
    """
    if api_key.lower().startswith(("basic ", "bearer ")):
        return api_key
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


def get_avatar_image_url(api_key: str, email: str = "") -> str:
    """
    Busca o avatar do Mestre Leme no D-ID pelo nome e retorna sua image_url.
    Dispensa upload manual da imagem.
    """
    result = _request("GET", f"{DID_API}/avatars", api_key, email)
    avatars = result if isinstance(result, list) else result.get("avatars", [])

    for av in avatars:
        name = av.get("name", "")
        if AVATAR_NAME.lower() in name.lower():
            url = av.get("image_url") or av.get("thumbnail_url") or av.get("url")
            if url:
                print(f"  Avatar '{name}' encontrado: {url[:60]}...")
                return url
            av_id = av.get("id")
            if av_id:
                detail = _request("GET", f"{DID_API}/avatars/{av_id}", api_key, email)
                url = detail.get("image_url") or detail.get("thumbnail_url")
                if url:
                    print(f"  Avatar '{name}' (id={av_id}) encontrado.")
                    return url

    names = [av.get("name", "?") for av in avatars]
    raise RuntimeError(
        f"Avatar '{AVATAR_NAME}' não encontrado no D-ID. "
        f"Avatares disponíveis: {names}. "
        f"Verifique o nome no Studio e ajuste AVATAR_NAME em video_creator.py."
    )


def create_bulletin_video(script: str, api_key: str, output_path: str = "bulletin.mp4",
                          email: str = "") -> str:
    """
    Gera o vídeo do Mestre Leme com o roteiro fornecido via D-ID.
    Retorna o caminho do arquivo de vídeo baixado.
    """
    image_url = get_avatar_image_url(api_key, email)

    print("  Criando vídeo no D-ID...")
    talk = _request("POST", f"{DID_API}/talks", api_key, email, {
        "source_url": image_url,
        "script": {
            "type": "text",
            "input": script,
            "provider": {
                "type": "microsoft",
                "voice_id": VOICE_ID,
            },
        },
        "config": {
            "fluent": True,
            "pad_audio": 0.5,
            "stitch": True,
        },
    })

    talk_id = talk.get("id")
    if not talk_id:
        raise RuntimeError(f"D-ID não retornou ID do vídeo: {talk}")
    print(f"  Vídeo criado (id={talk_id}), aguardando processamento...")

    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        status = _request("GET", f"{DID_API}/talks/{talk_id}", api_key, email)
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

    print(f"  Baixando vídeo...")
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
