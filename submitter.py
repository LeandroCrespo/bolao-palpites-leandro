"""
Submissão das previsões diretamente no banco PostgreSQL do bolão.
Usa SQLAlchemy Core com raw SQL (sem copiar os models do bolão).
"""

import os
from datetime import datetime, timezone

import pytz
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from fixtures import TEAMS

_BR_TZ = pytz.timezone("America/Sao_Paulo")


def _now_br() -> datetime:
    """Agora em horário de Brasília, naive (consistente com matches.datetime no banco)."""
    return datetime.now(_BR_TZ).replace(tzinfo=None)

# Traduz códigos internos (fixtures.py) para os códigos reais no banco
CODE_MAP = {
    "EUR_A": "BIH",   # Bósnia e Herzegovina
    "EUR_B": "SWE",   # Suécia
    "EUR_C": "TUR",   # Turquia
    "EUR_D": "CZE",   # Tchéquia
    "INT_1": "COD",   # RD Congo
    "INT_2": "IRQ",   # Iraque
    "CUR":   "CUW",   # Curaçao
}

def _real_code(code: str) -> str:
    return CODE_MAP.get(code, code)


def get_db_engine(db_url: str | None = None):
    load_dotenv()
    raw = db_url or os.getenv("DATABASE_URL") or os.getenv("NEON_CONNECTION_STRING") or ""
    # Remove BOM, espaços e aspas que podem vir do secret
    conn_str = raw.encode().decode("utf-8-sig").strip().strip("'\"").strip()
    if not conn_str:
        raise EnvironmentError("DATABASE_URL ou NEON_CONNECTION_STRING não encontrada")
    # SQLAlchemy 2.0 exige postgresql://, não postgres://
    if conn_str.startswith("postgres://"):
        conn_str = "postgresql://" + conn_str[len("postgres://"):]
    return create_engine(conn_str)


def get_team_id(conn, code: str) -> int | None:
    """Retorna o ID do time pelo código (ex: 'BRA', 'ESP')."""
    row = conn.execute(
        text("SELECT id FROM teams WHERE code = :code"), {"code": code}
    ).fetchone()
    return row[0] if row else None


def get_match_id(conn, match_number: int) -> int | None:
    """Retorna o ID do jogo pelo número (1-104)."""
    row = conn.execute(
        text("SELECT id FROM matches WHERE match_number = :n"), {"n": match_number}
    ).fetchone()
    return row[0] if row else None


def can_predict_match(conn, match_id: int) -> bool:
    """Verifica se o palpite do jogo ainda está aberto (horário não passou)."""
    row = conn.execute(
        text("SELECT datetime, status FROM matches WHERE id = :id"), {"id": match_id}
    ).fetchone()
    if not row:
        return False
    if row[1] != "scheduled":
        return False
    match_dt = row[0]
    # Compara naive (banco em horário de Brasília sem timezone) — usar
    # datetime.now() puro aqui comparava UTC (relógio do runner do GitHub
    # Actions) contra um horário em BRT, fechando o prazo 3h antes da hora
    # real e rejeitando silenciosamente ajustes legítimos do pré-jogo.
    return _now_br() < match_dt


def submit_match_prediction(
    conn, user_id: int, match_number: int, home_goals: int, away_goals: int,
    dry_run: bool = False
) -> str:
    """Upsert do palpite de um jogo. Retorna status string."""
    match_id = get_match_id(conn, match_number)
    if match_id is None:
        return f"  Jogo {match_number}: não encontrado no banco — PULADO"

    if not can_predict_match(conn, match_id):
        return f"  Jogo {match_number}: prazo encerrado — PULADO"

    existing = conn.execute(
        text("SELECT id, locked_at FROM predictions WHERE user_id=:u AND match_id=:m"),
        {"u": user_id, "m": match_id},
    ).fetchone()

    now_str = _now_br()

    if existing:
        if existing[1] is not None:
            return f"  Jogo {match_number}: palpite travado — PULADO"
        action = "UPDATE"
        if not dry_run:
            conn.execute(
                text("""
                    UPDATE predictions
                    SET pred_team1_score=:s1, pred_team2_score=:s2, updated_at=:now
                    WHERE id=:id
                """),
                {"s1": home_goals, "s2": away_goals, "now": now_str, "id": existing[0]},
            )
    else:
        action = "INSERT"
        if not dry_run:
            conn.execute(
                text("""
                    INSERT INTO predictions
                    (user_id, match_id, pred_team1_score, pred_team2_score, created_at, updated_at)
                    VALUES (:u, :m, :s1, :s2, :now, :now)
                """),
                {"u": user_id, "m": match_id, "s1": home_goals, "s2": away_goals, "now": now_str},
            )

    prefix = "[DRY-RUN] " if dry_run else ""
    return f"  {prefix}Jogo {match_number}: {home_goals}-{away_goals} — {action} OK"


def submit_group_prediction(
    conn, user_id: int, group_name: str, first_code: str, second_code: str,
    dry_run: bool = False
) -> str:
    """Upsert do palpite de classificados de um grupo."""
    first_code_db = _real_code(first_code)
    second_code_db = _real_code(second_code)
    first_id = get_team_id(conn, first_code_db)
    second_id = get_team_id(conn, second_code_db)

    if first_id is None:
        return f"  Grupo {group_name}: time '{first_code_db}' não encontrado — PULADO"
    if second_id is None:
        return f"  Grupo {group_name}: time '{second_code_db}' não encontrado — PULADO"

    existing = conn.execute(
        text("SELECT id FROM group_predictions WHERE user_id=:u AND group_name=:g"),
        {"u": user_id, "g": group_name},
    ).fetchone()

    now_str = _now_br()

    def _name(original, db_code):
        return (TEAMS.get(original) or TEAMS.get(db_code) or {}).get("name", db_code)

    first_name = _name(first_code, first_code_db)
    second_name = _name(second_code, second_code_db)

    if existing:
        action = "UPDATE"
        if not dry_run:
            conn.execute(
                text("""
                    UPDATE group_predictions
                    SET first_place_team_id=:f, second_place_team_id=:s, updated_at=:now
                    WHERE id=:id
                """),
                {"f": first_id, "s": second_id, "now": now_str, "id": existing[0]},
            )
    else:
        action = "INSERT"
        if not dry_run:
            conn.execute(
                text("""
                    INSERT INTO group_predictions
                    (user_id, group_name, first_place_team_id, second_place_team_id, created_at, updated_at)
                    VALUES (:u, :g, :f, :s, :now, :now)
                """),
                {"u": user_id, "g": group_name, "f": first_id, "s": second_id,
                 "now": now_str},
            )

    prefix = "[DRY-RUN] " if dry_run else ""
    return f"  {prefix}Grupo {group_name}: 1º {first_name}, 2º {second_name} — {action} OK"


def submit_podium_prediction(
    conn, user_id: int, champion_code: str, runner_up_code: str, third_code: str,
    dry_run: bool = False
) -> str:
    """Upsert do palpite de pódio."""
    champion_code = _real_code(champion_code)
    runner_up_code = _real_code(runner_up_code)
    third_code = _real_code(third_code)
    champion_id = get_team_id(conn, champion_code)
    runner_up_id = get_team_id(conn, runner_up_code)
    third_id = get_team_id(conn, third_code)

    for code, cid, label in [
        (champion_code, champion_id, "Campeão"),
        (runner_up_code, runner_up_id, "Vice"),
        (third_code, third_id, "3º lugar"),
    ]:
        if cid is None:
            return f"  Pódio: time '{code}' ({label}) não encontrado — PULADO"

    existing = conn.execute(
        text("SELECT id, locked FROM podium_predictions WHERE user_id=:u"),
        {"u": user_id},
    ).fetchone()

    champion_name = TEAMS.get(champion_code, {}).get("name", champion_code)
    runner_up_name = TEAMS.get(runner_up_code, {}).get("name", runner_up_code)
    third_name = TEAMS.get(third_code, {}).get("name", third_code)
    now_str = _now_br()

    if existing:
        if existing[1]:  # locked = True
            return f"  Pódio: palpite travado — PULADO"
        action = "UPDATE"
        if not dry_run:
            conn.execute(
                text("""
                    UPDATE podium_predictions
                    SET champion_team_id=:c, runner_up_team_id=:r, third_place_team_id=:t,
                        updated_at=:now
                    WHERE id=:id
                """),
                {"c": champion_id, "r": runner_up_id, "t": third_id, "now": now_str, "id": existing[0]},
            )
    else:
        action = "INSERT"
        if not dry_run:
            conn.execute(
                text("""
                    INSERT INTO podium_predictions
                    (user_id, champion_team_id, runner_up_team_id, third_place_team_id, created_at, updated_at)
                    VALUES (:u, :c, :r, :t, :now, :now)
                """),
                {"u": user_id, "c": champion_id, "r": runner_up_id, "t": third_id, "now": now_str},
            )

    prefix = "[DRY-RUN] " if dry_run else ""
    return (
        f"  {prefix}Pódio: [1] {champion_name} / [2] {runner_up_name} / [3] {third_name} — {action} OK"
    )


def submit_all(predictions: dict, dry_run: bool = False):
    """
    Submete todos os palpites ao banco:
    - 72 jogos da fase de grupos
    - 12 classificatórios de grupos
    - 1 pódio
    Os jogos do mata-mata são submetidos apenas se o time já estiver resolvido no banco.
    """
    load_dotenv()
    user_id = int(os.getenv("BOLAO_USER_ID", "0"))
    if not user_id:
        raise EnvironmentError("BOLAO_USER_ID não definido no .env")

    engine = get_db_engine()
    mode = "DRY-RUN" if dry_run else "SUBMISSÃO REAL"
    print(f"\n=== {mode} — user_id={user_id} ===")

    with engine.begin() as conn:

        # Jogos
        group_matches = [m for m in predictions["matches"] if m.get("phase") in ("Groups", "Grupos")]
        print(f"\n--- Palpites dos Jogos ({len(group_matches)} jogos da fase de grupos) ---")
        ok = skip = 0
        for mp in group_matches:
            status = submit_match_prediction(
                conn, user_id,
                mp["match_number"], mp["home_goals"], mp["away_goals"],
                dry_run=dry_run,
            )
            print(status)
            if " OK" in status:
                ok += 1
            else:
                skip += 1
        print(f"  > {ok} submetidos, {skip} pulados")

        # Classificatórios dos grupos
        print(f"\n--- Palpites de Classificados (12 grupos) ---")
        ok = skip = 0
        for group, gdata in predictions["groups"].items():
            status = submit_group_prediction(
                conn, user_id, group,
                gdata["first"], gdata["second"],
                dry_run=dry_run,
            )
            print(status)
            if " OK" in status:
                ok += 1
            else:
                skip += 1
        print(f"  > {ok} submetidos, {skip} pulados")

        # Pódio
        print(f"\n--- Palpite do Pódio ---")
        podium = predictions["podium"]
        status = submit_podium_prediction(
            conn, user_id,
            podium["champion"], podium["runner_up"], podium["third"],
            dry_run=dry_run,
        )
        print(status)

    print(f"\n{'[DRY-RUN] Nenhuma alteração foi gravada.' if dry_run else 'Palpites gravados com sucesso!'}")
