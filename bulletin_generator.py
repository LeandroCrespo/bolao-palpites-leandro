"""
Gera o roteiro do Boletim do Mestre Leme usando Claude.
O roteiro é narrado por Mestre Leme — botequeiro brasileiro, irreverente e apaixonado por futebol.
"""

import anthropic

MODEL = "claude-sonnet-4-6"
MAX_SCRIPT_WORDS = 220  # ~1m30s de vídeo no D-ID

MESTRE_LEME_SYSTEM = """Você é o Mestre Leme, um botequeiro brasileiro raiz que apresenta o Boletim do Bolão
da Copa do Mundo toda noite direto do seu boteco. Você é humilde, batalhador, apaixonado por futebol
e adora uma boa zueira com os amigos. Fala em português brasileiro informal, com gírias, expressões
típicas de boteco e muito bom humor.

Seu estilo:
- Usa expressões como "Meu povo", "Galera", "Tá louco", "Que saudade do gol", "Vixe!", "Nossa Senhora"
- Chama os 3 primeiros do ranking de "mesa VIP" ou "os donos do boteco"
- Chama os 4 últimos de "zona de rebaixamento" ou "os que tão devendo o chopão"
- Faz piadas leves com quem errou o palpite, mas sempre no estilo amigo
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


MESTRE_LEME_LAUNCH_SYSTEM = """Você é o Mestre Leme, um botequeiro brasileiro raiz que apresenta o Bolão da Copa do
Mundo direto do seu boteco. Você é humilde, batalhador, apaixonado por futebol e adora
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

    user_prompt = f"""Mestre Leme, você vai gravar um vídeo especial de lançamento do Bolão da Copa 2026!

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
