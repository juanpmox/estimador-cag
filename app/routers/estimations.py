"""
Endpoint de generacion de estimaciones de software.
"""

from fastapi import APIRouter, HTTPException, Query

from app.prompts.loader import render_estimation_prompt
from app.schemas import EstimationRequest, EstimationResponse
from app.services.llm_service import generate_estimation

router = APIRouter(tags=["estimations"])


@router.post("/estimate", response_model=EstimationResponse)
def estimate(
    request: EstimationRequest,
    prompt_version: str = Query(
        "v1",
        description="Version del prompt a usar (v1, v2, ...). Permite iterar "
        "sobre el prompt sin tocar el endpoint ni el cliente.",
    ),
) -> EstimationResponse:
    """
    Recibe un EstimationRequest tipado (descripcion + tipo de proyecto +
    nivel de detalle + formato de salida), renderiza el prompt versionado
    correspondiente (system + user por separado) y llama al LLM configurado.
    """
    try:
        system, user = render_estimation_prompt(request, version=prompt_version)
    except ValueError as exc:
        # Version de prompt inexistente o template faltante.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = generate_estimation(system, user)
    except ValueError as exc:
        # Errores de configuracion (p.ej. falta la API key del proveedor).
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        # Errores al llamar al proveedor del LLM.
        raise HTTPException(
            status_code=502, detail=f"Error llamando al proveedor LLM: {exc}"
        ) from exc

    return EstimationResponse(text=result.estimation, prompt_version=prompt_version)
