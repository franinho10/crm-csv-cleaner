import csv
import random
from itertools import permutations
from pathlib import Path

import pytest

from crm_csv_cleaner.config import config_from_dict, load_config
from crm_csv_cleaner.pipeline import run, write_output

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
INPUTS = sorted((EXAMPLES / "input").iterdir())
EXPECTED = EXAMPLES / "output" / "clientes_limpios.csv"
HEADER = "nombre;apellidos;telefono;email;fecha"


@pytest.fixture(scope="module")
def example_result():
    return run(INPUTS, load_config(EXAMPLES / "mapping.yaml"))


def write(path: Path, *lines: str) -> Path:
    path.write_text("\n".join([HEADER, *lines]) + "\n", encoding="utf-8")
    return path


def by_phone(result):
    return {r["Phone"]: r for r in result.rows}


# --- End-to-end contra examples/ -------------------------------------------------------------


def test_end_to_end_matches_expected_output(example_result):
    with EXPECTED.open(newline="", encoding="utf-8") as f:
        expected = list(csv.DictReader(f))
    assert example_result.columns == list(expected[0])
    assert example_result.rows == expected


def test_written_file_is_byte_identical(example_result, tmp_path):
    write_output(example_result, tmp_path / "out.csv")
    assert (tmp_path / "out.csv").read_bytes() == EXPECTED.read_bytes()


def test_end_to_end_report(example_result):
    r = example_result.report
    assert (r.rows_read, r.duplicates, r.output_rows) == (68, 21, 44)
    assert sorted(i.reason for i in r.discarded) == [
        "fila vacía",
        "sin teléfono ni email",
        "teléfono inválido y sin email",
    ]
    assert sorted(i.reason for i in r.warnings) == ["email inválido", "fecha inválida"]
    assert [m.names for m in r.doubtful_merges] == [["Sofía Robles Vega", "Héctor Gallardo Rey"]]


def test_doubtful_merge_keeps_newest_record(example_result):
    row = next(r for r in example_result.rows if r["First Name"] == "Héctor")
    assert (row["Email"], row["Date"], row["apariciones"]) == (
        "hector.g@example.org",
        "2025-08-01",
        "2",
    )
    assert not any(
        r["First Name"] == "Sofía" and r["Last Name"] == "Robles Vega" for r in example_result.rows
    )


def test_output_independent_of_file_order(example_result):
    config = load_config(EXAMPLES / "mapping.yaml")
    for order in permutations(INPUTS):
        result = run(list(order), config)
        assert result.rows == example_result.rows
        assert result.report == example_result.report
    shuffled = INPUTS[:]
    random.Random(1).shuffle(shuffled)
    assert run(shuffled, config).rows == example_result.rows


def test_console_report_never_shows_full_contacts(example_result):
    text = example_result.report.format_text()
    for row in example_result.rows:
        for value in (row["Phone"], row["Email"], row["Phone"].removeprefix("+34")):
            assert not value or value not in text


# --- Reglas de fusión ------------------------------------------------------------------------


def test_newest_wins_and_blanks_are_filled_without_overwriting(tmp_path):
    path = write(
        tmp_path / "a.csv",
        "Ana;Rey;600000001;viejo@example.com;01/01/2025",
        "Anabel;Rey;600000001;;01/06/2025",
        ";;600000001;medio@example.com;01/03/2025",
        "Ana;Rey Soler;600000002;nuevo@example.com;01/06/2025",
        "Ana;Rey;600000002;viejo2@example.com;01/01/2025",
    )
    rows = by_phone(run([path], config_from_dict({})))
    assert rows["+34600000001"]["First Name"] == "Anabel"  # el más reciente
    assert rows["+34600000001"]["Email"] == "medio@example.com"  # vacío -> siguiente más reciente
    assert rows["+34600000001"]["Date"] == "2025-06-01"
    assert rows["+34600000001"]["apariciones"] == "3"
    assert rows["+34600000002"]["Email"] == "nuevo@example.com"  # nunca se sobrescribe
    assert rows["+34600000002"]["Last Name"] == "Rey Soler"


def test_tie_last_read_wins_in_canonical_order(tmp_path):
    a = write(tmp_path / "a.csv", "Lucía;Ferrán;600000003;;05/05/2025")
    b = write(tmp_path / "b.csv", "Lucía;Ferrán Peña;600000003;;05/05/2025")
    for paths in ([a, b], [b, a]):
        row = run(paths, config_from_dict({})).rows[0]
        assert row["Last Name"] == "Ferrán Peña"  # b.csv es el último en orden canónico
        assert row["source_files"] == "a.csv|b.csv"


def test_undated_records_count_as_oldest(tmp_path):
    path = write(
        tmp_path / "a.csv", "Marta;Vega;600000004;;", "Marta;Vega Rey;600000004;;02/02/2025"
    )
    assert run([path], config_from_dict({})).rows[0]["Last Name"] == "Vega Rey"


def test_transitive_merge_across_files(tmp_path):
    a = write(tmp_path / "a.csv", "Iker;Soler;600000005;;01/01/2025")
    b = write(tmp_path / "b.csv", "Iker;Soler;600000005;iker@example.com;02/01/2025")
    c = write(tmp_path / "c.csv", "Iker;Soler;;iker@example.com;03/01/2025")
    result = run([c, a, b], config_from_dict({}))
    assert len(result.rows) == 1
    assert result.rows[0]["apariciones"] == "3"
    assert result.rows[0]["Phone"] == "+34600000005"
    assert result.report.duplicates == 2


def test_dedupe_by_phone_only(tmp_path):
    path = write(
        tmp_path / "a.csv",
        "Paula;Nieto;600000006;p@example.com;",
        "Paula;Nieto;600000007;p@example.com;",
    )
    config = config_from_dict({"dedupe": {"keys": ["telefono"]}})
    assert len(run([path], config).rows) == 2


# --- Descartes, avisos y fusiones dudosas ----------------------------------------------------


def test_discard_reasons(tmp_path):
    path = write(
        tmp_path / "a.csv",
        ";;;;",
        "Rubén;Soler;;;01/01/2025",
        "Elena;Prieto;12345;;",
        "Óscar;Rivas;;oscar@;",
        "Nerea;Calvo;999;nerea.example.com;",
    )
    report = run([path], config_from_dict({})).report
    assert [i.reason for i in report.discarded] == [
        "fila vacía",
        "sin teléfono ni email",
        "teléfono inválido y sin email",
        "email inválido y sin teléfono",
        "teléfono inválido y email inválido",
    ]
    assert [i.row for i in report.discarded] == [2, 3, 4, 5, 6]
    assert report.warnings == []  # las filas descartadas no generan avisos extra


def test_warnings_for_kept_rows(tmp_path):
    path = write(tmp_path / "a.csv", "Carmen;Nieto;600000008;carmen@;30/02/2025")
    result = run([path], config_from_dict({}))
    assert [i.reason for i in result.report.warnings] == ["email inválido", "fecha inválida"]
    assert result.rows[0]["Email"] == "" and result.rows[0]["Date"] == ""


def test_doubtful_merge_reported(tmp_path):
    path = write(
        tmp_path / "a.csv",
        "Lucía;Ferrán;600000009;;01/01/2025",
        "Tomás;Rivas;600000009;;02/01/2025",
        "LUCIA;ferran;600000010;;01/01/2025",
        "Lucía;Ferrán Peña;600000010;;02/01/2025",
    )
    report = run([path], config_from_dict({})).report
    assert len(report.doubtful_merges) == 1
    merge = report.doubtful_merges[0]
    assert merge.names == ["Lucía Ferrán", "Tomás Rivas"]
    assert merge.keys == ["+34•••••••09"]
    assert "600000009" not in report.format_text()


def test_full_name_column_is_split(tmp_path):
    path = tmp_path / "a.csv"
    path.write_text("Nombre completo;Móvil\n  íñigo  MARÍN vega ;600000011\n", encoding="utf-8")
    row = run([path], config_from_dict({})).rows[0]
    assert (row["First Name"], row["Last Name"]) == ("Íñigo", "Marín Vega")
