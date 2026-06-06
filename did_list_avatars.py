"""Script para listar avatares criados no D-ID e verificar nomes disponíveis."""
import base64
import json
import os
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("DID_API_KEY")
email = os.getenv("DID_EMAIL", "")
if not api_key:
    print("DID_API_KEY não encontrada no .env")
    exit(1)

if api_key.lower().startswith(("basic ", "bearer ")):
    auth = api_key
elif email:
    auth = "Basic " + base64.b64encode(f"{email}:{api_key}".encode()).decode()
else:
    auth = f"Basic {api_key}"

def _fetch(url):
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Erro {e.code}: {e.read().decode()}")
        return None

print("\n=== V4 Expressives Avatars (/expressives/avatars) ===")
data = _fetch("https://api.d-id.com/expressives/avatars")
if data is not None:
    avatars = data if isinstance(data, list) else data.get("avatars", [])
    if not avatars:
        print("Nenhum avatar V4 encontrado.")
    else:
        print(f"\n{len(avatars)} avatar(es):\n")
        for av in avatars:
            sentiments = [s.get("name", "?") for s in av.get("sentiments", [])]
            print(f"  ID:         {av.get('id', '?')}")
            print(f"  Nome:       {av.get('name', '?')}")
            print(f"  Sentiments: {', '.join(sentiments) or '(nenhum)'}")
            print()

print("\n=== Avatars legados (/avatars) ===")
data = _fetch("https://api.d-id.com/avatars")
if data is not None:
    avatars = data if isinstance(data, list) else data.get("avatars", [])
    if not avatars:
        print("Nenhum avatar legado encontrado.")
    else:
        print(f"\n{len(avatars)} avatar(es):\n")
        for av in avatars:
            print(f"  ID:   {av.get('id', '?')}")
            print(f"  Nome: {av.get('name', '?')}")
            print(f"  URL:  {av.get('image_url') or av.get('thumbnail_url', '?')}")
            print()
