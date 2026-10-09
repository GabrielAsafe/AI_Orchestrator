#!/data/data/com.termux/files/usr/bin/sh
# Exemplo para inspecionar e adaptar NO TELEMÓVEL; não executar cegamente.
# Instalar runit (termux-services) e llama.cpp/llama-server conforme runbook.
# Evitar guardar API key diretamente num script que será versionado.
# Termux service: ~/.termux/sv/llama-server/run (substituir MODEL_PATH)
exec 2>&1
exec llama-server -m "$HOME/models/MODEL_PATH.gguf" --host 127.0.0.1 --port 8080
