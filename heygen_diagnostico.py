"""Script de diagnóstico HeyGen — verifica conta, avatares e vozes disponíveis."""
import json
import os
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("HEYGEN_API_KEY", "").encode().decode("utf-8-sig").strip().strip("'\"")
if not api_key:
    print("HEYGEN_API_KEY não encontrada")
    exit(1)

BASE = "https://api.heygen.com"
HEADERS = {"X-Api-Key": api_key, "Accept": "application/json", "Content-Type": "application/json"}


def _fetch(url, method="GET", body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def show(label, code, result):
    print(f"\n{'='*55}")
    print(f"{label}  →  HTTP {code}")
    if isinstance(result, dict):
        print(json.dumps(result, indent=2, ensure_ascii=False)[:800])
    else:
        print(str(result)[:400])


# 1. Quota / conta
show("GET /v2/user/remaining.quota", *_fetch(f"{BASE}/v2/user/remaining.quota"))

# 2. Avatares
print(f"\n{'='*55}")
print("GET /v2/avatars")
code, result = _fetch(f"{BASE}/v2/avatars")
print(f"HTTP {code}")
if isinstance(result, dict):
    avatars = result.get("data", {}).get("avatars", [])
    print(f"Total: {len(avatars)} avatares\n")
    for av in avatars:
        print(f"  avatar_id: {av.get('avatar_id')}")
        print(f"  Nome:      {av.get('avatar_name')}  |  Tipo: {av.get('type','?')}")
        print()
else:
    print(result)

# 3. Vozes em português
print(f"\n{'='*55}")
code, result = _fetch(f"{BASE}/v2/voices")
print(f"GET /v2/voices → HTTP {code}")
if isinstance(result, dict):
    voices = result.get("data", {}).get("voices", [])
    pt_voices = [
        v for v in voices
        if "portuguese" in v.get("language", "").lower()
        or "brazil" in v.get("name", "").lower()
        or "pt-br" in v.get("language", "").lower()
    ]
    print(f"Vozes PT/BR: {len(pt_voices)} encontradas\n")
    for v in pt_voices:
        print(f"  voice_id: {v.get('voice_id')}")
        print(f"  Nome:     {v.get('name')}  |  Idioma: {v.get('language')}  |  Gênero: {v.get('gender')}")
        print()
else:
    print(result)
