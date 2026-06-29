"""
Agente Veo 3 — Gera os 9 clips do vídeo de lançamento do Mestre Leme.

Pré-requisitos:
  1. pip install google-genai
  2. GOOGLE_API_KEY no .env (obtido em aistudio.google.com/apikey)

Uso:
  python veo_creator.py            # gera todos os 9 clips + tenta combinar
  python veo_creator.py --clip 4   # gera apenas o clip 4 (índice 1-9)
  python veo_creator.py --combine  # só combina clips já gerados (precisa ffmpeg)
  python veo_creator.py --aviso    # clip único: Mestre Leme com camisa da Seleção anunciando boletins
  python veo_creator.py --vinheta  # clip único: vinheta de abertura "Plantão do Bolão dos Lemes"
"""

import os
import sys
import time
import subprocess
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Contexto fixo do personagem — prefixado em todos os prompts
# ---------------------------------------------------------------------------

_CONTEXT = (
    "Main character: Mestre Leme — Brazilian man approximately 55 years old, "
    "stocky and heavy-set build, short salt-and-pepper gray hair, thick gray mustache, "
    "warm brown skin, big wide smile showing teeth, expressive brown eyes. "
    "He wears an open blue-and-white plaid flannel shirt over a plain white undershirt. "
    "He holds a glass of chope (Brazilian draft beer). "
    "Setting: authentic Brazilian boteco — wooden bar counter, Brazilian green-and-yellow flag on wall, "
    "TV in background showing a football match, warm dim lighting, beer bottles and glasses around. "
    "Cinematic style, warm vibrant colors, photorealistic. 8 seconds. "
)

# ---------------------------------------------------------------------------
# Os 9 prompts (dados do VAR: 07/jun/2026)
# ---------------------------------------------------------------------------

PROMPTS = [
    # Clipe 1 — Abertura com apresentação
    _CONTEXT + (
        "SCENE 1 of 9 — OPENING AND SELF-INTRODUCTION: "
        "Mestre Leme is sitting at the wooden bar counter, smiling broadly at the camera. "
        "He points at himself with his thumb proudly and then opens his arms wide in welcome, "
        "like greeting his best friends. He introduces himself with great joy and charisma. "
        "DIALOGUE: 'Eu sou o Mestre Leme! E isso aqui é o Bolão dos Lemes — Copa 2026, meu povo!' "
        "CAMERA: Medium shot, slight zoom in toward his face. "
        "AUDIO: Upbeat samba music in background, boteco ambient noise."
    ),

    # Clipe 2 — O Bolão
    _CONTEXT + (
        "CENA 2 de 9 — O BOLÃO: "
        "Mestre Leme apoia os dois cotovelos no balcão do bar, se inclina para "
        "frente em posição íntima e conspiradora, como quem vai contar um segredo "
        "valioso. Olha diretamente para a câmera. "
        "FALA: 'Dezesseis participantes. Cento e quatro jogos para palpitar. "
        "Quem acertar mais, leva a taça — e o orgulho da família!' "
        "CÂMERA: Close no rosto expressivo, leve balanço de cabeça. "
        "ÁUDIO: Tom mais baixo e envolvente, barulho de bar ao fundo."
    ),

    # Clipe 3 — Copa 2026
    _CONTEXT + (
        "CENA 3 de 9 — A COPA: "
        "Mestre Leme vira para a TV do boteco que mostra a logo da Copa 2026, "
        "aponta com entusiasmo e depois vira para a câmera com expressão de "
        "criança na véspera do Natal. "
        "FALA: 'Copa do Mundo! Brasil, México, Canadá — "
        "onze de junho começa! Falta pouquíssimo, meu consagrado!' "
        "CÂMERA: Plano médio, gesto amplo apontando para a TV. "
        "ÁUDIO: Narração de gol de futebol ao fundo, depois música animada."
    ),

    # Clipe 4 — VAR: Chamada 1
    _CONTEXT + (
        "CENA 4 de 9 — O VAR ENTROU EM CAMPO: "
        "Mestre Leme vira para um telão improvisado no boteco que mostra "
        "'VAR DO MESTRE LEME'. Aponta para o telão e depois aponta "
        "para a câmera com expressão séria mas bem-humorada, como um "
        "técnico chamando o jogador na reserva. "
        "FALA: 'Bruno Monfardini! Marco Antonio! Cadê o "
        "palpite de pódio de vocês, meu irmão?!' "
        "CÂMERA: Plano médio, braços gesticulando animadamente. "
        "ÁUDIO: Som de apito de futebol ao fundo, depois silêncio dramático."
    ),

    # Clipe 5 — VAR: Chamada 2
    _CONTEXT + (
        "CENA 5 de 9 — MAIS NOMES NO VAR: "
        "Mestre Leme com expressão de desespero cômico, mãos na cabeça, "
        "olhando para a câmera. Depois aponta carinhosamente como chamando "
        "a família mesmo. "
        "FALA: 'Marcos Leme! Renata Leme! Vocês são família — "
        "não podem me deixar na mão assim, minha gente!' "
        "CÂMERA: Close no rosto expressivo, gesticulando com as mãos. "
        "ÁUDIO: Violino dramático de novela por 2 segundos, depois ri."
    ),

    # Clipe 6 — VAR: O mais urgente
    _CONTEXT + (
        "CENA 6 de 9 — CASO GRAVE: "
        "Mestre Leme pega um papel do balcão e lê com espanto, depois "
        "olha para a câmera apontando com o dedo indicador, expressão "
        "de 'isso é sério rapaz'. "
        "FALA: 'João Paulo e Flávio — zero grupo salvo! "
        "Zero! Tá no bolão de enfeite, meu consagrado!' "
        "CÂMERA: Plano médio, reação exagerada e cômica. "
        "ÁUDIO: Buzina de futebol ao fundo."
    ),

    # Clipe 7 — Convite
    _CONTEXT + (
        "CENA 7 de 9 — O CONVITE: "
        "Mestre Leme atrás do balcão, acena para a câmera com entusiasmo "
        "como quem chama alguém para entrar no bar, com expressão acolhedora "
        "e animada. "
        "FALA: 'E se você ainda não entrou no bolão — "
        "é agora ou nunca! A Copa não espera ninguém!' "
        "CÂMERA: Plano médio, faz gesto de vem cá com o braço. "
        "ÁUDIO: Música animada crescendo levemente."
    ),

    # Clipe 8 — Como participar
    _CONTEXT + (
        "CENA 8 de 9 — COMO ENTRAR: "
        "Mestre Leme segura o celular virado para a câmera com uma mão, "
        "com a outra aponta para a tela como se mostrasse o link do bolão, "
        "expressão de 'é muito fácil, ó'. "
        "FALA: 'Entra no link, faz seus palpites — "
        "grupos, pódio, tudo! O sistema tá esperando você.' "
        "CÂMERA: Close no celular e no rosto, alternando. "
        "ÁUDIO: Notificação de celular ao fundo, tom descontraído."
    ),

    # Clipe 9 — Encerramento
    _CONTEXT + (
        "CENA 9 de 9 — ENCERRAMENTO: "
        "Mestre Leme levanta um copo de chope gelado em direção à câmera "
        "com sorriso largo, olha direto para a câmera "
        "com expressão calorosa e satisfeita. "
        "FALA: 'Que venha a Copa! Que venha o Brasil! "
        "Bolão dos Lemes — vai ser épico. Saúde!' "
        "CÂMERA: Plano médio, leve slow-motion no brinde final. "
        "ÁUDIO: Música de Copa crescendo, aplausos ao fundo."
    ),
]

VEO_MODEL = "models/veo-3.0-fast-generate-001"
OUTPUT_DIR = Path("veo_clips")


# ---------------------------------------------------------------------------
# Agente principal
# ---------------------------------------------------------------------------

class VeoAgent:
    def __init__(self, api_key: str):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            print("Erro: pacote 'google-genai' não instalado.")
            print("Execute: pip install google-genai")
            sys.exit(1)

        self._genai = genai
        self._types = types
        self.client = genai.Client(api_key=api_key)
        OUTPUT_DIR.mkdir(exist_ok=True)
        self.reference_image_path: str | None = None

    def generate_all(self, start_from: int = 1):
        """Gera todos os clips sequencialmente. start_from=1..9."""
        total = len(PROMPTS)
        for i in range(start_from - 1, total):
            clip_num = i + 1
            output = OUTPUT_DIR / f"clip_{clip_num:02d}.mp4"
            if output.exists():
                print(f"\n[{clip_num}/{total}] {output.name} já existe — pulando.")
                continue
            print(f"\n[{clip_num}/{total}] Gerando clip {clip_num}...")
            self._generate_clip(PROMPTS[i], clip_num)

        print(f"\nTodos os clips gerados em: {OUTPUT_DIR}/")

    def _build_reference_images(self) -> list | None:
        """Carrega mestre_leme.jpg como referência de personagem, se existir."""
        if self.reference_image_path:
            path = Path(self.reference_image_path)
        else:
            # Procura imagem do Mestre Leme (vários nomes e extensões possíveis)
            candidates = [
                f"{base}.{ext}"
                for base in ("mestre_leme", "Mestre Leme", "mestre leme", "MestreLeme")
                for ext in ("png", "jpg", "jpeg", "webp")
            ]
            path = next(
                (Path(c) for c in candidates if Path(c).exists()),
                Path("mestre_leme.jpg")
            )
        if not path.exists():
            return None
        import mimetypes
        mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
        image_bytes = path.read_bytes()
        print(f"  Referência: {path.name} ({len(image_bytes)//1024} KB, {mime})")
        return [
            self._types.VideoGenerationReferenceImage(
                reference_type=self._types.VideoGenerationReferenceType.ASSET,
                image=self._types.Image(image_bytes=image_bytes, mime_type=mime),
            )
        ]

    def _generate_clip(self, prompt: str, index, model_override: str | None = None):
        label = f"{index:02d}" if isinstance(index, int) else str(index)
        output = OUTPUT_DIR / f"clip_{label}.mp4"

        model = model_override or VEO_MODEL
        config = self._types.GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=8,
            number_of_videos=1,
        )

        print(f"  Enviando prompt...")
        operation = self.client.models.generate_videos(
            model=model,
            prompt=prompt,
            config=config,
        )

        print(f"  Aguardando geração", end="", flush=True)
        elapsed = 0
        while not operation.done:
            time.sleep(15)
            elapsed += 15
            operation = self.client.operations.get(operation)
            print(".", end="", flush=True)
            if elapsed > 600:
                raise TimeoutError(f"Clip {index}: timeout após 10 minutos")
        print(f" ({elapsed}s)")

        videos = operation.response.generated_videos
        if not videos:
            raise RuntimeError(f"Clip {index}: Veo 3 não retornou vídeo")

        self._download(videos[0], output)
        size_kb = output.stat().st_size // 1024
        print(f"  Salvo: {output} ({size_kb} KB)")

    def _download(self, video_obj, output: Path):
        video = video_obj.video  # objeto Video com uri, video_bytes, mime_type

        # 1. Bytes já incluídos na resposta
        if video.video_bytes:
            with open(output, "wb") as f:
                f.write(video.video_bytes)
            return

        # 2. URI direta (URL assinada do GCS)
        if video.uri and video.uri.startswith("https://"):
            try:
                urllib.request.urlretrieve(video.uri, str(output))
                return
            except Exception:
                pass

        # 3. Fallback: download via SDK
        video_bytes = self.client.files.download(file=video)
        with open(output, "wb") as f:
            f.write(video_bytes)

    def combine_clips(self):
        """Combina os 9 clips em launch_video.mp4 usando ffmpeg."""
        clips = sorted(OUTPUT_DIR.glob("clip_*.mp4"))
        if len(clips) < 9:
            print(f"\nAtenção: só {len(clips)}/9 clips disponíveis para combinar.")

        concat_file = OUTPUT_DIR / "clips.txt"
        with open(concat_file, "w") as f:
            for clip in clips:
                f.write(f"file '{clip.resolve()}'\n")

        output = Path("launch_video.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output),
        ]

        print(f"\nCombinando {len(clips)} clips com ffmpeg...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                size_mb = output.stat().st_size / (1024 * 1024)
                print(f"Vídeo final: {output} ({size_mb:.1f} MB)")
            else:
                print(f"ffmpeg erro:\n{result.stderr[-500:]}")
        except FileNotFoundError:
            print("ffmpeg não encontrado no PATH.")
            print("Para instalar no Windows: winget install ffmpeg")
            print(f"Para combinar manualmente, importe os arquivos de {OUTPUT_DIR}/ em qualquer editor de vídeo.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY", "").encode().decode("utf-8-sig").strip().strip("'\"")
    if not api_key:
        print("GOOGLE_API_KEY não encontrada no .env")
        print("Obtenha em: aistudio.google.com/apikey")
        sys.exit(1)

    args = sys.argv[1:]
    agent = VeoAgent(api_key)

    # Imagem de referência: --reference caminho/imagem.jpg (padrão: mestre_leme.jpg)
    if "--reference" in args:
        idx = args.index("--reference")
        try:
            agent.reference_image_path = args[idx + 1]
        except IndexError:
            print("Uso: --reference <caminho_da_imagem>")
            sys.exit(1)

    if "--combine" in args:
        agent.combine_clips()
        return

    if "--aviso" in args:
        prompt_aviso = (
            "FIXED CHARACTER: Mestre Leme — a stocky, heavy-set Brazilian man, approximately 55 years old. "
            "FACE: round full face, warm caramel-brown skin, short salt-and-pepper hair cut very close to the head "
            "with gray dominating at the temples, thick prominent all-gray mustache in the classic Brazilian gaúcho "
            "style — dense and well-kept, covering the upper lip. Expressive heavy eyebrows, deep warm brown eyes "
            "with laugh lines at the corners, wide flat nose, a broad full smile showing teeth. "
            "OUTFIT: he wears the official Brazil 2026 World Cup home jersey — soft pastel canary yellow with a "
            "round collar featuring a deep green triangular V-cut at the front inspired by the 1970 tricampeon "
            "jersey (color called Geody Teal), green trim on the sleeve ends, vertical green stripes on the lateral "
            "sides of the torso, dark green shoulder lines, subtle jacquard fabric with Brazil flag patterns, "
            "CBF crest with five stars on the chest, Nike Swoosh logo. Dark shorts. "
            "He holds a thick glass of chope (Brazilian draft beer) with generous white foam at the rim. "
            "SETTING: interior of an authentic São Paulo neighborhood boteco — long dark wooden bar counter "
            "with worn varnish, mismatched high bar stools, Brazilian green-and-yellow flag pinned on the "
            "brick wall behind him, old CRT television showing Copa 2026 graphics, shelves with cachaça bottles, "
            "warm incandescent yellow lighting, boteco ambient sounds (low murmur, clinking glasses, samba radio). "
            "STYLE: photorealistic, cinematic, shallow depth of field, warm saturated amber color grade. 8 seconds. "
            "SCENE — BULLETIN ANNOUNCEMENT: "
            "Mestre Leme stands proudly behind the bar counter wearing the Brazil jersey. He pulls the jersey "
            "fabric gently with both hands and looks down at it with pride, then looks directly into the camera "
            "with a huge warm smile. He raises one finger as if making a solemn promise, then opens both arms "
            "wide toward the camera in a welcoming gesture. "
            "CAMERA: starts medium close-up slightly low angle emphasizing the CBF crest on the jersey, "
            "slowly pushes in toward his face during dialogue. "
            "VOICE: Brazilian Portuguese with São Paulo accent — warm, confident, like the host of the best "
            "show on television. "
            "DIALOGUE — tone: proud announcement, like revealing something special to close friends: "
            "'Meu povo! A Copa começou — e toda noite após os jogos, o Mestre Leme traz o Boletim do Bolão! "
            "Classificação, quem disputa o título, quem tá no rebaixamento — pode deixar comigo!' "
            "(COPA spoken with reverence; 'pode deixar comigo' with a warm wink and both thumbs up) "
            "AUDIO: upbeat samba melody starts low and builds. Brazil national team fanfare faintly audible "
            "from the TV. Boteco crowd cheers softly in background."
        )
        output = OUTPUT_DIR / "clip_aviso.mp4"
        OUTPUT_DIR.mkdir(exist_ok=True)
        print("=== CLIP DE AVISO — MESTRE LEME COM CAMISA DA SELEÇÃO ===")
        print(f"Modelo: {VEO_MODEL}\n")
        agent._generate_clip(prompt_aviso, "aviso")
        return

    if "--vinheta" in args:
        prompt_vinheta = (
            "SETTING: An abstract digital space - a dark stadium-at-night background with "
            "out-of-focus floodlights and a faint green soccer pitch glow at the bottom edge of "
            "frame. Floating in this space are dynamic graphic elements: a glowing soccer ball "
            "icon spinning slowly, gold and green light streaks sweeping diagonally across the "
            "frame, and small particle/confetti effects drifting upward. A small World Cup 2026 "
            "emblem glows softly in one corner. No people, no characters. "
            "SCENE - OPENING: The soccer ball icon spins faster and faster at the center of the "
            "frame while gold and green light streaks sweep in from both sides. The streaks "
            "converge and burst into a bold Brazilian Portuguese title in large clean uppercase "
            "sans-serif letters reading exactly: PLANTÃO DO BOLÃO DOS LEMES - note the tilde "
            "diacritic mark sits directly above the letter 'A' in 'PLANTÃO' and 'BOLÃO' (forming "
            "the 'Ã' character), NOT above the following letter 'O'. The title slides in from the "
            "sides and snaps together with a flash of golden light and a ripple of particle "
            "effects. The title settles in the center, glowing softly and perfectly legible with "
            "correct accent placement, as the stadium floodlights pulse gently in the background. "
            "Clip ends holding on this title card. "
            "CAMERA: Slow continuous push-in toward the center of the frame throughout, following "
            "the spinning ball and converging light streaks until the title settles. "
            "AUDIO: LOUD, attention-grabbing instrumental sting at high volume - bright blaring "
            "brass fanfare combined with punchy electronic percussion and a powerful rising synth "
            "swell, ending with a loud triumphant cymbal/impact crash exactly as the title "
            "'PLANTÃO DO BOLÃO DOS LEMES' snaps into place. The music is prominent and energetic, "
            "mixed at a louder volume than a typical background track, immediately grabbing the "
            "viewer's attention. No dialogue, no voiceover, no characters, purely instrumental. "
            "8 seconds."
        )
        OUTPUT_DIR.mkdir(exist_ok=True)
        print("=== VINHETA — PLANTAO DO BOLAO DOS LEMES ===")
        print(f"Modelo: {VEO_MODEL}\n")
        agent._generate_clip(prompt_vinheta, "vinheta")
        return

    if "--mascote" in args:
        prompt_mascote = (
            "Three animated mascot characters of Copa 2026: "
            "MAPLE — friendly moose in red and white Canada jersey with maple leaf symbol. "
            "ZAYU — energetic jaguar in green, white and red Mexico jersey. "
            "CLUTCH — confident eagle in blue and red USA jersey with stars. "
            "Scene: The three mascots walk together through the tunnel of a large Copa 2026 stadium, "
            "emerging onto the bright green field to a roaring crowd. "
            "They raise their arms celebrating, looking at the camera with pure joy. "
            "Vibrant colors, cinematic wide shot, stadium lights blazing. 8 seconds."
        )
        output = OUTPUT_DIR / "clip_mascote_teste.mp4"
        OUTPUT_DIR.mkdir(exist_ok=True)
        print("=== TESTE — MASCOTES DA COPA 2026 ===")
        print(f"Modelo: {VEO_MODEL}\n")
        agent._generate_clip(prompt_mascote, "mascote_teste")
        return

    start_from = 1
    if "--clip" in args:
        idx = args.index("--clip")
        try:
            start_from = int(args[idx + 1])
        except (IndexError, ValueError):
            print("Uso: python veo_creator.py --clip <1-9>")
            sys.exit(1)
        print(f"Gerando apenas clip {start_from}...")
        agent._generate_clip(PROMPTS[start_from - 1], start_from)
        agent.combine_clips()
        return

    print("=== GERAÇÃO DO VÍDEO DE LANÇAMENTO — MESTRE LEME ===")
    print(f"Modelo: {VEO_MODEL}")
    print(f"Clips: {len(PROMPTS)} × 8 segundos")
    print(f"Pasta de saída: {OUTPUT_DIR}/")
    print(f"Tempo estimado: 18–45 minutos\n")

    agent.generate_all(start_from=start_from)
    agent.combine_clips()


if __name__ == "__main__":
    main()
