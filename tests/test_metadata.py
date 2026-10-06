"""
Tests de la extraccion heuristica del `project_metadata`. No llaman a ningun
LLM: la heuristica es determinista y local.
"""

from app.metadata import extract_metadata


def test_detect_project_name():
    meta = extract_metadata("El proyecto se llama Atlas y estara listo en junio.")
    assert meta.project_name == "Atlas"


def test_detect_team_size_variants():
    assert extract_metadata("Trabajaremos con un equipo de 5 personas").assumed_team_size == 5
    assert extract_metadata("Somos 3 developers").assumed_team_size == 3


def test_detect_technologies():
    meta = extract_metadata("Usaremos React Native, PostgreSQL y Docker en AWS")

    assert "React Native" in meta.mentioned_technologies
    assert "PostgreSQL" in meta.mentioned_technologies
    assert "Docker" in meta.mentioned_technologies
    assert "AWS" in meta.mentioned_technologies
    # "React Native" consume el match: no debe contarse tambien "React".
    assert "React" not in meta.mentioned_technologies


def test_detect_scope():
    meta = extract_metadata("El alcance incluye login y pagos")

    assert meta.agreed_scope is not None
    assert "login" in meta.agreed_scope


def test_uses_response_text_too():
    meta = extract_metadata("sin datos utiles", "Asumo un equipo de 4 personas")
    assert meta.assumed_team_size == 4


def test_extraction_merges_without_losing_previous_facts():
    first = extract_metadata("El proyecto se llama Atlas. Usamos PostgreSQL.")
    second = extract_metadata("El alcance incluye pagos con Stripe", "", first)

    assert second.project_name == "Atlas"
    assert "PostgreSQL" in second.mentioned_technologies
    assert "Stripe" in second.mentioned_technologies


def test_no_facts_yields_empty_metadata():
    assert extract_metadata("hola que tal").is_empty()
