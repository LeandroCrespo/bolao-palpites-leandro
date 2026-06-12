"""
Gera o roteiro do Boletim do Mestre Leme usando Claude.
O roteiro é narrado por Mestre Leme — botequeiro brasileiro, irreverente e apaixonado por futebol.
"""

import anthropic

MODEL = "claude-sonnet-4-6"
MAX_SCRIPT_WORDS = 220  # ~1m30s de vídeo no D-ID

# ---------------------------------------------------------------------------
# Contexto fixo do personagem — prefixado em todos os prompts de vídeo
# ---------------------------------------------------------------------------

# Guarda-roupa do Mestre Leme — varia a cada boletim, mantendo rosto/corpo/cenário/personalidade fixos
_OUTFITS = [
    "open unbuttoned blue-and-white plaid flannel shirt over a plain white undershirt, dark jeans",
    "bright green and yellow Brazil football team (Seleção) jersey with sleeves slightly rolled up, dark jeans",
    "white short-sleeve guayabera-style shirt unbuttoned at the collar, dark jeans",
    "red and black checkered flannel shirt over a plain white undershirt, dark jeans",
    "yellow polo shirt with a small embroidered boteco logo on the chest, dark jeans",
    "open unbuttoned orange-and-brown plaid flannel shirt over a plain white undershirt, dark jeans",
    "navy blue zip-up jacket worn open over a plain white t-shirt, dark jeans",
]


def _build_fixed_context(date_str: str, location: dict | None = None) -> str:
    """
    Monta o bloco FIXED CHARACTER do Mestre Leme, variando a roupa a cada boletim
    (com base na data) e o cenário (com base na cidade onde ele está, acompanhando
    a Copa), mantendo rosto, corpo, bigode e personalidade fixos.
    """
    idx = sum(int(c) for c in date_str if c.isdigit()) % len(_OUTFITS)
    outfit = _OUTFITS[idx]

    if location:
        setting = (
            f"a lively spot in {location['city']}, {location['country']} — {location['vibe']}, "
            f"warm inviting lighting, constant ambient sounds of a cheering World Cup crowd mixed "
            f"with low conversation murmur and clinking glasses"
        )
    else:
        setting = (
            "interior of an authentic São Paulo neighborhood boteco — long dark wooden bar counter "
            "with worn varnish and glass ring stains, mismatched high bar stools, Brazilian green-and-yellow "
            "flag pinned on the brick wall behind him, old CRT television mounted in the upper corner showing "
            "football highlights, shelves lined with cachaça and beer bottles, warm incandescent yellow lighting "
            "casting amber tones, constant boteco ambient sounds (low conversation murmur, clinking glasses, "
            "faint samba radio)"
        )

    return f"""FIXED CHARACTER: Mestre Leme — a stocky, heavy-set Brazilian man, approximately 55 years old (match the provided reference photo exactly, if attached).
FACE: expressive full face with warm light-tan skin, FULL tousled dark salt-and-pepper hair — medium-short, slightly messy, graying at the temples and sides (NOT shaved, NOT cut close). Short scruffy salt-and-pepper beard of a few days' growth covering jaw and chin, blending into a fuller graying mustache. Thick dark eyebrows, warm brown eyes with deep laugh lines, strong nose, a huge open contagious smile showing the upper teeth — the kind of smile that makes every room feel welcoming.
BODY: stocky, heavy-set build with a proud round belly, broad shoulders, expressive Brazilian hand gestures while speaking.
OUTFIT: {outfit}. Holds a thick glass of chope (Brazilian draft beer) with generous white foam at the rim.
SETTING: {setting}.
STYLE: photorealistic, cinematic, shallow depth of field with background softly blurred, warm saturated amber color grade. Duration: exactly 8 seconds."""

_VIDEO_PROMPT_SYSTEM = """Você é roteirista e diretor de vídeo do Mestre Leme. Sua tarefa é criar 6 prompts
para o Gemini Pro (Veo 3), cada um de EXATAMENTE 8 segundos, que juntos formam um boletim de ~48 segundos.

PERSONAGEM: Mestre Leme — botequeiro brasileiro raiz, 55 anos, corpulento, cabelo grisalho cheio
e despenteado, barba por fazer grisalha com bigode, chope na mão. Fala Português Brasileiro com
sotaque paulistano (rápido, vogais fechadas).
Expressões típicas: "meu povo", "meu consagrado", "minha gente", "meu benzinho", "tá louco", "vixe!".
Apelidos para líderes: "mesa VIP" ou "donos do boteco". Para os últimos: "zona de rebaixamento" ou "devendo o chopão".

VIAGEM PELA COPA: Mestre Leme está viajando atrás da Seleção Brasileira pela Copa do Mundo 2026.
A cada boletim ele está em uma cidade-sede diferente (informada no contexto), com roupa e cenário
que mudam a cada vídeo, mas seu rosto, corpo, bigode e jeito de falar são SEMPRE os mesmos.

REGRAS OBRIGATÓRIAS:
1. Cada clip = EXATAMENTE 8 segundos — máximo 18 palavras de diálogo por clip
2. Os 6 clips formam uma CENA CONTÍNUA no local onde ele está — mesma posição, mesma luz, fluxo natural entre eles
3. Cada clip TERMINA com gesto/ação que o próximo clip CONTINUA (ex: começa a levantar o copo, próximo clip termina o brinde)
4. Escreva em INGLÊS (exceto as falas em português) para o Veo 3 entender melhor
5. Marque ênfase nas falas com LETRAS MAIÚSCULAS
6. Inclua sempre: CAMERA / DIALOGUE com cues de entonação / AUDIO / TRANSITION OUT
7. FIDELIDADE AOS DADOS: use APENAS os fatos fornecidos no contexto. NUNCA invente
   que alguém "não deu palpite", "esqueceu o palpite" ou tem pendência — pendências
   reais, quando existirem, virão listadas na seção "VAR — PENDÊNCIAS". Quem aparece
   com poucos pontos PALPITOU e pontuou pouco: a zueira deve ser sobre a pontuação
   baixa ou o erro do placar, nunca sobre ausência de palpite.

ESTRUTURA DOS 6 CLIPS:
- Clip 1: Abertura — diz onde está (cidade/local), comenta uma curiosidade local (bebida/comida/costume
  típico do lugar, fornecida no contexto) e dá a saudação animada com a data de hoje, Copa em andamento
- Clip 2: Resultados do dia — placares dos jogos (se não houver jogos, comentário de véspera)
- Clip 3: Destaque do dia — quem fez mais pontos, quem acertou mais
- Clip 4: Ranking — mesa VIP (top 3) e zona de rebaixamento com zueira carinhosa
- Clip 5: Zueira/VAR — erro mais gritante do dia ou situação engraçada (apenas fatos do contexto;
  só mencione pendência de palpite se ela vier listada explicitamente em "VAR — PENDÊNCIAS")
- Clip 6: Encerramento — levanta o chope (ou bebida típica do local), brinde, SAÚDE!

Separe os 6 clips com --- (três hifens sozinhos em uma linha).
NÃO inclua o bloco FIXED CHARACTER — ele será adicionado automaticamente pelo código.
Gere apenas a parte da cena: CLIP X OF 6 — TÍTULO, depois CAMERA / DIALOGUE / AUDIO / TRANSITION OUT."""

MESTRE_LEME_SYSTEM = """Você é o Mestre Leme, um botequeiro brasileiro raiz que apresenta o Boletim do Bolão dos Lemes
toda noite direto do seu boteco. Você é humilde, batalhador, apaixonado por futebol
e adora uma boa zueira com os amigos. Fala em português brasileiro informal, com gírias, expressões
típicas de boteco e muito bom humor.

Seu estilo:
- Usa expressões como "Meu povo", "Galera", "Tá louco", "Que saudade do gol", "Vixe!", "Nossa Senhora"
- Chama os 3 primeiros do ranking de "mesa VIP" ou "os donos do boteco"
- Chama os 4 últimos de "zona de rebaixamento" ou "os que tão devendo o chopão"
- Faz piadas leves com quem errou o palpite, mas sempre no estilo amigo
- NUNCA inventa fatos: só usa os dados fornecidos. Não diz que alguém "não palpitou"
  ou "esqueceu o palpite" a menos que isso esteja explícito nos dados — quem pontuou
  pouco PALPITOU, e a zueira é sobre a pontuação, não sobre ausência de palpite
- Sempre encerra com uma frase de incentivo botequeira
- Fala como se estivesse num programa esportivo de boteco, chopão na mão
- NÃO usa bullet points, listas ou markdown — fala corrido, como narração oral
- O roteiro deve ter no máximo 220 palavras (cerca de 1m30s de vídeo)"""


def _format_results(results: list[dict]) -> str:
    if not results:
        return "Nenhum jogo encerrado antes das 20h hoje."
    lines = []
    for r in results:
        lines.append(
            f"  Jogo {r['match_number']}: {r['team1_name']} {r['team1_score']} x "
            f"{r['team2_score']} {r['team2_name']} — {'Vencedor: ' + r['winner'] if r['winner'] != 'Empate' else 'Empate'}"
        )
    return "\n".join(lines)


def _format_ranking(ranking: list[dict]) -> str:
    lines = []
    for p in ranking:
        lines.append(f"  {p['position']}º {p['name']} — {p['total']} pontos")
    return "\n".join(lines)


def _format_top_scorers(scorers: list[dict]) -> str:
    if not scorers:
        return "Nenhum ponto distribuído hoje ainda."
    lines = [f"  {s['name']}: +{s['pts_today']} pontos" for s in scorers[:5]]
    return "\n".join(lines)


def generate_bulletin_script(data: dict) -> str:
    """
    Recebe os dados do boletim e retorna o roteiro narrado pelo Mestre Leme.
    """
    n = data["total_participants"]
    ranking = data["ranking"]
    top3 = ranking[:3]
    bottom4 = ranking[max(0, n - 4):]
    mid_zone_up = ranking[3:6] if n > 6 else []
    mid_zone_down = ranking[max(0, n - 7): max(0, n - 4)] if n > 7 else []

    user_prompt = f"""Data do boletim: {data['date']}

RESULTADOS DE HOJE (jogos encerrados até 20h):
{_format_results(data['results'])}

QUEM FEZ MAIS PONTOS HOJE:
{_format_top_scorers(data['top_scorers'])}

RANKING GERAL ATUAL:
{_format_ranking(ranking)}

MESA VIP (top 3 que estão ganhando):
{chr(10).join(f"  {p['position']}º {p['name']} — {p['total']} pts" for p in top3)}

ZONA DE REBAIXAMENTO (últimos {len(bottom4)}):
{chr(10).join(f"  {p['position']}º {p['name']} — {p['total']} pts" for p in bottom4)}

QUASE CAINDO (próximos da zona):
{chr(10).join(f"  {p['position']}º {p['name']} — {p['total']} pts" for p in mid_zone_down) or "  (dados insuficientes)"}

QUASE SUBINDO (próximos da mesa VIP):
{chr(10).join(f"  {p['position']}º {p['name']} — {p['total']} pts" for p in mid_zone_up) or "  (dados insuficientes)"}

Gere o roteiro do Boletim do Mestre Leme com base nesses dados. Máximo {MAX_SCRIPT_WORDS} palavras.
Se não houver resultados hoje, faça um boletim especial de véspera ou de dia sem jogos,
mantendo o humor e comentando o ranking atual."""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=MESTRE_LEME_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text.strip()


MESTRE_LEME_LAUNCH_SYSTEM = """Você é o Mestre Leme, um botequeiro brasileiro raiz que apresenta o Bolão dos Lemes
direto do seu boteco. Você é humilde, batalhador, apaixonado por futebol e adora
uma boa zueira com os amigos. Fala em português brasileiro informal, com gírias, expressões
típicas de boteco e muito bom humor.

Seu estilo:
- Usa expressões como "Meu povo", "Galera", "Tá louco", "Vixe!", "Nossa Senhora", "Prepara o coração"
- Faz piadas carinhosas com os amigos que ainda não deram os palpites
- Fala com emoção sobre a Copa que está chegando
- Convida novos participantes para o Bolão com empolgação
- Anuncia os boletins noturnos como se fossem um programa de TV do boteco
- NÃO usa bullet points, listas ou markdown — fala corrido, como narração oral
- O roteiro deve ter no máximo 250 palavras (cerca de 1m40s de vídeo)"""


def generate_launch_script(data: dict, missing: dict, copa_start_str: str, dias: int) -> str:
    """
    Gera o roteiro especial de lançamento/convite para a Copa.
    """
    sem_podio = missing["sem_podio"]
    grupos_inc = missing["grupos_incompletos"]
    total = missing["total_users"]

    # Monta lista de pendências
    pendencias = []
    if sem_podio:
        nomes = ", ".join(sem_podio)
        pendencias.append(f"Ainda não salvaram o palpite de PÓDIO ({len(sem_podio)}/{total}): {nomes}")
    if grupos_inc:
        detalhe = "; ".join(
            f"{p['name']} (falta(m) grupo(s): {', '.join(p['faltando'])})"
            if p["feitos"] > 0 else f"{p['name']} (nenhum grupo salvo)"
            for p in grupos_inc
        )
        pendencias.append(f"Palpites de grupos incompletos: {detalhe}")

    pendencias_str = "\n".join(pendencias) if pendencias else "Todos os palpites já foram salvos! Parabéns!"

    ranking_str = _format_ranking(data["ranking"])

    user_prompt = f"""Mestre Leme, você vai gravar um vídeo especial de lançamento do Bolão dos Lemes Copa 2026!

CONTEXTO:
- A Copa começa em {dias} dia(s) — {copa_start_str}!
- O Bolão tem {total} participantes inscritos
- O prazo para salvar palpites de pódio e grupos fecha quando a Copa começar

PALPITES PENDENTES (chame essas pessoas pelo nome, de forma carinhosa e com urgência!):
{pendencias_str}

RANKING ATUAL (todos zerados, Copa ainda não começou):
{ranking_str}

MISSÃO DO ROTEIRO:
1. Abrir com empolgação: Copa chegando, {dias} dia(s) pra começar!
2. Chamar quem está com palpite pendente pelo nome — de forma divertida, urgente e carinhosa
3. Convidar qualquer pessoa que ainda não está no Bolão a participar
4. Anunciar que durante a Copa, toda noite após os jogos, o Mestre Leme vai trazer o Boletim do Mestre Leme
   com resultados, ranking, quem acertou, quem errou e muita zueira
5. Encerrar com uma frase de incentivo botequeira, gritando pela Copa!

Máximo 250 palavras. Fala corrida, sem listas, como narração oral animada."""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=700,
        system=MESTRE_LEME_LAUNCH_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text.strip()


def generate_video_prompt(data: dict, missing: dict | None = None) -> str:
    """
    Gera 6 prompts completos para o Gemini Pro (Veo 3), prontos para copiar e colar.
    Retorna os 6 prompts separados por --- , cada um já com o _FIXED_CONTEXT prefixado.
    """
    n = data["total_participants"]
    ranking = data["ranking"]
    top3 = ranking[:3]
    bottom4 = ranking[max(0, n - 4):]

    var_str = ""
    if missing:
        if missing["sem_podio"]:
            nomes = ", ".join(missing["sem_podio"])
            var_str += f"Sem pódio: {nomes}\n"
        if missing["grupos_incompletos"]:
            inc = [p["name"] for p in missing["grupos_incompletos"]]
            var_str += f"Grupos incompletos: {', '.join(inc)}\n"

    location = data.get("location")
    local_str = ""
    if location:
        local_str = f"""ONDE O MESTRE LEME ESTÁ HOJE:
Cidade: {location['city']}, {location['country']} ({location.get('note', '')})
Curiosidade local para comentar: {location['curiosity']}
Bebida/comida típica do local: {location['drink']}
"""

    user_prompt = f"""Data do boletim: {data['date']}

{local_str}
RESULTADOS DE HOJE (jogos encerrados até 20h):
{_format_results(data['results'])}

QUEM FEZ MAIS PONTOS HOJE:
{_format_top_scorers(data['top_scorers'])}

RANKING ATUAL:
{_format_ranking(ranking)}

MESA VIP (top 3):
{chr(10).join(f"  {p['position']}º {p['name']} — {p['total']} pts" for p in top3)}

ZONA DE REBAIXAMENTO (últimos {len(bottom4)}):
{chr(10).join(f"  {p['position']}º {p['name']} — {p['total']} pts" for p in bottom4)}
{f"VAR — PENDÊNCIAS:{chr(10)}{var_str}" if var_str else ""}
Gere os 6 prompts de clip para o Gemini Pro com base nesses dados."""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        system=_VIDEO_PROMPT_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()

    # Extrai apenas os chunks que contêm conteúdo real de clip (ignora cabeçalhos)
    clips = [
        c.strip() for c in raw.split("---")
        if c.strip() and "clip" in c.lower()
    ]
    fixed_context = _build_fixed_context(data["date"], location)
    full_prompts = [fixed_context + "\n\n" + clip for clip in clips]
    return "\n\n---\n\n".join(full_prompts)


if __name__ == "__main__":
    from submitter import get_db_engine
    from bulletin_db import get_bulletin_data

    engine = get_db_engine()
    with engine.begin() as conn:
        data = get_bulletin_data(conn)

    script = generate_bulletin_script(data)
    print("\n=== ROTEIRO DO MESTRE LEME ===\n")
    print(script)
    print(f"\n({len(script.split())} palavras)")
