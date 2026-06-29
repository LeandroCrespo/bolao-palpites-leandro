"""
Analisa e submete palpites para todos os jogos R32 ainda não iniciados.
Usa o mesmo motor de _focused_pregame_eval do agente pré-jogo, mas sem
a restrição de janela de 40 minutos.

Segurança:
  - submit_match_prediction() chama can_predict_match() internamente
  - can_predict_match() bloqueia jogos com status != 'scheduled'
  - Só grava para BOLAO_USER_ID (user_id=15)
  - Nenhum outro usuário é tocado
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import anthropic
import pytz
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()
for _var in ("ANTHROPIC_API_KEY", "DATABASE_URL", "BOLAO_USER_ID",
             "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
    _val = os.environ.get(_var, "")
    if _val:
        os.environ[_var] = _val.encode().decode("utf-8-sig").strip().strip("'\"")

from agent_live import _focused_pregame_eval, _engine, TEAMS
from submitter import submit_match_prediction, can_predict_match, get_match_id

tz = pytz.timezone("America/Sao_Paulo")
now = datetime.now(tz).replace(tzinfo=None)
user_id = int(os.environ.get("BOLAO_USER_ID", "15"))

engine = _engine()
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT m.match_number, m.team1_code, m.team2_code,
               CAST(m.datetime AS VARCHAR), m.id,
               p.pred_team1_score, p.pred_team2_score
        FROM matches m
        LEFT JOIN predictions p ON p.match_id = m.id AND p.user_id = :uid
        WHERE m.phase = 'R32'
          AND m.status = 'scheduled'
          AND m.team1_id IS NOT NULL AND m.team1_code NOT LIKE '%%(%'
          AND m.team2_id IS NOT NULL AND m.team2_code NOT LIKE '%%(%'
        ORDER BY m.datetime
    """), {"uid": user_id}).fetchall()

if not rows:
    print("Nenhum jogo R32 disponível para análise.")
    sys.exit(0)

def tname(code):
    return TEAMS.get(code, {}).get("name", code)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

print(f"\n{'='*60}")
print(f"ANÁLISE R32 — {len(rows)} jogos — user_id={user_id}")
print(f"{'='*60}\n")

for mn, c1, c2, dt, match_id, p1, p2 in rows:
    home, away = tname(c1), tname(c2)
    kickoff = datetime.strptime(str(dt)[:19], "%Y-%m-%d %H:%M:%S")
    mins_left = max(1, round((kickoff - now).total_seconds() / 60))

    # Verifica se o jogo ainda está aberto para palpite
    with engine.connect() as conn:
        aberto = can_predict_match(conn, match_id)

    if not aberto:
        print(f"#{mn:3d} {home} x {away} — TRAVADO (jogo iniciado ou encerrado), pulando.")
        continue

    print(f"#{mn:3d} {home} x {away} ({kickoff.strftime('%d/%m %H:%M')}, {mins_left} min)")
    print(f"       Palpite atual: {p1}x{p2}")
    print(f"       Analisando com web search...", flush=True)

    res = _focused_pregame_eval(
        client, home, away, str(dt)[:16],
        p1 or 0, p2 or 0,
        mins_left=mins_left
    )

    nh, na = res["nh"], res["na"]
    razao = res.get("razao", "")

    print(f"       -> Novo palpite: {nh}x{na}  |  {razao}")

    with engine.begin() as conn:
        resultado = submit_match_prediction(conn, user_id, mn, nh, na)
    if "OK" in (resultado or ""):
        print(f"       OK Salvo no banco.")
    else:
        print(f"       AVISO: {resultado}")
    print()

print("Análise R32 concluída.")
