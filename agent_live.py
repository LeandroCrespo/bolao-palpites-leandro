"""
Agente autônomo para atualização de palpites durante a Copa 2026.
Usa Claude API com tool_use — sem intervenção manual.

Uso:
  python agent_live.py              # analisa, atualiza predictions.json e submete
  python agent_live.py --dry-run    # analisa e mostra o que mudaria, sem gravar
"""

import json
import os
import sys
from datetime import datetime

import anthropic
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from fixtures import TEAMS

PREDICTIONS_FILE = "predictions.json"
MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Helpers de banco
# ---------------------------------------------------------------------------

def _engine():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise EnvironmentError("DATABASE_URL não encontrado no .env")
    return create_engine(url)


def _user_id() -> int:
    load_dotenv()
    uid = int(os.getenv("BOLAO_USER_ID", "0"))
    if not uid:
        raise EnvironmentError("BOLAO_USER_ID não definido no .env")
    return uid


# ---------------------------------------------------------------------------
# Ferramentas do agente
# ---------------------------------------------------------------------------

def tool_get_tournament_status() -> dict:
    """Lê do banco os resultados reais e os próximos jogos com palpite ainda aberto."""
    engine = _engine()
    uid = _user_id()

    with engine.connect() as conn:
        completed = conn.execute(text("""
            SELECT match_number, team1_code, team2_code,
                   team1_score, team2_score, phase,
                   CAST(datetime AS VARCHAR)
            FROM matches
            WHERE team1_score IS NOT NULL AND team2_score IS NOT NULL
            ORDER BY match_number
        """)).fetchall()

        upcoming = conn.execute(text("""
            SELECT m.match_number, m.team1_code, m.team2_code,
                   CAST(m.datetime AS VARCHAR), m.phase, m.city,
                   p.pred_team1_score, p.pred_team2_score,
                   CASE WHEN p.locked_at IS NOT NULL THEN true ELSE false END
            FROM matches m
            LEFT JOIN predictions p ON p.match_id = m.id AND p.user_id = :uid
            WHERE m.team1_code IS NOT NULL
              AND m.team1_code NOT LIKE '%%(%'
              AND m.team2_code IS NOT NULL
              AND m.team2_code NOT LIKE '%%(%'
              AND m.status = 'scheduled'
              AND m.datetime > NOW()
            ORDER BY m.match_number
        """), {"uid": uid}).fetchall()

    def tname(code):
        return TEAMS.get(code, {}).get("name", code)

    return {
        "total_completed": len(completed),
        "completed_matches": [
            {
                "match_number": r[0],
                "home_team": r[1],
                "home_name": tname(r[1]),
                "away_team": r[2],
                "away_name": tname(r[2]),
                "home_goals": r[3],
                "away_goals": r[4],
                "phase": r[5],
                "date": str(r[6])[:10],
            }
            for r in completed
        ],
        "upcoming_matches": [
            {
                "match_number": r[0],
                "home_team": r[1],
                "home_name": tname(r[1]),
                "home_fifa_rank": TEAMS.get(r[1], {}).get("fifa_rank"),
                "away_team": r[2],
                "away_name": tname(r[2]),
                "away_fifa_rank": TEAMS.get(r[2], {}).get("fifa_rank"),
                "datetime": str(r[3]),
                "phase": r[4],
                "city": r[5],
                "current_prediction": (
                    f"{r[6]}-{r[7]}" if r[6] is not None else "sem palpite"
                ),
                "locked": bool(r[8]),
            }
            for r in upcoming
            if not r[8]  # só jogos não travados
        ],
    }


def tool_get_current_predictions() -> dict:
    """Lê predictions.json com os palpites atuais."""
    if not os.path.exists(PREDICTIONS_FILE):
        return {"error": f"{PREDICTIONS_FILE} não encontrado. Execute generate_predictions.py primeiro."}
    with open(PREDICTIONS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    # Retorna só o necessário para o agente (evita payload enorme)
    return {
        "generated_at": data.get("generated_at"),
        "podium": data.get("podium"),
        "total_matches": len(data.get("matches", [])),
        "matches_summary": [
            {
                "match_number": m["match_number"],
                "phase": m.get("phase"),
                "home_team": m.get("home_team"),
                "away_team": m.get("away_team"),
                "prediction": f"{m['home_goals']}-{m['away_goals']}",
            }
            for m in data.get("matches", [])
        ],
    }


def tool_update_predictions(new_preds: list, dry_run: bool) -> dict:
    """Atualiza predictions.json e submete ao banco."""
    if not os.path.exists(PREDICTIONS_FILE):
        return {"error": "predictions.json não encontrado"}

    with open(PREDICTIONS_FILE, encoding="utf-8") as f:
        predictions = json.load(f)

    pred_map = {m["match_number"]: m for m in predictions["matches"]}
    updates = []

    for np in new_preds:
        mn = int(np["match_number"])
        hg = int(np["home_goals"])
        ag = int(np["away_goals"])

        if mn in pred_map:
            old = f"{pred_map[mn].get('home_goals')}-{pred_map[mn].get('away_goals')}"
            pred_map[mn]["home_goals"] = hg
            pred_map[mn]["away_goals"] = ag
            if "winner" in np:
                pred_map[mn]["winner"] = np["winner"]
            if "went_to_penalties" in np:
                pred_map[mn]["went_to_penalties"] = np["went_to_penalties"]
            pred_map[mn]["reasoning"] = np.get("reasoning", "Atualizado pelo agente live")
            updates.append({"match_number": mn, "old": old, "new": f"{hg}-{ag}",
                            "reasoning": np.get("reasoning", "")})
        else:
            # Novo jogo do mata-mata (bracket resolvido)
            entry = {
                "match_number": mn,
                "phase": np.get("phase", "KO"),
                "home_team": np.get("home_team", ""),
                "away_team": np.get("away_team", ""),
                "home_goals": hg,
                "away_goals": ag,
                "winner": np.get("winner", ""),
                "went_to_penalties": np.get("went_to_penalties", False),
                "reasoning": np.get("reasoning", "Novo palpite agente live"),
            }
            pred_map[mn] = entry
            updates.append({"match_number": mn, "old": "sem palpite",
                            "new": f"{hg}-{ag}", "reasoning": np.get("reasoning", "")})

    predictions["matches"] = list(pred_map.values())
    predictions["last_updated"] = datetime.now().isoformat()

    if not dry_run:
        with open(PREDICTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(predictions, f, ensure_ascii=False, indent=2)

        from submitter import submit_all
        submit_all(predictions, dry_run=False)

    return {
        "updated_count": len(updates),
        "dry_run": dry_run,
        "updates": updates,
    }


# ---------------------------------------------------------------------------
# Dispatcher de ferramentas
# ---------------------------------------------------------------------------

def execute_tool(name: str, tool_input: dict, dry_run: bool) -> str:
    try:
        if name == "get_tournament_status":
            result = tool_get_tournament_status()
        elif name == "get_current_predictions":
            result = tool_get_current_predictions()
        elif name == "update_predictions":
            result = tool_update_predictions(tool_input["predictions"], dry_run)
        else:
            result = {"error": f"Ferramenta desconhecida: {name}"}
    except Exception as e:
        result = {"error": str(e)}

    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Loop principal do agente
# ---------------------------------------------------------------------------

TOOLS_SCHEMA = [
    {
        "name": "get_tournament_status",
        "description": (
            "Lê do banco os resultados reais de todos os jogos já disputados "
            "e os próximos jogos com times já definidos e palpite ainda aberto. "
            "Use sempre como primeiro passo."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_current_predictions",
        "description": (
            "Lê o predictions.json com os palpites atuais para todos os jogos. "
            "Use para saber o que já está palpitado antes de decidir o que atualizar."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "update_predictions",
        "description": (
            "Atualiza palpites de jogos específicos no predictions.json e submete "
            "automaticamente ao banco PostgreSQL do bolão. "
            "Use após analisar os resultados reais e decidir quais palpites revisar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "predictions": {
                    "type": "array",
                    "description": "Lista de palpites a atualizar",
                    "items": {
                        "type": "object",
                        "properties": {
                            "match_number": {"type": "integer"},
                            "home_team":    {"type": "string"},
                            "away_team":    {"type": "string"},
                            "home_goals":   {"type": "integer"},
                            "away_goals":   {"type": "integer"},
                            "winner": {
                                "type": "string",
                                "description": "Código do vencedor — obrigatório no mata-mata",
                            },
                            "went_to_penalties": {"type": "boolean"},
                            "phase":     {"type": "string"},
                            "reasoning": {
                                "type": "string",
                                "description": "Razão da mudança em 1 linha",
                            },
                        },
                        "required": ["match_number", "home_goals", "away_goals", "reasoning"],
                    },
                }
            },
            "required": ["predictions"],
        },
    },
]

SYSTEM_PROMPT = """Você é um agente especialista em previsões de futebol para o bolão da Copa do Mundo 2026.

Seu objetivo: rever os palpites dos jogos ainda não iniciados com base nos resultados reais do torneio.

PROCESSO:
1. Chame get_tournament_status para ver resultados reais e jogos futuros
2. Chame get_current_predictions para ver os palpites atuais
3. Analise: quais times mostraram forma acima/abaixo do esperado?
4. Decida quais palpites merecem revisão (não precisa mudar tudo — só o que faz sentido)
5. Chame update_predictions com as atualizações

REGRAS:
- Priorize jogos das próximas 48h
- Só atualize palpites que genuinamente mudaram com base nos resultados reais
- Se o palpite inicial ainda faz sentido, mantenha-o
- Para mata-mata: sempre inclua "winner" com o código da seleção vencedora
- Seja específico no reasoning: "Brasil marcou 8 gols em 2 jogos — aumentei a margem"

PONTUAÇÃO (calibre os placares):
- Placar exato: 20 pts — use placares realistas (1-0, 2-0, 2-1, 3-1)
- Resultado certo: 10 pts
- Vale mais um placar específico do que um genérico"""


def run_agent(dry_run: bool = False):
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY não encontrado no .env")

    client = anthropic.Anthropic(api_key=api_key)
    mode = "DRY-RUN" if dry_run else "MODO REAL"
    print(f"\n=== AGENTE LIVE — {mode} ===")
    print(f"Inicio: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")

    messages = [
        {
            "role": "user",
            "content": (
                "Analise o torneio e atualize os palpites necessários. "
                "Siga o processo: status → palpites atuais → analisar → atualizar."
            ),
        }
    ]

    for iteration in range(15):  # limite de segurança
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            tools=TOOLS_SCHEMA,
            messages=messages,
        )

        # Mostra texto intermediário do agente
        for block in response.content:
            if hasattr(block, "text") and block.text.strip():
                print(f"Agente: {block.text.strip()}\n")

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [{block.name}] executando...", end=" ", flush=True)
                    result = execute_tool(block.name, block.input, dry_run)
                    result_data = json.loads(result)
                    # Feedback resumido
                    if block.name == "get_tournament_status":
                        n = result_data.get("total_completed", 0)
                        u = len(result_data.get("upcoming_matches", []))
                        print(f"OK ({n} resultados reais, {u} jogos futuros abertos)")
                    elif block.name == "get_current_predictions":
                        t = result_data.get("total_matches", 0)
                        print(f"OK ({t} palpites carregados)")
                    elif block.name == "update_predictions":
                        n = result_data.get("updated_count", 0)
                        dr = " [DRY-RUN]" if dry_run else ""
                        print(f"OK ({n} palpites atualizados{dr})")
                        for u in result_data.get("updates", []):
                            print(f"    Jogo #{u['match_number']}: {u['old']} -> {u['new']}  |  {u['reasoning']}")
                    else:
                        print("OK")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            print(f"Stop reason inesperado: {response.stop_reason}")
            break

    print(f"\nAgente concluido: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_agent(dry_run=dry_run)
