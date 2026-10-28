from pathlib import Path

import pytest

from crm_csv_cleaner.config import ConfigError, config_from_dict, load_config

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_load_example_config():
    config = load_config(EXAMPLES / "mapping.yaml")
    assert config.default_region == "ES"
    assert config.dayfirst is True
    assert config.dedupe_keys == ("telefono", "email")
    assert list(config.output_columns.values()) == [
        "First Name",
        "Last Name",
        "Email",
        "Phone",
        "Date",
    ]


def test_empty_config_uses_defaults():
    config = config_from_dict({})
    assert config.recency_field == "fecha"
    assert "telefono" in config.fields


def test_column_map_ignores_accents_case_and_spaces():
    config = config_from_dict({})
    mapping, ignored, notes = config.column_map("x.csv", [" MÓVIL ", "Correo", "Notas", "Phone"])
    assert mapping == {" MÓVIL ": "telefono", "Correo": "email"}
    assert ignored == ["Notas"]
    assert notes and "Phone" in notes[0]  # segunda columna para el mismo campo


def test_source_override_wins():
    config = config_from_dict(
        {"sources": [{"file": "Raro.CSV", "columns": {"Col 3": "telefono", "Correo": "nombre"}}]}
    )
    mapping, _, _ = config.column_map("raro.csv", ["col 3", "Correo"])
    assert mapping == {"col 3": "telefono", "Correo": "nombre"}


@pytest.mark.parametrize(
    "data, message",
    [
        ([], "diccionario"),
        ({"otra": 1}, "claves desconocidas"),
        ({"default_region": "España"}, "default_region"),
        ({"date": {"dayfirst": "si"}}, "dayfirst"),
        ({"dedupe": {"keys": ["nombre"]}}, "dedupe.keys"),
        ({"dedupe": {"keys": []}}, "dedupe.keys"),
        ({"dedupe": {"recency_field": "alta"}}, "recency_field"),
        ({"fields": {"email": ["mail"], "telefono": ["mail"]}}, "mail"),
        ({"fields": {"email": "correo"}}, "telefono"),  # falta una clave de dedupe
        ({"output_columns": {"edad": "Age"}}, "output_columns"),
        ({"output_columns": {}}, "vacío"),
        ({"sources": [{"columns": {}}]}, "file"),
        ({"sources": [{"file": "a.csv", "columns": {"x": "edad"}}]}, "edad"),
    ],
)
def test_invalid_config(data, message):
    with pytest.raises(ConfigError, match=message):
        config_from_dict(data)


def test_invalid_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("fields: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML"):
        load_config(path)
