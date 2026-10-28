"""Lectura de CSV y Excel. Todo se lee como texto para no perder ceros ni formatos."""

import io
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

CSV_SUFFIXES = {".csv", ".txt", ".tsv"}
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}
DELIMITERS = (";", ",", "\t")


class ReaderError(ValueError):
    pass


@dataclass
class Table:
    path: Path
    headers: list[str]
    rows: list[dict[str, str]]
    encoding: str | None = None  # None en Excel
    delimiter: str | None = None


def read_table(path: Path) -> Table:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in CSV_SUFFIXES:
        return _read_csv(path)
    if suffix in EXCEL_SUFFIXES:
        return _read_excel(path)
    if suffix == ".xls":
        raise ReaderError(f"{path.name}: formato .xls no soportado; guárdalo como .xlsx o .csv")
    raise ReaderError(f"{path.name}: extensión no soportada ({suffix or 'sin extensión'})")


def decode(raw: bytes) -> tuple[str, str]:
    """UTF-8 (con o sin BOM) y, si falla, cp1252 (lo habitual al exportar desde Excel en España)."""
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp1252"), "cp1252"
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "latin-1"  # nunca falla: último recurso


def detect_delimiter(text: str) -> str:
    """Elige el separador más frecuente en la cabecera; ',' si no hay ninguno o empatan."""
    header = next((line for line in text.splitlines() if line.strip()), "")
    counts = {d: header.count(d) for d in DELIMITERS}
    best = max(DELIMITERS, key=lambda d: counts[d])
    if counts[best] == 0 or list(counts.values()).count(counts[best]) > 1:
        return ","
    return best


def _read_csv(path: Path) -> Table:
    text, encoding = decode(path.read_bytes())
    delimiter = detect_delimiter(text)
    df = pd.read_csv(
        io.StringIO(text), sep=delimiter, dtype=str, na_filter=False, skip_blank_lines=True
    )
    return _to_table(path, df, encoding=encoding, delimiter=delimiter)


def _read_excel(path: Path) -> Table:
    # dtype=str: un teléfono guardado como número llega como "600000123" (o "600000123.0" si
    # Excel lo guardó como decimal); normalize_phone acepta ambos.
    df = pd.read_excel(path, sheet_name=0, dtype=str, na_filter=False, engine="openpyxl")
    return _to_table(path, df)


def _to_table(
    path: Path, df: pd.DataFrame, encoding: str | None = None, delimiter: str | None = None
) -> Table:
    df.columns = [str(c).strip() for c in df.columns]
    rows = [
        {h: "" if v is None else str(v) for h, v in row.items()} for row in df.to_dict("records")
    ]
    return Table(path, list(df.columns), rows, encoding, delimiter)
