"""
Motor de simulação: chama Claude API para analisar confrontos e prever placares.
Calcula standings, resolve o bracket e simula o torneio inteiro de forma consistente.
"""

import json
import re
import time
import anthropic

from fixtures import (
    TEAMS, GROUP_STAGE_MATCHES, KNOCKOUT_MATCHES,
    GROUPS, get_group_matches, get_group_teams, team_display
)

MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Utilitários de JSON
# ---------------------------------------------------------------------------

def extract_json(text: str) -> dict:
    """Extrai JSON da resposta do Claude (que às vezes envolve em ```json```)."""
    # Tenta bloco ```json ... ```
    m = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if m:
        return json.loads(m.group(1))

    # Tenta bloco ``` ... ```
    m = re.search(r"```\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Tenta parsear o texto inteiro ou o primeiro objeto JSON
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return json.loads(text[start : end + 1])

    raise ValueError(f"JSON não encontrado na resposta:\n{text[:300]}")


def call_claude(client: anthropic.Anthropic, prompt: str, max_tokens: int = 3000,
                use_web_search: bool = False) -> str:
    """Faz uma chamada ao Claude e retorna o texto. Suporta web search server-side."""
    base_kwargs = dict(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if use_web_search:
        response = client.beta.messages.create(
            **base_kwargs,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            betas=["web-search-2025-03-05"],
        )
    else:
        response = client.messages.create(**base_kwargs)
    last_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            last_text = block.text
    return last_text


# ---------------------------------------------------------------------------
# Cálculo de standings (feito em Python, não por Claude)
# ---------------------------------------------------------------------------

def calculate_standings(group: str, match_predictions: list) -> list:
    """
    Calcula a classificação do grupo a partir dos placares previstos.
    Critérios: pontos > saldo > gols pró.
    """
    teams = get_group_teams(group)
    stats = {
        t: {"points": 0, "gf": 0, "ga": 0, "w": 0, "d": 0, "l": 0}
        for t in teams
    }

    for pred in match_predictions:
        home, away = pred["home_team"], pred["away_team"]
        hg, ag = pred["home_goals"], pred["away_goals"]

        if home not in stats or away not in stats:
            continue

        stats[home]["gf"] += hg
        stats[home]["ga"] += ag
        stats[away]["gf"] += ag
        stats[away]["ga"] += hg

        if hg > ag:
            stats[home]["points"] += 3
            stats[home]["w"] += 1
            stats[away]["l"] += 1
        elif hg < ag:
            stats[away]["points"] += 3
            stats[away]["w"] += 1
            stats[home]["l"] += 1
        else:
            stats[home]["points"] += 1
            stats[away]["points"] += 1
            stats[home]["d"] += 1
            stats[away]["d"] += 1

    standings = [
        {
            "team": t,
            "points": s["points"],
            "gf": s["gf"],
            "ga": s["ga"],
            "gd": s["gf"] - s["ga"],
            "w": s["w"],
            "d": s["d"],
            "l": s["l"],
        }
        for t, s in stats.items()
    ]

    standings.sort(key=lambda x: (-x["points"], -x["gd"], -x["gf"]))
    for i, row in enumerate(standings):
        row["position"] = i + 1

    return standings


# ---------------------------------------------------------------------------
# Previsão dos grupos
# ---------------------------------------------------------------------------

def predict_group(group: str, client: anthropic.Anthropic, retries: int = 3) -> dict:
    """
    Usa Claude para prever os 6 jogos do grupo.
    Retorna dict com matches, standings (calculados em Python), first, second, third.
    """
    matches = get_group_matches(group)
    teams = get_group_teams(group)

    teams_block = "\n".join(f"  {team_display(c)}" for c in teams)
    matches_block = "\n".join(
        f"  Jogo {m[0]}: {TEAMS[m[2]]['name']} ({m[2]}) x {TEAMS[m[3]]['name']} ({m[3]})"
        f" — {m[4]} {m[5]} em {m[6]}"
        for m in matches
    )

    # Monta lista de objetos vazios para guiar o formato
    matches_template = ",\n    ".join(
        f'{{"match_number": {m[0]}, "home_team": "{m[2]}", "away_team": "{m[3]}", '
        f'"home_goals": 0, "away_goals": 0, "reasoning": "..."}}'
        for m in matches
    )

    prompt = f"""Você é um analista expert em futebol internacional, fazendo previsões para a Copa do Mundo 2026 (sede: EUA, Canadá, México).

IMPORTANTE: Antes de prever os placares, pesquise na web informações atuais sobre as seleções deste grupo:
- Lesões e suspensões de titulares confirmadas
- Forma recente (últimos 2-3 jogos antes da Copa)
- Qualquer notícia relevante pré-Copa 2026 (convocações de última hora, problemas físicos)
Use essas informações para calibrar seus palpites com dados reais de junho de 2026.

GRUPO {group}:
{teams_block}

JOGOS DO GRUPO {group}:
{matches_block}

CONTEXTO IMPORTANTE:
• Argentina: campeã Copa 2022 e Copa América 2024 — melhor seleção do mundo
• Espanha: campeã Euro 2024, FIFA #1 — futebol de posse e qualidade técnica excepcional
• França: vice Copa 2022 — potência com Mbappé e elenco profundo
• Inglaterra: final Euro 2024 (perdeu nos pênaltis para Espanha) — Salah, Bellingham
• Brasil: eliminado quartas Copa 2022 — favorito com Vinicius Jr., Rodrygo, Endrick
• Marrocos: semifinalista Copa 2022 (maior feito da África) — defensivamente muito sólido
• Colômbia: vice Copa América 2024 — em excelente fase
• EUA e México: fator casa (torcida, clima, pressão local)
• Seleções de repescagem (EUR_A, EUR_B, EUR_C, EUR_D, INT_1, INT_2): qualidade incerta, média a baixa

ESTRATÉGIA DE PONTUAÇÃO DO BOLÃO (calibre seus placares):
• Placar exato = 20 pts → use placares realistas como 1-0, 2-0, 2-1, 1-1, 3-1
• Resultado + gols de 1 time = 15 pts
• Acertar só o vencedor/empate (mesmo com gols errados) = 10 pts
• Errar o vencedor/empate = 0 pts, mesmo que os gols fiquem próximos
• Favorito claro (Tier 1-2 vs Tier 4-5): vença por 2-3 gols
• Confronto equilibrado (mesmo tier): 1 gol de diferença ou empate
• PRIORIDADE: em caso de dúvida, proteja a DIREÇÃO do resultado (vitória/
  empate/derrota) antes de "arredondar" para um placar bonito — um placar
  exato errado mas com a direção certa garante 10-15 pts; um empate "1-1"
  escolhido só por parecer plausível, quando a evidência aponta levemente
  para um dos lados, arrisca 0 pts se a direção estiver errada
• Evite placares genéricos repetidos (todo jogo 1-0)

Retorne SOMENTE o JSON abaixo preenchido (sem texto extra, sem markdown):
{{
  "group": "{group}",
  "matches": [
    {matches_template}
  ],
  "group_analysis": "Análise do grupo em 2-3 frases explicando o contexto e os classificados prováveis."
}}"""

    last_error = None
    for attempt in range(retries):
        try:
            text = call_claude(client, prompt, max_tokens=2500, use_web_search=True)
            result = extract_json(text)

            # Valida estrutura
            if "matches" not in result or len(result["matches"]) != len(matches):
                raise ValueError(
                    f"Esperava {len(matches)} jogos, recebi {len(result.get('matches', []))}"
                )

            # Valida campos obrigatórios
            for mp in result["matches"]:
                for field in ("match_number", "home_team", "away_team", "home_goals", "away_goals"):
                    if field not in mp:
                        raise ValueError(f"Campo '{field}' faltando em {mp}")
                # Garante inteiros
                mp["home_goals"] = int(mp["home_goals"])
                mp["away_goals"] = int(mp["away_goals"])

            # Calcula standings em Python (confiável, determinístico)
            standings = calculate_standings(group, result["matches"])
            result["standings"] = standings
            result["first"] = standings[0]["team"]
            result["second"] = standings[1]["team"]
            result["third"] = standings[2]["team"] if len(standings) >= 3 else None

            return result

        except Exception as e:
            last_error = e
            print(f"    Tentativa {attempt + 1}/{retries} falhou: {e}")
            if attempt < retries - 1:
                wait = 65 if ("429" in str(e) or "rate_limit" in str(e)) else 5
                print(f"    Aguardando {wait}s antes de tentar novamente...")
                time.sleep(wait)

    raise RuntimeError(
        f"Nao foi possivel prever o Grupo {group} apos {retries} tentativas. "
        f"Ultimo erro: {last_error}"
    )


# ---------------------------------------------------------------------------
# Qualificação de 3ºs lugares para a Fase de 32
# ---------------------------------------------------------------------------

def get_third_place_qualifiers(all_group_results: dict) -> list:
    """
    Dos 12 times em 3º lugar (um por grupo), os melhores 8 avançam para a Fase de 32.
    Critério: pontos > saldo > gols pró.
    """
    thirds = []
    for group, result in all_group_results.items():
        standings = result["standings"]
        if len(standings) >= 3:
            t = standings[2]
            thirds.append(
                {
                    "team": t["team"],
                    "group": group,
                    "points": t["points"],
                    "gd": t["gd"],
                    "gf": t["gf"],
                }
            )

    thirds.sort(key=lambda x: (-x["points"], -x["gd"], -x["gf"]))
    return thirds[:8]  # Os 8 melhores classificam


# ---------------------------------------------------------------------------
# Resolução do bracket
# ---------------------------------------------------------------------------

def resolve_slot(slot: str, group_results: dict, third_qualifiers: list,
                 match_winners: dict) -> str:
    """
    Traduz um código de slot do bracket para o código da seleção:
    "1A" → 1º do Grupo A
    "2B" → 2º do Grupo B
    "3CDF" → melhor 3º entre grupos C, D, F que classificou
    "W73" → vencedor do jogo 73
    "L101" → perdedor do jogo 101 (usado na disputa de 3º lugar)
    """
    # "1A" ou "2B"
    if len(slot) == 2 and slot[0] in "12" and slot[1] in "ABCDEFGHIJKL":
        pos, grp = slot[0], slot[1]
        if grp not in group_results:
            return f"?({slot})"
        return group_results[grp]["first" if pos == "1" else "second"]

    # "3CDF" → melhor 3º dos grupos C, D e F que classificou
    if slot.startswith("3") and len(slot) >= 4:
        eligible_groups = list(slot[1:])
        candidates = [t for t in third_qualifiers if t["group"] in eligible_groups]
        if candidates:
            return candidates[0]["team"]
        # Fallback: melhor 3º geral (não deveria acontecer em simulações normais)
        return third_qualifiers[0]["team"] if third_qualifiers else f"?({slot})"

    # "W73" → vencedor do jogo 73
    if slot.startswith("W"):
        match_num = int(slot[1:])
        return match_winners.get(match_num, {}).get("winner", f"?({slot})")

    # "L101" → perdedor do jogo 101
    if slot.startswith("L"):
        match_num = int(slot[1:])
        return match_winners.get(match_num, {}).get("loser", f"?({slot})")

    return slot


# ---------------------------------------------------------------------------
# Simulação do mata-mata
# ---------------------------------------------------------------------------

def simulate_knockout_round(
    round_name: str,
    round_matches: list,
    group_results: dict,
    third_qualifiers: list,
    match_winners: dict,
    client: anthropic.Anthropic,
    retries: int = 3,
) -> list:
    """
    Simula uma fase do mata-mata (R32, R16, QF, SF, 3RD, FINAL).
    Resolve os slots, chama Claude para os placares e atualiza match_winners.
    Retorna lista de dicts com os resultados.
    """
    round_labels = {
        "R32": "Fase de 32", "R16": "Oitavas de Final",
        "QF": "Quartas de Final", "SF": "Semifinais",
        "3RD": "Disputa de 3º Lugar", "FINAL": "Final",
    }
    round_label = round_labels.get(round_name, round_name)

    # Resolve quem joga em cada partida
    resolved = []
    for m in round_matches:
        home_code = resolve_slot(m[2], group_results, third_qualifiers, match_winners)
        away_code = resolve_slot(m[3], group_results, third_qualifiers, match_winners)
        resolved.append({
            "match_number": m[0],
            "home_team": home_code,
            "away_team": away_code,
            "date": m[4],
            "city": m[6],
            "slot_home": m[2],
            "slot_away": m[3],
        })

    matches_block = "\n".join(
        f"  Jogo {r['match_number']}: {TEAMS.get(r['home_team'], {}).get('name', r['home_team'])} "
        f"({r['home_team']}, FIFA #{TEAMS.get(r['home_team'], {}).get('fifa_rank', '?')}) x "
        f"{TEAMS.get(r['away_team'], {}).get('name', r['away_team'])} "
        f"({r['away_team']}, FIFA #{TEAMS.get(r['away_team'], {}).get('fifa_rank', '?')}) "
        f"— {r['date']} em {r['city']}"
        for r in resolved
    )

    matches_template = ",\n    ".join(
        f'{{"match_number": {r["match_number"]}, "home_team": "{r["home_team"]}", '
        f'"away_team": "{r["away_team"]}", "home_goals": 0, "away_goals": 0, '
        f'"winner": "{r["home_team"]}", "went_to_penalties": false, "reasoning": "..."}}'
        for r in resolved
    )

    prompt = f"""Você é um analista expert em futebol. Copa do Mundo 2026 — {round_label}.

JOGOS:
{matches_block}

No mata-mata, os jogos tendem a ser mais fechados do que na fase de grupos.
Times favoritos vencem por 1-2 gols. Confrontos equilibrados frequentemente vão a pênaltis.
PRIORIDADE DE PONTUAÇÃO: entre dois placares igualmente plausíveis, escolha o
que preserva a direção do resultado que você considera mais provável (vitória/
empate/derrota) — isso garante pontuação parcial mesmo se o placar exato
errar; não escolha um empate "para arredondar" se a evidência apontar
levemente para um favorito.

Para cada jogo:
• Preveja o placar nos 90 minutos (ou após prorrogação se empate)
• Se empate nos 90 min: indique "went_to_penalties": true e quem venceu em "winner"
• "winner" DEVE conter o código da seleção vencedora (ex: "BRA", "ESP", "ARG")

Retorne SOMENTE o JSON (sem texto extra):
{{
  "round": "{round_name}",
  "matches": [
    {matches_template}
  ]
}}"""

    last_error = None
    for attempt in range(retries):
        try:
            text = call_claude(client, prompt, max_tokens=3000)
            result = extract_json(text)

            if "matches" not in result:
                raise ValueError("Campo 'matches' ausente na resposta")

            if len(result["matches"]) != len(round_matches):
                raise ValueError(
                    f"Esperava {len(round_matches)} jogos, recebi {len(result['matches'])}"
                )

            # Processa resultados e atualiza match_winners
            results = []
            for i, mp in enumerate(result["matches"]):
                match_num = mp.get("match_number", round_matches[i][0])
                home = mp.get("home_team", resolved[i]["home_team"])
                away = mp.get("away_team", resolved[i]["away_team"])
                winner = mp.get("winner", "")

                # Valida winner
                if winner not in (home, away):
                    # Tenta inferir pelo placar
                    hg = int(mp.get("home_goals", 0))
                    ag = int(mp.get("away_goals", 0))
                    winner = home if hg >= ag else away

                loser = away if winner == home else home

                match_winners[match_num] = {"winner": winner, "loser": loser}

                results.append({
                    "match_number": match_num,
                    "home_team": home,
                    "away_team": away,
                    "home_goals": int(mp.get("home_goals", 0)),
                    "away_goals": int(mp.get("away_goals", 0)),
                    "winner": winner,
                    "loser": loser,
                    "went_to_penalties": bool(mp.get("went_to_penalties", False)),
                    "reasoning": mp.get("reasoning", ""),
                })

            return results

        except Exception as e:
            last_error = e
            print(f"    Tentativa {attempt + 1}/{retries} falhou: {e}")
            if attempt < retries - 1:
                time.sleep(3)

    raise RuntimeError(
        f"Falha ao simular {round_label} após {retries} tentativas. Erro: {last_error}"
    )


# ---------------------------------------------------------------------------
# Simulação completa do torneio
# ---------------------------------------------------------------------------

def simulate_full_tournament(client: anthropic.Anthropic) -> dict:
    """
    Executa a simulação completa e consistente do torneio:
    1. Grupos (12 calls) → standings + classificados
    2. Determina 8 melhores 3ºs
    3. Mata-mata fase a fase (R32 → Final + 3º lugar)

    Retorna o dicionário completo de previsões.
    """
    print("\n=== FASE DE GRUPOS ===")
    group_results = {}
    all_match_predictions = {}  # match_number → {home_team, away_team, home_goals, away_goals}

    for group in GROUPS:
        print(f"  Analisando Grupo {group}...", end=" ", flush=True)
        result = predict_group(group, client)
        group_results[group] = result

        for mp in result["matches"]:
            all_match_predictions[mp["match_number"]] = mp

        first = TEAMS.get(result["first"], {}).get("name", result["first"])
        second = TEAMS.get(result["second"], {}).get("name", result["second"])
        print(f"OK  (1o {first}, 2o {second})")
        time.sleep(15)  # Respeita rate limit (web search usa mais tokens)

    print("\n=== QUALIFICAÇÃO DOS 3ºs LUGARES ===")
    third_qualifiers = get_third_place_qualifiers(group_results)
    print("  Top 8 classificados em 3º lugar:")
    for i, t in enumerate(third_qualifiers, 1):
        name = TEAMS.get(t["team"], {}).get("name", t["team"])
        print(f"    {i}. {name} (Grupo {t['group']}) — {t['points']} pts, SG {t['gd']:+d}")

    print("\n=== MATA-MATA ===")
    match_winners = {}  # match_number → {winner, loser}
    knockout_results = {}

    # Fase de 32 ao FINAL por fase
    phases = ["R32", "R16", "QF", "SF"]
    phase_labels = {
        "R32": "Fase de 32", "R16": "Oitavas de Final",
        "QF": "Quartas de Final", "SF": "Semifinais",
    }

    for phase in phases:
        matches_in_phase = [m for m in KNOCKOUT_MATCHES if m[1] == phase]
        print(f"  Simulando {phase_labels[phase]}...", end=" ", flush=True)
        results = simulate_knockout_round(
            phase, matches_in_phase, group_results,
            third_qualifiers, match_winners, client
        )
        knockout_results[phase] = results

        # Registra placares no mapa geral
        for r in results:
            all_match_predictions[r["match_number"]] = r

        print("OK")
        time.sleep(10)

    # 3º lugar e Final
    for phase in ["3RD", "FINAL"]:
        matches_in_phase = [m for m in KNOCKOUT_MATCHES if m[1] == phase]
        label = "Disputa de 3º Lugar" if phase == "3RD" else "Final"
        print(f"  Simulando {label}...", end=" ", flush=True)
        results = simulate_knockout_round(
            phase, matches_in_phase, group_results,
            third_qualifiers, match_winners, client
        )
        knockout_results[phase] = results
        for r in results:
            all_match_predictions[r["match_number"]] = r
        print("OK")
        time.sleep(10)

    # Extrai pódio
    final_result = knockout_results["FINAL"][0]
    third_result = knockout_results["3RD"][0]

    champion = final_result["winner"]
    runner_up = final_result["loser"]
    third = third_result["winner"]

    champion_name = TEAMS.get(champion, {}).get("name", champion)
    runner_up_name = TEAMS.get(runner_up, {}).get("name", runner_up)
    third_name = TEAMS.get(third, {}).get("name", third)

    print(f"\n=== PÓDIO PREVISTO ===")
    print(f"  [1] Campeao:       {champion_name} ({champion})")
    print(f"  [2] Vice-Campeao:  {runner_up_name} ({runner_up})")
    print(f"  [3] 3o Lugar:      {third_name} ({third})")

    return {
        "group_results": group_results,
        "third_qualifiers": third_qualifiers,
        "knockout_results": knockout_results,
        "all_match_predictions": all_match_predictions,
        "podium": {
            "champion": champion,
            "runner_up": runner_up,
            "third": third,
        },
    }
