"""
Tests de integracion de los endpoints de sesion.

Mockean la llamada al proveedor LLM (no hay llamadas reales ni red) y verifican
el comportamiento observable: memoria entre turnos, adjuntos incorporados al
prompt y ventana deslizante del historial.
"""

import io
from types import SimpleNamespace
from unittest.mock import patch

import docx

import app.sessions as sessions_module
from app.services.llm_service import EstimationResult

SESSIONS_URL = "/api/v1/sessions"


def _fake_llm(messages, **kwargs) -> EstimationResult:
    """Sustituto del proveedor LLM: devuelve una estimacion fija."""
    return EstimationResult(
        estimation="## Estimacion\nTotal: 120 horas", model="mock-model", provider="mock"
    )


def _build_docx(text: str) -> bytes:
    documento = docx.Document()
    documento.add_paragraph(text)
    buffer = io.BytesIO()
    documento.save(buffer)
    return buffer.getvalue()


def _create_session(client) -> str:
    response = client.post(SESSIONS_URL)
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _estimate(client, session_id, transcript, files=None, version="v2"):
    return client.post(
        f"{SESSIONS_URL}/{session_id}/estimate",
        params={"prompt_version": version},
        data={"transcript": transcript},
        files=files or [],
    )


def test_create_session_returns_unique_uuid(client):
    first = client.post(SESSIONS_URL).json()["session_id"]
    second = client.post(SESSIONS_URL).json()["session_id"]

    assert first != second


def test_estimate_on_unknown_session_returns_404(client):
    response = _estimate(client, "no-existe", "hola")

    assert response.status_code == 404


def test_first_turn_system_prompt_has_empty_metadata(client):
    session_id = _create_session(client)

    with patch("app.routers.sessions.generate_estimation_messages") as mock_llm:
        mock_llm.side_effect = _fake_llm
        response = _estimate(client, session_id, "Hola, quiero una app de reservas")

    assert response.status_code == 200, response.text
    messages = mock_llm.call_args.args[0]
    assert "<project_metadata>\n</project_metadata>" in messages[0]["content"]


def test_metadata_is_visible_across_turns(client):
    session_id = _create_session(client)

    with patch("app.routers.sessions.generate_estimation_messages") as first_call:
        first_call.side_effect = _fake_llm
        response1 = _estimate(
            client,
            session_id,
            "El proyecto se llama Atlas. Equipo de 4 personas. Usamos PostgreSQL.",
        )

    assert response1.status_code == 200, response1.text
    metadata1 = response1.json()["project_metadata"]
    assert metadata1["project_name"] == "Atlas"
    assert metadata1["assumed_team_size"] == 4

    with patch("app.routers.sessions.generate_estimation_messages") as second_call:
        second_call.side_effect = _fake_llm
        response2 = _estimate(client, session_id, "Anade pagos con Stripe y Kafka")

    assert response2.status_code == 200, response2.text
    metadata2 = response2.json()["project_metadata"]
    # Los hechos previos persisten aunque este turno no los repita.
    assert metadata2["project_name"] == "Atlas"
    assert "PostgreSQL" in metadata2["mentioned_technologies"]
    assert "Stripe" in metadata2["mentioned_technologies"]

    # El 2o turno envia: system (con los hechos) + historial + nuevo usuario.
    messages = second_call.call_args.args[0]
    assert "nombre_del_proyecto: Atlas" in messages[0]["content"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]


def test_attachment_text_reaches_the_prompt(client):
    session_id = _create_session(client)
    docx_bytes = _build_docx(
        "Especificacion tecnica: microservicios en Kubernetes con Kafka"
    )
    files = [
        (
            "attachments",
            (
                "spec.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        )
    ]

    with patch("app.routers.sessions.generate_estimation_messages") as mock_llm:
        mock_llm.side_effect = _fake_llm
        response = _estimate(
            client, session_id, "Adjunto la especificacion tecnica.", files=files
        )

    assert response.status_code == 200, response.text
    messages = mock_llm.call_args.args[0]
    user_content = messages[-1]["content"]
    assert "--- attachment: spec.docx ---" in user_content
    assert "Kubernetes" in user_content
    # La tecnologia del adjunto tambien alimenta la memoria del proyecto.
    assert "Kubernetes" in response.json()["project_metadata"]["mentioned_technologies"]


def test_unsupported_attachment_returns_400(client):
    session_id = _create_session(client)
    files = [("attachments", ("imagen.png", b"\x89PNG\r\n", "image/png"))]

    response = _estimate(client, session_id, "Con adjunto no soportado", files=files)

    assert response.status_code == 400


def test_sliding_window_never_exceeds_max_turns(client, monkeypatch):
    monkeypatch.setattr(
        sessions_module,
        "get_settings",
        lambda: SimpleNamespace(session_max_turns=3),
    )
    session_id = _create_session(client)

    captured = []
    with patch("app.routers.sessions.generate_estimation_messages") as mock_llm:
        mock_llm.side_effect = _fake_llm
        for index in range(5):
            response = _estimate(client, session_id, f"Turno numero {index}")
            assert response.status_code == 200, response.text
        captured = list(mock_llm.call_args_list)

    # En el ultimo turno, el historial conservado son 3 turnos (6 mensajes)
    # mas el system prompt y el nuevo mensaje de usuario.
    last_messages = captured[-1].args[0]
    assistant_messages = [m for m in last_messages if m["role"] == "assistant"]
    assert len(assistant_messages) == 3
    assert len(last_messages) == 1 + 3 * 2 + 1
