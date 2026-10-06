# Estimador CAG

Servicio IA (FastAPI) + cliente (Streamlit) que generan una estimación de
software a partir de una descripción de proyecto. El prompt vive en
**templates Jinja2 versionados**, no en un f-string dentro del código, y el
cliente envía un **formulario tipado** (Pydantic v2) en vez de texto libre.

## Estructura del proyecto

```
estimador-cag/
├── app/
│   ├── main.py                       # App FastAPI, incluye el router y /health
│   ├── config.py                     # Settings (pydantic-settings) desde .env
│   ├── schemas.py                    # Contrato tipado: Estimation* + ProjectMetadata + Session*
│   ├── sessions.py                   # Estado de sesión: historial (ventana) + memória del proyecto
│   ├── attachments.py                # Camino B: extracción local de texto (pypdf / python-docx)
│   ├── metadata.py                   # Extracción heurística del project_metadata
│   ├── prompts/
│   │   ├── loader.py                 # render_estimation_prompt + render_session_*_prompt
│   │   └── estimation/
│   │       ├── v1/                   # Prompt transaccional (endpoint /estimate)
│   │       │   ├── system.j2
│   │       │   ├── user.j2
│   │       │   └── examples.j2
│   │       └── v2/                   # Prompt conversacional (bloque <project_metadata>)
│   │           ├── system.j2
│   │           ├── user.j2
│   │           └── examples.j2
│   ├── routers/
│   │   ├── estimations.py            # POST /api/v1/estimate
│   │   └── sessions.py               # POST /api/v1/sessions (crear) y .../{id}/estimate
│   └── services/
│       └── llm_service.py            # Wrapper de proveedor (OpenAI/Anthropic/OpenRouter)
├── streamlit_app.py                  # Cliente: conversación multi-turno con adjuntos
├── tests/
│   ├── test_sessions_unit.py         # Historial/ventana y memoria (sin LLM)
│   ├── test_metadata.py              # Heurística de extracción (sin LLM)
│   ├── test_attachments.py           # Extracción local PDF/Word (sin LLM)
│   ├── test_sessions_integration.py  # Endpoints con el LLM mockeado
│   └── prompts/
│       ├── test_estimation_v1.py     # Render del template transaccional
│       └── test_estimation_v2.py     # Render del template conversacional
├── scripts/
│   └── verify.sh
├── sample_data/
├── openspec/                         # Specs (SDD): specs/, changes/ y config.yaml
├── .cline/  ·  .clinerules/          # Skills y comandos /opsx-* para Cline
├── AGENTS.md                         # Instrucciones para asistentes de IA
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

## Por qué este diseño

- **Formulario tipado en vez de chat libre**: el espacio de tareas es
  acotado (tipo de proyecto, nivel de detalle, formato de salida). Un
  `st.form` con estos campos elimina la ambigüedad de "¿qué tengo que
  escribir?" y le da al backend parámetros validados (`ProjectType`,
  `DetailLevel`, `OutputFormat`) en vez de tener que interpretarlos de un
  texto libre.
- **Prompt en templates `.j2`, no en un string en el código**: cambiar el
  tono, agregar un ejemplo o ajustar una instrucción ya no implica tocar
  Python ni redeployar el servicio con un diff en medio de la lógica de
  negocio — es un cambio de contenido en `app/prompts/estimation/v1/`.
- **Versionado real (`v1/`, `v2/`, ...)**: cada versión del prompt vive en
  su propia carpeta con sus propios `.j2`. El endpoint acepta
  `?prompt_version=` para elegir cuál usar, así que podés comparar
  versiones en producción (A/B, rollback) sin tocar código — solo cambiás
  qué carpeta lee el loader.
- **Tests de template, no del modelo**: los tests en `tests/prompts/`
  verifican que el *render* es correcto (la descripción aparece, el
  condicional correcto se activa) sin llamar a ningún LLM. Corren en
  milisegundos y no dependen de tener una API key configurada.
- **Historial y memoria del proyecto separados**: el historial es transporte
  (acotado por una ventana deslizante), la memoria del proyecto es estado
  (sobrevive a la ventana y se inyecta en el system prompt). Mezclarlos hace
  que el resumen del proyecto se pierda en cuanto la ventana avanza.
- **Adjuntos con extracción local (Camino B)**: es independiente del proveedor
  LLM, testeable sin red y deja el texto listo para el chunking de RAG de un
  módulo posterior (ver la sección de memoria y adjuntos).

## Requisitos

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) como gestor de paquetes
- Una API key de OpenAI, Anthropic y/o OpenRouter
- **Node.js 20.19+** y el CLI de [OpenSpec](https://github.com/Fission-AI/OpenSpec)
  (`npm install -g @fission-ai/openspec@latest`) — solo para el flujo de specs
  guiadas (SDD), no para correr la app.

## Setup

1. Instala las dependencias:

   ```bash
   uv sync
   ```

2. Copia `.env.example` a `.env` y completa tus valores:

   ```bash
   cp .env.example .env
   ```

   | Variable                | Descripción                                                        |
   |--------------------------|--------------------------------------------------------------------|
   | `LLM_PROVIDER`           | `openai`, `anthropic` u `openrouter`                                |
   | `OPENAI_API_KEY`         | API key de OpenAI (si usas ese proveedor)                           |
   | `OPENAI_MODEL`           | Modelo económico, ej. `gpt-4o-mini`                                 |
   | `ANTHROPIC_API_KEY`      | API key de Anthropic (si usas ese proveedor)                        |
   | `ANTHROPIC_MODEL`        | Modelo económico, ej. `claude-haiku-4-5-20251001`                   |
   | `OPENROUTER_API_KEY`     | API key de OpenRouter (si usas ese proveedor)                       |
   | `OPENROUTER_MODEL`       | Modelo con prefijo de proveedor, ej. `anthropic/claude-3.5-haiku`   |
   | `OPENROUTER_BASE_URL`    | Por defecto `https://openrouter.ai/api/v1`                          |
   | `SESSION_MAX_TURNS`      | Turnos (pares user+assistant) que conserva la ventana deslizante (default `6`) |
| `ATTACHMENT_MAX_CHARS`   | Máximo de caracteres de texto extraído por adjunto (default `20000`) |
| `API_BASE_URL`           | URL del servicio IA que usa el cliente Streamlit (default `http://localhost:8000`) |

3. Arranca el **servicio IA** (FastAPI):

   ```bash
   uv run uvicorn app.main:app --reload
   ```

4. En otra terminal, arranca el **cliente** (Streamlit):

   ```bash
   uv run streamlit run streamlit_app.py
   ```

   Esto abre `http://localhost:8501`. El cliente crea una sesión y **conversa**
   con el servicio IA: cada turno hace `POST /api/v1/sessions/{session_id}/estimate`
   (`multipart/form-data` con la transcripción y, opcionalmente, adjuntos). El
   panel lateral muestra la memoria del proyecto que el servicio va acumulando.

5. O probá el endpoint directamente:

   ```bash
   curl -X POST "http://localhost:8000/api/v1/estimate?prompt_version=v1" \
     -H "Content-Type: application/json" \
     -d '{
       "description": "Necesitamos una app móvil de delivery de comida con seguimiento en tiempo real del repartidor y pagos integrados.",
       "project_type": "mobile_app",
       "detail_level": "detailed",
       "output_format": "phases_table"
     }'
   ```

   O abrí Swagger UI en [http://localhost:8000/docs](http://localhost:8000/docs).

## Memoria conversacional y adjuntos

Además del endpoint transaccional, el servicio expone un flujo conversacional
con **memoria de sesión**:

```bash
# 1) Crear una sesión
curl -X POST http://localhost:8000/api/v1/sessions
# -> {"session_id": "..."}

# 2) Turno 1 (transcripción)
curl -X POST "http://localhost:8000/api/v1/sessions/<sid>/estimate?prompt_version=v2" \
  -F "transcript=El proyecto se llama Atlas. Equipo de 4 personas. Usamos PostgreSQL."

# 3) Turno 2, con un adjunto Word (PDF/Word/texto)
curl -X POST "http://localhost:8000/api/v1/sessions/<sid>/estimate?prompt_version=v2" \
  -F "transcript=Adjunto la especificación técnica." \
  -F "attachments=@spec.docx"
```

La respuesta incluye `session_id`, `text`, `prompt_version` y el
`project_metadata` actualizado.

### Cómo se mantiene la memoria (dos estructuras separadas)

- **Historial de mensajes** (`ConversationHistory`): los pares user+assistant
  que viajan al LLM en cada llamada. Es un detalle de *transporte* y está
  acotado por una **ventana deslizante** (`deque(maxlen=SESSION_MAX_TURNS)`):
  al superar el límite se descartan los turnos más antiguos. El system prompt
  no vive aquí, así que nunca se pierde.
- **Memoria del proyecto** (`ProjectMetadata`): los hechos del proyecto
  (nombre, equipo asumido, tecnologías, alcance acordado). Vive *aparte* del
  historial, **sobrevive a la ventana deslizante** y se inyecta en el system
  prompt dentro de un bloque `<project_metadata>`, que se regenera en cada
  turno. Si está vacío, el bloque sale vacío (primera llamada de la sesión).

El estado vive en **memoria del proceso** (un diccionario `session_id -> Session`
en `app/sessions.py`). Se pierde al reiniciar el servicio — decisión consciente
de esta fase, sin BBDD ni Redis; `SessionStore` es el único punto a sustituir
si más adelante hace falta persistencia.

### Adjuntos: extracción local (Camino B)

Los adjuntos se procesan **en el servicio** con `pypdf` (PDF) y `python-docx`
(Word); el texto extraído se concatena a la transcripción con un separador por
archivo (`--- attachment: <nombre> ---`). Elegimos esto en vez de subir el PDF
al LLM multimodal (Camino A) porque:

- no acopla el servicio a la Files API de un proveedor,
- es testeable sin red ni llamadas reales al modelo,
- deja el texto listo para el chunking de RAG de un módulo posterior.

### `project_metadata`: extracción heurística

La memoria se actualiza con **reglas/regex** (`app/metadata.py`), no con una
segunda llamada al LLM: coste cero por turno, determinista y testeable sin
modelo. Los hechos nuevos se *mergean* sobre los previos, así que un turno que
no repite el nombre del proyecto no lo borra. Limitación conocida: no entiende
lenguaje libre arbitrario; en el directo se reemplaza por un extractor con LLM
sin cambiar la interfaz.

## Cómo se arma el prompt

**Flujo transaccional (v1)** — `POST /api/v1/estimate`:

```
[system]  ← app/prompts/estimation/v1/system.j2
            (rol + {% include "examples.j2" %} + condicionales
             según output_format y detail_level)
[user]    ← app/prompts/estimation/v1/user.j2
            (envuelve la descripción del proyecto del usuario)
```

**Flujo conversacional (v2)** — `POST /api/v1/sessions/{id}/estimate`:

```
[system]   ← app/prompts/estimation/v2/system.j2
             (rol conversacional + {% include "examples.j2" %} +
              bloque <project_metadata> regenerado en cada turno)
[messages] ← historial con ventana deslizante (pares user/assistant)
[user]     ← app/prompts/estimation/v2/user.j2 (envuelve la transcripción,
             ya con los adjuntos concatenados)
```

`app/prompts/loader.py` expone:

```python
render_estimation_prompt(request: EstimationRequest, version: str = "v1") -> tuple[str, str]
render_session_system_prompt(project_metadata: dict, version: str = "v2") -> str
render_session_user_prompt(transcript: str, version: str = "v2") -> str
render_session_prompt(project_metadata: dict, transcript: str, version: str = "v2") -> tuple[str, str]
```

Usa un `Environment` de Jinja2 por versión, con `StrictUndefined` (si el
template referencia una variable que no se pasó en el contexto, revienta en
vez de imprimir vacío — así un typo se detecta al toque) y
`trim_blocks=True` / `lstrip_blocks=True` para que las etiquetas `{% %}` no
dejen líneas en blanco sueltas en el prompt final.

El endpoint transaccional (`app/routers/estimations.py`) llama a
`render_estimation_prompt`, obtiene `(system, user)`, y se los pasa a
`generate_estimation` en `llm_service.py` **como dos mensajes separados** (no
concatenados en uno solo). El flujo conversacional
(`app/routers/sessions.py`) construye el array `messages` completo (system +
historial + nuevo turno) y lo pasa a `generate_estimation_messages`; para
Anthropic el system se separa al parámetro `system=` (requisito de su API).

### Versionar el prompt

El flujo conversacional usa `v2/` (copia de `v1/` con el bloque
`<project_metadata>`); `v1/` queda intacto para el endpoint transaccional. Para
agregar una `v3` con una variación (tono, ejemplos distintos, etc.):

```bash
cp -r app/prompts/estimation/v2 app/prompts/estimation/v3
# editá los .j2 de v3/ como quieras
```

Y pedila con `?prompt_version=v3` en el POST — no hace falta tocar ni el
endpoint ni el loader, la firma ya soporta cualquier carpeta de versión que
exista.

## Tests

```bash
uv run pytest
```

Toda la suite corre sin llamar a ningún LLM ni API externa:

- `tests/prompts/test_estimation_v1.py` — render del template transaccional
  (la descripción aparece dentro de `<project_description>`; el `output_format`
  y `detail_level` correctos se activan y los demás no; los ejemplos few-shot
  están incluidos; una versión inexistente levanta `ValueError`).
- `tests/prompts/test_estimation_v2.py` — render del template conversacional:
  el bloque `<project_metadata>` sale **vacío** sin hechos y con los hechos
  cuando los hay; la transcripción aparece verbatim en el user prompt; `v1`
  sigue intacto.
- `tests/test_sessions_unit.py` — la ventana deslizante descarta los turnos
  más antiguos y conserva el system prompt; `ProjectMetadata` arranca vacío;
  el system prompt se regenera desde la memoria actual.
- `tests/test_metadata.py` — la heurística detecta proyecto, equipo,
  tecnologías y alcance, y **mergea** sin perder hechos de turnos previos.
- `tests/test_attachments.py` — extracción de texto de `.docx` (generado en
  memoria) y de un PDF mínimo; el separador `--- attachment: <nombre> ---`;
  tipo no soportado → `ValueError`.
- `tests/test_sessions_integration.py` — endpoints reales con el LLM
  **mockeado**: creación de sesión, 404 en sesión inexistente, memoria visible
  entre turnos (el system prompt del 2º turno ya lleva los hechos), texto del
  adjunto presente en las `messages` enviadas al LLM, 400 con adjunto no
  soportado y ventana deslizante respetada (`MAX_TURNS`).

Corren en milisegundos porque son tests de *render* y de *lógica local*, no de
generación. `tests/conftest.py` normaliza el cliente HTTP (`httpx` o `httpx2`)
y limpia el almacén de sesiones entre tests.

## Verificación end-to-end (opcional)

`scripts/verify.sh` valida la estructura de carpetas, instala dependencias,
corre los tests y levanta el servidor real para probar `/health`, el endpoint
transaccional `POST /api/v1/estimate` y la creación de sesión
(`POST /api/v1/sessions`):

```bash
chmod +x scripts/verify.sh
./scripts/verify.sh
```

El mismo chequeo corre en CI (`.github/workflows/verify.yml`) en cada push.

## Desarrollo guiado por specs (OpenSpec)

El repo usa [OpenSpec](https://github.com/Fission-AI/OpenSpec) para escribir
especificaciones antes de tocar código (spec-driven development). No hay que
documentar todo el repo: se escriben *deltas* solo para lo que se va a cambiar.

```bash
npm install -g @fission-ai/openspec@latest   # una sola vez (requiere Node 20.19+)
openspec init --tools cline                  # ya ejecutado: crea openspec/, .cline/ y .clinerules/
```

En el chat de Cline (los comandos quedan como `/opsx-<id>`):

```text
/opsx-propose "una idea concreta"   # genera proposal.md, specs/, design.md y tasks.md
/opsx-apply                         # implementa las tareas de la spec
/opsx-archive                       # fusiona la spec en openspec/specs/ y archiva el cambio
```

- Contexto y reglas del proyecto para la IA: `openspec/config.yaml`.
- Comportamiento actual del sistema: `openspec/specs/`.
- Cambios propuestos (uno por carpeta): `openspec/changes/`.
- Validación (la misma que corre en CI y en `verify.sh`):
  `openspec validate --all --strict --no-interactive`.

`openspec/`, `.cline/` y `.clinerules/` se versionan en git (son la fuente de
verdad y los comandos del equipo). Si querés el perfil ampliado de comandos
(`new`, `continue`, `ff`, `verify`, `onboard`), corré `openspec config profile`
y luego `openspec update`.

## Fuera de alcance de esta fase

Quedan reservados para la sesión en vivo o módulos posteriores (no se
implementaron a propósito):

- **Estrategia de resumen acumulativo o híbrida con anclas** para la memoria:
  aquí la ventana es puramente deslizante.
- **Tier dinámico** derivado del contexto en runtime.
- **Persistencia de la memoria** entre reinicios del servicio (sin BBDD ni
  Redis; el estado es un diccionario en memoria del proceso).
- **`project_metadata` con LLM extractor**: se usa heurística simple.
- **Camino A de adjuntos** (subir el PDF al LLM multimodal vía Files API): se
  eligió el Camino B (extracción local).
- Forzar salida estructurada (JSON) del LLM — la respuesta sigue siendo texto
  libre en `EstimationResponse.text`.
- Validación del output con guardrails y cacheo semántico de respuestas.
- Streaming en el cliente: las funciones de streaming de `llm_service.py`
  (`stream_estimation`) se mantienen en el código para cuando se reintroduzca,
  pero el cliente conversacional hace un POST síncrono por turno y muestra el
  resultado completo.
- Búsqueda web, function calling contra la BBDD del backend y el patrón
  Actor-Critic-Boss.

## Próximos pasos (bonus)

- Sustituir la heurística de `app/metadata.py` por un extractor con LLM (o
  mover la extracción a una herramienta), manteniendo la firma de
  `extract_metadata`.
- Persistir `SessionStore` (SQLite/Redis) para sobrevivir a reinicios.
- Estrategia de memoria con resumen/anclas cuando el historial sea largo.
- Campo opcional `reference_projects` en `EstimationRequest` para que el
  template itere proyectos similares con `{% for %}`.
- `structlog` en el loader para loguear versión de prompt + hash del
  contenido en cada render.
