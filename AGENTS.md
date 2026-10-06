# AGENTS.md — Estimador CAG

Instrucciones para asistentes de IA (Cline, etc.) que trabajen en este repo.
Este proyecto usa **OpenSpec** para desarrollo guiado por especificaciones; ver
la seccion [OpenSpec](#openspec) mas abajo.

## Que es este proyecto

Servicio **FastAPI** + cliente **Streamlit** que generan una estimacion de
software a partir de una descripcion de proyecto, con arquitectura **CAG**
(contexto estatico inyectado en el prompt, no RAG).

## Stack

- Python >= 3.11, gestionado con **`uv`** (`pyproject.toml` + `uv.lock`).
- **FastAPI** + `uvicorn` (servicio), **Streamlit** (cliente).
- **Pydantic v2** / `pydantic-settings` (contrato y config).
- **Jinja2** (templates de prompt).
- Proveedores LLM: OpenAI, Anthropic, OpenRouter.
- El runtime de la app **no** depende de Node; `uv` es el unico gestor de
  dependencias de Python.

## Comandos utiles

```bash
uv sync                                   # instalar dependencias
uv run pytest                             # tests (rapidos, sin llamar a ningun LLM)
uv run uvicorn app.main:app --reload      # servicio IA (http://localhost:8000)
uv run streamlit run streamlit_app.py     # cliente (http://localhost:8501)
./scripts/verify.sh                       # verificacion end-to-end
```

## Convenciones (respetar siempre)

- **Prompts solo en templates Jinja2 versionados**: `app/prompts/estimation/<version>/{system,user,examples}.j2`.
  Nunca hardcodear prompts en strings de Python. El loader vive en
  `app/prompts/loader.py`.
- **Versionado de prompts**: agregar una version es copiar la carpeta (`v1/` -> `v2/`).
  El endpoint elige con `?prompt_version=`. No tocar el endpoint ni el loader.
- **Contrato tipado** en `app/schemas.py` (Pydantic v2). Cliente y servicio son
  procesos separados que se comunican por **HTTP**, no por import directo.
- **Tests de render, no de generacion**: los tests en `tests/prompts/` verifican
  el render de Jinja2 y no deben llamar a ningun LLM ni API externa.
- **Idioma**: escribe codigo, comentarios y artefactos en **espanol** (los
  identificadores tecnicos pueden ir en ingles). Una nueva version de prompt es
  `v1/` -> `v2/`.
- **Docs y specs**: `README.md` documenta el proyecto; `openspec/` documenta el
  comportamiento del sistema y los cambios propuestos.

## OpenSpec

Este repo usa [OpenSpec](https://github.com/Fission-AI/OpenSpec) (SDD). El flujo
escribe artefactos de planificacion **antes** de tocar codigo.

- Contexto y reglas del proyecto: `openspec/config.yaml`.
- Specs (comportamiento actual): `openspec/specs/`.
- Cambios propuestos (deltas): `openspec/changes/`.
- Comandos en el chat de Cline: `/opsx-propose`, `/opsx-explore`, `/opsx-apply`,
  `/opsx-sync`, `/opsx-update`, `/opsx-archive`.

Flujo tipico: `/opsx-propose "una idea concreta"` -> revisar los artefactos ->
`/opsx-apply` -> `/opsx-archive`.

> `openspec/`, `.cline/` y `.clinerules/` se versionan en git (son la fuente de
> verdad y los comandos del equipo).
