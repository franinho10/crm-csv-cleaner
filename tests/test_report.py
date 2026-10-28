import pytest

from crm_csv_cleaner.report import Report, RowIssue, mask_contact


@pytest.mark.parametrize(
    "value, expected",
    [
        ("+34600000123", "+34•••••••23"),
        ("600 000 123", "••• ••• •23"),
        ("12345", "•••45"),
        ("lucia.f@example.com", "l***@example.com"),
        ("carmen.nieto.example.com", "c***"),
        ("", ""),
    ],
)
def test_mask_contact(value, expected):
    assert mask_contact(value) == expected


def test_contacts_masked_in_text_and_dict_but_dates_shown():
    report = Report(
        warnings=[
            RowIssue("a.csv", 2, "email inválido", "email", "ana@example"),
            RowIssue("a.csv", 3, "fecha inválida", "fecha", "2025-02-30"),
        ],
        discarded=[RowIssue("a.csv", 4, "teléfono inválido y sin email", "telefono", "6000001")],
    )
    text = report.format_text()
    assert "ana@example" not in text and "6000001" not in text
    assert "a***@example" in text and "2025-02-30" in text
    data = report.to_dict()
    assert data["warnings"][0]["value"] == "a***@example"
    assert data["discarded"][0]["value"] == "•••••01"


def test_long_lists_are_truncated():
    report = Report(
        warnings=[RowIssue("a.csv", i, "fecha inválida", "fecha", "x") for i in range(25)]
    )
    assert "… y 5 más" in report.format_text()
