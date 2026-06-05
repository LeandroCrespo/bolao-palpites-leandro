"""
Registra no Agendador de Tarefas do Windows a tarefa de atualização
automática dos palpites da Copa 2026.

Execute uma única vez:
  python setup_agendamento.py

A tarefa rodará automaticamente todos os dias às 06:00.
Logs salvos em: D:\\Bolao Copa\\live_log.txt
"""

import subprocess
import sys
import os
from pathlib import Path

TASK_NAME = "BolaoCopa2026LiveUpdate"
PROJECT_DIR = Path(__file__).parent.resolve()
BAT_PATH = PROJECT_DIR / "live_update.bat"
LOG_PATH = PROJECT_DIR / "live_log.txt"

# Horário padrão: 06:00 (antes dos jogos do dia começarem)
# Pode ser alterado abaixo
HORA = "06:00"


def criar_tarefa():
    print(f"Registrando tarefa '{TASK_NAME}' no Agendador de Tarefas do Windows...")
    print(f"  Script: {BAT_PATH}")
    print(f"  Horario: todos os dias as {HORA}")
    print(f"  Log: {LOG_PATH}")
    print()

    # Cria a tarefa agendada usando schtasks
    resultado = subprocess.run(
        [
            "schtasks", "/create",
            "/tn", TASK_NAME,
            "/tr", str(BAT_PATH),
            "/sc", "daily",
            "/st", HORA,
            "/f",          # sobrescreve se já existir
        ],
        capture_output=True,
        text=True,
        encoding="cp1252",
        errors="replace",
    )

    if resultado.returncode == 0:
        print("Tarefa criada com sucesso!")
        print()
        print("Para verificar, abra o Agendador de Tarefas do Windows")
        print("e procure por 'BolaoCopa2026LiveUpdate'.")
        print()
        print("Para testar agora mesmo, rode:")
        print("  python main.py live")
        print()
        print("Para ver os logs das execucoes automaticas:")
        print(f"  Abra o arquivo: {LOG_PATH}")
    else:
        print("ERRO ao criar a tarefa:")
        print(resultado.stderr or resultado.stdout)
        print()
        print("Tente rodar este script como Administrador:")
        print("  Clique com botao direito no terminal > 'Executar como administrador'")
        print("  Depois rode: python setup_agendamento.py")


def remover_tarefa():
    """Remove a tarefa agendada (caso queira cancelar)."""
    resultado = subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True, text=True
    )
    if resultado.returncode == 0:
        print(f"Tarefa '{TASK_NAME}' removida com sucesso.")
    else:
        print("Tarefa nao encontrada ou erro ao remover.")


def verificar_tarefa():
    """Verifica se a tarefa está registrada."""
    resultado = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME],
        capture_output=True, text=True, encoding="cp1252", errors="replace"
    )
    if resultado.returncode == 0:
        print(f"Tarefa '{TASK_NAME}' encontrada:")
        print(resultado.stdout)
    else:
        print(f"Tarefa '{TASK_NAME}' nao encontrada.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "remover":
        remover_tarefa()
    elif len(sys.argv) > 1 and sys.argv[1] == "verificar":
        verificar_tarefa()
    else:
        criar_tarefa()
