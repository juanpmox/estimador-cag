"""
Loader de prompts versionados para el servicio de estimacion.

Cada version vive en su propia carpeta (app/prompts/estimation/v1/, v2/, ...)
con tres templates Jinja2: system.j2, user.j2 y examples.j2 (este ultimo
incluido por system.j2 via {% include %}). Cambiar de version de prompt es
cuestion de pasar un string distinto a `render_estimation_prompt` — el resto
del codigo (endpoint, servicio LLM) no se entera de que cambio.
"""

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from app.schemas import EstimationRequest

PROMPTS_ROOT = Path(__file__).parent / "estimation"


@lru_cache
def _get_environment(version: str) -> Environment:
    """
    Devuelve (y cachea) un Environment de Jinja2 apuntado a la carpeta de una
    version concreta del prompt de estimacion.

    StrictUndefined hace que renderizar con una variable faltante lance un
    error en vez de imprimir silenciosamente una cadena vacia — asi un typo
    entre el template y el contexto del render se detecta de inmediato.
    """
    version_dir = PROMPTS_ROOT / version
    if not version_dir.is_dir():
        raise ValueError(
            f"No existe la version de prompt '{version}' "
            f"(se esperaba encontrar {version_dir})"
        )

    return Environment(
        loader=FileSystemLoader(str(version_dir)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )


def render_estimation_prompt(
    request: EstimationRequest, version: str = "v1"
) -> tuple[str, str]:
    """
    Renderiza el system y el user prompt de `version` a partir de un
    EstimationRequest ya validado. Devuelve (system, user), listos para
    enviarse al LLM como dos mensajes separados (no concatenados).
    """
    env = _get_environment(version)

    try:
        system_template = env.get_template("system.j2")
        user_template = env.get_template("user.j2")
    except TemplateNotFound as exc:
        raise ValueError(
            f"Falta el template '{exc.name}' en la version de prompt '{version}'"
        ) from exc

    context = {
        "description": request.description,
        "project_type": request.project_type.value,
        "detail_level": request.detail_level.value,
        "output_format": request.output_format.value,
    }

    system = system_template.render(**context)
    user = user_template.render(**context)

    return system, user
