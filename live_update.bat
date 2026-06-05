@echo off
cd /d "D:\Bolao Copa"
echo [%date% %time%] Iniciando atualizacao de palpites... >> live_log.txt
python main.py live >> live_log.txt 2>&1
echo [%date% %time%] Concluido. >> live_log.txt
