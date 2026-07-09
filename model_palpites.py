"""
model_palpites.py — Modelo de previsão de placares para o mata-mata da Copa 2026.

Metodologia:
  1. Ataque/defesa por seleção via Poisson MLE iterativo (esquema de Maher),
     com decaimento temporal exponencial (meia-vida ~1,5 ano) e peso por
     importância do torneio (Copa do Mundo pesa mais que amistoso).
     Base: international_results (histórico) + jogos já disputados da Copa 2026
     (tabela matches), estes com peso máximo por refletirem a forma atual.
  2. Ajuste de Dixon-Coles (rho) para corrigir a dependência em placares baixos
     (0x0, 1x0, 0x1, 1x1), estimado por busca em grade na base recente.
  3. Matriz de probabilidade de placar (0-8 gols) por confronto.
  4. Valor esperado (EV) de cada palpite possível sob as regras do bolão:
     exato=20 / resultado+gols de um time=15 / resultado=10 / gols de um time=5.
  5. Monte Carlo do chaveamento restante para probabilidades de pódio e
     comparação dos palpites de pódio travados (Leandro x Maurício x Danilo).

Uso:  py model_palpites.py            (análise completa)
      py model_palpites.py --sims N   (nº de simulações do Monte Carlo)

Análise privada — não integra o app do bolão.
"""

import os
import sys
import math
from datetime import datetime, date

import numpy as np
from sqlalchemy import text

from submitter import get_db_engine

# ------------------------------------------------------------------
# Configuração
# ------------------------------------------------------------------

DATA_INICIO = date(2021, 1, 1)      # janela de treino
MEIA_VIDA_DIAS = 547                # decaimento temporal (~1,5 ano)
MAX_GOLS = 8                        # dimensão da matriz de placares
HOJE = date(2026, 7, 9)

# Peso por importância do torneio (multiplicador do peso temporal)
PESO_TORNEIO = {
    "FIFA World Cup": 3.0,
    "Copa 2026": 4.0,               # jogos desta Copa (tabela matches)
    "FIFA World Cup qualification": 2.0,
    "UEFA Euro": 2.5,
    "Copa América": 2.5,
    "UEFA Euro qualification": 1.8,
    "African Cup of Nations": 2.0,
    "AFC Asian Cup": 2.0,
    "CONCACAF Championship": 1.8,
    "UEFA Nations League": 1.5,
    "CONCACAF Nations League": 1.3,
}
PESO_TORNEIO_DEFAULT = 1.0          # amistosos e demais

# Pontuação do bolão (valores reais do banco, via scoring.py)
PTS_EXATO = 20
PTS_RESULTADO_GOLS = 15
PTS_RESULTADO = 10
PTS_GOLS = 5

# Pódio (valores reais do banco)
PODIO_COMPLETO = 45
PODIO_CAMPEAO = 15
PODIO_VICE = 15
PODIO_TERCEIRO = 15
PODIO_FORA_ORDEM = 10

# Palpites de pódio travados (público — não pode mais ser alterado)
PODIOS_TRAVADOS = {
    "Leandro":  ("FRA", "ESP", "ARG"),
    "Mauricio": ("FRA", "ESP", "BRA"),
    "Danilo":   ("FRA", "ESP", "POR"),
}

# Times vivos e seus nomes na base histórica
CODE_TO_NAME = {
    "FRA": "France", "NOR": "Norway", "ENG": "England", "ESP": "Spain",
    "BEL": "Belgium", "ARG": "Argentina", "SUI": "Switzerland", "MAR": "Morocco",
}

# Aliases para mapear códigos da tabela matches -> nomes do dataset martj42
ALIASES = {
    "USA": ["United States", "USA"],
    "COD": ["DR Congo", "Congo DR"],
    "CPV": ["Cape Verde", "Cape Verde Islands"],
    "TUR": ["Türkiye", "Turkey"],
    "CZE": ["Czechia", "Czech Republic"],
    "KOR": ["South Korea"],
    "RSA": ["South Africa"],
    "KSA": ["Saudi Arabia"],
    "CIV": ["Ivory Coast"],
    "IRN": ["Iran"],
    "NED": ["Netherlands"],
    "GER": ["Germany"],
    "CRO": ["Croatia"],
    "CUW": ["Curaçao", "Curacao"],
    "BIH": ["Bosnia and Herzegovina", "Bosnia & Herzegovina"],
    "NZL": ["New Zealand"],
    "HAI": ["Haiti"],
    "JOR": ["Jordan"],
    "UZB": ["Uzbekistan"],
    "QAT": ["Qatar"],
    "SCO": ["Scotland"],
    "SEN": ["Senegal"],
    "TUN": ["Tunisia"],
    "EGY": ["Egypt"],
    "ALG": ["Algeria"],
    "GHA": ["Ghana"],
    "AUS": ["Australia"],
    "AUT": ["Austria"],
    "JPN": ["Japan"],
    "MEX": ["Mexico"],
    "CAN": ["Canada"],
    "PAN": ["Panama"],
    "PAR": ["Paraguay"],
    "URU": ["Uruguay"],
    "ECU": ["Ecuador"],
    "COL": ["Colombia"],
    "BRA": ["Brazil"],
    "POR": ["Portugal"],
    "SWE": ["Sweden"],
    "IRQ": ["Iraq"],
}


# ------------------------------------------------------------------
# Carga de dados
# ------------------------------------------------------------------

def load_data(engine):
    """Carrega histórico + jogos da Copa 2026 e devolve lista de
    (home, away, gh, ga, peso, neutro)."""
    rows = []
    with engine.connect() as conn:
        # Histórico internacional
        hist = conn.execute(text("""
            SELECT date, home_team, away_team, home_score, away_score,
                   tournament, neutral
            FROM international_results
            WHERE date >= :d0
        """), {"d0": DATA_INICIO}).fetchall()

        # Nomes válidos no dataset (para resolver códigos da Copa)
        nomes_validos = {r[0] for r in conn.execute(text(
            "SELECT DISTINCT home_team FROM international_results WHERE date >= :d0"
        ), {"d0": DATA_INICIO}).fetchall()}
        nomes_validos |= {r[0] for r in conn.execute(text(
            "SELECT DISTINCT away_team FROM international_results WHERE date >= :d0"
        ), {"d0": DATA_INICIO}).fetchall()}

        # Jogos finalizados da Copa 2026 (placar de 90 min — consistente com o bolão)
        copa = conn.execute(text("""
            SELECT m.datetime, t1.code, t2.code, m.team1_score, m.team2_score
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE m.status = 'finished'
              AND m.team1_score IS NOT NULL AND m.team2_score IS NOT NULL
        """)).fetchall()

    def resolve(code):
        for cand in ([CODE_TO_NAME.get(code)] if code in CODE_TO_NAME else []) + ALIASES.get(code, []):
            if cand and cand in nomes_validos:
                return cand
        return None

    nao_resolvidos = set()

    for d, h, a, gh, ga, tour, neutral in hist:
        idade = (HOJE - d).days
        w_tempo = math.exp(-math.log(2) * idade / MEIA_VIDA_DIAS)
        w = w_tempo * PESO_TORNEIO.get(tour, PESO_TORNEIO_DEFAULT)
        rows.append((h, a, int(gh), int(ga), w, bool(neutral)))

    for dt, c1, c2, g1, g2, in copa:
        n1, n2 = resolve(c1), resolve(c2)
        if not n1 or not n2:
            nao_resolvidos.add(c1 if not n1 else c2)
            continue
        idade = (HOJE - dt.date()).days
        w_tempo = math.exp(-math.log(2) * idade / MEIA_VIDA_DIAS)
        w = w_tempo * PESO_TORNEIO["Copa 2026"]
        rows.append((n1, n2, int(g1), int(g2), w, True))  # Copa em campo neutro

    if nao_resolvidos:
        print(f"[AVISO] Codigos sem nome no dataset (jogos ignorados): {sorted(nao_resolvidos)}")

    return rows


# ------------------------------------------------------------------
# Modelo: Poisson iterativo (Maher) + Dixon-Coles
# ------------------------------------------------------------------

def fit_model(rows, n_iter=60):
    """Estima forca de ataque/defesa por time + vantagem de casa.
    Modelo: gols_home ~ Poisson(mu * att_h * def_a * gamma^(nao-neutro))
            gols_away ~ Poisson(mu * att_a * def_h)
    """
    teams = sorted({r[0] for r in rows} | {r[1] for r in rows})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    H = np.array([idx[r[0]] for r in rows])
    A = np.array([idx[r[1]] for r in rows])
    GH = np.array([r[2] for r in rows], dtype=float)
    GA = np.array([r[3] for r in rows], dtype=float)
    W = np.array([r[4] for r in rows])
    NEUTRO = np.array([r[5] for r in rows])

    att = np.ones(n)
    dfs = np.ones(n)
    gamma = 1.25   # vantagem de casa inicial
    mu = (W @ (GH + GA)) / (2 * W.sum())   # média de gols por time/jogo

    for _ in range(n_iter):
        g_home = np.where(NEUTRO, 1.0, gamma)
        # lambda esperado por jogo
        lam_h = mu * att[H] * dfs[A] * g_home
        lam_a = mu * att[A] * dfs[H]

        # Atualiza ataque: soma ponderada de gols / soma ponderada de exposicao
        num_att = np.zeros(n); den_att = np.zeros(n)
        np.add.at(num_att, H, W * GH)
        np.add.at(den_att, H, W * mu * dfs[A] * g_home)
        np.add.at(num_att, A, W * GA)
        np.add.at(den_att, A, W * mu * dfs[H])
        att = np.where(den_att > 0, num_att / den_att, 1.0)
        att /= att.mean()  # normaliza

        # Atualiza defesa (multiplicador de gols sofridos)
        num_def = np.zeros(n); den_def = np.zeros(n)
        np.add.at(num_def, A, W * GH)
        np.add.at(den_def, A, W * mu * att[H] * g_home)
        np.add.at(num_def, H, W * GA)
        np.add.at(den_def, H, W * mu * att[A])
        dfs = np.where(den_def > 0, num_def / den_def, 1.0)
        dfs /= dfs.mean()

        # Atualiza vantagem de casa (apenas jogos nao-neutros)
        mask = ~NEUTRO
        if mask.sum() > 0:
            num_g = (W[mask] * GH[mask]).sum()
            den_g = (W[mask] * mu * att[H[mask]] * dfs[A[mask]]).sum()
            gamma = num_g / den_g

    return teams, idx, att, dfs, gamma, mu


def two_pass_fit(rows, protect=None, pct_corte=40):
    """Ajuste em duas passadas: a primeira estima forças; a segunda descarta
    jogos envolvendo seleções muito fracas (abaixo do percentil de corte),
    que distorcem os parâmetros de defesa das seleções de elite via goleadas.
    Times em `protect` (ex.: participantes da Copa) nunca são descartados."""
    protect = protect or set()
    teams, idx, att, dfs, gamma, mu = fit_model(rows)
    forca = {}
    for t in teams:
        a_, d_ = att[idx[t]], dfs[idx[t]]
        forca[t] = (a_ / d_) if d_ > 0 and np.isfinite(a_) else 0.0
    corte = np.percentile([v for v in forca.values() if np.isfinite(v)], pct_corte)
    fortes = {t for t in teams if forca[t] >= corte} | protect
    rows2 = [r for r in rows if r[0] in fortes and r[1] in fortes]
    return fit_model(rows2)


def calibrate_scale(rows, idx, att, dfs, mu):
    """Fator de escala de gols estimado apenas em jogos NEUTROS de torneios
    competitivos (contexto = Copa): razão entre gols reais e previstos.
    Corrige o viés de subestimação em campo neutro."""
    num = den = 0.0
    for h, a, gh, ga, w, neutro in rows:
        if not neutro or w < 0.05:
            continue
        if h not in idx or a not in idx:
            continue
        lh = mu * att[idx[h]] * dfs[idx[a]]
        la = mu * att[idx[a]] * dfs[idx[h]]
        num += w * (gh + ga)
        den += w * (lh + la)
    return num / den if den > 0 else 1.0


def dc_tau(gh, ga, lh, la, rho):
    """Fator de correcao Dixon-Coles para placares baixos."""
    if gh == 0 and ga == 0:
        return 1 - lh * la * rho
    if gh == 0 and ga == 1:
        return 1 + lh * rho
    if gh == 1 and ga == 0:
        return 1 + la * rho
    if gh == 1 and ga == 1:
        return 1 - rho
    return 1.0


def fit_rho(rows, idx, att, dfs, gamma, mu, scale=1.0):
    """Busca em grade do rho de Dixon-Coles maximizando log-verossimilhanca
    ponderada da base recente (2 anos)."""
    recentes = [r for r in rows if r[4] > 0.3 and r[0] in idx and r[1] in idx]
    best_rho, best_ll = 0.0, -np.inf
    for rho in np.arange(-0.20, 0.11, 0.02):
        ll = 0.0
        for h, a, gh, ga, w, neutro in recentes:
            g = 1.0 if neutro else gamma
            s = scale if neutro else 1.0
            lh = mu * att[idx[h]] * dfs[idx[a]] * g * s
            la = mu * att[idx[a]] * dfs[idx[h]] * s
            tau = dc_tau(gh, ga, lh, la, rho)
            if tau <= 0:
                ll = -np.inf
                break
            p = (math.exp(-lh) * lh**gh / math.factorial(gh)
                 * math.exp(-la) * la**ga / math.factorial(ga) * tau)
            if p <= 0:
                ll = -np.inf
                break
            ll += w * math.log(p)
        if ll > best_ll:
            best_ll, best_rho = ll, rho
    return best_rho


def score_matrix(t1, t2, idx, att, dfs, mu, rho, scale=1.0):
    """Matriz P(placar) para jogo em campo neutro."""
    l1 = mu * att[idx[t1]] * dfs[idx[t2]] * scale
    l2 = mu * att[idx[t2]] * dfs[idx[t1]] * scale
    P = np.zeros((MAX_GOLS + 1, MAX_GOLS + 1))
    for i in range(MAX_GOLS + 1):
        for j in range(MAX_GOLS + 1):
            p = (math.exp(-l1) * l1**i / math.factorial(i)
                 * math.exp(-l2) * l2**j / math.factorial(j))
            P[i, j] = p * dc_tau(i, j, l1, l2, rho)
    P /= P.sum()
    return P, l1, l2


# ------------------------------------------------------------------
# Valor esperado dos palpites
# ------------------------------------------------------------------

def build_model(rows, protect=None, verbose=False):
    """Pipeline completo: fit em duas passadas + calibracao de escala + rho.
    Retorna dict com todos os parametros necessarios para prever."""
    teams, idx, att, dfs, gamma, mu = two_pass_fit(rows, protect=protect)
    scale = calibrate_scale(rows, idx, att, dfs, mu)
    rho = fit_rho(rows, idx, att, dfs, gamma, mu, scale=scale)
    if verbose:
        print(f"  {len(teams)} selecoes | mu={mu:.3f} | gamma={gamma:.2f} | "
              f"escala neutra={scale:.3f} | rho={rho:+.2f}")
    return {"teams": teams, "idx": idx, "att": att, "dfs": dfs,
            "gamma": gamma, "mu": mu, "scale": scale, "rho": rho}


def predict(model, t1, t2):
    """Matriz de placares usando o modelo calibrado."""
    return score_matrix(t1, t2, model["idx"], model["att"], model["dfs"],
                        model["mu"], model["rho"], scale=model["scale"])


def pontos(pred, real):
    pa, pb = pred
    ra, rb = real
    res_p = 0 if pa == pb else (1 if pa > pb else -1)
    res_r = 0 if ra == rb else (1 if ra > rb else -1)
    acertou_res = res_p == res_r
    acertou_gol = (pa == ra) or (pb == rb)
    if pa == ra and pb == rb:
        return PTS_EXATO
    if acertou_res and acertou_gol:
        return PTS_RESULTADO_GOLS
    if acertou_res:
        return PTS_RESULTADO
    if acertou_gol:
        return PTS_GOLS
    return 0


def ev_palpites(P, top=8):
    """EV de cada palpite candidato, ordenado."""
    evs = []
    for a in range(6):
        for b in range(6):
            ev = sum(P[i, j] * pontos((a, b), (i, j))
                     for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1))
            evs.append(((a, b), ev))
    evs.sort(key=lambda x: -x[1])
    return evs[:top]


def resumo_matriz(P, t1, t2):
    pv1 = np.tril(P, -1).sum()   # t1 vence (linhas > colunas)
    pe = np.trace(P)
    pv2 = np.triu(P, 1).sum()
    print(f"    P({t1} vence 90min) = {pv1:.1%} | empate = {pe:.1%} | P({t2} vence) = {pv2:.1%}")
    flat = [((i, j), P[i, j]) for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1)]
    flat.sort(key=lambda x: -x[1])
    tops = "  ".join(f"{i}x{j}:{p:.1%}" for (i, j), p in flat[:6])
    print(f"    Placares mais provaveis: {tops}")


# ------------------------------------------------------------------
# Monte Carlo do chaveamento
# ------------------------------------------------------------------

def sample_result(P, rng):
    """Sorteia um placar de 90 min a partir da matriz."""
    flat = P.flatten()
    k = rng.choice(len(flat), p=flat / flat.sum())
    return divmod(k, MAX_GOLS + 1)


def winner_after_draw(t1, t2, idx, att, dfs, rng):
    """Vencedor em prorrogacao/penaltis: probabilidade proporcional a forca,
    encolhida para 50/50 (penaltis sao quase cara-ou-coroa)."""
    f1 = att[idx[t1]] / dfs[idx[t1]]
    f2 = att[idx[t2]] / dfs[idx[t2]]
    p1 = f1 / (f1 + f2)
    p1 = 0.5 + 0.5 * (p1 - 0.5)   # encolhe 50% em direcao a 0.5
    return t1 if rng.random() < p1 else t2


def podium_points(pred, real):
    """Pontos de podio: pred/real = (campeao, vice, terceiro) em codigos."""
    pc, pv, pt = pred
    rc, rv, rt = real
    if pc == rc and pv == rv and pt == rt:
        return PODIO_COMPLETO
    total = 0
    podio_real = {rc, rv, rt}
    if pc == rc:
        total += PODIO_CAMPEAO
    elif pc in podio_real:
        total += PODIO_FORA_ORDEM
    if pv == rv:
        total += PODIO_VICE
    elif pv in podio_real:
        total += PODIO_FORA_ORDEM
    if pt == rt:
        total += PODIO_TERCEIRO
    elif pt in podio_real:
        total += PODIO_FORA_ORDEM
    return total


def monte_carlo(model, n_sims, rng):
    idx, att, dfs = model["idx"], model["att"], model["dfs"]
    """Simula QF restantes + SF + 3o lugar + final.
    Estrutura atual do chaveamento:
      #98 NOR x ENG, #99 ESP x BEL, #100 ARG x SUI (QF)
      #101 FRA x W98 | #102 W99 x W100 (SF)
      #103 L101 x L102 | #104 W101 x W102
    """
    matrices = {}

    def M(a, b):
        if (a, b) not in matrices:
            matrices[(a, b)] = predict(model, a, b)[0]
        return matrices[(a, b)]

    nome = {v: k for k, v in CODE_TO_NAME.items()}

    def play(c1, c2):
        t1, t2 = CODE_TO_NAME[c1], CODE_TO_NAME[c2]
        g1, g2 = sample_result(M(t1, t2), rng)
        if g1 > g2:
            return c1, c2
        if g2 > g1:
            return c2, c1
        w = winner_after_draw(t1, t2, idx, att, dfs, rng)
        wc = nome[w]
        return (wc, c2 if wc == c1 else c1)

    cont_campeao = {}
    cont_vice = {}
    cont_terceiro = {}
    pts_users = {u: 0.0 for u in PODIOS_TRAVADOS}
    dist_gap = []   # pontos Leandro - pontos Mauricio por sim

    for _ in range(n_sims):
        w98, _l98 = play("NOR", "ENG")
        w99, _l99 = play("ESP", "BEL")
        w100, _l100 = play("ARG", "SUI")

        w101, l101 = play("FRA", w98)
        w102, l102 = play(w99, w100)

        w103, _ = play(l101, l102)          # 3o lugar
        w104, l104 = play(w101, w102)       # final

        real = (w104, l104, w103)
        cont_campeao[w104] = cont_campeao.get(w104, 0) + 1
        cont_vice[l104] = cont_vice.get(l104, 0) + 1
        cont_terceiro[w103] = cont_terceiro.get(w103, 0) + 1

        pts = {u: podium_points(p, real) for u, p in PODIOS_TRAVADOS.items()}
        for u in pts_users:
            pts_users[u] += pts[u]
        dist_gap.append(pts["Leandro"] - pts["Mauricio"])

    print("\n=== MONTE CARLO DO CHAVEAMENTO (n = {:,}) ===".format(n_sims))
    for label, cont in [("Campeao", cont_campeao), ("Vice", cont_vice), ("3o lugar", cont_terceiro)]:
        top = sorted(cont.items(), key=lambda x: -x[1])[:5]
        linha = "  ".join(f"{c}:{v / n_sims:.1%}" for c, v in top)
        print(f"  {label}: {linha}")

    print("\n  Pontos esperados de podio (palpites travados):")
    for u, total in sorted(pts_users.items(), key=lambda x: -x[1]):
        print(f"    {u}: {total / n_sims:.1f} pts  (palpite: {' / '.join(PODIOS_TRAVADOS[u])})")

    gap = np.array(dist_gap)
    print(f"\n  Ganho de podio Leandro vs Mauricio: media {gap.mean():+.1f} pts | "
          f"P(ganha algo) = {(gap > 0).mean():.1%} | P(empata) = {(gap == 0).mean():.1%}")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    n_sims = 100_000
    if "--sims" in sys.argv:
        n_sims = int(sys.argv[sys.argv.index("--sims") + 1])

    rng = np.random.default_rng(42)
    engine = get_db_engine()

    print("Carregando dados...")
    rows = load_data(engine)
    print(f"  {len(rows):,} jogos na base de treino (desde {DATA_INICIO})")

    print("Ajustando modelo (duas passadas + calibracao de escala + rho)...")
    protect = {CODE_TO_NAME[c] for c in CODE_TO_NAME}
    model = build_model(rows, protect=protect, verbose=True)
    idx, att, dfs = model["idx"], model["att"], model["dfs"]

    # Forcas das selecoes vivas
    print("\n=== FORCA DAS SELECOES VIVAS (ataque x defesa; defesa menor = melhor) ===")
    vivos = ["FRA", "ENG", "ESP", "ARG", "BEL", "NOR", "SUI"]
    for c in sorted(vivos, key=lambda c: -att[idx[CODE_TO_NAME[c]]] / dfs[idx[CODE_TO_NAME[c]]]):
        t = CODE_TO_NAME[c]
        print(f"  {c}: ataque {att[idx[t]]:.2f} | defesa {dfs[idx[t]]:.2f} | forca {att[idx[t]]/dfs[idx[t]]:.2f}")

    # QF restantes
    print("\n=== QUARTAS DE FINAL — MATRIZES E EV DOS PALPITES ===")
    jogos = [("98", "NOR", "ENG"), ("99", "ESP", "BEL"), ("100", "ARG", "SUI")]
    for num, c1, c2 in jogos:
        t1, t2 = CODE_TO_NAME[c1], CODE_TO_NAME[c2]
        P, l1, l2 = predict(model, t1, t2)
        print(f"\n  Jogo #{num}: {c1} x {c2}  (lambdas: {l1:.2f} x {l2:.2f})")
        resumo_matriz(P, c1, c2)
        print("    Melhores palpites por EV:")
        for (a, b), ev in ev_palpites(P):
            print(f"      {a} x {b}  ->  EV = {ev:.2f} pts")

    # SF possiveis (condicionais)
    print("\n=== SEMIFINAIS POSSIVEIS (EV condicional, para planejamento) ===")
    sf_possiveis = [
        ("101", "FRA", "NOR"), ("101", "FRA", "ENG"),
        ("102", "ESP", "ARG"), ("102", "ESP", "SUI"),
        ("102", "BEL", "ARG"), ("102", "BEL", "SUI"),
    ]
    for num, c1, c2 in sf_possiveis:
        t1, t2 = CODE_TO_NAME[c1], CODE_TO_NAME[c2]
        P, l1, l2 = predict(model, t1, t2)
        best = ev_palpites(P, top=3)
        picks = " | ".join(f"{a}x{b} EV={ev:.2f}" for (a, b), ev in best)
        pv1 = np.tril(P, -1).sum(); pe = np.trace(P); pv2 = np.triu(P, 1).sum()
        print(f"  #{num} {c1} x {c2}: [{pv1:.0%}/{pe:.0%}/{pv2:.0%}]  {picks}")

    # Monte Carlo do podio
    monte_carlo(model, n_sims, rng)


if __name__ == "__main__":
    main()
