"""
Cliente (Streamlit) del Estimador CAG — conversacion con memoria.

Ya no es un formulario de un solo disparo: es una conversacion. El cliente
crea una sesion (`POST /api/v1/sessions`) y reenvia el `session_id` en cada
turno (`POST /api/v1/sessions/{session_id}/estimate`). El servicio mantiene el
historial (ventana deslizante) y el `project_metadata` (memoria del proyecto),
que el cliente muestra en el panel lateral.

Los adjuntos (PDF/Word/texto) se envian en el mismo turno como
`multipart/form-data`; el servicio extrae su texto localmente (Camino B).

Cliente y servicio son procesos separados que se comunican por HTTP.

Ejecutar (en dos terminales):
    uv run uvicorn app.main:app --reload          # servicio IA
    uv run streamlit run streamlit_app.py          # cliente
"""

import requests
import streamlit as st

from app.config import get_settings

st.set_page_config(page_title="Estimador CAG", page_icon="🧮", layout="wide")

settings = get_settings()

# Estado de la conversacion en el cliente. El historial "de verdad" vive en el
# servicio; aqui solo guardamos lo necesario para pintar la pantalla.
st.session_state.setdefault("api_base_url", settings.api_base_url)
st.session_state.setdefault("prompt_version", "v2")
st.session_state.setdefault("session_id", None)
st.session_state.setdefault("messages", [])
st.session_state.setdefault("project_metadata", {})


def _api_base() -> str:
    return st.session_state["api_base_url"].rstrip("/")


def _error_detail(response: requests.Response) -> str:
    try:
        return response.json().get("detail", response.text)
    except ValueError:
        return response.text


def _create_session() -> str | None:
    try:
        response = requests.post(f"{_api_base()}/api/v1/sessions", timeout=30)
        response.raise_for_status()
        return response.json()["session_id"]
    except requests.exceptions.RequestException as exc:
        st.sidebar.error(f"No se pudo crear la sesión: {exc}")
        return None


def _render_memory(metadata: dict) -> None:
    if not metadata or not any(metadata.values()):
        st.caption("Aún no hay hechos del proyecto.")
        return
    if metadata.get("project_name"):
        st.write(f"**Proyecto:** {metadata['project_name']}")
    if metadata.get("assumed_team_size"):
        st.write(f"**Equipo asumido:** {metadata['assumed_team_size']}")
    if metadata.get("mentioned_technologies"):
        st.write("**Tecnologías:** " + ", ".join(metadata["mentioned_technologies"]))
    if metadata.get("agreed_scope"):
        st.write(f"**Alcance:** {metadata['agreed_scope']}")


st.title("🧮 Estimador CAG")
st.caption(
    "Conversá con el estimador: cada turno refina la estimación y el servicio "
    "recuerda los hechos del proyecto (memoria del proyecto) entre turnos."
)

with st.sidebar:
    st.header("⚙️ Configuración")
    st.text_input("URL del servicio IA", key="api_base_url")
    st.text_input("Versión de prompt", key="prompt_version")

    if st.button("🆕 Nueva conversación", use_container_width=True):
        st.session_state.session_id = None
        st.session_state.messages = []
        st.session_state.project_metadata = {}
        st.rerun()

    st.divider()
    st.subheader("🧠 Memoria del proyecto")
    _render_memory(st.session_state.project_metadata)

    st.divider()
    uploaded_files = st.file_uploader(
        "Adjuntar documentos (PDF/Word/texto)",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
    )
    st.caption("El texto se extrae localmente en el servicio IA (Camino B).")


# Crea la sesion la primera vez (o tras "Nueva conversación").
if st.session_state.session_id is None:
    new_session_id = _create_session()
    if new_session_id:
        st.session_state.session_id = new_session_id

if st.session_state.session_id:
    st.caption(f"Sesión: `{st.session_state.session_id}`")

# Pinta el historial de mensajes del cliente.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

transcript = st.chat_input("Escribí la transcripción del nuevo turno...")

if transcript:
    if not st.session_state.session_id:
        st.error(
            "No hay sesión activa. ¿Está corriendo el servicio IA "
            "(`uv run uvicorn app.main:app --reload`)?"
        )
        st.stop()

    st.session_state.messages.append({"role": "user", "content": transcript})
    with st.chat_message("user"):
        st.markdown(transcript)

    files_payload = [
        ("attachments", (f.name, f.getvalue(), f.type or "application/octet-stream"))
        for f in (uploaded_files or [])
    ]

    with st.chat_message("assistant"):
        with st.spinner("Generando estimación..."):
            try:
                response = requests.post(
                    f"{_api_base()}/api/v1/sessions/"
                    f"{st.session_state.session_id}/estimate",
                    params={"prompt_version": st.session_state.prompt_version},
                    data={"transcript": transcript},
                    files=files_payload or None,
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.HTTPError:
                st.error(
                    f"El servicio IA devolvió un error: {_error_detail(response)}"
                )
            except requests.exceptions.ConnectionError:
                st.error(
                    f"No se pudo conectar con el servicio IA en {_api_base()}. "
                    "¿Está corriendo `uv run uvicorn app.main:app --reload`?"
                )
            except requests.exceptions.RequestException as exc:
                st.error(f"Error inesperado llamando al servicio IA: {exc}")
            else:
                st.markdown(data["text"])
                st.session_state.messages.append(
                    {"role": "assistant", "content": data["text"]}
                )
                st.session_state.project_metadata = data["project_metadata"]
                if files_payload:
                    st.caption(
                        f"Se incorporaron {len(files_payload)} adjunto(s) "
                        "al contexto de este turno."
                    )

