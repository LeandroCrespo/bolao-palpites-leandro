"""
Consultas somente leitura ao banco para geração do Boletim do Mestre Leme.
Nunca altera palpites nem qualquer dado de participantes.
"""

from datetime import datetime, date, time
import pytz
from sqlalchemy import text

BRASILIA = pytz.timezone("America/Sao_Paulo")
BULLETIN_HOUR = 20  # 20h Brasília — jogos após esse horário vão para o boletim do dia seguinte
ADMIN_USER_ID = 1


def _bulletin_cutoff(target_date: date) -> datetime:
    """Retorna o datetime de corte (20h Brasília) para o boletim do dia."""
    dt = datetime.combine(target_date, time(BULLETIN_HOUR, 0, 0))
    return BRASILIA.localize(dt)


def get_ranking(conn, exclude_admin: bool = True) -> list[dict]:
    """
    Retorna ranking geral de todos os participantes com pontuação total.
    Somente leitura — não altera nenhum dado.
    """
    query = text("""
        SELECT
            u.id,
            u.name,
            COALESCE(mp.pts, 0) + COALESCE(gp.pts, 0) + COALESCE(pp.pts, 0) AS total,
            COALESCE(mp.pts, 0)  AS match_pts,
            COALESCE(gp.pts, 0)  AS group_pts,
            COALESCE(pp.pts, 0)  AS podium_pts
        FROM users u
        LEFT JOIN (
            SELECT user_id, COALESCE(SUM(points_awarded), 0) AS pts
            FROM predictions GROUP BY user_id
        ) mp ON mp.user_id = u.id
        LEFT JOIN (
            SELECT user_id, COALESCE(SUM(points_awarded), 0) AS pts
            FROM group_predictions GROUP BY user_id
        ) gp ON gp.user_id = u.id
        LEFT JOIN (
            SELECT user_id, COALESCE(SUM(points_awarded), 0) AS pts
            FROM podium_predictions GROUP BY user_id
        ) pp ON pp.user_id = u.id
        WHERE u.active = true
        ORDER BY total DESC, u.name
    """)
    rows = conn.execute(query).fetchall()

    ranking = []
    position = 1
    for row in rows:
        if exclude_admin and row[0] == ADMIN_USER_ID:
            continue
        ranking.append({
            "position": position,
            "user_id": row[0],
            "name": row[1],
            "total": row[2],
            "match_pts": row[3],
            "group_pts": row[4],
            "podium_pts": row[5],
        })
        position += 1
    return ranking


def get_todays_results(conn, target_date: date) -> list[dict]:
    """
    Retorna jogos finalizados até o horário de corte do boletim (20h Brasília).
    Somente leitura.
    """
    cutoff = _bulletin_cutoff(target_date)
    query = text("""
        SELECT
            m.match_number,
            m.team1_code,
            t1.name AS team1_name,
            m.team1_score,
            m.team2_score,
            t2.name AS team2_name,
            m.team2_code,
            m.phase,
            m.datetime
        FROM matches m
        LEFT JOIN teams t1 ON t1.id = m.team1_id
        LEFT JOIN teams t2 ON t2.id = m.team2_id
        WHERE m.team1_score IS NOT NULL
          AND m.team2_score IS NOT NULL
          AND m.datetime >= :day_start
          AND m.datetime < :cutoff
        ORDER BY m.datetime
    """)
    day_start = datetime.combine(target_date, time(0, 0, 0))
    rows = conn.execute(query, {"day_start": day_start, "cutoff": cutoff.replace(tzinfo=None)}).fetchall()

    results = []
    for row in rows:
        s1, s2 = row[3], row[4]
        if s1 > s2:
            winner = row[2]
        elif s2 > s1:
            winner = row[5]
        else:
            winner = "Empate"
        results.append({
            "match_number": row[0],
            "team1_code": row[1],
            "team1_name": row[2],
            "team1_score": s1,
            "team2_score": s2,
            "team2_name": row[5],
            "team2_code": row[6],
            "phase": row[7],
            "datetime": row[8],
            "winner": winner,
        })
    return results


def get_todays_top_scorers(conn, target_date: date, exclude_admin: bool = True) -> list[dict]:
    """
    Retorna participantes ordenados por pontos ganhos hoje (jogos até 20h).
    Somente leitura.
    """
    cutoff = _bulletin_cutoff(target_date)
    day_start = datetime.combine(target_date, time(0, 0, 0))
    query = text("""
        SELECT
            u.id,
            u.name,
            COALESCE(SUM(p.points_awarded), 0) AS pts_today
        FROM users u
        JOIN predictions p ON p.user_id = u.id
        JOIN matches m ON m.id = p.match_id
        WHERE u.active = true
          AND m.datetime >= :day_start
          AND m.datetime < :cutoff
          AND p.points_awarded IS NOT NULL
        GROUP BY u.id, u.name
        ORDER BY pts_today DESC, u.name
    """)
    rows = conn.execute(query, {
        "day_start": day_start,
        "cutoff": cutoff.replace(tzinfo=None),
    }).fetchall()

    scorers = []
    for row in rows:
        if exclude_admin and row[0] == ADMIN_USER_ID:
            continue
        if row[2] > 0:
            scorers.append({"user_id": row[0], "name": row[1], "pts_today": row[2]})
    return scorers


def get_copa_start(conn) -> datetime | None:
    """Retorna a data de início da Copa a partir da config. Somente leitura."""
    row = conn.execute(text("SELECT value FROM config WHERE key = 'data_inicio_copa'")).fetchone()
    if not row:
        return datetime(2026, 6, 11, 13, 0)
    raw = row[0].strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return datetime(2026, 6, 11, 13, 0)


def get_missing_predictions_data(conn) -> dict:
    """Retorna quem ainda não salvou pódio e/ou grupos. Somente leitura."""
    users = conn.execute(text("""
        SELECT id, name FROM users
        WHERE active = true AND role != 'admin'
        ORDER BY name
    """)).fetchall()

    sem_podio = []
    grupos_incompletos = []

    for user_id, name in users:
        row = conn.execute(text("""
            SELECT id FROM podium_predictions
            WHERE user_id = :uid
              AND champion_team_id IS NOT NULL
              AND runner_up_team_id IS NOT NULL
              AND third_place_team_id IS NOT NULL
        """), {"uid": user_id}).fetchone()
        if not row:
            sem_podio.append(name)

        feitos_rows = conn.execute(text("""
            SELECT DISTINCT group_name FROM group_predictions
            WHERE user_id = :uid
              AND first_place_team_id IS NOT NULL
              AND second_place_team_id IS NOT NULL
        """), {"uid": user_id}).fetchall()
        feitos = {r[0] for r in feitos_rows}
        faltando = sorted(set("ABCDEFGHIJKL") - feitos)
        if faltando:
            grupos_incompletos.append({
                "name": name,
                "feitos": len(feitos),
                "faltando": faltando,
            })

    return {
        "total_users": len(users),
        "sem_podio": sem_podio,
        "grupos_incompletos": grupos_incompletos,
    }


def get_bulletin_data(conn, target_date: date | None = None) -> dict:
    """Agrega todos os dados necessários para o boletim."""
    if target_date is None:
        target_date = datetime.now(BRASILIA).date()

    ranking = get_ranking(conn)
    results = get_todays_results(conn, target_date)
    top_scorers = get_todays_top_scorers(conn, target_date)

    return {
        "date": target_date.strftime("%d/%m/%Y"),
        "ranking": ranking,
        "results": results,
        "top_scorers": top_scorers,
        "total_participants": len(ranking),
    }
