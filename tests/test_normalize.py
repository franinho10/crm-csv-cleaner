import math
from datetime import date, datetime

import pytest

from crm_csv_cleaner.normalize import (
    fold,
    is_blank,
    normalize_email,
    normalize_name,
    normalize_phone,
    parse_date,
    sort_key,
    split_full_name,
)

# --- Teléfono --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "600 000 123",
        "600000123",
        "+34 600 00 01 23",
        "+34600000123",
        "0034600000123",
        "(+34) 600-000-123",
        "600.000.123",
        " 600000123 ",
        600000123,
        600000123.0,
        "600000123.0",
    ],
)
def test_phone_variants_to_e164(raw):
    assert normalize_phone(raw) == "+34600000123"


@pytest.mark.parametrize("raw", ["12345", "abc", "600 000", "+34 123 456 789", "", None, math.nan])
def test_phone_invalid_or_blank(raw):
    assert normalize_phone(raw) is None


def test_phone_keeps_foreign_numbers_with_prefix():
    assert normalize_phone("+44 20 7946 0000") == "+442079460000"


def test_phone_region_is_configurable():
    assert normalize_phone("020 7946 0000", region="GB") == "+442079460000"


# --- Email -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (" LUCIA.F@Example.COM ", "lucia.f@example.com"),
        ("Ainhoa.marin19@example.com", "ainhoa.marin19@example.com"),
        ("mailto:ana@example.org", "ana@example.org"),
        ("a+tag@sub.example.org", "a+tag@sub.example.org"),
    ],
)
def test_email_normalized(raw, expected):
    assert normalize_email(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "carmen.nieto.example.com",
        "ana@",
        "@example.com",
        "ana@example",
        "ana @example.com",
        "ana@@example.com",
        "ana..b@example.com",
        "",
        None,
    ],
)
def test_email_invalid_or_blank(raw):
    assert normalize_email(raw) is None


# --- Fecha -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "03/04/2025",
        "3/4/2025",
        "03-04-2025",
        "3-4-2025",
        "03.04.2025",
        "03/04/25",
        "2025-04-03",
        "2025/04/03",
        "2025-04-03 00:00:00",
        "2025-04-03T10:30:00",
        "20250403",
        "3-abr-25",
        "3 abr 2025",
        "3 de abril de 2025",
        "3-Apr-2025",
        "3 ABR. 2025",
        datetime(2025, 4, 3, 18, 45),
        date(2025, 4, 3),
        45750,
        45750.0,
        "45750",
    ],
)
def test_date_variants_to_iso(raw):
    assert parse_date(raw) == "2025-04-03"


def test_date_monthfirst():
    assert parse_date("04/03/2025", dayfirst=False) == "2025-04-03"


def test_iso_ignores_dayfirst():
    assert parse_date("2025-04-03", dayfirst=False) == "2025-04-03"


@pytest.mark.parametrize(
    "raw", ["2025-02-30", "31/02/2025", "13/13/2025", "ayer", "3-xyz-25", "", None, 12, math.nan]
)
def test_date_invalid_or_blank(raw):
    assert parse_date(raw) is None


def test_two_digit_year_pivot():
    assert parse_date("01/01/69") == "2069-01-01"
    assert parse_date("01/01/70") == "1970-01-01"


# --- Nombre ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("  lucía   FERRÁN ", "Lucía Ferrán"),
        ("AINHOA MARÍN SERRANO", "Ainhoa Marín Serrano"),
        ("íñigo", "Íñigo"),
        ("maría DE LA cruz", "María de la Cruz"),
        ("ana-maría o'neill", "Ana-María O'Neill"),
        ("McDonald", "McDonald"),
        ("De la Fuente", "De la Fuente"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        (" Rubén Ortega Castaño ", ("Rubén", "Ortega Castaño")),
        ("TOMÁS", ("Tomás", "")),
        ("", ("", "")),
    ],
)
def test_split_full_name(raw, expected):
    assert split_full_name(raw) == expected


# --- Utilidades ------------------------------------------------------------------------------


def test_fold_removes_accents_and_case():
    assert fold("Ñúñez ÁLVAREZ") == "nunez alvarez"


def test_sort_key_is_accent_and_case_insensitive():
    names = ["Ortega", "Óscar", "ibáñez", "Ibarra", "Álvarez", "alonso"]
    assert sorted(names, key=sort_key) == [
        "alonso",
        "Álvarez",
        "ibáñez",
        "Ibarra",
        "Ortega",
        "Óscar",
    ]


def test_sort_key_is_total_order():
    # Igual tras plegar -> desempata por el original, así el orden nunca depende de la entrada.
    assert sorted(["Pena", "Peña"], key=sort_key) == sorted(["Peña", "Pena"], key=sort_key)


@pytest.mark.parametrize("value", [None, math.nan, "", "  ", "nan", "NaT"])
def test_is_blank(value):
    assert is_blank(value)


@pytest.mark.parametrize("value", ["0", 0, "a"])
def test_is_not_blank(value):
    assert not is_blank(value)
