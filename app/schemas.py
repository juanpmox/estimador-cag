"""
Contrato tipado entre el cliente (formulario Streamlit) y el servicio IA.

Reemplaza al textarea libre de la sesion anterior: el espacio de tareas es
acotado (tipo de proyecto, nivel de detalle, formato de salida), asi que un
formulario con estos campos produce mejor producto que un chat de texto
libre.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ProjectType(str, Enum):
    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(str, Enum):
    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"


class EstimationRequest(BaseModel):
    description: str = Field(min_length=20, max_length=2000)
    project_type: ProjectType
    detail_level: DetailLevel
    output_format: OutputFormat


class EstimationResponse(BaseModel):
    text: str
    prompt_version: str


class ProjectMetadata(BaseModel):
    """
    Hechos relevantes del proyecto en curso (memoria de la sesion).

    Vive separado del historial de mensajes: sobrevive a la ventana deslizante
    y se inyecta en el system prompt via el bloque `<project_metadata>`.
    """

    project_name: str | None = None
    assumed_team_size: int | None = None
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = None

    def is_empty(self) -> bool:
        """True si aun no se ha capturado ningun hecho del proyecto."""
        return (
            self.project_name is None
            and self.assumed_team_size is None
            and not self.mentioned_technologies
            and self.agreed_scope is None
        )


class SessionCreateResponse(BaseModel):
    """Respuesta de `POST /api/v1/sessions`."""

    session_id: str


class SessionEstimationResponse(BaseModel):
    """Respuesta de `POST /api/v1/sessions/{session_id}/estimate`."""

    session_id: str
    text: str
    prompt_version: str
    project_metadata: ProjectMetadata
