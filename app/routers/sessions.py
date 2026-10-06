"""
Endpoints de sesiones conversacionales.

Dos rutas:

- `POST /sessions`: crea una sesion vacia y devuelve su `session_id`.
- `POST /sessions/{session_id}/estimate`: procesa un turno (transcripcion +
  adjuntos opcionales) dentro de esa sesion, manteniendo la memoria
  conversacional y el `project_metadata`.

El estado vive en `app.sessions.session_store` (memoria del proceso). El
endpoint transaccional `POST /estimate` (v1) no cambia.
"""

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.attachments import build_transcript_with_attachments, extract_text
from app.metadata import extract_metadata
from app.prompts.loader import (
    DEFAULT_SESSION_PROMPT_VERSION,
    render_session_user_prompt,
)
from app.schemas import SessionCreateResponse, SessionEstimationResponse
from app.services.llm_service import generate_estimation_messages
from app.sessions import session_store

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionCreateResponse)
def create_session() -> SessionCreateResponse:
    """
    Crea una sesion conversacional vacia (sin historial ni hechos de proyecto).
    El cliente reenvia el `session_id` en cada turno posterior.
    """
    session = session_store.create()
    return SessionCreateResponse(session_id=session.session_id)


@router.post(
    "/sessions/{session_id}/estimate", response_model=SessionEstimationResponse
)
async def estimate_in_session(
    session_id: str,
    transcript: str = Form(
        ..., min_length=1, description="Transcripcion del nuevo turno."
    ),
    attachments: list[UploadFile] = File(
        default=[],
        description="Adjuntos opcionales (PDF/Word/texto) a incorporar al contexto.",
    ),
    prompt_version: str = Query(
        DEFAULT_SESSION_PROMPT_VERSION,
        description="Version del prompt a usar (v2, ...).",
    ),
) -> SessionEstimationResponse:
    """
    Procesa un turno de la sesion:

    1. Extrae localmente el texto de los adjuntos (Camino B) y lo concatena a
       la transcripcion con un separador por archivo.
    2. Construye los mensajes para el LLM: system prompt regenerado desde el
       `project_metadata` actual + el historial conservado (ventana deslizante)
       + el nuevo turno.
    3. Llama al LLM, actualiza el `project_metadata` (extraccion heuristica) y
       guarda el turno en el historial.
    """
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"Sesion '{session_id}' no encontrada"
        )

    # 1) Extraccion local del texto de los adjuntos.
    extracted: list[tuple[str, str]] = []
    for upload in attachments or []:
        filename = upload.filename or "adjunto"
        data = await upload.read()
        if not data:
            continue
        try:
            text = extract_text(filename, data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400,
                detail=f"No se pudo extraer el texto de '{filename}': {exc}",
            ) from exc
        extracted.append((filename, text))

    enriched_transcript = build_transcript_with_attachments(transcript, extracted)

    # 2) Mensajes: system (memoria actual) + historial + nuevo turno.
    try:
        messages = session.to_messages_list(version=prompt_version)
        messages.append(
            {
                "role": "user",
                "content": render_session_user_prompt(
                    enriched_transcript, version=prompt_version
                ),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 3) Llamada al LLM con el array completo de mensajes.
    try:
        result = generate_estimation_messages(messages)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"Error llamando al proveedor LLM: {exc}"
        ) from exc

    # 4) Actualizacion de la memoria del proyecto y del historial.
    session.metadata = extract_metadata(
        enriched_transcript, result.estimation, session.metadata
    )
    session.history.add_turn(enriched_transcript, result.estimation)
    session.touch()

    return SessionEstimationResponse(
        session_id=session.session_id,
        text=result.estimation,
        prompt_version=prompt_version,
        project_metadata=session.metadata,
    )
