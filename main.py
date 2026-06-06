"""
CLI principal do motor de previsão da Copa 2026.

Uso:
  python main.py analyze              # Analisa e gera predictions.json
  python main.py review               # Exibe as previsões em formato tabular
  python main.py submit               # Envia previsões ao banco PostgreSQL
  python main.py submit --dry-run     # Simula o envio sem gravar
  python main.py live                 # Atualiza palpites de jogos futuros com resultados reais
  python main.py all                  # analyze + review + submit em sequência
  python main.py bulletin             # Gera e envia o Boletim do Mestre Leme via Telegram
  python main.py bulletin --script    # Só imprime o roteiro, sem gerar vídeo
"""

import sys
import json
import os
from tabulate import tabulate
from dotenv import load_dotenv
from sqlalchemy import text

from fixtures import TEAMS, GROUPS, GROUP_STAGE_MATCHES, KNOCKOUT_MATCHES
from predictor import run_analysis, load_predictions, PREDICTIONS_FILE
from submitter import submit_all, get_db_engine, get_match_id, get_team_id


# ---------------------------------------------------------------------------
# Review: exibe previsões no terminal
# ---------------------------------------------------------------------------

def cmd_review():
    predictions = load_predictions()
    generated = predictions.get("generated_at", "?")
    print(f"\nPrevisões geradas em: {generated}")

    # Grupos
    print("\n" + "=" * 60)
    print("CLASSIFICATÓRIOS DOS GRUPOS")
    print("=" * 60)
    rows = []
    for group in GROUPS:
        gdata = predictions["groups"].get(group, {})
        first = TEAMS.get(gdata.get("first", ""), {}).get("name", gdata.get("first", "?"))
        second = TEAMS.get(gdata.get("second", ""), {}).get("name", gdata.get("second", "?"))
        rows.append([f"Grupo {group}", f"1º {first}", f"2º {second}"])
    print(tabulate(rows, headers=["Grupo", "1º Lugar", "2º Lugar"], tablefmt="simple"))

    # Pódio
    print("\n" + "=" * 60)
    print("PÓDIO PREVISTO")
    print("=" * 60)
    podium = predictions.get("podium", {})
    champ = TEAMS.get(podium.get("champion", ""), {}).get("name", podium.get("champion", "?"))
    runner = TEAMS.get(podium.get("runner_up", ""), {}).get("name", podium.get("runner_up", "?"))
    third = TEAMS.get(podium.get("third", ""), {}).get("name", podium.get("third", "?"))
    print(f"  [1] Campeao:       {champ}")
    print(f"  [2] Vice-Campea:   {runner}")
    print(f"  [3] 3o Lugar:      {third}")

    # Jogos por grupo
    print("\n" + "=" * 60)
    print("PALPITES DA FASE DE GRUPOS")
    print("=" * 60)
    group_matches = [m for m in predictions["matches"] if m.get("phase") == "Groups"]
    matches_by_group = {g: [] for g in GROUPS}
    for m in group_matches:
        grp = m.get("group", "?")
        if grp in matches_by_group:
            matches_by_group[grp].append(m)

    for group in GROUPS:
        rows = []
        for m in matches_by_group[group]:
            home = TEAMS.get(m["home_team"], {}).get("name", m["home_team"])
            away = TEAMS.get(m["away_team"], {}).get("name", m["away_team"])
            score = f"{m['home_goals']} x {m['away_goals']}"
            reason = m.get("reasoning", "")[:60]
            rows.append([f"#{m['match_number']}", home, score, away, reason])
        print(f"\n--- Grupo {group} ---")
        print(tabulate(rows, headers=["Jogo", "Casa", "Placar", "Visitante", "Razão"], tablefmt="simple"))

    # Mata-mata (resumo)
    print("\n" + "=" * 60)
    print("MATA-MATA — RESUMO")
    print("=" * 60)
    phase_labels = {
        "R32": "Fase de 32", "R16": "Oitavas",
        "QF": "Quartas", "SF": "Semis",
        "3RD": "3º Lugar", "FINAL": "Final",
    }
    ko_matches = [m for m in predictions["matches"] if m.get("phase") != "Groups"]
    for phase_key, label in phase_labels.items():
        phase_matches = [m for m in ko_matches if m.get("phase") == phase_key]
        if not phase_matches:
            continue
        rows = []
        for m in phase_matches:
            home = TEAMS.get(m["home_team"], {}).get("name", m["home_team"])
            away = TEAMS.get(m["away_team"], {}).get("name", m["away_team"])
            score = f"{m['home_goals']} x {m['away_goals']}"
            winner = TEAMS.get(m.get("winner", ""), {}).get("name", m.get("winner", "?"))
            pens = " (pen)" if m.get("went_to_penalties") else ""
            rows.append([f"#{m['match_number']}", home, score, away, f"> {winner}{pens}"])
        print(f"\n{label}:")
        print(tabulate(rows, headers=["Jogo", "Casa", "Placar", "Visitante", "Vencedor"], tablefmt="simple"))


# ---------------------------------------------------------------------------
# Live: atualiza palpites de jogos futuros baseado nos resultados reais
# ---------------------------------------------------------------------------

def cmd_live():
    """
    Modo live (SEM API): lê os resultados reais do banco e exibe o estado atual
    do torneio para que o usuário possa consultar o Claude Code e atualizar
    o predictions.json manualmente antes de rodar 'python main.py submit'.
    """
    load_dotenv()
    user_id = int(os.getenv("BOLAO_USER_ID", "0"))
    if not user_id:
        raise EnvironmentError("BOLAO_USER_ID não definido no .env")

    engine = get_db_engine()

    print("\n=== MODO LIVE — ESTADO ATUAL DO TORNEIO ===")
    print("Lendo resultados reais do banco...")

    with engine.begin() as conn:
        # Resultados já registrados (jogos disputados)
        completed = conn.execute(text("""
            SELECT m.match_number, m.team1_code, m.team2_code,
                   m.team1_score, m.team2_score, m.phase
            FROM match m
            WHERE m.team1_score IS NOT NULL AND m.team2_score IS NOT NULL
            ORDER BY m.match_number
        """)).fetchall()

        # Jogos futuros ainda não iniciados (grupo E mata-mata com times definidos)
        rows = conn.execute(text("""
            SELECT m.match_number, m.id, m.team1_code, m.team2_code,
                   m.datetime, m.phase, m.city
            FROM match m
            WHERE m.team1_code IS NOT NULL
              AND m.team1_code NOT LIKE '%%(%'
              AND m.team2_code IS NOT NULL
              AND m.team2_code NOT LIKE '%%(%'
              AND m.status = 'scheduled'
              AND m.datetime > NOW()
            ORDER BY m.match_number
        """)).fetchall()

    if not rows:
        print("Nenhum jogo futuro encontrado.")
        return

    # Formata resultados já disputados para contexto
    completed_block = ""
    if completed:
        lines = []
        for r in completed:
            home = TEAMS.get(r[1], {}).get("name", r[1])
            away = TEAMS.get(r[2], {}).get("name", r[2])
            lines.append(f"  Jogo {r[0]}: {home} {r[3]} x {r[4]} {away}")
        completed_block = "RESULTADOS REAIS JÁ DISPUTADOS:\n" + "\n".join(lines)
    else:
        completed_block = "Nenhum jogo disputado ainda."

    # Exibe resultados já disputados
    print(f"\nResultados reais registrados: {len(completed)}")
    if completed:
        rows_table = []
        for r in completed:
            home = TEAMS.get(r[1], {}).get("name", r[1])
            away = TEAMS.get(r[2], {}).get("name", r[2])
            rows_table.append([f"#{r[0]}", r[5], home, f"{r[3]}-{r[4]}", away])
        print(tabulate(rows_table, headers=["Jogo", "Fase", "Casa", "Placar", "Visitante"], tablefmt="simple"))

    # Exibe jogos futuros sem palpite
    if not rows:
        print("\nTodos os jogos futuros ja tem palpite ou ainda nao estao definidos.")
        return

    print(f"\nJogos futuros com palpite possivel: {len(rows)}")
    future_rows = []
    for r in rows:
        home = TEAMS.get(r[2], {}).get("name", r[2])
        away = TEAMS.get(r[3], {}).get("name", r[3])
        future_rows.append([f"#{r[0]}", r[5], home, "vs", away, str(r[4])[:10], r[6]])
    print(tabulate(future_rows, headers=["Jogo", "Fase", "Casa", "", "Visitante", "Data", "Cidade"], tablefmt="simple"))

    print("\n" + "="*60)
    print("PROXIMO PASSO:")
    print("  1. Copie os resultados acima e cole para o Claude Code")
    print("  2. Peca para reavaliar os palpites dos jogos futuros")
    print("  3. Atualize o predictions.json com as novas previsoes")
    print("  4. Execute: python main.py submit")
    print("="*60)


# ---------------------------------------------------------------------------
# Bulletin: Boletim do Mestre Leme
# ---------------------------------------------------------------------------

def cmd_bulletin(script_only: bool = False, launch: bool = False):
    """Gera o roteiro, cria o vídeo e envia pelo Telegram."""
    import os
    from datetime import datetime
    from dotenv import load_dotenv
    from submitter import get_db_engine
    from bulletin_db import get_bulletin_data, get_missing_predictions_data, get_copa_start
    from bulletin_generator import generate_bulletin_script, generate_launch_script

    load_dotenv()

    engine = get_db_engine()

    if launch:
        print("\n=== VÍDEO DE LANÇAMENTO DO MESTRE LEME ===")
        with engine.begin() as conn:
            data = get_bulletin_data(conn)
            missing = get_missing_predictions_data(conn)
            copa_start = get_copa_start(conn)

        now = datetime.now()
        dias = max(0, (copa_start - now).days)
        copa_start_str = copa_start.strftime("%d/%m/%Y às %H:%M")
        print(f"Copa começa em: {copa_start_str} ({dias} dias)")
        print(f"Sem pódio: {len(missing['sem_podio'])}/{missing['total_users']}")
        print(f"Grupos incompletos: {len(missing['grupos_incompletos'])}/{missing['total_users']}")
        print("\nGerando roteiro de lançamento com Claude...")

        script = generate_launch_script(data, missing, copa_start_str, dias)
        caption = f"🎙️ <b>Boletim do Mestre Leme — Lançamento do Bolão Copa 2026!</b>"
    else:
        print("\n=== BOLETIM DO MESTRE LEME ===")
        with engine.begin() as conn:
            data = get_bulletin_data(conn)

        print(f"Data: {data['date']}")
        print(f"Jogos encerrados hoje: {len(data['results'])}")
        print(f"Participantes no ranking: {data['total_participants']}")
        print("\nGerando roteiro com Claude...")

        script = generate_bulletin_script(data)
        caption = f"🎙️ <b>Boletim do Mestre Leme</b> — {data['date']}"

    print(f"\n--- ROTEIRO ({len(script.split())} palavras) ---\n{script}\n---\n")

    if script_only:
        print("Modo --script: roteiro impresso, vídeo não gerado.")
        return

    api_key = os.getenv("DID_API_KEY")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not api_key:
        print("DID_API_KEY não encontrada — enviando roteiro em texto pelo Telegram.")
        if token and chat_id:
            from bulletin_sender import send_text_fallback
            send_text_fallback(script, token, chat_id, caption=caption)
        return

    from video_creator import create_bulletin_video
    from bulletin_sender import send_bulletin_video, send_text_fallback

    video_path = "bulletin.mp4"
    try:
        print("Gerando vídeo no D-ID...")
        create_bulletin_video(script, api_key, video_path)
    except Exception as e:
        print(f"Erro ao gerar vídeo: {e}")
        print("Enviando roteiro em texto como fallback...")
        if token and chat_id:
            send_text_fallback(script, token, chat_id, caption=caption)
        return

    if token and chat_id:
        send_bulletin_video(video_path, caption, token, chat_id)
    else:
        print("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não encontrados — vídeo salvo localmente.")

    import os as _os
    if _os.path.exists(video_path):
        _os.remove(video_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    command = args[0].lower()
    dry_run = "--dry-run" in args

    if command == "analyze":
        run_analysis()

    elif command == "review":
        cmd_review()

    elif command == "submit":
        predictions = load_predictions()
        submit_all(predictions, dry_run=dry_run)

    elif command == "live":
        from agent_live import run_agent
        run_agent(dry_run=dry_run)

    elif command == "all":
        predictions = run_analysis()
        cmd_review()
        if sys.stdin.isatty():
            confirm = input("\nDeseja submeter ao banco? (s/N): ").strip().lower()
            if confirm != "s":
                print("Submissao cancelada.")
                sys.exit(0)
        else:
            print("\nModo automatico (GitHub Actions) — submetendo ao banco...")
        submit_all(predictions, dry_run=False)

    elif command == "bulletin":
        cmd_bulletin(script_only="--script" in args, launch="--launch" in args)

    else:
        print(f"Comando desconhecido: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
