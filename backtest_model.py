"""
backtest_model.py — Validação do modelo de palpites contra os jogos já
disputados da Copa 2026.

Protocolo (walk-forward honesto, sem vazamento):
  1. Treina o modelo apenas com dados ANTERIORES a cada rodada da Copa.
  2. Para cada jogo finalizado, gera a matriz de placares e escolhe o palpite
     de maior EV.
  3. Pontua o palpite pelo placar real com as regras do bolão.
  4. Compara: pontos do modelo x pontos reais do Leandro x melhor participante.

Também reporta métricas estatísticas (log-loss 1X2 vs baseline) e diagnóstico
de calibração de gols (média prevista x média real).

Uso: py backtest_model.py
"""

import math
from datetime import date, datetime

import numpy as np
from sqlalchemy import text

from submitter import get_db_engine
from model_palpites import (
    DATA_INICIO, MEIA_VIDA_DIAS, PESO_TORNEIO, PESO_TORNEIO_DEFAULT,
    ALIASES, CODE_TO_NAME, MAX_GOLS,
    build_model, predict, ev_palpites, pontos,
)

COPA_INICIO = date(2026, 6, 11)


def load_hist(engine, ate: date):
    """Histórico internacional até uma data (exclusive), com pesos calculados
    em relação a essa data (sem olhar o futuro)."""
    rows = []
    with engine.connect() as conn:
        hist = conn.execute(text("""
            SELECT date, home_team, away_team, home_score, away_score,
                   tournament, neutral
            FROM international_results
            WHERE date >= :d0 AND date < :d1
        """), {"d0": DATA_INICIO, "d1": ate}).fetchall()
    for d, h, a, gh, ga, tour, neutral in hist:
        idade = (ate - d).days
        w = math.exp(-math.log(2) * idade / MEIA_VIDA_DIAS) * PESO_TORNEIO.get(tour, PESO_TORNEIO_DEFAULT)
        rows.append((h, a, int(gh), int(ga), w, bool(neutral)))
    return rows


def load_copa_games(engine):
    """Jogos finalizados da Copa em ordem cronológica, com nomes resolvidos."""
    with engine.connect() as conn:
        nomes_validos = {r[0] for r in conn.execute(text(
            "SELECT DISTINCT home_team FROM international_results WHERE date >= :d0"
        ), {"d0": DATA_INICIO}).fetchall()}
        nomes_validos |= {r[0] for r in conn.execute(text(
            "SELECT DISTINCT away_team FROM international_results WHERE date >= :d0"
        ), {"d0": DATA_INICIO}).fetchall()}

        copa = conn.execute(text("""
            SELECT m.id, m.match_number, m.datetime, t1.code, t2.code,
                   m.team1_score, m.team2_score
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE m.status = 'finished'
              AND m.team1_score IS NOT NULL AND m.team2_score IS NOT NULL
            ORDER BY m.datetime
        """)).fetchall()

    def resolve(code):
        cands = ([CODE_TO_NAME[code]] if code in CODE_TO_NAME else []) + ALIASES.get(code, [])
        for c in cands:
            if c in nomes_validos:
                return c
        return None

    games, skipped = [], []
    for mid, num, dt, c1, c2, g1, g2 in copa:
        n1, n2 = resolve(c1), resolve(c2)
        if n1 and n2:
            games.append({"id": mid, "num": num, "dt": dt, "c1": c1, "c2": c2,
                          "n1": n1, "n2": n2, "g1": int(g1), "g2": int(g2)})
        else:
            skipped.append((num, c1, c2))
    if skipped:
        print(f"[AVISO] {len(skipped)} jogos pulados por nome nao resolvido: {skipped}")
    return games


def leandro_points(engine, match_ids):
    """Pontos reais do Leandro (user 15) e do melhor participante nesses jogos."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT p.user_id, u.name, SUM(p.points_awarded)
            FROM predictions p JOIN users u ON u.id = p.user_id
            WHERE p.match_id = ANY(:ids) AND p.points_awarded IS NOT NULL
              AND u.active = TRUE AND u.role <> 'admin'
            GROUP BY p.user_id, u.name
            ORDER BY SUM(p.points_awarded) DESC
        """), {"ids": match_ids}).fetchall()
    return rows


def main():
    engine = get_db_engine()
    games = load_copa_games(engine)
    print(f"{len(games)} jogos finalizados da Copa para backtest\n")

    # Pontos de corte para re-treino (walk-forward): antes da Copa e a cada fase
    cortes = [
        date(2026, 6, 11),   # abertura (treina só pré-Copa)
        date(2026, 6, 19),   # meio da fase de grupos
        date(2026, 6, 27),   # fim da fase de grupos
        date(2026, 7, 1),    # R32
        date(2026, 7, 5),    # R16
        date(2026, 7, 9),    # QF
    ]

    total_model = 0
    total_por_fase = {}
    ll_model, ll_base = 0.0, 0.0
    gols_prev, gols_real = [], []
    acertos = {"exato": 0, "res_gols": 0, "resultado": 0, "gols": 0, "zero": 0}
    detalhe = []

    modelo_cache = None
    corte_atual = None

    for g in games:
        gd = g["dt"].date()
        # Seleciona o corte mais recente anterior ao jogo
        corte = max((c for c in cortes if c <= gd), default=cortes[0])
        if corte != corte_atual:
            corte_atual = corte
            rows = load_hist(engine, corte)
            # Jogos da Copa anteriores ao corte entram no treino com peso alto
            for gg in games:
                if gg["dt"].date() < corte:
                    idade = (corte - gg["dt"].date()).days
                    w = math.exp(-math.log(2) * idade / MEIA_VIDA_DIAS) * PESO_TORNEIO["Copa 2026"]
                    rows.append((gg["n1"], gg["n2"], gg["g1"], gg["g2"], w, True))
            protect = {gg["n1"] for gg in games} | {gg["n2"] for gg in games}
            modelo_cache = build_model(rows, protect=protect)
            m = modelo_cache
            print(f"[treino ate {corte}] {len(rows):,} jogos | mu={m['mu']:.3f} "
                  f"gamma={m['gamma']:.2f} escala={m['scale']:.3f} rho={m['rho']:+.2f}")

        model = modelo_cache
        if g["n1"] not in model["idx"] or g["n2"] not in model["idx"]:
            continue

        P, l1, l2 = predict(model, g["n1"], g["n2"])
        (pa, pb), ev = ev_palpites(P, top=1)[0]
        pts = pontos((pa, pb), (g["g1"], g["g2"]))
        total_model += pts
        fase_key = corte.isoformat()
        total_por_fase[fase_key] = total_por_fase.get(fase_key, 0) + pts

        if pts == 20: acertos["exato"] += 1
        elif pts == 15: acertos["res_gols"] += 1
        elif pts == 10: acertos["resultado"] += 1
        elif pts == 5: acertos["gols"] += 1
        else: acertos["zero"] += 1

        # log-loss 1X2
        pv1 = np.tril(P, -1).sum(); pe = np.trace(P); pv2 = np.triu(P, 1).sum()
        res = 0 if g["g1"] > g["g2"] else (2 if g["g2"] > g["g1"] else 1)
        p_res = [pv1, pe, pv2][res]
        ll_model += -math.log(max(p_res, 1e-9))
        ll_base += -math.log(1/3)

        gols_prev.append(l1 + l2)
        gols_real.append(g["g1"] + g["g2"])

        detalhe.append((g["num"], g["c1"], g["c2"], f"{pa}x{pb}", f"{g['g1']}x{g['g2']}", pts))

    n = len(detalhe)
    print(f"\n=== RESULTADO DO BACKTEST ({n} jogos) ===")
    print(f"  Pontos do MODELO (palpite de maior EV): {total_model}  "
          f"({total_model/n:.2f} pts/jogo)")
    print(f"  Distribuicao: exato={acertos['exato']} res+gols={acertos['res_gols']} "
          f"resultado={acertos['resultado']} gols={acertos['gols']} zero={acertos['zero']}")
    print(f"  Log-loss 1X2: modelo={ll_model/n:.3f} | baseline uniforme={ll_base/n:.3f} "
          f"({'MELHOR' if ll_model < ll_base else 'PIOR'} que o baseline)")
    print(f"  Gols/jogo: previsto={np.mean(gols_prev):.2f} | real={np.mean(gols_real):.2f}")

    # Comparação com participantes reais
    ids = [g["id"] for g in games]
    ranking = leandro_points(engine, ids)
    print(f"\n=== COMPARACAO COM PARTICIPANTES (mesmos {n} jogos) ===")
    for uid, nome, pts in ranking[:5]:
        marker = " <-- VOCE" if uid == 15 else ""
        print(f"  {nome}: {pts} pts{marker}")
    leandro = next((p for u, _, p in ranking if u == 15), None)
    if leandro is not None:
        diff = total_model - leandro
        print(f"\n  MODELO {total_model} x {leandro} LEANDRO -> "
              f"{'modelo GANHOU por' if diff > 0 else 'modelo PERDEU por'} {abs(diff)} pts")

    # Últimos 16 jogos (mata-mata) — relevante para o que vem pela frente
    print("\n=== DETALHE DOS ULTIMOS 18 JOGOS (mata-mata) ===")
    for num, c1, c2, pred, real, pts in detalhe[-18:]:
        print(f"  #{num} {c1} x {c2}: palpite {pred} | real {real} | {pts} pts")


if __name__ == "__main__":
    main()
