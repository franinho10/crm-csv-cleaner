import csv
import json
from pathlib import Path

import pytest

from crm_csv_cleaner.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
INPUT = str(EXAMPLES / "input")
CONFIG = str(EXAMPLES / "mapping.yaml")
EXPECTED = EXAMPLES / "output" / "clientes_limpios.csv"


def expected_contacts() -> list[str]:
    with EXPECTED.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [v for r in rows for v in (r["Phone"], r["Phone"][3:], r["Email"]) if v]


def test_full_run_writes_all_outputs(tmp_path, capsys):
    out, rej, rep = tmp_path / "out" / "limpio.csv", tmp_path / "rej.csv", tmp_path / "rep.json"
    code = main([INPUT, "-c", CONFIG, "-o", str(out), "--rejects", str(rej), "--report", str(rep)])
    assert code == 0
    assert out.read_bytes() == EXPECTED.read_bytes()
    stdout = capsys.readouterr().out
    assert "Filas leídas:          68" in stdout
    assert "sin enmascarar" in stdout
    assert not any(c in stdout for c in expected_contacts())


def test_report_json_is_masked(tmp_path):
    rep = tmp_path / "rep.json"
    assert main([INPUT, "-c", CONFIG, "-o", str(tmp_path / "o.csv"), "--report", str(rep)]) == 0
    text = rep.read_text(encoding="utf-8")
    data = json.loads(text)
    assert (data["rows_read"], data["duplicates"], data["output_rows"]) == (68, 21, 44)
    assert len(data["doubtful_merges"]) == 1
    assert not any(c in text for c in expected_contacts() + ["12345"])
    assert "+34•••••••" in text and "•••45" in text
    assert all("raw" not in issue for issue in data["discarded"])


def test_rejects_keep_original_data(tmp_path):
    rej = tmp_path / "rej.csv"
    assert main([INPUT, "-c", CONFIG, "-o", str(tmp_path / "o.csv"), "--rejects", str(rej)]) == 0
    with rej.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["reason"] for r in rows] == [
        "teléfono inválido y sin email",
        "fila vacía",
        "sin teléfono ni email",
    ]
    assert rows[0]["phone"] == "12345"  # sin enmascarar, para revisión
    assert rows[2]["Nombre completo"] == "Rubén Soler Vega"


def test_dry_run_creates_nothing(tmp_path, capsys):
    target = tmp_path / "sub" / "dir"
    code = main(
        [
            INPUT,
            "-c",
            CONFIG,
            "--dry-run",
            "-o",
            str(target / "o.csv"),
            "--rejects",
            str(target / "r.csv"),
            "--report",
            str(target / "r.json"),
        ]
    )
    assert code == 0
    assert list(tmp_path.iterdir()) == []
    assert "no se ha escrito ningún archivo" in capsys.readouterr().out


def test_dry_run_without_output(tmp_path, capsys):
    assert main([INPUT, "--dry-run"]) == 0
    assert "Filas leídas" in capsys.readouterr().out


def test_does_not_overwrite_without_force(tmp_path, capsys):
    out = tmp_path / "o.csv"
    out.write_text("no tocar", encoding="utf-8")
    assert main([INPUT, "-c", CONFIG, "-o", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "no tocar"
    assert "--force" in capsys.readouterr().err
    assert main([INPUT, "-c", CONFIG, "-o", str(out), "--force"]) == 0
    assert out.read_bytes() == EXPECTED.read_bytes()


def test_existing_report_also_protected(tmp_path):
    rep = tmp_path / "rep.json"
    rep.write_text("{}", encoding="utf-8")
    assert main([INPUT, "-o", str(tmp_path / "o.csv"), "--report", str(rep)]) == 1
    assert not (tmp_path / "o.csv").exists()  # falla antes de escribir nada


def corrupt_xlsx(tmp_path):
    bad = tmp_path / "roto.xlsx"
    bad.write_bytes(b"esto no es un xlsx")
    return [str(bad), "-o", str(tmp_path / "o.csv")]


def invalid_yaml(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text("fields: [sin cerrar", encoding="utf-8")
    return [INPUT, "-c", str(cfg), "-o", str(tmp_path / "o.csv")]


@pytest.mark.parametrize(
    "build_args, code, message",
    [
        (lambda t: [], 2, "al menos un archivo"),
        (lambda t: [INPUT], 2, "-o"),
        (lambda t: [str(t / "no.csv"), "-o", str(t / "o.csv")], 1, "no existe"),
        (lambda t: [INPUT, "-c", str(t / "no.yaml"), "-o", str(t / "o.csv")], 1, "no existe"),
        (invalid_yaml, 1, "YAML inválido"),
        (corrupt_xlsx, 1, "no se pudo leer"),
        (lambda t: [str(t), "-o", str(t / "o.csv")], 1, "no contiene archivos"),
        (lambda t: [INPUT, "-o", str(t / "a.csv"), "--report", str(t / "a.csv")], 2, "distintos"),
        (lambda t: [INPUT, "--opcion-rara"], 2, "--opcion-rara"),
    ],
)
def test_errors_are_clean(tmp_path, capsys, build_args, code, message):
    assert main(build_args(tmp_path)) == code
    err = capsys.readouterr().err
    assert message in err
    assert "Traceback" not in err


def test_help_warns_about_rejects(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "SIN enmascarar" in help_text
