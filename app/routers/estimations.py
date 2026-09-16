"""
Endpoints relacionados con la generacion de estimaciones de software.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.llm_service import generate_estimation

router = APIRouter(tags=["estimations"])


class EstimationRequest(BaseModel):
    transcription: str = Field(
        ...,
        min_length=10,
        description="Texto de la transcripcion de la reunion con el cliente.",
        examples=[
            "En la reunion con el equipo de marketing, el cliente explico que "
            "necesita una landing page con formulario de contacto, integracion "
            "con su CRM actual (HubSpot), y una seccion de blog con editor "
            "WYSIWYG. El plazo ideal seria tenerlo listo en 4 semanas. El "
            "diseno ya existe en Figma."
        ],
    )


class EstimationResponse(BaseModel):
    estimation: str
    model: str
    provider: str


@router.post("/estimate", response_model=EstimationResponse)
def estimate(request: EstimationRequest) -> EstimationResponse:
    """
    Recibe la transcripcion de una reunion y devuelve una estimacion de
    software generada por el LLM configurado, usando arquitectura CAG
    (contexto estatico inyectado en el prompt).
    """
    try:
        result = generate_estimation(request.transcription)
    except ValueError as exc:
        # Errores de configuracion (p.ej. falta la API key)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        # Errores al llamar al proveedor del LLM
        raise HTTPException(
            status_code=502, detail=f"Error llamando al proveedor LLM: {exc}"
        ) from exc

    return EstimationResponse(
        estimation=result.estimation,
        model=result.model,
        provider=result.provider,
    )
