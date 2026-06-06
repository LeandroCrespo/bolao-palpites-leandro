"""Script temporário para listar avatares criados no D-ID e pegar os IDs."""
import json
import os
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("DID_API_KEY")
if not api_key:
    print("DID_API_KEY não encontrada no .env")
    exit(1)

auth = api_key if api_key.lower().startswith(("basic ", "bearer ")) else f"Basic {api_key}"
req = urllib.request.Request(
    "https://api.d-id.com/avatars",
    headers={"Authorization": auth, "Accept": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
except urllib.error.HTTPError as e:
    print(f"Erro {e.code}: {e.read().decode()}")
    exit(1)

avatars = data if isinstance(data, list) else data.get("avatars", [])
if not avatars:
    print("Nenhum avatar encontrado.")
    exit(0)

print(f"\n{len(avatars)} avatar(es) encontrado(s):\n")
for av in avatars:
    print(f"  ID:   {av.get('id', '?')}")
    print(f"  Nome: {av.get('name', '?')}")
    print(f"  URL:  {av.get('image_url') or av.get('thumbnail_url', '?')}")
    print()
