# Tasks

## 1. Dependencias y configuracion base

- [x] 1.1 Añadir `pypdf` y `python-docx` a `pyproject.toml` (grupo de dependencias principal) y verificar que `uv sync` instala y que `uv run python -c "import pypdf, docx"` funciona.
- [x] 1.2 Añadir `session_max_turns: int = 6` y `attachment_max_chars: int` a `app/config.py`, reflejarlos en `.env.example` (`SESSION_MAX_TURNS`, `ATTACHMENT_MAX_CHARS`) y verificar con `uv run python -c "from app.config import get_settings; print(get_settings().session_max_turns)"`.

## 2. Estado de sesion

- [x] 2.1 Crear `app/sessions.py` con `ProjectMetadata`, `ConversationTurn`, `ConversationHistory` (ventana deslizante con `deque(maxlen)` y `to_messages_list()`), `Session` y `SessionStore` (singleton en memoria del proceso), con docstrings que expliquen la volatilidad aceptada en esta fase.
- [x] 2.2 Añadir `tests/test_sessions_unit.py` que verifique: la ventana descarta los turnos mas antiguos y conserva el system prompt; `ProjectMetadata` arranca vacio y detecta `is_empty()`.

## 3. Adjuntos (Camino B)

- [x] 3.1 Crear `app/attachments.py` con `extract_text(filename, data)` (pypdf para PDF, python-docx para Word, decode para texto plano) y `build_transcript_with_attachments(transcript, adjuntos)` con el separador `--- attachment: <nombre> ---`; imports perezosos de `pypdf`/`docx`.
- [x] 3.2 Añadir `tests/test_attachments.py` que verifique la extraccion de un `.docx` generado en memoria, la extraccion de un PDF minimo, el separador en la transcripcion combinada y el `ValueError` en un tipo no soportado.

## 4. Extraccion heuristica de project_metadata

- [x] 4.1 Crear `app/metadata.py` con `extract_metadata(transcript, response, previous)` que detecte nombre de proyecto, tamano de equipo, tecnologias mencionadas y alcance, mergeando sobre el `ProjectMetadata` previo.
- [x] 4.2 Añadir `tests/test_metadata.py` que verifique la deteccion de cada campo y que un turno posterior no borra hechos previos.

## 5. Prompts v2 y loader

- [x] 5.1 Crear `app/prompts/estimation/v2/` copiando `v1/` y añadir el bloque `<project_metadata>` (vacio si no hay hechos) al `system.j2`; el `user.j2` envuelve la transcripcion.
- [x] 5.2 Añadir `render_session_prompt(project_metadata, transcript, version="v2")` a `app/prompts/loader.py` sin tocar `render_estimation_prompt`.
- [x] 5.3 Añadir `tests/prompts/test_estimation_v2.py` que verifique el bloque `<project_metadata>` vacio y relleno, y que la transcripcion aparece verbatim en el user prompt.

## 6. Llamada multi-mensaje al LLM

- [x] 6.1 Añadir `generate_estimation_messages(messages)` a `app/services/llm_service.py` (separa `system` para Anthropic) y hacer que `generate_estimation(system, user)` delegue en ella.

## 7. Schema, router de sesiones y wiring

- [x] 7.1 Añadir `SessionCreateResponse` y `SessionEstimationResponse` a `app/schemas.py` sin modificar `EstimationRequest`/`EstimationResponse`.
- [x] 7.2 Crear `app/routers/sessions.py` con `POST /sessions` y `POST /sessions/{session_id}/estimate` (multipart: `transcript` + `attachments`), e incluirlo en `app/main.py` bajo el prefijo `/api/v1`.
- [x] 7.3 Añadir `tests/test_sessions_integration.py` (con `httpx.AsyncClient` y LLM mockeado) que verifique: (a) dos peticiones encadenadas actualizan el `project_metadata`; (b) un adjunto cuyo texto aparece en las `messages` enviadas al LLM; (c) 8 turnos nunca superan `MAX_TURNS` mensajes `assistant`.

## 8. Cliente Streamlit

- [x] 8.1 Reescribir `streamlit_app.py`: crear sesion al cargar (guardar `session_id` en `session_state`), chat multi-turno, `file_uploader` multiple, panel de `project_metadata` y boton "Nueva conversacion"; verificar arranque manual con `uv run streamlit run streamlit_app.py`.

## 9. Documentacion y verificacion final

- [x] 9.1 Actualizar `README.md` (endpoints de sesion, Camino B y por que, extraccion heuristica y por que, como levantar y probar).
- [x] 9.2 Actualizar `scripts/verify.sh` y `.github/workflows/verify.yml` (nuevos archivos en el chequeo de estructura + smoke de `POST /sessions`).
- [x] 9.3 Correr `uv run pytest` (verde, sin llamadas reales a LLM) y `openspec validate --all --strict --no-interactive`.

## Workflow follow-up

- Archivar el change (`/opsx-archive`) una vez implementado y revisado, fusionando las specs en `openspec/specs/`.
