"""
Tests del template de prompts (version v1). No llaman a ningun LLM ni API
externa — solo verifican que el render de Jinja2 produce el texto esperado
segun los parametros de la request. Deben correr en milisegundos.
"""

import pytest

from app.prompts.loader import render_estimation_prompt
from app.schemas import DetailLevel, EstimationRequest, OutputFormat, ProjectType


def _make_request(**overrides) -> EstimationRequest:
    defaults = dict(
        description="Descripcion de prueba con mas de veinte caracteres para pasar la validacion.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.LINE_ITEMS,
    )
    defaults.update(overrides)
    return EstimationRequest(**defaults)


def test_user_prompt_includes_description_verbatim():
    description = "Plataforma de reservas de salas con calendario compartido y notificaciones."
    request = _make_request(description=description)

    _, user = render_estimation_prompt(request)

    assert "<project_description>" in user
    assert "</project_description>" in user
    assert description in user


@pytest.mark.parametrize(
    "output_format, expected_keyword",
    [
        (OutputFormat.PHASES_TABLE, "phases_table"),
        (OutputFormat.LINE_ITEMS, "line_items"),
        (OutputFormat.NARRATIVE, "narrative"),
    ],
)
def test_system_prompt_reflects_selected_output_format(output_format, expected_keyword):
    request = _make_request(output_format=output_format)
    system, _ = render_estimation_prompt(request)

    assert expected_keyword in system

    # Los formatos no seleccionados no deben aparecer en el system prompt.
    other_keywords = {"phases_table", "line_items", "narrative"} - {expected_keyword}
    for keyword in other_keywords:
        assert keyword not in system


def test_system_prompt_includes_per_phase_assumptions_only_when_detailed():
    detailed_request = _make_request(detail_level=DetailLevel.DETAILED)
    summary_request = _make_request(detail_level=DetailLevel.SUMMARY)

    system_detailed, _ = render_estimation_prompt(detailed_request)
    system_summary, _ = render_estimation_prompt(summary_request)

    assert "asunciones por fase" in system_detailed
    assert "asunciones por fase" not in system_summary


def test_examples_are_included_in_system_prompt():
    request = _make_request()
    system, _ = render_estimation_prompt(request)

    # examples.j2 se incluye via {% include %} en system.j2 — verificamos
    # que al menos uno de los ejemplos few-shot este presente.
    assert "Ejemplo 1" in system
    assert "Ejemplo 2" in system


def test_unknown_prompt_version_raises_value_error():
    request = _make_request()

    with pytest.raises(ValueError):
        render_estimation_prompt(request, version="v999-no-existe")
