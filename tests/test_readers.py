from datetime import datetime

import pytest
from openpyxl import Workbook

from crm_csv_cleaner.normalize import normalize_phone, parse_date
from crm_csv_cleaner.readers import ReaderError, decode, detect_delimiter, read_table


def test_semicolon_utf8(tmp_path):
    path = tmp_path / "a.csv"
    path.write_text("Nombre;Móvil\nÍñigo;600000001\n", encoding="utf-8")
    table = read_table(path)
    assert (table.encoding, table.delimiter) == ("utf-8", ";")
    assert table.rows == [{"Nombre": "Íñigo", "Móvil": "600000001"}]


def test_comma_cp1252_fallback(tmp_path):
    path = tmp_path / "b.csv"
    path.write_bytes("nombre,apellidos\nNoelia,Muñoz Ibáñez\n".encode("cp1252"))
    table = read_table(path)
    assert (table.encoding, table.delimiter) == ("cp1252", ",")
    assert table.rows[0]["apellidos"] == "Muñoz Ibáñez"


def test_utf8_bom_is_stripped(tmp_path):
    path = tmp_path / "c.csv"
    path.write_bytes("﻿email;tlf\nana@example.com;600000002\n".encode())
    assert read_table(path).headers == ["email", "tlf"]


def test_everything_is_text_and_blanks_are_empty(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text("id,tlf,notas\n007,600000003,\n", encoding="utf-8")
    assert read_table(path).rows == [{"id": "007", "tlf": "600000003", "notas": ""}]


def test_excel_numeric_phones_and_dates(tmp_path):
    path = tmp_path / "e.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Tlf", "Fecha", "Notas"])
    ws.append([600000004, datetime(2025, 3, 9), None])
    ws.append([600000005.0, "09.03.2025", "x"])
    wb.save(path)
    rows = read_table(path).rows
    assert all(isinstance(v, str) for r in rows for v in r.values())
    assert [normalize_phone(r["Tlf"]) for r in rows] == ["+34600000004", "+34600000005"]
    assert [parse_date(r["Fecha"]) for r in rows] == ["2025-03-09", "2025-03-09"]
    assert rows[0]["Notas"] in {"", "None", "nan"}  # vacío para is_blank()


@pytest.mark.parametrize(
    "header, expected",
    [("a;b;c", ";"), ("a,b,c", ","), ("a\tb", "\t"), ("solo", ","), ("a;b,c", ",")],
)
def test_detect_delimiter(header, expected):
    assert detect_delimiter(header + "\n1;2\n") == expected


def test_decode_never_fails():
    assert decode(b"\x81\x8d")[1] == "latin-1"


@pytest.mark.parametrize("name", ["x.xls", "x.json", "x"])
def test_unsupported_formats(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"")
    with pytest.raises(ReaderError):
        read_table(path)
