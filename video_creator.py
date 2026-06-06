"""
Integração com D-ID para geração do vídeo do Mestre Leme.
Tenta V4 Expressives API (/expressives) primeiro; se não disponível,
usa V1/V2 Talks API (/talks) com voz Microsoft pt-BR.
"""

import base64
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

PREFERRED_SENTIMENTS = ["excited", "friendly", "professional", "empathetic"]


def _build_auth(api_key: str, email: str = "") -> str:
    """
    D-ID API key do dashboard já vem como base64(email:raw_key).
    Detecta se já está nesse formato (contém colon decodificado) e
    adiciona apenas o prefixo 'Basic '.
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


# ---------------------------------------------------------------------------
# V4 Expressives API
# ---------------------------------------------------------------------------

def _get_expressive_avatar(api_key: str, email: str) -> tuple[str, str] | None:
    """Tenta encontrar avatar V4 em /expressives/avatars. Retorna (avatar_id, sentiment_id) ou None."""
    try:
        result = _request("GET", f"{DID_API}/expressives/avatars", api_key, email)
    except RuntimeError as e:
        print(f"  V4 expressives não disponível: {e}")
        return None

    avatars = result if isinstance(result, list) else result.get("avatars", [])
    print(f"  V4 avatares encontrados: {len(avatars)}")

    for av in avatars:
        name = av.get("name", "")
        if AVATAR_NAME.lower() in name.lower():
            avatar_id = av.get("id")
            sentiments = av.get("sentiments", [])
            print(f"  Avatar '{name}' (id={avatar_id}) — {len(sentiments)} sentiment(s)")

            sentiment_id = None
            for pref in PREFERRED_SENTIMENTS:
                for snt in sentiments:
                    if pref in snt.get("name", "").lower():
                        sentiment_id = snt.get("id")
                        print(f"  Sentiment escolhido: {snt.get('name')} ({sentiment_id})")
                        break
                if sentiment_id:
                    break
            if not sentiment_id and sentiments:
                sentiment_id = sentiments[0].get("id")
                print(f"  Sentiment (1º): {sentiments[0].get('name')} ({sentiment_id})")

            if avatar_id and sentiment_id:
                return avatar_id, sentiment_id

    if avatars:
        names = [av.get("name", "?") for av in avatars]
        print(f"  Avatar '{AVATAR_NAME}' não encontrado. Disponíveis: {names}")
    else:
        print(f"  Nenhum avatar V4 disponível. Crie um no D-ID Studio com nome '{AVATAR_NAME}'.")
    return None


def _create_expressive_video(script: str, avatar_id: str, sentiment_id: str,
                              api_key: str, email: str, output_path: str) -> str:
    """Cria vídeo via /expressives e aguarda conclusão."""
    print("  Criando vídeo via /expressives...")
    exp = _request("POST", f"{DID_API}/expressives", api_key, email, {
        "avatar_id": avatar_id,
        "sentiment_id": sentiment_id,
        "script": {"type": "text", "input": script},
    })
    exp_id = exp.get("id")
    if not exp_id:
        raise RuntimeError(f"D-ID não retornou ID: {exp}")
    print(f"  ID: {exp_id}, aguardando...")
    return _poll_and_download(f"{DID_API}/expressives/{exp_id}", exp_id, api_key, email, output_path)


# ---------------------------------------------------------------------------
# V1/V2 Talks API (fallback)
# ---------------------------------------------------------------------------

def _get_talks_avatar(api_key: str, email: str) -> str | None:
    """Tenta encontrar image_url do avatar em /avatars. Retorna URL ou None."""
    try:
        result = _request("GET", f"{DID_API}/avatars", api_key, email)
    except RuntimeError as e:
        print(f"  /avatars não disponível: {e}")
        return None

    avatars = result if isinstance(result, list) else result.get("avatars", [])
    print(f"  Avatares legados encontrados: {len(avatars)}")

    for av in avatars:
        name = av.get("name", "")
        if AVATAR_NAME.lower() in name.lower():
            url = av.get("image_url") or av.get("thumbnail_url") or av.get("url")
            if url:
                print(f"  Avatar legado '{name}' encontrado.")
                return url
            av_id = av.get("id")
            if av_id:
                try:
                    detail = _request("GET", f"{DID_API}/avatars/{av_id}", api_key, email)
                    url = detail.get("image_url") or detail.get("thumbnail_url")
                    if url:
                        return url
                except RuntimeError:
                    pass

    names = [av.get("name", "?") for av in avatars]
    print(f"  Avatar '{AVATAR_NAME}' não encontrado em /avatars. Disponíveis: {names}")
    return None


def _create_talks_video(script: str, image_url: str,
                         api_key: str, email: str, output_path: str) -> str:
    """Cria vídeo via /talks com voz Microsoft pt-BR."""
    print("  Criando vídeo via /talks (pt-BR-AntonioNeural)...")
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
        "config": {"fluent": True, "pad_audio": 0.5, "stitch": True},
    })
    talk_id = talk.get("id")
    if not talk_id:
        raise RuntimeError(f"D-ID não retornou ID: {talk}")
    print(f"  ID: {talk_id}, aguardando...")
    return _poll_and_download(f"{DID_API}/talks/{talk_id}", talk_id, api_key, email, output_path)


# ---------------------------------------------------------------------------
# Polling + download
# ---------------------------------------------------------------------------

def _poll_and_download(status_url: str, job_id: str,
                        api_key: str, email: str, output_path: str) -> str:
    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        status = _request("GET", status_url, api_key, email)
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
                          email: str = "", source_url: str = "") -> str:
    """
    Gera o vídeo do Mestre Leme via D-ID.
    Se source_url for fornecida, usa /talks diretamente (ignora lookup de avatar).
    Caso contrário tenta V4 Expressives, depois /talks com lookup automático.
    """
    # Caminho rápido: URL da imagem fornecida diretamente
    if source_url:
        print(f"  Usando source_url fornecida: {source_url[:60]}...")
        return _create_talks_video(script, source_url, api_key, email, output_path)

    # Tenta V4 Expressives
    expressive = _get_expressive_avatar(api_key, email)
    if expressive:
        avatar_id, sentiment_id = expressive
        return _create_expressive_video(script, avatar_id, sentiment_id, api_key, email, output_path)

    # Fallback: V1/V2 Talks com lookup automático
    print("  Tentando API /talks como fallback...")
    image_url = _get_talks_avatar(api_key, email)
    if image_url:
        return _create_talks_video(script, image_url, api_key, email, output_path)

    raise RuntimeError(
        f"Avatar não encontrado. Defina DID_SOURCE_URL com a URL da imagem do avatar "
        f"(clique direito na foto no D-ID Studio → Copiar endereço da imagem)."
    )


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
