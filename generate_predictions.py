"""
Previsões geradas por análise do Claude Code — Copa do Mundo 2026.

ELENCOS CONFIRMADOS (principais informações):
Brasil (Ancelotti): Vinicius Jr., Neymar (voltou!), Raphinha, Endrick, Bruno Guimarães, Casemiro
  AUSENTES: Rodrygo (lesão), Estêvão (lesão), Militão (lesão)
Argentina (Scaloni): Messi (6ª Copa!), Lautaro, J.Álvarez, Enzo Fernandez, De Paul, Mac Allister
Espanha (De la Fuente): Yamal, Pedri, Rodri, Nico Williams, Ferran Torres
França (Deschamps): Mbappé (Real Madrid, pico 27 anos), Thuram, Dembele, Tchouameni, Kanté
Inglaterra (Tuchel): Bellingham, Rice, Kane, Saka, Rashford
Portugal (Martinez): Ronaldo (41 anos!), Bernardo Silva, Bruno Fernandes, Leão
Holanda (Koeman): De Jong, Gakpo, Gravenberch, Memphis Depay
Alemanha (Nagelsmann): Musiala, Wirtz, Havertz, Rüdiger
Uruguai (Bielsa): Darwin Nunez, Valverde, Bentancur
Colômbia (Lorenzo): Luis Díaz (Bayern!), Cucho Hernandez, James Rodriguez
Suécia/EUR_B (Potter): Gyokeres (Arsenal) + Isak (Liverpool) — dois atacantes de elite!
México (Aguirre): Gimenez (Milan), Jimenez
Croácia (Dalić): Modric (Milan, 40 anos), Kovacic
EUA (Pochettino): Pulisic, Balogun, Reyna

PONTUAÇÃO DO BOLÃO:
- Placar exato: 20 pts | Resultado + gols 1 time: 15 pts | Só resultado: 10 pts | Só gols: 5 pts
- Grupos: 20 pts (ordem certa) | 10 pts (invertido) | 5 pts (1 certo)
- Pódio (OPÇÃO A — direto, sem bracket): Spain 1º, France 2º, Argentina 3º
  45pts (pódio completo) | 15pts por posição certa | 10pts por time no pódio posição errada

ESTRATÉGIA: placares máximos de 2 gols por time (mais realistas para o bolão).
"""

import json
from datetime import datetime

# ---------------------------------------------------------------------------
# 72 jogos da fase de grupos (match_number, home, away, home_goals, away_goals, reasoning)
# ---------------------------------------------------------------------------
GROUP_MATCH_PREDICTIONS = [
    # ===== GRUPO A: México, África do Sul, Coreia do Sul, Tchéquia =====
    # México tem Gimenez (Milan) e Jimenez — ataque forte + fator casa enorme
    # Coreia: Son Heung-min (34 anos, ainda forte) — 2ª mais forte
    (1,  "MEX",   "RSA",   2, 0, "México em casa com Gimenez e Jimenez; África do Sul sem nível"),
    (2,  "KOR",   "EUR_D", 1, 0, "Coreia do Sul tecnicamente superior à Tchéquia"),
    (3,  "EUR_D", "RSA",   1, 0, "Tchéquia mais experiente; jogo fechado e difícil para ambos"),
    (4,  "MEX",   "KOR",   1, 0, "México decide com gol único; torcida transforma o jogo"),
    (5,  "EUR_D", "MEX",   0, 2, "México na Cidade do México; Tchéquia sem resposta ao ataque"),
    (6,  "RSA",   "KOR",   0, 1, "Coreia confirma 2º lugar; África do Sul não pontua"),

    # ===== GRUPO B: Canadá, Bósnia, Qatar, Suíça =====
    # Canadá com J.David (Juventus) — em casa, perigoso
    # Suíça sólida (FIFA 17) — favorita do grupo
    (7,  "CAN",   "EUR_A", 2, 0, "Canadá em casa (Toronto) com Jonathan David; Bósnia fraca"),
    (8,  "QAT",   "SUI",   0, 2, "Suíça domina; Qatar sem nível para disputar"),
    (9,  "SUI",   "EUR_A", 2, 0, "Suíça organizada supera Bósnia com facilidade"),
    (10, "CAN",   "QAT",   2, 0, "Canadá goleia em Vancouver; David marca novamente"),
    (11, "SUI",   "CAN",   2, 1, "Suíça mais experiente vence duelo decisivo do grupo"),
    (12, "EUR_A", "QAT",   1, 0, "Bósnia vence jogo sem importância para ambos"),

    # ===== GRUPO C: Brasil, Marrocos, Haiti, Escócia =====
    # Brasil sem Rodrygo/Estêvão/Militão mas tem Vinicius Jr. e Neymar de volta
    # Marrocos: semi Copa 2022, organizado (Regragui)
    (13, "BRA",  "MAR",  1, 1, "Brasil vs Marrocos — empate justo; Marrocos defensivo, Brasil sem Rodrygo"),
    (14, "HAI",  "SCO",  0, 2, "Escócia claramente superior ao Haiti"),
    (15, "SCO",  "MAR",  0, 1, "Marrocos sólido na defesa; Escócia sem criatividade"),
    (16, "BRA",  "HAI",  2, 0, "Brasil vence com tranquilidade; Endrick se destaca"),
    (17, "SCO",  "BRA",  0, 1, "Brasil vence jogo mais fechado; sem Rodrygo a criação é menor"),
    (18, "MAR",  "HAI",  2, 0, "Marrocos confirma 2º lugar com vitória tranquila"),

    # ===== GRUPO D: EUA, Paraguai, Austrália, Turquia =====
    # EUA com Pulisic (Milan) e Pochettino — forte em casa
    # Turquia (FIFA 28) equilibrada
    (19, "USA",   "PAR",   2, 0, "EUA em casa (LA) com Pulisic decisivo; Paraguai sem criar"),
    (20, "AUS",   "EUR_C", 1, 1, "Austrália vs Turquia — empate justo entre times equilibrados"),
    (21, "EUR_C", "PAR",   1, 0, "Turquia mais técnica; Paraguai sem ofensividade"),
    (22, "USA",   "AUS",   1, 0, "EUA vence jogo fechado em Seattle; torcida decide"),
    (23, "EUR_C", "USA",   1, 1, "Turquia não se intimida; EUA empata já classificado"),
    (24, "PAR",   "AUS",   1, 1, "Empate equilibrado; ambos já eliminados"),

    # ===== GRUPO E: Alemanha, Curaçao, Costa do Marfim, Equador =====
    # Alemanha com Musiala + Wirtz (Liverpool) — geração de ouro emergindo
    (25, "GER",  "CUR",  2, 0, "Alemanha domina com Musiala e Wirtz; Curaçao sem chances"),
    (26, "CIV",  "ECU",  1, 1, "Confronto equilibrado; Costa do Marfim vs Equador parelho"),
    (27, "GER",  "CIV",  1, 0, "Alemanha vence jogo fechado; Costa do Marfim defensiva"),
    (28, "ECU",  "CUR",  2, 0, "Equador vence com facilidade; diferença de nível clara"),
    (29, "ECU",  "GER",  0, 1, "Alemanha melhor; Wirtz decide em jogo bem disputado"),
    (30, "CUR",  "CIV",  0, 1, "Costa do Marfim confirma 3º com vitória sobre Curaçao"),

    # ===== GRUPO F: Holanda, Japão, Suécia, Tunísia =====
    # SUÉCIA muito mais forte do que esperado: Gyokeres (Arsenal) + Isak (Liverpool)!
    # Graham Potter é um bom técnico
    (31, "NED",   "JPN",   2, 1, "Holanda favorita; Japão perigoso mas De Jong e Gakpo decidem"),
    (32, "EUR_B", "TUN",   2, 0, "Suécia com Gyokeres e Isak goleia Tunísia sem dificuldade"),
    (33, "NED",   "EUR_B", 2, 0, "Holanda supera Suécia; sistema defensivo holandês prevalece"),
    (34, "TUN",   "JPN",   0, 1, "Japão vence Tunísia com eficiência; organização tática"),
    (35, "TUN",   "NED",   0, 2, "Holanda confirma 1º lugar; Tunísia sem resposta"),
    (36, "JPN",   "EUR_B", 0, 1, "SURPRESA: Gyokeres decide para a Suécia; Japão cai em 3º"),

    # ===== GRUPO G: Bélgica, Egito, Irã, Nova Zelândia =====
    # Bélgica com De Bruyne + Doku + Lukaku — ainda forte apesar da geração dourada envelhecer
    (37, "BEL",  "EGY",  2, 1, "Bélgica com De Bruyne e Doku; Egito marca mas perde"),
    (38, "IRN",  "NZL",  1, 0, "Irã sólido e organizado; Nova Zelândia muito inferior"),
    (39, "BEL",  "IRN",  1, 0, "Bélgica vence Irã em jogo fechado; qualidade decide"),
    (40, "NZL",  "EGY",  0, 1, "Egito vence jogo duro; 3 pontos cruciais"),
    (41, "EGY",  "IRN",  1, 1, "Empate tático; ambos disputam 2º lugar"),
    (42, "NZL",  "BEL",  0, 2, "Bélgica finaliza fase de grupos com vitória tranquila"),

    # ===== GRUPO H: Espanha, Cabo Verde, Arábia Saudita, Uruguai =====
    # Espanha: melhor seleção do mundo — Yamal (18), Pedri, Rodri, Nico Williams
    # Uruguai com Bielsa (futebol de pressão) + Darwin Nunez + Valverde
    (43, "ESP",  "CPV",  2, 0, "Espanha campeã Euro 2024 mostra qualidade; Yamal brilha"),
    (44, "KSA",  "URU",  0, 1, "Uruguai de Bielsa + Darwin Nunez; Arábia sem argumentos"),
    (45, "ESP",  "KSA",  2, 0, "Espanha domina com Nico Williams e Ferran Torres"),
    (46, "URU",  "CPV",  2, 0, "Uruguai goleia; Darwin Nunez decisivo novamente"),
    (47, "URU",  "ESP",  1, 2, "Espanha mesmo sem pressão joga bem; Uruguai honra mas perde"),
    (48, "CPV",  "KSA",  1, 1, "Empate entre eliminados; jogo irrelevante"),

    # ===== GRUPO I: França, Senegal, Iraque, Noruega =====
    # França com Mbappé (Real Madrid, 27 anos no pico!) + Thuram + Dembele + Kanté de volta
    # Noruega com Haaland: jogo entre Mbappé e Haaland é o confronto mais esperado!
    (49, "FRA",   "SEN",  2, 1, "França favorita; Mbappé decisivo contra Senegal competitivo"),
    (50, "INT_2", "NOR",  0, 2, "Haaland goleia Iraque; diferença abismal de qualidade"),
    (51, "FRA",   "INT_2", 2, 0, "França passa Iraque com facilidade; Mbappé marca"),
    (52, "NOR",   "SEN",  2, 1, "Haaland decide; Noruega vence Senegal em jogo disputado"),
    (53, "NOR",   "FRA",  1, 2, "MBAPPÉ vs HAALAND! França vence duelo épico; Mbappé decide"),
    (54, "SEN",   "INT_2", 2, 0, "Senegal vence Iraque; confirma 3º lugar"),

    # ===== GRUPO J: Argentina, Argélia, Áustria, Jordânia =====
    # Argentina: Messi (6ª Copa! 38-39 anos), Lautaro, J.Álvarez, Enzo, De Paul
    # Campeã Copa 2022 e Copa América 2024 — favorita ao título
    (55, "ARG",  "ALG",  2, 0, "Argentina campeã absoluta; Messi e Lautaro decidem"),
    (56, "AUT",  "JOR",  2, 0, "Áustria (FIFA 24) supera Jordânia com conforto"),
    (57, "ARG",  "AUT",  1, 0, "Argentina vence jogo mais complicado; Áustria organizada"),
    (58, "JOR",  "ALG",  0, 1, "Argélia vence confronto direto; Jordânia sem ataque"),
    (59, "JOR",  "ARG",  0, 1, "Argentina confirma 1º; Messi joga em ritmo controlado"),
    (60, "ALG",  "AUT",  1, 1, "Áustria confirma 2º por saldo; empate justo"),

    # ===== GRUPO K: Portugal, Congo DR, Uzbequistão, Colômbia =====
    # Portugal com Ronaldo (41 anos!), Bernardo Silva, Bruno Fernandes, Leão
    # Colômbia muito forte: Luis Díaz (Bayern!), Cucho Hernandez, James Rodriguez
    (61, "POR",   "INT_1", 2, 0, "Portugal com Leão e Bruno Fernandes; Congo DR sem nível"),
    (62, "UZB",   "COL",   0, 2, "Colômbia com Luis Díaz (Bayern) e James; Uzbequistão superado"),
    (63, "POR",   "UZB",   2, 0, "Portugal confirma favoritismo; Uzbequistão sem chance"),
    (64, "COL",   "INT_1", 2, 0, "Colômbia goleia; confirma 2º lugar"),
    (65, "COL",   "POR",   0, 1, "Portugal decide confronto direto; Leão marca em Miami"),
    (66, "INT_1", "UZB",  1, 1, "Jogo sem importância; empate entre eliminados"),

    # ===== GRUPO L: Inglaterra, Croácia, Gana, Panamá =====
    # Inglaterra (Tuchel): Bellingham + Rice + Kane + Saka + Rashford (Barcelona)
    # Croácia: Modric (Milan, 40 anos) — ainda conduz mas com limitações físicas
    (67, "ENG",  "CRO",  2, 1, "Inglaterra vence; Bellingham e Saka dominam. Modric ainda presente"),
    (68, "GHA",  "PAN",  1, 1, "Empate equilibrado entre times de nível similar"),
    (69, "ENG",  "GHA",  2, 0, "Inglaterra goleia; Kane e Saka eficientes"),
    (70, "PAN",  "CRO",  0, 2, "Croácia com Modric e Kovacic controla jogo; Panamá superado"),
    (71, "PAN",  "ENG",  0, 2, "Inglaterra confirma 1º com vitória tranquila"),
    (72, "CRO",  "GHA",  1, 0, "Croácia confirma 2º lugar em jogo fechado"),
]

# ---------------------------------------------------------------------------
# Mata-mata (match_number, home, away, home_goals, away_goals, winner, penalties, reasoning)
# NOTA: Estas previsões serão refinadas em live mode conforme a copa avança
# ---------------------------------------------------------------------------
KNOCKOUT_PREDICTIONS = [
    # ===== FASE DE 32 =====
    # 3rd place slot assignment (approximate):
    # 3CDF=SCO, 3AEF=CIV, 3BEF=JPN(3rd), 3ABD=CZE, 3ABC=BIH, 3DEF=EGY,
    # 3GIJ=ALG, 3HIK=SEN, 3GHK=AUS(fallback), 3JKL=GHA(fallback)
    (73,  "MEX", "SCO",  2, 0, "MEX", False, "México em casa com Gimenez; Escócia sem recursos"),
    (74,  "MAR", "TUR",  1, 0, "MAR", False, "Marrocos defensivo vence Turquia em jogo fechado"),
    (75,  "SUI", "CIV",  2, 1, "SUI", False, "Suíça mais experiente supera Costa do Marfim"),
    (76,  "KOR", "CAN",  0, 1, "CAN", False, "Canadá em casa vence Coreia; Jonathan David decide"),
    (77,  "USA", "JPN",  2, 1, "USA", False, "EUA em casa supera Japão; Pulisic e Balogun eficientes"),
    (78,  "BRA", "CZE",  2, 0, "BRA", False, "Brasil supera Tchéquia; Vinicius Jr. faz a diferença"),
    (79,  "ECU", "SWE",  1, 2, "SWE", False, "SUÉCIA SURPREENDE! Gyokeres marca 2; Suécia nas oitavas"),
    (80,  "NED", "BIH",  2, 0, "NED", False, "Holanda passa Bósnia sem dificuldade; De Jong controla"),
    (81,  "GER", "EGY",  2, 0, "GER", False, "Alemanha com Wirtz e Musiala domina o Egito"),
    (82,  "IRN", "URU",  0, 1, "URU", False, "Uruguai de Bielsa e Darwin Nunez vence Irã"),
    (83,  "ESP", "ALG",  2, 0, "ESP", False, "Espanha domina com Yamal e Nico Williams; Argélia superada"),
    (84,  "BEL", "SEN",  1, 0, "BEL", False, "Bélgica vence Senegal em jogo duro; De Bruyne decide"),
    (85,  "NOR", "AUT",  2, 1, "NOR", False, "Haaland marca 2; Noruega supera Áustria com dificuldade"),
    (86,  "ARG", "SCO",  2, 0, "ARG", False, "Argentina com Messi e Lautaro; Escócia sem resposta"),
    (87,  "FRA", "GHA",  2, 0, "FRA", False, "França com Mbappé passa Gana sem dificuldades"),
    (88,  "COL", "CRO",  1, 0, "COL", False, "Colômbia mais jovem vence Croácia envelhecida; Luis Díaz"),

    # ===== OITAVAS DE FINAL =====
    (89,  "MEX", "MAR",  1, 0, "MEX", False, "México quebra maldição em casa! Gimenez decide"),
    (90,  "SUI", "CAN",  1, 0, "SUI", False, "Suíça organizada elimina Canadá em jogo fechado"),
    (91,  "USA", "BRA",  1, 2, "BRA", False, "Brasil vence EUA em jogo tenso; Vinicius e Neymar decidem"),
    (92,  "SWE", "NED",  1, 2, "NED", False, "Holanda supera Suécia; De Jong neutraliza Gyokeres"),
    (93,  "GER", "URU",  1, 0, "GER", False, "Alemanha vence Uruguai de Bielsa em jogo muito disputado"),
    (94,  "ESP", "BEL",  2, 0, "ESP", False, "Espanha domina Bélgica; Yamal e Nico Williams imparáveis"),
    (95,  "NOR", "ARG",  0, 1, "ARG", False, "Argentina para Haaland! Defesa organizada + Lautaro decide"),
    (96,  "FRA", "COL",  2, 1, "FRA", False, "França supera Colômbia; Mbappé marca e dá assistência"),

    # ===== QUARTAS DE FINAL =====
    (97,  "MEX", "SUI",  0, 1, "SUI", False, "Suíça elimina México; organização defensiva prevalece"),
    (98,  "BRA", "NED",  2, 1, "BRA", False, "Brasil elimina Holanda; Vinicius Jr. brilhante nas quartas"),
    (99,  "GER", "ESP",  1, 2, "ESP", False, "Espanha supera Alemanha em clássico europeu; Rodri domina"),
    (100, "ARG", "FRA",  1, 2, "FRA", False, "Mbappé vs Messi — França vence Argentina em clássico"),

    # ===== SEMIFINAIS =====
    (101, "SUI", "BRA",  0, 1, "BRA", False, "Brasil supera Suíça em jogo fechado; Raphinha decide"),
    (102, "ESP", "FRA",  2, 1, "ESP", False, "Espanha bate França como no Euro 2024; Yamal genial"),

    # ===== DISPUTA DE 3º LUGAR =====
    (103, "SUI", "FRA",  1, 2, "FRA", False, "França vence Suíça; bronze digno de uma grande seleção"),

    # ===== FINAL =====
    (104, "BRA", "ESP",  1, 2, "ESP", False, "Espanha bicampeã! Yamal decide contra Brasil valente"),
]

# ---------------------------------------------------------------------------
# PÓDIO — OPÇÃO A: definido diretamente pela análise de qualidade dos elencos
# Espanha: FIFA #1, campeã Euro 2024, Yamal+Pedri+Rodri — melhor seleção coletiva
# França: Mbappé (Real Madrid, 27 anos peak), Thuram, Tchouameni, Kanté — 2ª mais completa
# Argentina: Messi (última Copa), Lautaro+Álvarez, campeã Copa 2022+CA2024 — maior experiência
# ---------------------------------------------------------------------------
PODIUM = {
    "champion": "FRA",
    "runner_up": "ESP",
    "third": "ARG",
}

# ---------------------------------------------------------------------------
# Construtor do predictions.json
# ---------------------------------------------------------------------------

def build_predictions():
    from fixtures import (TEAMS, GROUP_STAGE_MATCHES, KNOCKOUT_MATCHES, GROUPS)
    from simulator import calculate_standings

    def cap(hg, ag, mx=2):
        if hg > mx or ag > mx:
            if hg > ag:
                hg, ag = min(hg, mx), min(ag, mx - 1)
            elif ag > hg:
                ag, hg = min(ag, mx), min(hg, mx - 1)
            else:
                hg = ag = min(hg, mx)
        return hg, ag

    predictions = {
        "generated_at": datetime.now().isoformat(),
        "generated_by": "Claude Code — análise de elencos confirmados Copa 2026",
        "squad_notes": {
            "BRA": "Sem Rodrygo, Estêvão, Militão (lesões). Neymar voltou.",
            "ESP": "Plantel completo. Yamal, Pedri, Rodri, Nico Williams.",
            "FRA": "Mbappé no Real Madrid. Tchouameni, Kanté, Thuram.",
            "ARG": "Messi confirma 6ª Copa. Lautaro, Álvarez, Enzo, De Paul.",
            "ENG": "Tuchel novo técnico. Bellingham, Rice, Kane, Saka, Rashford.",
            "POR": "Ronaldo (41 anos) convocado. Bernardo, Bruno Fernandes, Leão.",
            "EUR_B": "Suécia com Gyokeres (Arsenal) + Isak (Liverpool) — ataque de elite!",
            "URU": "Bielsa técnico. Darwin Nunez, Valverde, Bentancur.",
            "COL": "Luis Díaz (Bayern), James Rodriguez, Cucho Hernandez.",
        },
        "matches": [],
        "groups": {},
        "podium": PODIUM,
    }

    match_lookup = {m[0]: m for m in GROUP_STAGE_MATCHES}
    ko_lookup = {m[0]: m for m in KNOCKOUT_MATCHES}

    # Jogos da fase de grupos
    for mn, home, away, hg, ag, reason in GROUP_MATCH_PREDICTIONS:
        hg, ag = cap(hg, ag)
        m = match_lookup[mn]
        predictions["matches"].append({
            "match_number": mn,
            "phase": "Groups",
            "group": m[1],
            "home_team": home,
            "away_team": away,
            "date": m[4],
            "home_goals": hg,
            "away_goals": ag,
            "reasoning": reason,
        })

    # Standings e classificados de cada grupo
    for group in GROUPS:
        group_matches_pred = [
            {"home_team": h, "away_team": a, "home_goals": hg, "away_goals": ag}
            for mn, h, a, hg, ag, _ in GROUP_MATCH_PREDICTIONS
            if match_lookup[mn][1] == group
        ]
        standings = calculate_standings(group, group_matches_pred)
        # Aplica cap para o standings (já foi aplicado acima, mas recalcula correto)
        group_matches_capped = []
        for mn, h, a, hg, ag, _ in GROUP_MATCH_PREDICTIONS:
            if match_lookup[mn][1] == group:
                hg2, ag2 = cap(hg, ag)
                group_matches_capped.append({"home_team": h, "away_team": a,
                                              "home_goals": hg2, "away_goals": ag2})
        standings = calculate_standings(group, group_matches_capped)

        predictions["groups"][group] = {
            "first": standings[0]["team"],
            "second": standings[1]["team"],
            "third": standings[2]["team"] if len(standings) > 2 else None,
            "standings": standings,
            "analysis": _group_analysis(group),
        }

    # Jogos do mata-mata
    for mn, home, away, hg, ag, winner, pen, reason in KNOCKOUT_PREDICTIONS:
        hg, ag = cap(hg, ag)
        loser = away if winner == home else home
        predictions["matches"].append({
            "match_number": mn,
            "phase": ko_lookup[mn][1],
            "home_team": home,
            "away_team": away,
            "home_goals": hg,
            "away_goals": ag,
            "winner": winner,
            "loser": loser,
            "went_to_penalties": pen,
            "reasoning": reason,
        })

    return predictions


def _group_analysis(group: str) -> str:
    return {
        "A": "México em casa com Gimenez (Milan) domina; Coreia do Sul confirma 2º pelo nível individual",
        "B": "Suíça lidera grupo fraco; Canadá com Jonathan David (Juventus) aproveita fator casa",
        "C": "Brasil sem Rodrygo/Estêvão mas tem Vinicius+Neymar; Marrocos defensivo avança em 2º",
        "D": "EUA em casa com Pochettino e Pulisic; Turquia mais técnica que Austrália e Paraguai",
        "E": "Alemanha com Musiala e Wirtz domina; Equador supera Costa do Marfim no saldo",
        "F": "Holanda 1ª; SUÉCIA SURPRESA com Gyokeres+Isak elimina Japão da 2ª posição",
        "G": "Bélgica com De Bruyne e Doku lidera; Irã disciplinado passa Egito pelo saldo",
        "H": "Espanha (#1 FIFA) domina; Uruguai de Bielsa com Darwin Nunez confirma 2º",
        "I": "França com Mbappé (Real Madrid) lidera; Noruega com Haaland surpreende em 2º",
        "J": "Argentina com Messi (6ª Copa) domina; Áustria confirma 2º pelo saldo sobre Argélia",
        "K": "Portugal com Ronaldo (41!) e Leão lidera; Colômbia com Luis Díaz (Bayern) em 2º",
        "L": "Inglaterra com Tuchel, Bellingham e Saka domina; Croácia com Modric (40) em 2º",
    }.get(group, "")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    predictions = build_predictions()

    with open("predictions.json", "w", encoding="utf-8") as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)

    total = len(predictions["matches"])
    print(f"predictions.json gerado com sucesso!")
    print(f"  Jogos: {total} ({total-32} grupos + 32 mata-mata)")
    print(f"  Grupos: {len(predictions['groups'])}/12")
    p = predictions["podium"]
    print(f"  Podio (Opcao A): {p['champion']} / {p['runner_up']} / {p['third']}")
    print()
    print("CLASSIFICADOS POR GRUPO:")
    from fixtures import TEAMS
    for g, d in predictions["groups"].items():
        f = TEAMS.get(d["first"], {}).get("name", d["first"])
        s = TEAMS.get(d["second"], {}).get("name", d["second"])
        print(f"  Grupo {g}: 1 {f}  |  2 {s}")
