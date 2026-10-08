#!/bin/sh
set -eu

PORT="${PORT:-8787}"
BIND="${BIND:-127.0.0.1}"

echo "Kanban: http://${BIND}:${PORT}"
echo "Diretório: $(pwd)"

if command -v python3 >/dev/null 2>&1; then
    exec python3 -m http.server "$PORT" --bind "$BIND"
fi

if command -v busybox >/dev/null 2>&1; then
    exec busybox httpd -f -p "${BIND}:${PORT}"
fi

echo "Erro: é necessário python3 ou busybox para servir os ficheiros por HTTP." >&2
exit 1
