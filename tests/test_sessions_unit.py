"""
Tests unitarios del estado de sesion (historial con ventana deslizante y
memoria del proyecto). No llaman a ningun LLM ni hacen I/O de red.
"""

import pytest

from app.schemas import ProjectMetadata
from app.sessions import ConversationHistory, Session, SessionStore


def test_window_discards_oldest_turns():
    history = ConversationHistory(max_turns=3)
    for i in range(5):
        history.add_turn(f"u{i}", f"a{i}")

    assert len(history) == 3
    assert [turn.user for turn in history.turns] == ["u2", "u3", "u4"]


def test_messages_list_starts_with_system_and_alternates_roles():
    history = ConversationHistory(max_turns=2)
    for i in range(4):
        history.add_turn(f"u{i}", f"a{i}")

    messages = history.to_messages_list("SYSTEM")

    assert messages[0] == {"role": "system", "content": "SYSTEM"}
    assert [m["role"] for m in messages[1:]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    # El turno mas antiguo conservado es u2 (se descartaron u0 y u1).
    assert messages[1]["content"] == "u2"


def test_history_requires_positive_max_turns():
    with pytest.raises(ValueError):
        ConversationHistory(max_turns=0)


def test_project_metadata_starts_empty():
    assert ProjectMetadata().is_empty()


def test_project_metadata_is_not_empty_with_any_fact():
    assert not ProjectMetadata(project_name="Atlas").is_empty()
    assert not ProjectMetadata(assumed_team_size=4).is_empty()
    assert not ProjectMetadata(mentioned_technologies=["Python"]).is_empty()
    assert not ProjectMetadata(agreed_scope="login y pagos").is_empty()


def test_session_renders_system_prompt_from_current_metadata():
    session = Session(max_turns=2)
    session.metadata.project_name = "Atlas"
    session.history.add_turn("hola", "respuesta")

    messages = session.to_messages_list()

    assert messages[0]["role"] == "system"
    assert "nombre_del_proyecto: Atlas" in messages[0]["content"]
    assert [m["role"] for m in messages[1:]] == ["user", "assistant"]


def test_session_ids_are_unique():
    assert Session(max_turns=1).session_id != Session(max_turns=1).session_id


def test_session_store_create_and_get():
    store = SessionStore(max_turns=2)
    session = store.create()

    assert store.get(session.session_id) is session
    assert store.get("no-existe") is None
    assert len(store) == 1

    store.clear()
    assert store.get(session.session_id) is None
