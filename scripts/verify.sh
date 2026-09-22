#!/usr/bin/env bash
# Valida la estructura del proyecto y hace un smoke test del servicio.
# Uso: ./scripts/verify.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== 1. Verificando estructura de carpetas =="
REQUIRED_PATHS=(
  "app/main.py"
  "app/config.py"
  "app/routers/estimations.py"
  "app/services/llm_service.py"
  "app/context/examples.py"
  "streamlit_app.py"
  ".env.example"
  ".gitignore"
  "pyproject.toml"
)

for path in "${REQUIRED_PATHS[@]}"; do
  if [ ! -f "$path" ]; then
    echo "FALTA: $path"
    exit 1
  fi
done
echo "OK: estructura de carpetas correcta."

echo "== 2. Instalando dependencias =="
uv sync

echo "== 3. Arrancando el servidor en background =="
uv run uvicorn app.main:app --port 8000 > /tmp/estimador-cag.log 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

# Espera a que el servidor esté listo
for i in $(seq 1 20); do
  if curl -s -o /dev/null http://localhost:8000/health; then
    break
  fi
  sleep 0.5
done

echo "== 4. Probando GET /health =="
curl -sf http://localhost:8000/health | tee /tmp/health.json
echo

echo "== 5. Probando POST /api/v1/estimate =="
curl -sf -X POST http://localhost:8000/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d @sample_data/meeting_transcription.json | tee /tmp/estimate.json
echo

echo
echo "== Verificacion completada correctamente =="
