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
