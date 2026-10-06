"""
Punto de entrada de la aplicacion FastAPI.
"""

from fastapi import FastAPI

from app.config import get_settings
from app.routers import estimations, sessions

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Servicio que recibe la transcripcion de una reunion y devuelve una "
        "estimacion de software generada por un LLM, usando arquitectura CAG "
        "(contexto estatico inyectado en el prompt)."
    ),
    version="0.1.0",
)

app.include_router(estimations.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def health():
    """Endpoint de salud del servicio."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "llm_provider": settings.llm_provider,
    }
