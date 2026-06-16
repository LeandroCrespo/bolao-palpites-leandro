"""
Consultas somente leitura ao banco para geração do Boletim do Mestre Leme.
Nunca altera palpites nem qualquer dado de participantes.
"""

from datetime import datetime, date, time
import pytz
from sqlalchemy import text

BRASILIA = pytz.timezone("America/Sao_Paulo")
BULLETIN_HOUR = 23  # 23h Brasília — cobre jogos das 21h (que terminam ~23h); o boletim roda após isso
ADMIN_USER_ID = 1

COPA_OPENING_DATE = date(2026, 6, 11)

# Curiosidades locais das cidades-sede da Copa 2026 — usadas para o Mestre Leme
# comentar bebidas/costumes típicos do lugar onde está a cada boletim.
HOST_CITY_INFO = {
    "Cidade do México": {
        "country": "México",
        "vibe": "praça do Zócalo, a maior da América Latina, com a Catedral Metropolitana iluminada ao fundo, Palácio Nacional à direita, vendedores de tacos e elote nas calçadas, multidão animada comemorando a Copa",
        "drink": "uma michelada ou um shot de tequila",
        "curiosity": "o Zócalo é uma das maiores praças do mundo e coração histórico e cultural do México",
    },
    "Guadalajara": {
        "country": "México",
        "vibe": "calçadão do centro histórico de Guadalajara em frente à icônica Catedral com suas torres gêmeas douradas, mariachis tocando ao vivo, papel picado colorido ao vento, turistas e torcedores misturados",
        "drink": "uma tequila ou um copo de tejuino gelado",
        "curiosity": "Guadalajara é considerada o berço do mariachi e da tequila",
    },
    "Monterrey": {
        "country": "México",
        "vibe": "Macroplaza de Monterrey, uma das maiores praças do mundo, com o Cerro de la Silla ao fundo, o Faro del Comercio laranja iluminado à direita e o Palácio de Gobierno ao fundo",
        "drink": "uma cerveja gelada com limão e sal",
        "curiosity": "Monterrey é famosa pelo cabrito assado e pelas montanhas que cercam a cidade",
    },
    "Nova York": {
        "country": "EUA",
        "vibe": "Times Square iluminada com telões gigantes anunciando a Copa do Mundo, arranha-céus ao redor, taxis amarelos passando, bandeiras de dezenas de países misturadas com os anúncios luminosos",
        "drink": "um copo de cerveja artesanal ou um bagel com cream cheese",
        "curiosity": "o MetLife Stadium vai sediar a grande final da Copa do Mundo",
    },
    "Filadélfia": {
        "country": "EUA",
        "vibe": "escadaria icônica do Museu de Arte de Filadélfia — os famosos 'Rocky Steps' — com a vista panorâmica da Benjamin Franklin Parkway e o skyline da cidade ao fundo, torcedores subindo as degraus em festa",
        "drink": "um cheesesteak e uma cerveja gelada",
        "curiosity": "Filadélfia é famosa pelo Philly cheesesteak e pelo sino da liberdade",
    },
    "Miami": {
        "country": "EUA",
        "vibe": "Ocean Drive em Miami Beach, palmeiras tropicais altas, fachadas art déco coloridas dos anos 1930, sol forte batendo na calçada, Oceano Atlântico azul visível ao fundo",
        "drink": "um mojito ou um suco de cana gelado",
        "curiosity": "Miami tem uma das maiores comunidades brasileiras dos Estados Unidos",
    },
    "Atlanta": {
        "country": "EUA",
        "vibe": "Centennial Olympic Park, com os anéis olímpicos nas fontes interativas e gramado verde, lembrança das Olimpíadas de 1996, arranha-céus do centro ao fundo, torcedores da Copa descansando nas fontes",
        "drink": "uma Coca-Cola gelada (a marca nasceu em Atlanta) ou um chá doce sulista",
        "curiosity": "Atlanta sediou os Jogos Olímpicos de 1996 e é cidade natal da Coca-Cola",
    },
    "Boston": {
        "country": "EUA",
        "vibe": "Faneuil Hall Marketplace, o mercado público histórico mais antigo dos EUA, paredes de tijolo e pedra do século XVIII, bancas de comida ao ar livre, torcedores misturados com turistas no coração histórico de Boston",
        "drink": "uma clam chowder quentinha com uma cerveja",
        "curiosity": "Boston tem uma das comunidades mais antigas de imigrantes irlandeses dos EUA",
    },
    "Dallas": {
        "country": "EUA",
        "vibe": "Reunion Tower, a torre com a cúpula esférica iluminada símbolo de Dallas, skyline texana ao entardecer ao fundo, West End Marketplace movimentado, chapéus de cowboy misturados com camisas de seleções",
        "drink": "um chá gelado bem doce ou uma cerveja artesanal texana",
        "curiosity": "Dallas abriga o maior museu sobre o assassinato de John F. Kennedy",
    },
    "Houston": {
        "country": "EUA",
        "vibe": "Space Center Houston, o centro de controle da NASA, com réplicas de foguetes Saturn V ao fundo, torcedores tirando fotos ao lado de trajes espaciais e cápsulas Apollo originais",
        "drink": "um chá gelado Texas-style ou uma cerveja artesanal local",
        "curiosity": "Houston é a cidade que controla as missões espaciais da NASA",
    },
    "Kansas City": {
        "country": "EUA",
        "vibe": "Country Club Plaza, o primeiro shopping center a céu aberto dos EUA, inspirado na arquitetura espanhola de Sevilha com fontes, azulejos e campanários, decorado com bandeiras da Copa",
        "drink": "uma costelinha de churrasco BBQ estilo Kansas City com um refrigerante gelado",
        "curiosity": "Kansas City tem mais fontes de água do que Roma",
    },
    "Los Angeles": {
        "country": "EUA",
        "vibe": "Calçada da Fama de Hollywood (Walk of Fame), estrelas dos famosos no chão, TCL Chinese Theatre ao fundo, palmeiras altíssimas, sol californiano forte, turistas e torcedores fotografando as estrelas",
        "drink": "um smoothie tropical ou uma cerveja artesanal californiana",
        "curiosity": "o Walk of Fame tem mais de 2.700 estrelas de celebridades no calçamento de Hollywood",
    },
    "San Francisco": {
        "country": "EUA",
        "vibe": "mirador com vista direta para a Golden Gate Bridge, névoa característica envolvendo as torres laranja, baía de São Francisco brilhando ao fundo, torcedores fotografando uma das pontes mais famosas do mundo",
        "drink": "um clam chowder servido dentro de um pão (sourdough bread bowl)",
        "curiosity": "o pão sourdough é uma marca registrada de San Francisco",
    },
    "Seattle": {
        "country": "EUA",
        "vibe": "Pike Place Market, o mercado público mais antigo dos EUA em funcionamento contínuo, peixeiros jogando salmões no ar, bancas de flores coloridas, vista da Puget Sound e das montanhas olímpicas ao fundo",
        "drink": "um café especial bem forte (Seattle é a capital mundial do café)",
        "curiosity": "Seattle é considerada a capital mundial do café — lá nasceu uma famosa rede de cafeterias",
    },
    "Toronto": {
        "country": "Canadá",
        "vibe": "base da Torre CN com a estrutura imponente dominando o enquadramento, Lake Ontario e a skyline de Toronto ao fundo, turistas de todas as partes do mundo esperando para subir à torre mais famosa do Canadá",
        "drink": "uma poutine quentinha com uma cerveja gelada",
        "curiosity": "a Torre CN já foi a estrutura mais alta do mundo e ainda é o símbolo maior de Toronto",
    },
    "Vancouver": {
        "country": "Canadá",
        "vibe": "Stanley Park com os totens indígenas tradicionais e a Burrard Inlet ao fundo, montanhas nevadas da Costa Range ao longe, natureza exuberante dentro da cidade que é marca registrada de Vancouver",
        "drink": "uma poutine ou um café gelado",
        "curiosity": "Vancouver é cercada de montanhas e mar ao mesmo tempo, um cenário único entre as sedes",
    },
}


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


def get_mestre_leme_location(conn, target_date: date) -> dict:
    """
    Retorna onde o Mestre Leme está hoje. Somente leitura.
    No dia da abertura da Copa (11/06/2026) ele está na Cidade do México, saindo do
    Estádio Azteca. Nos dias seguintes, ele acompanha a Seleção Brasileira e está
    na cidade do próximo jogo do Brasil (até esse jogo acontecer, quando então
    "viaja" para a cidade do jogo seguinte).
    """
    if target_date <= COPA_OPENING_DATE:
        info = dict(HOST_CITY_INFO["Cidade do México"])
        info["city"] = "Cidade do México"
        info["note"] = "dia da abertura da Copa do Mundo, saindo do Estádio Azteca após a cerimônia de abertura"
        return info

    rows = conn.execute(text("""
        SELECT m.city, m.datetime
        FROM matches m
        WHERE (m.team1_code = 'BRA' OR m.team2_code = 'BRA')
          AND m.city IS NOT NULL
        ORDER BY m.datetime
    """)).fetchall()

    chosen_city = None
    for city, dt in rows:
        if dt.date() >= target_date:
            chosen_city = city
            break
    if chosen_city is None and rows:
        chosen_city = rows[-1][0]
    if chosen_city is None:
        chosen_city = "Cidade do México"

    info = dict(HOST_CITY_INFO.get(chosen_city, HOST_CITY_INFO["Cidade do México"]))
    info["city"] = chosen_city
    info["note"] = "acompanhando a Seleção Brasileira pela Copa"
    return info


def get_bulletin_data(conn, target_date: date | None = None) -> dict:
    """Agrega todos os dados necessários para o boletim."""
    if target_date is None:
        target_date = datetime.now(BRASILIA).date()

    ranking = get_ranking(conn)
    results = get_todays_results(conn, target_date)
    top_scorers = get_todays_top_scorers(conn, target_date)
    location = get_mestre_leme_location(conn, target_date)

    return {
        "date": target_date.strftime("%d/%m/%Y"),
        "ranking": ranking,
        "results": results,
        "top_scorers": top_scorers,
        "total_participants": len(ranking),
        "location": location,
    }
