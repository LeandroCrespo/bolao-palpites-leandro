"""
Agente autônomo para atualização de palpites durante a Copa 2026.
Usa Claude API com tool_use — sem intervenção manual.

Uso:
  python agent_live.py              # analisa, atualiza predictions.json e submete
  python agent_live.py --dry-run    # analisa e mostra o que mudaria, sem gravar
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta

import anthropic
import pytz
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from fixtures import TEAMS

PREDICTIONS_FILE = "predictions.json"
MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Notificação Telegram
# ---------------------------------------------------------------------------

def send_telegram(token: str, chat_id: str, text: str):
    """Envia mensagem via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  Telegram: falha ao enviar ({e})")


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


def _model_recommendations():
    """Recomendações do modelo estatístico calibrado (model_palpites.py) para
    os jogos ainda não iniciados com ambos os times definidos.

    O modelo (Poisson/Dixon-Coles com calibração de escala) foi validado em
    backtest walk-forward nos 97 jogos já disputados desta Copa: 1015 pts
    contra 975 do melhor participante humano.

    Retorna (texto_geral, por_jogo) onde por_jogo mapeia match_number -> bloco
    de texto. Em qualquer erro retorna ("", {}) e o agente segue sem âncora.
    """
    try:
        import numpy as _np
        from model_palpites import (
            load_data, build_model, predict, ev_palpites, CODE_TO_NAME, ALIASES,
        )
        engine = _engine()
        rows = load_data(engine)
        model = build_model(rows, protect=set(CODE_TO_NAME.values()))

        with engine.connect() as conn:
            pend = conn.execute(text("""
                SELECT m.match_number, m.team1_code, m.team2_code
                FROM matches m
                WHERE m.status = 'scheduled'
                  AND m.team1_id IS NOT NULL AND m.team2_id IS NOT NULL
                ORDER BY m.match_number
            """)).fetchall()

        def _resolve(code):
            cands = ([CODE_TO_NAME[code]] if code in CODE_TO_NAME else []) + ALIASES.get(code, [])
            for cand in cands:
                if cand in model["idx"]:
                    return cand
            return None

        por_jogo, linhas = {}, []
        for mn, c1, c2 in pend:
            n1, n2 = _resolve(c1), _resolve(c2)
            if not n1 or not n2:
                continue
            P, _l1, _l2 = predict(model, n1, n2)
            pv1 = float(_np.tril(P, -1).sum())
            pe = float(_np.trace(P))
            pv2 = float(_np.triu(P, 1).sum())
            top = ev_palpites(P, top=5)
            (ba, bb), _ = top[0]
            picks = " | ".join(f"{a}x{b} (EV {ev:.1f})" for (a, b), ev in top)
            bloco = (
                f"#{mn} {c1} x {c2}: P({c1})={pv1:.0%} empate={pe:.0%} P({c2})={pv2:.0%}. "
                f"PLACAR ÂNCORA: {ba}x{bb}. Top-5 por EV: {picks}"
            )
            por_jogo[mn] = bloco
            linhas.append("  " + bloco)
        return ("\n".join(linhas), por_jogo)
    except Exception as e:
        print(f"[modelo] indisponível ({e}) — seguindo sem âncora estatística")
        return ("", {})


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
            placar_mudou = old != f"{hg}-{ag}"
            pred_map[mn]["home_goals"] = hg
            pred_map[mn]["away_goals"] = ag
            if "winner" in np:
                pred_map[mn]["winner"] = np["winner"]
            if "went_to_penalties" in np:
                pred_map[mn]["went_to_penalties"] = np["went_to_penalties"]
            pred_map[mn]["reasoning"] = np.get("reasoning", "Atualizado pelo agente live")
            # Só conta como atualização (log + Telegram) se o PLACAR mudou.
            # Reconfirmar o mesmo placar (só reasoning) não polui a notificação.
            if placar_mudou:
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
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 20,
    },
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
                                "description": (
                                    "Justificativa COMPLETA do palpite (3-5 frases): média de "
                                    "gols feitos/sofridos dos DOIS times em números, retrospecto "
                                    "recente, desfalques confirmados se houver, o placar âncora "
                                    "do modelo estatístico e o argumento central da decisão"
                                ),
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

Seu objetivo: rever os palpites dos jogos ainda não iniciados com base nos resultados reais e em informações atuais.

⚠️ REGRA MAIS IMPORTANTE DESTE PROMPT — AMOSTRA NUNCA SÓ DA COPA: como a fase
de grupos da Copa 2026 só tem 3 jogos (e agora pouco depois do início, só 2),
usar SÓ os jogos da Copa de cada seleção é SEMPRE uma amostra pequena demais
e SEMPRE proibido. Em TODA seleção que você analisar, é OBRIGATÓRIO buscar
também os jogos de ANTES da Copa (eliminatórias, amistosos, continentais —
use web_search "[Time] amistosos eliminatorias resultados antes da copa
2026") até reunir pelo menos 6 jogos no total. Se na sua resposta a média de
gols de algum time vier de "2 jogos" ou "3 jogos", isso é um ERRO de
processo — pare, busque mais jogos daquele time, e só then calcule a média.

PROCESSO:
1. Chame get_tournament_status para ver resultados reais e jogos futuros
2. Para cada jogo nas próximas 48h, use web_search para montar uma visão AMPLA
   de cada seleção (não se baseie em um único fator). Pesquise SEMPRE estas
   buscas, nesta ordem, pras DUAS seleções do confronto:
   - Desfalques: "[Time A] [Time B] Copa do Mundo 2026 lesoes suspensoes"
   - Jogos DESTA Copa: "[Time] Copa do Mundo 2026 resultados"
   - OBRIGATÓRIO — jogos de ANTES da Copa (não pule esta busca mesmo se já
     tiver os jogos da Copa): "[Time] amistosos eliminatorias resultados
     antes da copa 2026"
   - Estatísticas ofensivas/defensivas: "[Time] xG gols esperados estatisticas recentes"
   - Confronto direto: "[Time A] x [Time B] historico confronto direto"
   Junte os jogos da Copa COM os jogos de antes (até reunir pelo menos 6 no
   total, mais recentes primeiro) e estime a MÉDIA DE GOLS MARCADOS, a MÉDIA
   DE GOLS SOFRIDOS e o xG (gols esperados) por jogo de cada seleção sobre
   essa amostra combinada (ver item 4 da PONDERAÇÃO) — calculada a partir
   dos resultados das buscas acima, sem precisar de uma busca adicional só
   pra isso.
3. Chame get_current_predictions para ver os palpites atuais
4. Analise cruzando TODOS os fatores → o que mudou em relação ao palpite inicial?
5. OBRIGATÓRIO: chame update_predictions A CADA GRUPO analisado (ou a cada
   2-3 jogos), em vez de acumular tudo pra uma única chamada gigante no
   final. Ex.: termine a análise do Grupo A → chame update_predictions já
   com as mudanças do Grupo A → siga pro Grupo B → chame de novo. Isso evita
   perder TODAS as decisões do dia se a resposta for cortada por limite de
   tokens no meio da análise de um grupo mais tarde (já aconteceu: a análise
   ficou ótima, mas nada foi salvo porque a chamada da ferramenta só viria
   no final, que nunca chegou). Escrever a análise em texto NÃO altera
   nada — só a chamada da ferramenta aplica. Se, após analisar TUDO, nenhum
   palpite precisa mudar, aí sim pode encerrar sem chamar a ferramenta,
   dizendo explicitamente "nenhum ajuste necessário".

PONDERAÇÃO (peso dos fatores, do maior para o menor):
1) Forma recente e MOMENTUM: os ~6 a 10 jogos MAIS RECENTES de cada seleção,
   somando TODAS as competições — Copa 2026, eliminatórias, amistosos,
   continentais — TODAS com o MESMO peso entre si. Os jogos desta Copa 2026
   NÃO recebem peso especial só por serem da Copa; entram na análise como
   qualquer outro jogo recente. O que determina o peso de cada jogo é
   exclusivamente quão RECENTE ele é, nunca a competição. PRIORIZE SEMPRE os
   jogos MAIS RECENTES — um bom começo de 2025 vale pouco se a seleção caiu de
   produção agora; o que importa é o MOMENTO ATUAL, olhando o conjunto
   completo de jogos recentes.
   AMOSTRA MÍNIMA OBRIGATÓRIA: se a seleção jogou menos de 6 jogos NESTA Copa
   2026 até agora (o normal, já que a fase de grupos tem só 3), é OBRIGATÓRIO
   completar a amostra com jogos de ANTES da Copa (eliminatórias, amistosos,
   continentais) até reunir pelo menos 6 jogos no total. NUNCA calcule a
   "forma recente" ou a média de gols usando só 1-2 jogos — isso não é uma
   amostra confiável, é ruído (ex.: 1 jogo isolado com gols sofridos por
   lesão não representa a defesa real da seleção).
2) Disponibilidade de elenco: desfalques de titulares (lesões/suspensões)
3) Confronto direto / histórico recente — fator menor, para desempate
4) Métricas ofensivas/defensivas dos MESMOS jogos recentes do item 1: média de
   gols marcados, média de gols sofridos, e xG (gols esperados) quando
   disponível — use para calibrar a MAGNITUDE do placar (não a direção). Esse
   cálculo usa os mesmos jogos recentes do item 1, sem peso especial pra
   jogos da Copa; jogos antigos (fora da janela de ~6-10 mais recentes) não
   entram na média.
(O ranking FIFA do get_tournament_status é só referência leve de força, como antes.)
IMPORTANTE: priorize SEMPRE os jogos MAIS RECENTES, de QUALQUER competição, sem dar
peso extra à Copa; um desfalque isolado ou 1-2 jogos recentes NÃO devem dominar a
previsão — pondere contra o momentum recente completo e o retrospecto.

REGRAS:
- Priorize jogos das próximas 48h
- Só atualize palpites com base em evidências reais (resultados ou notícias encontradas)
- Se o palpite inicial ainda faz sentido depois de cruzar os fatores, mantenha-o
- Para mata-mata: sempre inclua "winner" com o código da seleção vencedora
- Reasoning COMPLETO citando os principais fatores, não apenas um, e SEMPRE
  com a média de gols feitos/sofridos por jogo dos DOIS times em números
  (ex.: "Marrocos tem média de 1,8 gols feitos e 0,6 sofridos, Brasil tem 2,2
  feitos e 1,0 sofridos"). Ex. completo:
  "Marrocos com 2 desfalques na defesa, mas vem de 4 vitorias (1,8 gols feitos
  e 0,6 sofridos por jogo); Brasil em alta (2,2 feitos e 1,0 sofridos) — mantenho
  favoritismo do Brasil, ajusto 2-1"
- O reasoning vai DENTRO da chamada update_predictions (campo reasoning), não
  como texto solto. Decidiu mudar → chame a ferramenta.

PONTUACAO (calibre os placares):
- Placar exato: 20 pts — use placares realistas
- Resultado certo (vencedor/empate), mesmo com gols errados: 10 pts
- Errar a direção do resultado: 0 pts, independente dos gols
- SEM teto fixo de gols por time — esta Copa está com média de ~3 gols por
  jogo e vários resultados elásticos (3x0, 4x1, 7x1). Se a média de gols
  marcados/sofridos e o xG (item 4 da PONDERAÇÃO) e o favoritismo claramente
  sustentarem um placar elástico, pode prever — mas não infle o placar sem
  essa evidência (placares "estourados" sem base seguem improváveis)
- Ao reavaliar, se as evidencias forem mistas/incertas, priorize manter ou
  ajustar para a direcao de resultado mais sustentada pelos dados — nao troque
  o placar so para "acertar mais em cheio" se isso arriscar virar a direcao do
  resultado sem evidencia forte

MODELO ESTATÍSTICO (ÂNCORA DE PLACAR — REGRA PRIORITÁRIA):
Quando a mensagem do usuário contiver um bloco "MODELO ESTATÍSTICO VALIDADO",
ele traz, para cada jogo, as probabilidades e o PLACAR ÂNCORA calculados por um
modelo Poisson/Dixon-Coles calibrado que, em backtest honesto nos 97 jogos já
disputados desta Copa, superou TODOS os participantes do bolão (1015 pts contra
975 do líder). Nesse caso:
1. O PLACAR ÂNCORA do modelo é o palpite padrão de cada jogo — adote-o.
2. Sua pesquisa web serve para VALIDAR a direção e detectar fatos que o modelo
   não vê: desfalque confirmado de titular-chave, suspensão, crise interna.
3. Só desvie do placar âncora com evidência FORTE e CONFIRMADA — e mesmo
   assim escolha outro placar DENTRO do Top-5 por EV listado para o jogo.
4. NUNCA dê palpite fora do Top-5 por EV do modelo.
5. No reasoning, cite que o placar segue o modelo estatístico e acrescente os
   fatores qualitativos encontrados na pesquisa."""


def run_agent(dry_run: bool = False):
    load_dotenv()

    # Limpa BOM e aspas dos secrets (problema comum em GitHub Actions)
    for _var in ("ANTHROPIC_API_KEY", "DATABASE_URL", "BOLAO_USER_ID", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        _val = os.environ.get(_var, "")
        if _val:
            os.environ[_var] = _val.encode().decode("utf-8-sig").strip().strip("'\"")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY não encontrado no .env")

    client = anthropic.Anthropic(api_key=api_key)
    mode = "DRY-RUN" if dry_run else "MODO REAL"
    print(f"\n=== AGENTE LIVE — {mode} ===")
    print(f"Inicio: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")

    # Recomendações do modelo estatístico (âncora de placar)
    print("Calculando recomendações do modelo estatístico...", flush=True)
    modelo_txt, _ = _model_recommendations()
    conteudo = (
        "Analise o torneio e atualize os palpites necessários. "
        "Siga o processo: status → palpites atuais → analisar → atualizar."
    )
    if modelo_txt:
        conteudo += (
            "\n\nMODELO ESTATÍSTICO VALIDADO — probabilidades e placares âncora "
            "por jogo (siga a REGRA PRIORITÁRIA do sistema):\n" + modelo_txt
        )

    messages = [{"role": "user", "content": conteudo}]

    all_updates = []  # coleta todas as atualizações para o Telegram
    truncado = False  # True se a resposta foi cortada antes de terminar a análise

    for iteration in range(15):  # limite de segurança
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            tools=TOOLS_SCHEMA,
            messages=messages,
            betas=["web-search-2025-03-05"],
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
                            all_updates.append(u)
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
            truncado = True
            break

    print(f"\nAgente concluido: {datetime.now().strftime('%H:%M:%S')}")

    # Notificacao Telegram (nao for dry-run)
    if not dry_run:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        hoje = datetime.now().strftime("%d/%m/%Y")
        if token and chat_id and all_updates:
            # Mesmo formato da reavaliação pré-jogo: jogo, ajuste e RAZÃO completa
            nomes = {}
            try:
                with _engine().connect() as _conn:
                    _rs = _conn.execute(text(
                        "SELECT match_number, team1_code, team2_code FROM matches"
                    )).fetchall()
                for _mn, _c1, _c2 in _rs:
                    nomes[_mn] = (
                        TEAMS.get(_c1, {}).get("name", _c1),
                        TEAMS.get(_c2, {}).get("name", _c2),
                    )
            except Exception:
                pass
            linhas = ["⚽ Agente de Palpites — Bolão Copa 2026", f"Análise de {hoje}:", ""]
            for u in all_updates:
                mn = u["match_number"]
                t1, t2 = nomes.get(mn, ("", ""))
                linhas.append(f"Jogo #{mn}" + (f": {t1} x {t2}" if t1 else ""))
                linhas.append(f"  🔁 AJUSTADO: {u['old']} → {u['new']}")
                if u.get("reasoning"):
                    linhas.append(f"  {u['reasoning']}")
                linhas.append("")
            linhas.append(f"Total: {len(all_updates)} palpite(s) alterado(s)")
            if truncado:
                linhas.append(
                    "\n⚠️ A análise foi interrompida antes de terminar (limite de "
                    "tokens) — pode haver jogos que ainda não foram reavaliados hoje."
                )
            send_telegram(token, chat_id, "\n".join(linhas))
        elif token and chat_id and truncado:
            # Nada foi salvo a tempo, mas o usuario precisa saber que a
            # analise de hoje nao terminou (em vez de silencio total).
            send_telegram(
                token, chat_id,
                f"Copa 2026 - {hoje}\n\n⚠️ A análise diária foi interrompida antes "
                "de aplicar qualquer atualização (limite de tokens no meio da "
                "análise). Nenhum palpite foi alterado hoje por essa execução."
            )
            print(f"  Notificacao Telegram enviada ({len(all_updates)} atualizacoes)")


# ---------------------------------------------------------------------------
# Reavaliação pré-jogo (~30 min antes de cada jogo)
# ---------------------------------------------------------------------------

PREGAME_WINDOW_MIN = 40  # janela: jogos começando nos próximos ~30-40 min
# Voltou de 180 para 40 min: a ideia do pré-jogo é avaliar perto da hora real
# do jogo, quando a escalação confirmada já costuma estar disponível (uma
# reavaliação feita 2-3h antes não tem essa informação). A confiabilidade do
# disparo agora é garantida pelo workflow rodar em loop contínuo a cada 5 min
# (pregame_update.yml), não pela largura desta janela.

_PREGAME_SYSTEM = """Você é um agente especialista em previsões de futebol de seleções
para o bolão da Copa 2026. Reavalie placares com base em: forma recente e MOMENTUM —
os ~6-10 jogos MAIS RECENTES de cada seleção, somando TODAS as competições (Copa
2026, eliminatórias, amistosos, continentais) com o MESMO peso entre si. Os jogos
desta Copa NÃO recebem peso especial só por serem da Copa — o que importa é
exclusivamente quão recente é o jogo, nunca a competição. Se a seleção jogou menos
de 6 jogos nesta Copa até agora, é OBRIGATÓRIO completar a amostra com jogos de
ANTES da Copa até reunir pelo menos 6 — NUNCA calcule a forma/média de gols usando
só 1-2 jogos isolados. Priorize SEMPRE os jogos mais recentes, de qualquer
competição. Considere também: desfalques/escalação
confirmada da véspera; retrospecto; e a média de gols marcados/sofridos por jogo e
o xG (gols esperados, quando disponível) nesses mesmos jogos recentes. Placares
realistas — SEM teto fixo de gols por time (esta Copa está com média de ~3 gols
por jogo e vários resultados elásticos); só preveja um placar elástico (3x0, 4x1
etc.) se a média de gols/xG e o favoritismo sustentarem isso claramente. Não
troque a direção do resultado (quem vence) sem evidência forte — só ajuste a
magnitude com base na média de gols e no xG."""

_PREGAME_PROMPT = """REAVALIAÇÃO PRÉ-JOGO — faltam aproximadamente {mins_left} minutos para começar.

Jogo: {home} (mandante) x {away} (visitante) — {date}
Palpite atual: {ph}-{pa}

Pesquise: os ÚLTIMOS jogos (mais recentes, com PLACAR, de TODAS as
competições — não só a Copa) de cada seleção, e o retrospecto. Priorize
SEMPRE os jogos mais recentes, independente da competição — jogos da Copa
NÃO têm peso especial, contam como qualquer outro jogo recente.
OBRIGATÓRIO: como cada seleção só tem 2-3 jogos nesta Copa até agora, NUNCA
calcule a média usando só os jogos da Copa — busque também "[Time]
amistosos eliminatorias resultados antes da copa 2026" pra completar pelo
menos 6 jogos no total por seleção. Com os placares combinados (Copa + antes
da Copa), estime a média de gols marcados/sofridos por jogo de cada seleção
e o xG (gols esperados), quando disponível.

ESCALAÇÃO: busque ATIVAMENTE a escalação confirmada de cada seleção pra
este jogo — pesquise "[Time A] escalação confirmada hoje" e "[Time B]
escalação confirmada hoje" (e suspensões/lesões de última hora).
Como faltam poucos minutos pro jogo, a escalação titular já deve estar
divulgada ou bem adiantada — isso é mais confiável que uma notícia de
desfalque de dias atrás.
REGRA CRÍTICA: só pese a escalação na reavaliação se houver CONFIRMAÇÃO
OFICIAL (a lista/escalação foi divulgada pela seleção ou federação, ou um
titular confirmado está FORA por lesão/suspensão oficial). Especulação de
rotação, "pode poupar", "deve descansar" ou qualquer hipótese não confirmada
deve ser COMPLETAMENTE IGNORADA — assuma que ambos os times jogam com o
MELHOR ELENCO DISPONÍVEL até prova em contrário. Não reduza nem aumente o
favoritismo baseado em especulação de escalação.

{model_hint}Reavalie se este palpite ainda é o ideal. NÃO use o resultado real (o jogo
ainda não começou).

Seja DIRETO na análise — só os fatores relevantes em texto corrido, SEM
títulos/seções markdown longos. O importante é sempre chegar nas linhas
finais abaixo, custe o que custar:

Responda SEMPRE com este bloco no final, nesta ordem:
1ª linha: "MANTER" (se o palpite atual continua o melhor) OU "PALPITE: X-Y"
   (novo placar, X = gols do mandante {home}).
2ª em diante: "RAZAO: <parágrafo de 4-6 frases>" — OBRIGATÓRIA NOS DOIS CASOS.
   Inclua OBRIGATORIAMENTE:
   - Média de gols feitos/sofridos por jogo dos DOIS times, em números: "{home}
     tem média de X gols feitos e Y sofridos, enquanto {away} tem média de Z
     gols feitos e W sofridos."
   - Retrospecto recente relevante (últimos 3-5 jogos).
   - Desfalques confirmados ou escalação titular relevante, se houver.
   - Por que o palpite foi mantido ou alterado (argumento central).
   Escreva em texto corrido, sem bullets. Pode ocupar várias linhas."""


def _focused_pregame_eval(client, home, away, date_str, ph, pa, mins_left=30, model_hint=""):
    """Reavalia um jogo. Retorna dict {nh, na, razao, mudou} ou None em erro.
    Captura a justificativa SEMPRE — tanto quando ajusta quanto quando mantém.
    model_hint: bloco do modelo estatístico (âncora de placar), se disponível."""
    hint = ""
    if model_hint:
        hint = (
            "MODELO ESTATÍSTICO VALIDADO (âncora de placar — em backtest nos 97 "
            "jogos já disputados desta Copa superou todos os participantes do "
            "bolão):\n" + model_hint + "\n"
            "REGRA PRIORITÁRIA: o PLACAR ÂNCORA acima é o palpite padrão. Use a "
            "pesquisa apenas para validar a direção e checar desfalques/escalação "
            "confirmada. Só desvie do placar âncora com evidência FORTE e "
            "confirmada — e escolha outro placar DENTRO do Top-5 por EV. NUNCA "
            "responda um placar fora do Top-5 por EV do modelo.\n\n"
        )
    prompt = _PREGAME_PROMPT.format(home=home, away=away, date=date_str, ph=ph,
                                    pa=pa, mins_left=mins_left, model_hint=hint)
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=5000,
            system=_PREGAME_SYSTEM,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
            betas=["web-search-2025-03-05"],
            messages=[{"role": "user", "content": prompt}],
        )
        texto = "".join(b.text for b in resp.content if hasattr(b, "text"))
    except Exception as e:
        print(f"  [erro pregame {home} x {away}: {e}]")
        return None
    rz = re.findall(r"RAZ[ÃA]O:\s*(.+)", texto, re.IGNORECASE | re.DOTALL)
    if rz:
        # Preserva parágrafos mas limpa espaços extras dentro de cada linha
        linhas_rz = [" ".join(l.split()) for l in rz[-1].splitlines()]
        razao = "\n".join(l for l in linhas_rz if l).strip("*").strip()
    else:
        # fallback: última frase significativa (ignora linhas de comando)
        linhas = [l.strip() for l in texto.splitlines() if l.strip()]
        linhas = [l for l in linhas if not re.match(r"^(MANTER|PALPITE:)", l, re.IGNORECASE)]
        razao = linhas[-1][:300] if linhas else "(sem justificativa)"
    m = re.findall(r"PALPITE:\s*(\d+)\s*[-x]\s*(\d+)", texto, re.IGNORECASE)
    if m:  # decidiu por um placar explícito
        nh, na = int(m[-1][0]), int(m[-1][1])
        return {"nh": nh, "na": na, "razao": razao, "mudou": (nh != ph or na != pa)}
    return {"nh": ph, "na": pa, "razao": razao, "mudou": False}  # MANTER


def run_pregame(dry_run: bool = False):
    """Reavalia, ~30 min antes do início, os palpites dos jogos prestes a começar.
    Se o placar mudar, atualiza (apenas o jogo, apenas o próprio usuário, apenas
    jogos ainda não iniciados) e avisa no Telegram. Idempotente: cada jogo é
    reavaliado uma única vez (marca em predictions.json -> pregame_checked).
    O palpite atual (ph/pa) é lido do banco — não do predictions.json — para
    garantir que o valor real seja avaliado mesmo quando o chaveamento mudou."""
    load_dotenv()
    for _var in ("ANTHROPIC_API_KEY", "DATABASE_URL", "BOLAO_USER_ID", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        _val = os.environ.get(_var, "")
        if _val:
            os.environ[_var] = _val.encode().decode("utf-8-sig").strip().strip("'\"")

    uid = _user_id()
    tz = pytz.timezone("America/Sao_Paulo")
    now = datetime.now(tz).replace(tzinfo=None)
    limite = now + timedelta(minutes=PREGAME_WINDOW_MIN)

    engine = _engine()
    with engine.connect() as conn:
        # Lê os jogos prestes a começar E o palpite atual do banco (não do predictions.json),
        # pois o chaveamento real pode diferir do que foi previsto antes da Copa.
        rows = conn.execute(text("""
            SELECT m.match_number, m.team1_code, m.team2_code,
                   CAST(m.datetime AS VARCHAR),
                   COALESCE(p.pred_team1_score, 0) AS ph,
                   COALESCE(p.pred_team2_score, 0) AS pa
            FROM matches m
            LEFT JOIN predictions p ON p.match_id = m.id AND p.user_id = :uid
            WHERE m.status = 'scheduled'
              AND m.team1_id IS NOT NULL AND m.team2_id IS NOT NULL
              AND m.datetime > :agora AND m.datetime <= :lim
            ORDER BY m.datetime
        """), {"agora": now, "lim": limite, "uid": uid}).fetchall()

    if not rows:
        print(f"[PRÉ-JOGO] Nenhum jogo começando nos próximos {PREGAME_WINDOW_MIN} min — nada a fazer.")
        return

    # predictions.json só é usado para rastrear quais jogos já foram avaliados (pregame_checked)
    if not os.path.exists(PREDICTIONS_FILE):
        print("predictions.json não encontrado — abortando.")
        return
    with open(PREDICTIONS_FILE, encoding="utf-8") as f:
        predictions = json.load(f)
    checked = set(predictions.get("pregame_checked", []))

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Âncoras do modelo estatístico (uma única construção para todos os jogos)
    print("[PRÉ-JOGO] Calculando âncoras do modelo estatístico...", flush=True)
    _, model_hints = _model_recommendations()

    def tname(code):
        return TEAMS.get(code, {}).get("name", code)

    updates = []        # só os jogos com placar alterado (vão ao banco)
    avaliacoes = []     # TODOS os jogos avaliados (mantidos + alterados) p/ Telegram
    processou = False
    for mn, c1, c2, dt, ph, pa in rows:
        if mn in checked:
            continue
        processou = True
        home, away = tname(c1), tname(c2)
        kickoff = datetime.strptime(str(dt)[:19], "%Y-%m-%d %H:%M:%S")
        mins_left = max(1, round((kickoff - now).total_seconds() / 60))
        print(f"[PRÉ-JOGO] Reavaliando #{mn}: {home} x {away} (atual {ph}-{pa}, faltam {mins_left} min)...", flush=True)
        res = _focused_pregame_eval(client, home, away, str(dt)[:16], ph, pa,
                                    mins_left=mins_left,
                                    model_hint=model_hints.get(mn, ""))
        checked.add(mn)
        if res is None:
            print(f"  -> ERRO/sem resposta — mantém {ph}-{pa}")
            avaliacoes.append({"match_number": mn, "home": home, "away": away,
                               "mudou": False, "old": f"{ph}-{pa}", "new": f"{ph}-{pa}",
                               "razao": "Não foi possível reavaliar — palpite mantido.",
                               "salvo": True})
            continue
        razao = res["razao"]
        if not res["mudou"]:
            print(f"  -> MANTER {ph}-{pa} | {razao}")
            avaliacoes.append({"match_number": mn, "home": home, "away": away,
                               "mudou": False, "old": f"{ph}-{pa}", "new": f"{ph}-{pa}",
                               "razao": razao, "salvo": True})
            continue
        nh, na = res["nh"], res["na"]
        item = {"match_number": mn, "home": home, "away": away, "mudou": True,
                "old": f"{ph}-{pa}", "new": f"{nh}-{na}", "razao": razao, "salvo": False}
        updates.append(item)
        avaliacoes.append(item)
        print(f"  -> AJUSTAR {ph}-{pa} => {nh}-{na} | {razao}")

    if not processou:
        print("[PRÉ-JOGO] Jogos na janela já haviam sido reavaliados — nada a fazer.")
        return

    predictions["pregame_checked"] = sorted(checked)
    if dry_run:
        print(f"[PRÉ-JOGO][DRY-RUN] {len(avaliacoes)} avaliado(s), {len(updates)} ajuste(s) — nada gravado.")
        return

    with open(PREDICTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)

    # Submete SÓ os jogos alterados — submit_match_prediction garante:
    # apenas o próprio usuário (BOLAO_USER_ID) e apenas jogos não iniciados.
    if updates:
        from submitter import get_db_engine, submit_match_prediction
        eng = get_db_engine()
        with eng.begin() as conn:
            for u in updates:
                nh, na = map(int, u["new"].split("-"))
                resultado = submit_match_prediction(conn, uid, u["match_number"], nh, na, dry_run=False)
                print(resultado)
                u["salvo"] = " OK" in resultado
                if not u["salvo"]:
                    u["fail_reason"] = resultado.strip()

    # Telegram: avisa SEMPRE (mantido ou alterado), para todos os jogos avaliados
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if avaliacoes and token and chat_id:
        linhas = ["⚽ VAR — Bolão Copa 2026", "Reavaliação pré-jogo:", ""]
        for a in avaliacoes:
            linhas.append(f"Jogo #{a['match_number']}: {a['home']} x {a['away']}")
            if a["mudou"] and a.get("salvo"):
                linhas.append(f"  🔁 AJUSTADO: {a['old']} → {a['new']}")
            elif a["mudou"] and not a.get("salvo"):
                linhas.append(f"  ⚠️ SUGERIDO {a['new']} — NÃO SALVO ({a.get('fail_reason', 'prazo encerrado')})")
            else:
                linhas.append(f"  ✅ MANTIDO: {a['new']}")
            if a["razao"]:
                linhas.append(f"  {a['razao']}")
            linhas.append("")
        send_telegram(token, chat_id, "\n".join(linhas).rstrip())
        print(f"  Notificacao Telegram enviada ({len(avaliacoes)} jogo(s): {len(updates)} ajuste(s))")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if "--pregame" in sys.argv:
        run_pregame(dry_run=dry_run)
    else:
        run_agent(dry_run=dry_run)
