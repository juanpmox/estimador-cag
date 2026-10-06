"""
Extraccion heuristica de los hechos del proyecto (`project_metadata`).

Elegimos heuristica simple (regex + lista de tecnologias conocidas) en vez de
un LLM extractor porque:

- no añade una llamada al proveedor por turno (coste/latencia cero),
- es determinista y testeable sin llamar a ningun LLM,
- los campos de esta fase son pocos y las frases, acotadas.

Limitacion conocida: no entiende lenguaje libre arbitrario. En el directo se
sustituye por un extractor con LLM; la interfaz de esta funcion no cambia.

La extraccion es *acumulativa*: los hechos nuevos se mergean sobre el
`ProjectMetadata` previo para no olvidar lo ya conocido entre turnos.
"""

from __future__ import annotations

import re

from app.schemas import ProjectMetadata

# Tecnologias/librerias que reconocemos por nombre (case-insensitive). Se puede
# ampliar sin tocar la logica.
TECH_KEYWORDS: tuple[str, ...] = (
    "React Native", "React", "Next.js", "Vue", "Angular", "Svelte",
    "Node.js", "Django", "Flask", "FastAPI", "Spring Boot", "Rails",
    "Laravel", "TypeScript", "JavaScript", "Python", "Kotlin", "Swift",
    "GraphQL", "REST", "gRPC", "PostgreSQL", "Postgres", "MySQL", "MongoDB",
    "Redis", "Elasticsearch", "Kafka", "RabbitMQ", "Airflow", "Spark",
    "Snowflake", "BigQuery", "Databricks", "Docker", "Kubernetes", "Terraform",
    "AWS", "Azure", "GCP", "Stripe", "OAuth2", "OAuth", "S3",
)

_PROJECT_NAME_PATTERNS = (
    r"(?:proyecto|app|aplicaci[oó]n|plataforma|sistema|herramienta|producto)\s+"
    r"(?:se\s+llama|llamad[oa]s?|denominad[oa]s?)\s+"
    r"[«\"“'`]?([A-ZÁÉÍÓÚÑ][\w.\-áéíóúñ]*)",
    r"se\s+llama\s+[«\"“'`]?([A-ZÁÉÍÓÚÑ][\w.\-áéíóúñ]*)",
    r"(?:proyecto|app|aplicaci[oó]n|plataforma|sistema|producto)\s+"
    r"[«\"“'`]([^»\"”'`\n]{2,40})[»\"”'`]",
)

_TEAM_PATTERNS = (
    r"equipo\s+de\s+(\d+)",
    r"(\d+)\s+(?:personas|desarrollador(?:es)?|ingenieros?|devs?)",
    r"(\d+)\s+miembros?\s+de\s+equipo",
)


def _detect_project_name(text: str) -> str | None:
    for pattern in _PROJECT_NAME_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".,;:")
    return None


def _detect_team_size(text: str) -> int | None:
    for pattern in _TEAM_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _detect_technologies(text: str) -> list[str]:
    # Ordenamos de mas largo a mas corto y "consumimos" cada match para que
    # "React Native" no cuente tambien como "React".
    working = text
    found: set[str] = set()
    for keyword in sorted(TECH_KEYWORDS, key=len, reverse=True):
        pattern = re.compile(
            r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", re.IGNORECASE
        )
        if pattern.search(working):
            found.add(keyword)
            working = pattern.sub(" ", working)
    return sorted(found)


def _detect_scope(transcript: str) -> str | None:
    match = re.search(r"alcance[^.\n]{0,200}", transcript, re.IGNORECASE)
    return match.group(0).strip() if match else None


def extract_metadata(
    transcript: str,
    response: str = "",
    previous: ProjectMetadata | None = None,
) -> ProjectMetadata:
    """
    Devuelve el `ProjectMetadata` actualizado a partir de la nueva interaccion
    (transcripcion del usuario + respuesta del modelo), mergeando sobre
    `previous` para no perder hechos ya conocidos.
    """
    previous = previous or ProjectMetadata()
    text = f"{transcript}\n{response}"

    project_name = _detect_project_name(text) or previous.project_name
    team_size = _detect_team_size(text) or previous.assumed_team_size
    technologies = sorted(
        set(previous.mentioned_technologies) | set(_detect_technologies(text))
    )
    scope = _detect_scope(transcript) or previous.agreed_scope

    return ProjectMetadata(
        project_name=project_name,
        assumed_team_size=team_size,
        mentioned_technologies=technologies,
        agreed_scope=scope,
    )
