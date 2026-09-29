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
│   ├── schemas.py                    # EstimationRequest / EstimationResponse (contrato tipado)
│   ├── prompts/
│   │   ├── loader.py                 # render_estimation_prompt(request, version) -> (system, user)
│   │   └── estimation/
│   │       └── v1/
│   │           ├── system.j2         # Rol + instrucciones + condicionales por formato/detalle
│   │           ├── user.j2           # Envuelve la descripción del proyecto
│   │           └── examples.j2       # Few-shot, incluido por system.j2
│   ├── routers/
│   │   └── estimations.py            # POST /api/v1/estimate
│   └── services/
│       └── llm_service.py            # Wrapper de proveedor (OpenAI/Anthropic/OpenRouter)
├── streamlit_app.py                  # Cliente: formulario tipado, POST al servicio IA
├── tests/
│   └── prompts/
│       └── test_estimation_v1.py     # Tests del template (sin llamar a ningún LLM)
├── scripts/
│   └── verify.sh
├── sample_data/
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

## Requisitos

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) como gestor de paquetes
- Una API key de OpenAI, Anthropic y/o OpenRouter

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
   | `API_BASE_URL`           | URL del servicio IA que usa el cliente Streamlit (default `http://localhost:8000`) |

3. Arranca el **servicio IA** (FastAPI):

   ```bash
   uv run uvicorn app.main:app --reload
   ```

4. En otra terminal, arranca el **cliente** (Streamlit):

   ```bash
   uv run streamlit run streamlit_app.py
   ```

   Esto abre `http://localhost:8501`. Completás el formulario (descripción,
   tipo de proyecto, nivel de detalle, formato de salida) y el cliente hace
   `POST /api/v1/estimate` contra el servicio IA con ese JSON.

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

## Cómo se arma el prompt

```
[system]  ← app/prompts/estimation/<version>/system.j2
            (rol del modelo + {% include "examples.j2" %} + condicionales
             según output_format y detail_level)
[user]    ← app/prompts/estimation/<version>/user.j2
            (envuelve la descripción del proyecto del usuario)
```

`app/prompts/loader.py` expone:

```python
render_estimation_prompt(request: EstimationRequest, version: str = "v1") -> tuple[str, str]
```

Usa un `Environment` de Jinja2 por versión, con `StrictUndefined` (si el
template referencia una variable que no se pasó en el contexto, revienta en
vez de imprimir vacío — así un typo se detecta al toque) y
`trim_blocks=True` / `lstrip_blocks=True` para que las etiquetas `{% %}` no
dejen líneas en blanco sueltas en el prompt final.

El endpoint (`app/routers/estimations.py`) llama a `render_estimation_prompt`,
obtiene `(system, user)`, y se los pasa a `generate_estimation` en
`llm_service.py` **como dos mensajes separados** (no concatenados en uno
solo) antes de llamar al proveedor configurado.

### Versionar el prompt

Para agregar una `v2` con una variación (tono, ejemplos distintos, etc.):

```bash
cp -r app/prompts/estimation/v1 app/prompts/estimation/v2
# editá los .j2 de v2/ como quieras
```

Y pedila con `?prompt_version=v2` en el POST — no hace falta tocar ni el
endpoint ni el loader, la firma ya soporta cualquier carpeta de versión que
exista.

## Tests

```bash
uv run pytest
```

`tests/prompts/test_estimation_v1.py` cubre, sin llamar a ningún LLM:

- que la descripción del usuario aparece literalmente dentro de
  `<project_description>` en el user prompt;
- que el system prompt contiene la palabra clave del `output_format`
  seleccionado (`phases_table`, `line_items`, `narrative`) y **no** las de
  los otros formatos;
- que `detail_level=detailed` agrega la instrucción de listar "asunciones
  por fase" y que `detail_level=summary` no la incluye;
- que los ejemplos few-shot de `examples.j2` están efectivamente incluidos
  en el system prompt renderizado;
- que pedir una versión de prompt inexistente levanta un `ValueError`
  claro (y el endpoint lo traduce a un `400`).

Corren en milisegundos porque son tests de *render*, no de generación.

## Verificación end-to-end (opcional)

`scripts/verify.sh` valida la estructura de carpetas, instala dependencias,
corre los tests y levanta el servidor real para probar `/health`:

```bash
chmod +x scripts/verify.sh
./scripts/verify.sh
```

El mismo chequeo corre en CI (`.github/workflows/verify.yml`) en cada push.

## Fuera de alcance de este refactor

Quedan reservados para la sesión en vivo (no se implementaron a propósito):

- Forzar salida estructurada (JSON) del LLM — la respuesta sigue siendo
  texto libre en `EstimationResponse.text`.
- Validación del output con guardrails.
- Cacheo semántico de respuestas.
- Streaming en el cliente: las funciones de streaming de `llm_service.py`
  (`stream_estimation`) se mantienen en el código para cuando se
  reintroduzca, pero el formulario actual hace un POST síncrono y muestra
  el resultado completo — streamear un formulario que dispara un solo
  request/response es un tema aparte que toca la sesión en vivo.

## Próximos pasos (bonus)

- `v2/` de prompt con una variación de tono o de ejemplos (ver arriba).
- Campo opcional `reference_projects` en `EstimationRequest` para que el
  template itere proyectos similares con `{% for %}`.
- `structlog` en el loader para loguear versión de prompt + hash del
  contenido en cada render.
