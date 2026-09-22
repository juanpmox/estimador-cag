"""
Interfaz conversacional (Streamlit) para el Estimador CAG.

Reutiliza exactamente la misma logica de construccion de prompt y llamada al
LLM que el endpoint FastAPI (`app/services/llm_service.py`), asi que ambas
interfaces (REST y chat) comparten el mismo comportamiento CAG.

Ejecutar con:
    uv run streamlit run streamlit_app.py
"""

import streamlit as st

from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES, get_examples_as_text
from app.services.llm_service import build_system_prompt, stream_estimation

st.set_page_config(page_title="Estimador CAG", page_icon="🧮", layout="wide")

settings = get_settings()

# -----------------------------------------------------------------------
# Nivel 3 (opcional): panel lateral con el contexto CAG activo y metricas
# de la ultima llamada al modelo.
# -----------------------------------------------------------------------
with st.sidebar:
    st.header("🧠 Contexto CAG")
    st.caption(
        "Esto es exactamente lo que se inyecta en el prompt antes de cada "
        "estimacion — el mismo contexto estatico que usa el endpoint REST."
    )

    with st.expander("System prompt activo", expanded=False):
        st.text(build_system_prompt())

    with st.expander(
        f"Ejemplos de estimaciones inyectados ({len(ESTIMATION_EXAMPLES)})",
        expanded=False,
    ):
        st.markdown(get_examples_as_text())

    st.divider()
    st.subheader("📊 Última llamada")

    last_stats = st.session_state.get("last_stats")
    if last_stats:
        st.markdown(f"**Proveedor:** `{last_stats.get('provider', '—')}`")
        st.markdown(f"**Modelo:** `{last_stats.get('model', '—')}`")
        col_in, col_out = st.columns(2)
        col_in.metric("Tokens entrada", last_stats.get("input_tokens", "—"))
        col_out.metric("Tokens salida", last_stats.get("output_tokens", "—"))
        st.metric("Tiempo de respuesta", f"{last_stats.get('elapsed_seconds', '—')} s")
    else:
        st.caption("Todavía no se hizo ninguna consulta en esta sesión.")

# -----------------------------------------------------------------------
# Nivel 1 + 2: chat con historial persistente y respuesta en streaming.
# -----------------------------------------------------------------------
st.title("🧮 Estimador CAG")
st.caption(
    f"Proveedor activo: **{settings.llm_provider}** · "
    "Pegá la transcripción de una reunión y recibí una estimación de software."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

# Repinta el historial existente en cada rerun de Streamlit.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Pegá acá la transcripción de la reunión...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        stats: dict = {}
        try:
            # st.write_stream consume el generador, va renderizando cada
            # fragmento a medida que llega (Nivel 2) y devuelve el texto
            # completo acumulado al finalizar.
            full_response = st.write_stream(stream_estimation(prompt, stats))
        except ValueError as exc:
            # Errores de configuracion: falta una API key, etc.
            full_response = f"⚠️ Error de configuración: {exc}"
            st.error(full_response)
        except Exception as exc:  # noqa: BLE001
            # Errores al llamar al proveedor del LLM (red, auth, rate limit...).
            full_response = f"⚠️ Error llamando al proveedor LLM: {exc}"
            st.error(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    if stats:
        st.session_state.last_stats = stats
        # Vuelve a correr el script para que el panel lateral (Nivel 3)
        # muestre las metricas recien calculadas de esta llamada.
        st.rerun()
