"""
Tests del render de la version v2 del prompt (bloque <project_metadata>).
Solo verifican el render de Jinja2: no llaman a ningun LLM.
"""

import pytest

from app.prompts.loader import (
    render_estimation_prompt,
    render_session_prompt,
    render_session_system_prompt,
    render_session_user_prompt,
)
from app.schemas import (
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectMetadata,
    ProjectType,
)


def test_empty_metadata_renders_empty_block():
    system = render_session_system_prompt(ProjectMetadata().model_dump())

    assert "<project_metadata>\n</project_metadata>" in system


def test_metadata_facts_are_injected_into_block():
    metadata = ProjectMetadata(
        project_name="Atlas",
        assumed_team_size=4,
        mentioned_technologies=["React Native", "PostgreSQL"],
        agreed_scope="login y pagos",
    )

    system = render_session_system_prompt(metadata.model_dump())

    assert "nombre_del_proyecto: Atlas" in system
    assert "tamano_de_equipo_asumido: 4" in system
    assert "tecnologias_mencionadas: React Native, PostgreSQL" in system
    assert "alcance_acordado: login y pagos" in system


def test_transcript_appears_verbatim_in_user_prompt():
    transcript = "Necesitamos una app de reservas con calendario compartido."

    user = render_session_user_prompt(transcript)

    assert "<transcript>" in user
    assert transcript in user


def test_combined_render_keeps_attachment_separator():
    transcript = "base\n\n--- attachment: spec.pdf ---\ncontenido del adjunto"

    system, user = render_session_prompt(ProjectMetadata().model_dump(), transcript)

    assert "estimador de software" in system
    assert transcript in user


def test_unknown_version_raises_value_error():
    with pytest.raises(ValueError):
        render_session_system_prompt(ProjectMetadata().model_dump(), version="v999")


def test_v1_transactional_prompt_is_untouched():
    request = EstimationRequest(
        description="Descripcion de prueba con mas de veinte caracteres.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.LINE_ITEMS,
    )

    system, user = render_estimation_prompt(request, version="v1")

    assert "line_items" in system
    assert "<project_description>" in user
