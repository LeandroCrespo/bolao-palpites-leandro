"""
Dados oficiais da Copa do Mundo 2026 — 48 seleções, 104 jogos.
Fonte: copa2026_data.py do repositório do bolão + tier data de pagina_dicas.py
"""

# Tier 1: Favoritas (FIFA rank 1-5)
# Tier 2: Fortes candidatas (rank 6-10)
# Tier 3: Competitivas (rank 11-20)
# Tier 4: Médias (rank 21-40)
# Tier 5: Zebras (rank 41+)

TEAMS = {
    # ---------- Grupo A ----------
    "MEX": {"name": "México",          "flag": "🇲🇽", "fifa_rank": 15, "tier": 3},
    "RSA": {"name": "África do Sul",   "flag": "🇿🇦", "fifa_rank": 61, "tier": 5},
    "KOR": {"name": "Coreia do Sul",   "flag": "🇰🇷", "fifa_rank": 22, "tier": 3},
    "EUR_D": {
        "name": "Tchéquia", "flag": "🇨🇿", "fifa_rank": 40, "tier": 3,
        "playoff": ["Rep. Tcheca", "Irlanda", "Dinamarca", "Macedônia do Norte"],
    },

    # ---------- Grupo B ----------
    "CAN": {"name": "Canadá",          "flag": "🇨🇦", "fifa_rank": 27, "tier": 4},
    "SUI": {"name": "Suíça",           "flag": "🇨🇭", "fifa_rank": 17, "tier": 3},
    "QAT": {"name": "Qatar",           "flag": "🇶🇦", "fifa_rank": 54, "tier": 5},
    "EUR_A": {
        "name": "Bósnia e Herzegovina", "flag": "🇧🇦", "fifa_rank": 62, "tier": 4,
        "playoff": ["Itália", "Irlanda do Norte", "País de Gales", "Bósnia"],
    },

    # ---------- Grupo C ----------
    "BRA": {"name": "Brasil",          "flag": "🇧🇷", "fifa_rank": 6,  "tier": 2},
    "MAR": {"name": "Marrocos",        "flag": "🇲🇦", "fifa_rank": 7,  "tier": 2},
    "HAI": {"name": "Haiti",           "flag": "🇭🇹", "fifa_rank": 84, "tier": 5},
    "SCO": {"name": "Escócia",         "flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "fifa_rank": 36, "tier": 4},

    # ---------- Grupo D ----------
    "USA": {"name": "Estados Unidos",  "flag": "🇺🇸", "fifa_rank": 14, "tier": 3},
    "PAR": {"name": "Paraguai",        "flag": "🇵🇾", "fifa_rank": 39, "tier": 4},
    "AUS": {"name": "Austrália",       "flag": "🇦🇺", "fifa_rank": 26, "tier": 3},
    "EUR_C": {
        "name": "Turquia", "flag": "🇹🇷", "fifa_rank": 28, "tier": 3,
        "playoff": ["Turquia", "Romênia", "Eslováquia", "Kosovo"],
    },

    # ---------- Grupo E ----------
    "GER": {"name": "Alemanha",        "flag": "🇩🇪", "fifa_rank": 10, "tier": 2},
    "CIV": {"name": "Costa do Marfim", "flag": "🇨🇮", "fifa_rank": 42, "tier": 4},
    "ECU": {"name": "Equador",         "flag": "🇪🇨", "fifa_rank": 23, "tier": 3},
    "CUR": {"name": "Curaçao",         "flag": "🇨🇼", "fifa_rank": 82, "tier": 5},

    # ---------- Grupo F ----------
    "NED": {"name": "Holanda",         "flag": "🇳🇱", "fifa_rank": 8,  "tier": 2},
    "JPN": {"name": "Japão",           "flag": "🇯🇵", "fifa_rank": 18, "tier": 3},
    "TUN": {"name": "Tunísia",         "flag": "🇹🇳", "fifa_rank": 41, "tier": 4},
    "EUR_B": {
        "name": "Suécia", "flag": "🇸🇪", "fifa_rank": 25, "tier": 3,
        "playoff": ["Ucrânia", "Suécia", "Polônia", "Albânia"],
    },

    # ---------- Grupo G ----------
    "BEL": {"name": "Bélgica",         "flag": "🇧🇪", "fifa_rank": 9,  "tier": 2},
    "EGY": {"name": "Egito",           "flag": "🇪🇬", "fifa_rank": 35, "tier": 4},
    "IRN": {"name": "Irã",             "flag": "🇮🇷", "fifa_rank": 20, "tier": 3},
    "NZL": {"name": "Nova Zelândia",   "flag": "🇳🇿", "fifa_rank": 87, "tier": 5},

    # ---------- Grupo H ----------
    "ESP": {"name": "Espanha",         "flag": "🇪🇸", "fifa_rank": 2,  "tier": 1},
    "URU": {"name": "Uruguai",         "flag": "🇺🇾", "fifa_rank": 16, "tier": 3},
    "KSA": {"name": "Arábia Saudita",  "flag": "🇸🇦", "fifa_rank": 60, "tier": 5},
    "CPV": {"name": "Cabo Verde",      "flag": "🇨🇻", "fifa_rank": 67, "tier": 5},

    # ---------- Grupo I ----------
    "FRA": {"name": "França",          "flag": "🇫🇷", "fifa_rank": 1,  "tier": 1},
    "SEN": {"name": "Senegal",         "flag": "🇸🇳", "fifa_rank": 19, "tier": 3},
    "NOR": {"name": "Noruega",         "flag": "🇳🇴", "fifa_rank": 29, "tier": 4},
    "INT_2": {
        "name": "Iraque", "flag": "🇮🇶", "fifa_rank": 68, "tier": 5,
        "playoff": ["Bolívia", "Suriname", "Iraque"],
    },

    # ---------- Grupo J ----------
    "ARG": {"name": "Argentina",       "flag": "🇦🇷", "fifa_rank": 3,  "tier": 1},
    "ALG": {"name": "Argélia",         "flag": "🇩🇿", "fifa_rank": 34, "tier": 4},
    "AUT": {"name": "Áustria",         "flag": "🇦🇹", "fifa_rank": 24, "tier": 3},
    "JOR": {"name": "Jordânia",        "flag": "🇯🇴", "fifa_rank": 64, "tier": 5},

    # ---------- Grupo K ----------
    "POR": {"name": "Portugal",        "flag": "🇵🇹", "fifa_rank": 5,  "tier": 1},
    "COL": {"name": "Colômbia",        "flag": "🇨🇴", "fifa_rank": 13, "tier": 3},
    "UZB": {"name": "Uzbequistão",     "flag": "🇺🇿", "fifa_rank": 50, "tier": 4},
    "INT_1": {
        "name": "RD Congo", "flag": "🇨🇩", "fifa_rank": 64, "tier": 5,
        "playoff": ["Congo DR", "Jamaica", "Nova Caledônia"],
    },

    # ---------- Grupo L ----------
    "ENG": {"name": "Inglaterra",      "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "fifa_rank": 4,  "tier": 1},
    "CRO": {"name": "Croácia",         "flag": "🇭🇷", "fifa_rank": 13, "tier": 3},
    "GHA": {"name": "Gana",            "flag": "🇬🇭", "fifa_rank": 72, "tier": 5},
    "PAN": {"name": "Panamá",          "flag": "🇵🇦", "fifa_rank": 30, "tier": 4},
}

# Formato: (match_number, group, home_team, away_team, date, time, city)
GROUP_STAGE_MATCHES = [
    # ===== GRUPO A =====
    (1,  "A", "MEX",   "RSA",   "2026-06-11", "16:00", "Cidade do México"),
    (2,  "A", "KOR",   "EUR_D", "2026-06-11", "23:00", "Guadalajara"),
    (3,  "A", "EUR_D", "RSA",   "2026-06-18", "13:00", "Atlanta"),
    (4,  "A", "MEX",   "KOR",   "2026-06-18", "22:00", "Guadalajara"),
    (5,  "A", "EUR_D", "MEX",   "2026-06-24", "22:00", "Cidade do México"),
    (6,  "A", "RSA",   "KOR",   "2026-06-24", "22:00", "Monterrey"),

    # ===== GRUPO B =====
    (7,  "B", "CAN",   "EUR_A", "2026-06-12", "16:00", "Toronto"),
    (8,  "B", "QAT",   "SUI",   "2026-06-13", "16:00", "San Francisco"),
    (9,  "B", "SUI",   "EUR_A", "2026-06-18", "16:00", "Los Angeles"),
    (10, "B", "CAN",   "QAT",   "2026-06-18", "19:00", "Vancouver"),
    (11, "B", "SUI",   "CAN",   "2026-06-24", "16:00", "Vancouver"),
    (12, "B", "EUR_A", "QAT",   "2026-06-24", "16:00", "Seattle"),

    # ===== GRUPO C =====
    (13, "C", "BRA",   "MAR",   "2026-06-13", "19:00", "Nova York"),
    (14, "C", "HAI",   "SCO",   "2026-06-13", "22:00", "Boston"),
    (15, "C", "SCO",   "MAR",   "2026-06-19", "19:00", "Boston"),
    (16, "C", "BRA",   "HAI",   "2026-06-19", "22:00", "Filadélfia"),
    (17, "C", "SCO",   "BRA",   "2026-06-24", "19:00", "Miami"),
    (18, "C", "MAR",   "HAI",   "2026-06-24", "19:00", "Atlanta"),

    # ===== GRUPO D =====
    (19, "D", "USA",   "PAR",   "2026-06-12", "22:00", "Los Angeles"),
    (20, "D", "AUS",   "EUR_C", "2026-06-13", "01:00", "Vancouver"),
    (21, "D", "EUR_C", "PAR",   "2026-06-19", "01:00", "San Francisco"),
    (22, "D", "USA",   "AUS",   "2026-06-19", "16:00", "Seattle"),
    (23, "D", "EUR_C", "USA",   "2026-06-25", "23:00", "Los Angeles"),
    (24, "D", "PAR",   "AUS",   "2026-06-25", "23:00", "San Francisco"),

    # ===== GRUPO E =====
    (25, "E", "GER",   "CUR",   "2026-06-14", "14:00", "Houston"),
    (26, "E", "CIV",   "ECU",   "2026-06-14", "20:00", "Filadélfia"),
    (27, "E", "GER",   "CIV",   "2026-06-20", "17:00", "Toronto"),
    (28, "E", "ECU",   "CUR",   "2026-06-20", "21:00", "Kansas City"),
    (29, "E", "ECU",   "GER",   "2026-06-25", "17:00", "Nova York"),
    (30, "E", "CUR",   "CIV",   "2026-06-25", "17:00", "Filadélfia"),

    # ===== GRUPO F =====
    (31, "F", "NED",   "JPN",   "2026-06-14", "17:00", "Dallas"),
    (32, "F", "EUR_B", "TUN",   "2026-06-14", "23:00", "Monterrey"),
    (33, "F", "NED",   "EUR_B", "2026-06-20", "14:00", "Houston"),
    (34, "F", "TUN",   "JPN",   "2026-06-21", "01:00", "Monterrey"),
    (35, "F", "TUN",   "NED",   "2026-06-25", "20:00", "Kansas City"),
    (36, "F", "JPN",   "EUR_B", "2026-06-25", "20:00", "Dallas"),

    # ===== GRUPO G =====
    (37, "G", "BEL",   "EGY",   "2026-06-15", "16:00", "Seattle"),
    (38, "G", "IRN",   "NZL",   "2026-06-15", "22:00", "Los Angeles"),
    (39, "G", "BEL",   "IRN",   "2026-06-21", "16:00", "Los Angeles"),
    (40, "G", "NZL",   "EGY",   "2026-06-21", "22:00", "Vancouver"),
    (41, "G", "EGY",   "IRN",   "2026-06-27", "00:00", "Seattle"),
    (42, "G", "NZL",   "BEL",   "2026-06-27", "00:00", "Vancouver"),

    # ===== GRUPO H =====
    (43, "H", "ESP",   "CPV",   "2026-06-15", "13:00", "Atlanta"),
    (44, "H", "KSA",   "URU",   "2026-06-15", "19:00", "Miami"),
    (45, "H", "ESP",   "KSA",   "2026-06-21", "13:00", "Atlanta"),
    (46, "H", "URU",   "CPV",   "2026-06-21", "19:00", "Miami"),
    (47, "H", "URU",   "ESP",   "2026-06-26", "21:00", "Guadalajara"),
    (48, "H", "CPV",   "KSA",   "2026-06-26", "21:00", "Houston"),

    # ===== GRUPO I =====
    (49, "I", "FRA",   "SEN",   "2026-06-16", "16:00", "Nova York"),
    (50, "I", "INT_2", "NOR",   "2026-06-16", "19:00", "Boston"),
    (51, "I", "FRA",   "INT_2", "2026-06-22", "18:00", "Filadélfia"),
    (52, "I", "NOR",   "SEN",   "2026-06-22", "21:00", "Nova York"),
    (53, "I", "NOR",   "FRA",   "2026-06-26", "16:00", "Boston"),
    (54, "I", "SEN",   "INT_2", "2026-06-26", "16:00", "Toronto"),

    # ===== GRUPO J =====
    (55, "J", "ARG",   "ALG",   "2026-06-16", "22:00", "Kansas City"),
    (56, "J", "AUT",   "JOR",   "2026-06-17", "01:00", "San Francisco"),
    (57, "J", "ARG",   "AUT",   "2026-06-22", "14:00", "Dallas"),
    (58, "J", "JOR",   "ALG",   "2026-06-23", "00:00", "San Francisco"),
    (59, "J", "JOR",   "ARG",   "2026-06-27", "23:00", "Dallas"),
    (60, "J", "ALG",   "AUT",   "2026-06-27", "23:00", "Kansas City"),

    # ===== GRUPO K =====
    (61, "K", "POR",   "INT_1", "2026-06-17", "14:00", "Houston"),
    (62, "K", "UZB",   "COL",   "2026-06-17", "23:00", "Cidade do México"),
    (63, "K", "POR",   "UZB",   "2026-06-23", "14:00", "Houston"),
    (64, "K", "COL",   "INT_1", "2026-06-23", "23:00", "Guadalajara"),
    (65, "K", "COL",   "POR",   "2026-06-27", "20:30", "Miami"),
    (66, "K", "INT_1", "UZB",   "2026-06-27", "20:30", "Atlanta"),

    # ===== GRUPO L =====
    (67, "L", "ENG",   "CRO",   "2026-06-17", "17:00", "Dallas"),
    (68, "L", "GHA",   "PAN",   "2026-06-17", "20:00", "Toronto"),
    (69, "L", "ENG",   "GHA",   "2026-06-23", "17:00", "Boston"),
    (70, "L", "PAN",   "CRO",   "2026-06-23", "20:00", "Toronto"),
    (71, "L", "PAN",   "ENG",   "2026-06-27", "18:00", "Nova York"),
    (72, "L", "CRO",   "GHA",   "2026-06-27", "18:00", "Filadélfia"),
]

# Formato: (match_number, phase, team1_code, team2_code, date, time, city)
# "1A" = 1º do Grupo A, "2B" = 2º do Grupo B, "3CDF" = melhor 3º entre grupos C/D/F
# "W73" = vencedor do jogo 73, "L101" = perdedor do jogo 101
KNOCKOUT_MATCHES = [
    # ===== FASE DE 32 =====
    (73,  "R32",   "1A",   "3CDF",  "2026-06-28", "16:00", "Los Angeles"),
    (74,  "R32",   "2C",   "2D",    "2026-06-29", "17:30", "Boston"),
    (75,  "R32",   "1B",   "3AEF",  "2026-06-29", "22:00", "Monterrey"),
    (76,  "R32",   "2A",   "2B",    "2026-06-29", "14:00", "Houston"),
    (77,  "R32",   "1D",   "3BEF",  "2026-06-30", "18:00", "Nova York"),
    (78,  "R32",   "1C",   "3ABD",  "2026-06-30", "14:00", "Dallas"),
    (79,  "R32",   "2E",   "2F",    "2026-06-30", "22:00", "Cidade do México"),
    (80,  "R32",   "1F",   "3ABC",  "2026-07-01", "13:00", "Atlanta"),
    (81,  "R32",   "1E",   "3DEF",  "2026-07-01", "21:00", "San Francisco"),
    (82,  "R32",   "2G",   "2H",    "2026-07-01", "17:00", "Seattle"),
    (83,  "R32",   "1H",   "3GIJ",  "2026-07-02", "20:00", "Toronto"),
    (84,  "R32",   "1G",   "3HIK",  "2026-07-02", "16:00", "Los Angeles"),
    (85,  "R32",   "2I",   "2J",    "2026-07-03", "00:00", "Vancouver"),
    (86,  "R32",   "1J",   "3GHK",  "2026-07-03", "19:00", "Miami"),
    (87,  "R32",   "1I",   "3JKL",  "2026-07-03", "22:30", "Kansas City"),
    (88,  "R32",   "2K",   "2L",    "2026-07-03", "15:00", "Dallas"),

    # ===== OITAVAS DE FINAL =====
    (89,  "R16",   "W73",  "W74",   "2026-07-04", "18:00", "Filadélfia"),
    (90,  "R16",   "W75",  "W76",   "2026-07-04", "14:00", "Houston"),
    (91,  "R16",   "W77",  "W78",   "2026-07-05", "17:00", "Nova York"),
    (92,  "R16",   "W79",  "W80",   "2026-07-05", "21:00", "Cidade do México"),
    (93,  "R16",   "W81",  "W82",   "2026-07-06", "16:00", "Dallas"),
    (94,  "R16",   "W83",  "W84",   "2026-07-06", "21:00", "Seattle"),
    (95,  "R16",   "W85",  "W86",   "2026-07-07", "13:00", "Atlanta"),
    (96,  "R16",   "W87",  "W88",   "2026-07-07", "17:00", "Vancouver"),

    # ===== QUARTAS DE FINAL =====
    (97,  "QF",    "W89",  "W90",   "2026-07-09", "17:00", "Boston"),
    (98,  "QF",    "W91",  "W92",   "2026-07-10", "16:00", "Los Angeles"),
    (99,  "QF",    "W93",  "W94",   "2026-07-11", "18:00", "Miami"),
    (100, "QF",    "W95",  "W96",   "2026-07-11", "22:00", "Kansas City"),

    # ===== SEMIFINAIS =====
    (101, "SF",    "W97",  "W98",   "2026-07-14", "16:00", "Dallas"),
    (102, "SF",    "W99",  "W100",  "2026-07-15", "16:00", "Atlanta"),

    # ===== DISPUTA DE 3º LUGAR =====
    (103, "3RD",   "L101", "L102",  "2026-07-18", "18:00", "Miami"),

    # ===== FINAL =====
    (104, "FINAL", "W101", "W102",  "2026-07-19", "16:00", "Nova York"),
]

ALL_MATCHES = GROUP_STAGE_MATCHES + KNOCKOUT_MATCHES

# Aliases: códigos reais do banco → mesma entrada do TEAMS
# (times de repescagem registrados com código oficial após confirmação)
TEAMS["BIH"] = TEAMS["EUR_A"]   # Bósnia e Herzegovina
TEAMS["SWE"] = TEAMS["EUR_B"]   # Suécia
TEAMS["TUR"] = TEAMS["EUR_C"]   # Turquia
TEAMS["CZE"] = TEAMS["EUR_D"]   # Tchéquia
TEAMS["COD"] = TEAMS["INT_1"]   # RD Congo
TEAMS["IRQ"] = TEAMS["INT_2"]   # Iraque
TEAMS["CUW"] = TEAMS.get("CUR", {"name": "Curaçao", "flag": "🇨🇼", "fifa_rank": 82, "tier": 5})

# Mapa: código da seleção → grupo
TEAM_GROUP: dict[str, str] = {}
for _m in GROUP_STAGE_MATCHES:
    TEAM_GROUP[_m[2]] = _m[1]
    TEAM_GROUP[_m[3]] = _m[1]

GROUPS = list("ABCDEFGHIJKL")


def get_group_matches(group: str) -> list:
    return [m for m in GROUP_STAGE_MATCHES if m[1] == group]


def get_group_teams(group: str) -> list[str]:
    seen, teams = set(), []
    for m in GROUP_STAGE_MATCHES:
        if m[1] == group:
            for code in (m[2], m[3]):
                if code not in seen:
                    seen.add(code)
                    teams.append(code)
    return teams


def team_display(code: str) -> str:
    t = TEAMS.get(code, {})
    rank = f"FIFA #{t['fifa_rank']}" if t.get('fifa_rank') else "Repescagem"
    tier = t.get('tier', '?')
    playoff = f" (candidatos: {', '.join(t['playoff'])})" if t.get('playoff') else ""
    return f"{t.get('name', code)} ({code}) — {rank} — Tier {tier}{playoff}"
