# Estimador CAG

Servicio FastAPI que recibe la transcripción de una reunión y devuelve una
estimación de software generada por un LLM, usando arquitectura **CAG**
(*Context-Augmented Generation*): todo el contexto de referencia (ejemplos de
estimaciones previas) viaja como texto estático dentro del prompt, en cada
llamada. No hay base de datos ni retrieval en esta fase — eso llega más
adelante con RAG.

## Estructura del proyecto

```
estimador-cag/
├── app/
│   ├── main.py                 # App FastAPI, incluye el router y /health
│   ├── config.py               # Settings (pydantic-settings) desde .env
│   ├── routers/
│   │   └── estimations.py      # POST /api/v1/estimate
│   ├── services/
│   │   └── llm_service.py      # Prompt CAG + llamadas (sync y streaming) al LLM
│   └── context/
│       └── examples.py         # Ejemplos estáticos (few-shot) inyectados en el prompt
├── streamlit_app.py            # Interfaz de chat (Streamlit), con streaming
├── scripts/
│   └── verify.sh               # Valida estructura + arranca el server + prueba /health y /estimate
├── sample_data/
│   └── meeting_transcription.md
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

## Requisitos

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) como gestor de paquetes
- Una API key de OpenAI y/o Anthropic

## Setup

1. Instala las dependencias:

   ```bash
   uv sync
   ```

2. Copia `.env.example` a `.env` y completa tus valores:

   ```bash
   cp .env.example .env
   ```

   Variables relevantes:

   | Variable                | Descripción                                                  |
   |-------------------------|---------------------------------------------------------------|
   | `LLM_PROVIDER`          | `openai`, `anthropic` u `openrouter`                           |
   | `OPENAI_API_KEY`        | API key de OpenAI (si usas ese proveedor)                      |
   | `OPENAI_MODEL`          | Modelo económico, ej. `gpt-4o-mini`                            |
   | `ANTHROPIC_API_KEY`     | API key de Anthropic (si usas ese proveedor)                   |
   | `ANTHROPIC_MODEL`       | Modelo económico, ej. `claude-haiku-4-5-20251001`              |
   | `OPENROUTER_API_KEY`    | API key de OpenRouter (si usas ese proveedor)                  |
   | `OPENROUTER_MODEL`      | Modelo con prefijo de proveedor, ej. `anthropic/claude-3.5-haiku`, `openai/gpt-4o-mini`, `meta-llama/llama-3.1-8b-instruct` |
   | `OPENROUTER_BASE_URL`   | Por defecto `https://openrouter.ai/api/v1`                     |
   | `OPENROUTER_SITE_URL`   | Opcional — para rankings/analytics en el dashboard de OpenRouter |
   | `OPENROUTER_SITE_NAME`  | Opcional — idem                                                |

   > **¿Por qué OpenRouter es "opcional" a nivel de código?** Su API es compatible con la de OpenAI, así que `_call_openrouter()` reutiliza el mismo `openai` SDK, solo cambiando `base_url` y el nombre del modelo (que en OpenRouter lleva el prefijo del proveedor real, ej. `anthropic/...`, `google/...`). No hace falta instalar ninguna dependencia nueva.

3. Arranca el servidor:

   ```bash
   uv run uvicorn app.main:app --reload
   ```

4. Prueba el endpoint:

   ```bash
   curl -X POST http://localhost:8000/api/v1/estimate \
     -H "Content-Type: application/json" \
     -d @sample_data/meeting_transcription.json
   ```

   O abre Swagger UI en [http://localhost:8000/docs](http://localhost:8000/docs).

## Interfaz de chat (Streamlit)

Además del endpoint REST, el proyecto incluye una interfaz conversacional
para no depender de `curl`/Postman/Swagger:

```bash
uv run streamlit run streamlit_app.py
```

Esto abre `http://localhost:8501` en el navegador. Pegás la transcripción de
una reunión en el chat y la estimación se va mostrando en streaming, token a
token, a medida que el modelo la genera.

Qué incluye:

- **Historial persistente** durante la sesión (`st.session_state`), podés
  encadenar varias transcripciones sin perder el contexto visual del chat.
- **Streaming real**, no simulado: usa `st.write_stream` sobre un generador
  (`stream_estimation` en `llm_service.py`) que reenvía los chunks tal como
  los va devolviendo el proveedor (OpenAI, Anthropic u OpenRouter).
- **Panel lateral con el contexto CAG**: el system prompt activo y los
  ejemplos estáticos inyectados, para que se vea exactamente qué está
  "sabiendo" el modelo al generar cada estimación.
- **Métricas de la última llamada**: proveedor, modelo, tokens de entrada y
  salida, y tiempo de respuesta.
- La API key se lee siempre desde `.env` (vía `app/config.py`), igual que en
  el endpoint REST — nunca está hardcodeada en `streamlit_app.py`.

> Si en algún momento deployás esto en Streamlit Community Cloud, podés
> reemplazar el `.env` por `st.secrets` sin tocar `streamlit_app.py`: alcanza
> con que `app/config.py` lea también `st.secrets` como fuente adicional, o
> con exportar esas mismas variables como "Secrets" en la configuración de la
> app en Streamlit Cloud.



`scripts/verify.sh` valida que la estructura de carpetas esperada exista,
instala dependencias, levanta el servidor en background, y prueba
`GET /health` y `POST /api/v1/estimate` contra el servidor real:

```bash
chmod +x scripts/verify.sh
./scripts/verify.sh
```

Este mismo script es el que se usa en el pipeline de CI (ver
`.gitea/workflows/verify.yml` o el equivalente de GitHub Actions) para
validar cada push a la rama del ejercicio.

## Arquitectura CAG (resumen)

```
[system]    → System prompt con el rol del modelo + ejemplos estáticos de
              estimaciones previas (app/context/examples.py)
[user]      → Transcripción de la reunión a estimar
[assistant] → Estimación generada (respuesta del modelo)
```

El corazón de la arquitectura está en `app/services/llm_service.py`, donde
`_build_system_prompt()` inyecta los ejemplos de `context/examples.py`
directamente en el system prompt antes de cada llamada al LLM.

## Próximos pasos

- Iterar sobre la calidad de los ejemplos de contexto y el prompt.
- Explorar parámetros del modelo (temperature, max_tokens).
- Evolucionar de CAG a RAG cuando el volumen de ejemplos de referencia crezca
  más allá de lo que razonablemente cabe en el contexto.
