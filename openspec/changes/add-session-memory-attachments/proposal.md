# Proposal

## Why

Hasta la sesión 04 el estimador es un sistema transaccional: una transcripción entra, una estimación sale, sin estado. En una empresa real la estimación es una conversación iterativa donde el cliente refina el alcance, añade información y adjunta documentos (especificaciones técnicas, propuestas previas, diagramas). Sin memoria de sesión el modelo "se olvida" del proyecto en curso en cada turno y no hay forma de enriquecer la transcripción con documentación complementaria.

## What Changes

- **Nuevo endpoint `POST /api/v1/sessions`** que crea una sesión vacía en memoria del proceso y devuelve `{"session_id": "<uuid4>"}`.
- **Nuevo endpoint `POST /api/v1/sessions/{session_id}/estimate`** que acepta `multipart/form-data` con `transcript` (texto) y `attachments` (lista opcional de `UploadFile`) y devuelve la estimación + el `project_metadata` actualizado.
- **Memoria conversacional con ventana deslizante**: el servicio mantiene, por `session_id`, el historial de mensajes (pares user+assistant) en un diccionario en memoria del proceso, conservando los últimos `MAX_TURNS` (6 por defecto, configurable). El system prompt es invariante y se regenera en cada turno.
- **`project_metadata` separado del historial**: un `ProjectMetadata` (nombre, equipo asumido, tecnologías mencionadas, alcance acordado) se inyecta en el system prompt dentro de un bloque `<project_metadata>` y se actualiza tras cada turno mediante extracción **heurística simple**.
- **Adjuntos con extracción local (Camino B)**: PDFs con `pypdf` y documentos Word con `python-docx`; el texto extraído se concatena a la transcripción con un separador claro (`--- attachment: <nombre> ---`) antes de pasarlo al prompt.
- **Nueva versión de prompt `v2/`** (`app/prompts/estimation/v2/{system,user,examples}.j2`): `system.j2` añade el bloque `<project_metadata>` y el encuadre conversacional; `user.j2` envuelve la transcripción (ya con adjuntos). Se crea una carpeta nueva, **no** se modifica `v1/`.
- **Cliente Streamlit** adaptado a conversación multi-turno: crea sesión al cargar, muestra el chat, selector múltiple de archivos, panel de `project_metadata` y botón "Nueva conversación".

**Fuera de alcance de este cambio** (se construye en el directo o en módulos posteriores):

- Estrategia de resumen acumulativo o híbrida con anclas.
- Tier dinámico derivado del contexto en runtime.
- Persistencia de la memoria entre reinicios del servicio (un diccionario en memoria del proceso es suficiente en esta fase; sin BBDD ni Redis).
- Extracción de `project_metadata` por LLM extractor (se elige heurística simple).
- Camino A de adjuntos (subir PDF al LLM multimodal vía Files API): se elige el Camino B (extracción local).
- Búsqueda web integrada, function calling contra BBDD del backend, y cualquier pieza del patrón Actor-Critic-Boss.

## Capabilities

### New Capabilities

- `session-memory`: ciclo de vida de sesiones conversacionales, historial con ventana deslizante, y `project_metadata` separado del historial e inyectado en el system prompt.
- `attachment-ingestion`: ingesta de adjuntos PDF/Word por `multipart/form-data` y su incorporación al contexto de la estimación.

### Modified Capabilities

<!-- Ninguna: no existen specs previas en openspec/specs/ y el comportamiento de v1 del endpoint /estimate no cambia. -->

## Impact

- **Código nuevo**: `app/sessions.py` (estado de sesión), `app/attachments.py` (extracción local), `app/metadata.py` (heurística), `app/routers/sessions.py`, `app/prompts/estimation/v2/`.
- **Código modificado**: `app/main.py` (incluye el router de sesiones), `app/config.py` (nuevos settings), `app/schemas.py` (nuevos modelos de respuesta), `app/services/llm_service.py` (variante multi-mensaje), `app/prompts/loader.py` (`render_session_prompt`), `streamlit_app.py`, `README.md`, `scripts/verify.sh`, `.github/workflows/verify.yml`, `pyproject.toml`/`uv.lock`.
- **Contrato tipado**: `EstimationRequest`/`EstimationResponse` **no cambian**. Se añaden `SessionCreateResponse` y `SessionEstimationResponse`. El nuevo endpoint es `multipart/form-data`, no JSON.
- **Dependencias nuevas**: `pypdf`, `python-docx`. `python-multipart` ya está presente (necesario para form-data).
- **Retrocompatibilidad**: `POST /api/v1/estimate` (JSON, v1) sigue funcionando sin cambios.
