"""
Orquestrador: executa a simulação completa e salva predictions.json.
"""

import json
import os
from datetime import datetime

import anthropic
from dotenv import load_dotenv

from simulator import simulate_full_tournament
from fixtures import TEAMS, GROUP_STAGE_MATCHES, GROUPS

PREDICTIONS_FILE = "predictions.json"


def run_analysis() -> dict:
    """Executa a simulação e salva predictions.json. Retorna o resultado."""
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY não encontrada no .env")

    client = anthropic.Anthropic(api_key=api_key)

    print("Copa do Mundo 2026 — Motor de Previsão")
    print("=" * 50)
    print(f"Iniciando análise em {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    result = simulate_full_tournament(client)

    # Monta predictions.json
    predictions = {
        "generated_at": datetime.now().isoformat(),
        "matches": [],
        "groups": {},
        "podium": result["podium"],
        "third_qualifiers": result["third_qualifiers"],
    }

    # Jogos da fase de grupos
    for m in GROUP_STAGE_MATCHES:
        pred = result["all_match_predictions"].get(m[0])
        if pred:
            predictions["matches"].append({
                "match_number": m[0],
                "phase": "Groups",
                "group": m[1],
                "home_team": m[2],
                "away_team": m[3],
                "date": m[4],
                "home_goals": pred["home_goals"],
                "away_goals": pred["away_goals"],
                "reasoning": pred.get("reasoning", ""),
            })

    # Jogos do mata-mata
    for phase, phase_results in result["knockout_results"].items():
        for r in phase_results:
            predictions["matches"].append({
                "match_number": r["match_number"],
                "phase": phase,
                "home_team": r["home_team"],
                "away_team": r["away_team"],
                "home_goals": r["home_goals"],
                "away_goals": r["away_goals"],
                "winner": r.get("winner"),
                "went_to_penalties": r.get("went_to_penalties", False),
                "reasoning": r.get("reasoning", ""),
            })

    # Classificatórios dos grupos
    for group in GROUPS:
        gr = result["group_results"][group]
        predictions["groups"][group] = {
            "first": gr["first"],
            "second": gr["second"],
            "third": gr.get("third"),
            "standings": gr["standings"],
            "analysis": gr.get("group_analysis", ""),
        }

    # Salva em disco
    with open(PREDICTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)

    total_matches = len(predictions["matches"])
    print(f"\nPrevisões salvas em {PREDICTIONS_FILE}")
    print(f"  Total de jogos previstos: {total_matches}")
    print(f"  Grupos com classificados: {len(predictions['groups'])}")
    print(f"  Pódio: {result['podium']}")

    return predictions


def load_predictions() -> dict:
    """Carrega predictions.json do disco."""
    if not os.path.exists(PREDICTIONS_FILE):
        raise FileNotFoundError(
            f"{PREDICTIONS_FILE} não encontrado. Execute 'python main.py analyze' primeiro."
        )
    with open(PREDICTIONS_FILE, encoding="utf-8") as f:
        return json.load(f)
