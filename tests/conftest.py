"""
Configuracion comun de la suite de tests.

Ademas de dejar la raiz del proyecto en `sys.path`, normaliza el cliente HTTP
(el entorno puede traer `httpx` o solo `httpx2`, del que FastAPI/Starlette
depende) y limpia el almacen de sesiones entre tests para que no se filtren
estados de un caso a otro.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Algunos entornos instalan `httpx`; otros traen `httpx2`. Starlette (y por
# tanto el TestClient de FastAPI) importa `httpx`, asi que si solo esta
# `httpx2` lo aliasamos para que `import httpx` funcione.
try:  # pragma: no cover - depende del entorno
    import httpx  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - depende del entorno
    import httpx2

    httpx2.alias_httpx()

import pytest  # noqa: E402

from app.sessions import session_store  # noqa: E402


@pytest.fixture
def client():
    """TestClient de FastAPI apuntando a la app real."""
    from starlette.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clean_session_store():
    """Aisla cada test: arranca y termina con el almacen de sesiones vacio."""
    session_store.clear()
    yield
    session_store.clear()

