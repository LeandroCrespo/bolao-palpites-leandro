"""Script de diagnóstico D-ID — verifica conta, plano, créditos e avatares."""
import base64
import json
import os
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("DID_API_KEY", "").encode().decode("utf-8-sig").strip().strip("'\"")
email = os.getenv("DID_EMAIL", "").encode().decode("utf-8-sig").strip().strip("'\"")
if not api_key:
    print("DID_API_KEY não encontrada")
    exit(1)

# Detecta formato da chave
try:
    decoded = base64.b64decode(api_key + "==").decode("utf-8", errors="replace")
    if ":" in decoded:
        auth = f"Basic {api_key}"
        print(f"Chave: já codificada em base64 (email detectado no início)")
    else:
        if email:
            auth = "Basic " + base64.b64encode(f"{email}:{api_key}".encode()).decode()
            print(f"Chave: raw — construindo Basic com email")
        else:
            auth = f"Basic {api_key}"
            print(f"Chave: formato indefinido, usando Basic direto")
except Exception:
    auth = f"Basic {api_key}"
    print(f"Chave: erro ao decodificar, usando Basic direto")

BASE = "https://api.d-id.com"
HEADERS = {"Authorization": auth, "Accept": "application/json", "Content-Type": "application/json"}

def _fetch(url, method="GET", body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def show(label, code, result):
    print(f"\n{'='*50}")
    print(f"{label}  →  HTTP {code}")
    if isinstance(result, dict):
        print(json.dumps(result, indent=2, ensure_ascii=False)[:800])
    else:
        print(str(result)[:400])

# 1. Informações da conta
show("GET /user", *_fetch(f"{BASE}/user"))

# 2. Créditos
show("GET /credits", *_fetch(f"{BASE}/credits"))

# 3. Avatares V4 Expressives
show("GET /expressives/avatars", *_fetch(f"{BASE}/expressives/avatars"))

# 4. Clips criados (vídeos já gerados)
show("GET /clips", *_fetch(f"{BASE}/clips"))

# 5. Avatares legados
show("GET /scenes/avatars", *_fetch(f"{BASE}/scenes/avatars"))

# 6. Avatares de talks
show("GET /talks/streams", *_fetch(f"{BASE}/talks/streams"))

# 7. Teste de POST /expressives com avatar público (ver erro exato)
print(f"\n{'='*50}")
print("POST /expressives (teste com avatar público)  →  ", end="")
code, result = _fetch(f"{BASE}/expressives", method="POST", body={
    "avatar_id": "public_amber_casual@avt_PfMblk",
    "script": {"type": "text", "input": "Teste"},
})
print(f"HTTP {code}")
print(str(result)[:400])
