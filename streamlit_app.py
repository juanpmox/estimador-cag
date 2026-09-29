"""
Cliente (Streamlit) del Estimador CAG.

Ya no es un chat: es un formulario tipado. El espacio de tareas es acotado
(tipo de proyecto, nivel de detalle, formato de salida) asi que un
formulario produce mejor producto que un textarea libre — evita ambiguedad
en la entrada y deja que el prompt (no el usuario) decida como pedirle la
estimacion al modelo.

El formulario arma un EstimationRequest y hace POST /api/v1/estimate contra
el servicio IA (FastAPI) via HTTP — cliente y servicio son procesos
separados que se comunican por API, no un import directo.

Ejecutar (en dos terminales):
    uv run uvicorn app.main:app --reload          # servicio IA
    uv run streamlit run streamlit_app.py          # cliente
"""

import requests
import streamlit as st

from app.config import get_settings
from app.schemas import DetailLevel, EstimationRequest, OutputFormat, ProjectType

st.set_page_config(page_title="Estimador CAG", page_icon="🧮", layout="centered")

settings = get_settings()

PROJECT_TYPE_LABELS = {
    ProjectType.MOBILE_APP: "App móvil",
    ProjectType.WEB_SAAS: "Web / SaaS",
    ProjectType.INTERNAL_TOOL: "Herramienta interna",
    ProjectType.DATA_PIPELINE: "Pipeline de datos",
}

DETAIL_LEVEL_LABELS = {
    DetailLevel.SUMMARY: "Resumen (solo totales)",
    DetailLevel.MEDIUM: "Medio (por fase)",
    DetailLevel.DETAILED: "Detallado (por fase y tarea)",
}

OUTPUT_FORMAT_LABELS = {
    OutputFormat.PHASES_TABLE: "Tabla de fases",
    OutputFormat.LINE_ITEMS: "Líneas de trabajo (line items)",
    OutputFormat.NARRATIVE: "Narrativo",
}

st.title("🧮 Estimador CAG")
st.caption(
    "Completá el formulario con los parámetros del proyecto. "
    "El servicio IA arma el prompt con templates versionados y genera la estimación."
)

with st.sidebar:
    st.header("⚙️ Configuración")
    api_base_url = st.text_input("URL del servicio IA", value=settings.api_base_url)
    prompt_version = st.text_input("Versión de prompt", value="v1")
    st.caption(
        "El servicio soporta múltiples versiones de prompt en paralelo "
        "(`app/prompts/estimation/<version>/`). Cambiar esto no requiere "
        "tocar código, solo el nombre de la carpeta de versión."
    )

with st.form("estimation_form"):
    description = st.text_area(
        "Descripción del proyecto",
        placeholder=(
            "Ej: Necesitamos una app móvil de delivery de comida con "
            "seguimiento en tiempo real del repartidor y pagos integrados."
        ),
        height=150,
        max_chars=2000,
    )

    col1, col2 = st.columns(2)
    with col1:
        project_type = st.selectbox(
            "Tipo de proyecto",
            options=list(ProjectType),
            format_func=lambda p: PROJECT_TYPE_LABELS[p],
        )
        detail_level = st.selectbox(
            "Nivel de detalle",
            options=list(DetailLevel),
            format_func=lambda d: DETAIL_LEVEL_LABELS[d],
            index=1,
        )
    with col2:
        output_format = st.selectbox(
            "Formato de salida",
            options=list(OutputFormat),
            format_func=lambda o: OUTPUT_FORMAT_LABELS[o],
        )

    submitted = st.form_submit_button("Generar estimación", use_container_width=True)

if submitted:
    if len(description.strip()) < 20:
        st.error("La descripción debe tener al menos 20 caracteres.")
    else:
        # Construimos y validamos el request con el mismo schema Pydantic
        # que usa el servicio, asi el error de validacion (si lo hay) se ve
        # antes de salir de la maquina del cliente.
        request = EstimationRequest(
            description=description.strip(),
            project_type=project_type,
            detail_level=detail_level,
            output_format=output_format,
        )

        with st.spinner("Generando estimación..."):
            try:
                response = requests.post(
                    f"{api_base_url}/api/v1/estimate",
                    params={"prompt_version": prompt_version},
                    json=request.model_dump(mode="json"),
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.ConnectionError:
                st.error(
                    f"No se pudo conectar con el servicio IA en {api_base_url}. "
                    "¿Está corriendo `uv run uvicorn app.main:app --reload`?"
                )
            except requests.exceptions.HTTPError:
                detail = response.json().get("detail", response.text)
                st.error(f"El servicio IA devolvió un error: {detail}")
            except requests.exceptions.RequestException as exc:
                st.error(f"Error inesperado llamando al servicio IA: {exc}")
            else:
                st.success(f"Estimación generada (prompt {data['prompt_version']})")
                st.markdown(data["text"])
