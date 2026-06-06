"""
Envia o vídeo do Boletim do Mestre Leme via Telegram.
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path


def send_bulletin_video(video_path: str, caption: str, token: str, chat_id: str) -> bool:
    """
    Envia o vídeo do boletim via Telegram sendVideo.
    Retorna True se enviado com sucesso.
    """
    url = f"https://api.telegram.org/bot{token}/sendVideo"
    video_file = Path(video_path)

    if not video_file.exists():
        raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")

    size_mb = video_file.stat().st_size / (1024 * 1024)
    if size_mb > 50:
        raise ValueError(f"Vídeo muito grande: {size_mb:.1f}MB (limite Telegram: 50MB)")

    with open(video_path, "rb") as f:
        video_data = f.read()

    boundary = "----TelegramBoundary7MA4YWxk"
    content_type_header = f"multipart/form-data; boundary={boundary}"

    def _field(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode("utf-8")

    body = (
        _field("chat_id", chat_id)
        + _field("caption", caption)
        + _field("parse_mode", "HTML")
        + (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="video"; filename="boletim_mestre_leme.mp4"\r\n'
            f"Content-Type: video/mp4\r\n\r\n"
        ).encode("utf-8")
        + video_data
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": content_type_header,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"  Boletim enviado ao Telegram com sucesso!")
                return True
            raise RuntimeError(f"Telegram retornou erro: {result}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {e.code}: {error_body}") from e


def send_text_fallback(text: str, token: str, chat_id: str, caption: str = "🎙️ <b>Boletim do Mestre Leme</b>"):
    """Envia roteiro em texto caso a geração de vídeo falhe."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": chat_id,
        "text": f"{caption}\n\n{text}",
        "parse_mode": "HTML",
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        print("  Fallback texto enviado ao Telegram.")
    except Exception as e:
        print(f"  Falha no fallback texto: {e}")


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    video = "test_bulletin.mp4"

    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não encontrados no .env")
        sys.exit(1)
    if not Path(video).exists():
        print(f"Arquivo {video} não encontrado. Rode primeiro: python video_creator.py")
        sys.exit(1)

    send_bulletin_video(video, "🎙️ Boletim do Mestre Leme — teste", token, chat_id)
