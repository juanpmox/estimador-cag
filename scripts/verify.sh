#!/usr/bin/env bash
# Valida la estructura del proyecto, corre los tests de templates y hace un
# smoke test del servicio real.
# Uso: ./scripts/verify.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== 1. Verificando estructura de carpetas =="
REQUIRED_PATHS=(
  "app/main.py"
  "app/config.py"
  "app/schemas.py"
  "app/sessions.py"
  "app/attachments.py"
  "app/metadata.py"
  "app/prompts/loader.py"
  "app/prompts/estimation/v1/system.j2"
  "app/prompts/estimation/v1/user.j2"
  "app/prompts/estimation/v1/examples.j2"
  "app/prompts/estimation/v2/system.j2"
  "app/prompts/estimation/v2/user.j2"
  "app/prompts/estimation/v2/examples.j2"
  "app/routers/estimations.py"
  "app/routers/sessions.py"
  "app/services/llm_service.py"
  "streamlit_app.py"
  "tests/prompts/test_estimation_v1.py"
  "tests/prompts/test_estimation_v2.py"
  "tests/test_sessions_unit.py"
  "tests/test_attachments.py"
  "tests/test_metadata.py"
  "tests/test_sessions_integration.py"
  "openspec/config.yaml"
  "AGENTS.md"
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

echo "== 3. Corriendo tests de templates (sin tocar APIs externas) =="
uv run pytest -v

echo "== 4. Validando specs de OpenSpec (si el CLI esta instalado) =="
if command -v openspec >/dev/null 2>&1; then
  openspec validate --all --strict --no-interactive
else
  echo "AVISO: 'openspec' no esta instalado; se omite la validacion de specs."
  echo "       Instalalo con: npm install -g @fission-ai/openspec@latest"
fi

echo "== 5. Arrancando el servicio IA en background =="
uv run uvicorn app.main:app --port 8000 > /tmp/estimador-cag.log 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

for i in $(seq 1 20); do
  if curl -s -o /dev/null http://localhost:8000/health; then
    break
  fi
  sleep 0.5
done

echo "== 6. Probando GET /health =="
curl -sf http://localhost:8000/health | tee /tmp/health.json
echo

echo "== 7. Probando POST /api/v1/estimate =="
ESTIMATE_STATUS=$(curl -s -o /tmp/estimate.json -w "%{http_code}" -X POST \
  "http://localhost:8000/api/v1/estimate?prompt_version=v1" \
  -H "Content-Type: application/json" \
  -d @sample_data/estimation_request.json)
if [ "$ESTIMATE_STATUS" = "200" ]; then
  echo "OK (200): generacion real completada."
  cat /tmp/estimate.json | head -c 400
  echo
elif [ "$ESTIMATE_STATUS" = "500" ] && grep -q "no esta configurada" /tmp/estimate.json; then
  echo "AVISO: no hay API key configurada en .env; se omite la generacion real."
  echo "       El endpoint respondio 500 por configuracion (esperado sin key)."
else
  echo "FALLO: /api/v1/estimate devolvio $ESTIMATE_STATUS"
  cat /tmp/estimate.json
  exit 1
fi

echo "== 8. Probando POST /api/v1/sessions (crear sesion) =="
SESSION_JSON=$(curl -sf -X POST "http://localhost:8000/api/v1/sessions")
echo "$SESSION_JSON"
SESSION_ID=$(printf '%s' "$SESSION_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")

echo "== 9. Comprobando errores del endpoint de sesion (404 y 400) =="
STATUS_404=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "http://localhost:8000/api/v1/sessions/no-existe/estimate" -F "transcript=hola")
if [ "$STATUS_404" != "404" ]; then
  echo "FALLO: se esperaba 404 en sesion inexistente y llego $STATUS_404"
  exit 1
fi

printf 'PNGDATA' > /tmp/estimador-adjunto.png
STATUS_400=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "http://localhost:8000/api/v1/sessions/$SESSION_ID/estimate?prompt_version=v2" \
  -F "transcript=con adjunto no soportado" \
  -F "attachments=@/tmp/estimador-adjunto.png;type=image/png")
if [ "$STATUS_400" != "400" ]; then
  echo "FALLO: se esperaba 400 con adjunto no soportado y llego $STATUS_400"
  exit 1
fi
echo "OK: 404 (sesion inexistente) y 400 (adjunto no soportado) verificados."
echo

echo
echo "== Verificacion completada correctamente =="
