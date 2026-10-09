#!/usr/bin/env bash
set -euo pipefail
: "${WORKER_URL:?Definir WORKER_URL}"
: "${WORKER_API_KEY:?Definir WORKER_API_KEY}"
# Passar o header por stdin evita colocar o token diretamente nos argumentos de curl.
curl --config - --fail --silent --max-time 5 "${WORKER_URL%/}/health" <<EOF
header = "Authorization: Bearer ${WORKER_API_KEY}"
EOF
printf '\n'
curl --config - --fail --silent --max-time 120 \
  -H 'Content-Type: application/json' \
  -d '{"model":"local-model","messages":[{"role":"user","content":"Responde OK"}],"max_tokens":12,"stream":false}' \
  "${WORKER_URL%/}/v1/chat/completions" <<EOF
header = "Authorization: Bearer ${WORKER_API_KEY}"
EOF
printf '\n'
