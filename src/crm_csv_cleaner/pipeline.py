"""Pipeline: leer -> mapear -> normalizar -> validar -> deduplicar -> fusionar -> ordenar.

Reglas de fusión:
- Gana el registro más reciente (según `recency_field`); los registros sin fecha cuentan como
  los más antiguos. Empate: gana el último leído.
- Los campos vacíos del ganador se rellenan con el siguiente registro más reciente que tenga
  valor. Nunca se sobrescribe un valor existente.
- Los archivos se leen siempre en orden canónico (por nombre, con `sort_key`), así que el
  resultado no depende del orden en que se pasen.
"""

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from crm_csv_cleaner.config import CONTACT_FIELDS, NAME_FIELDS, Config
from crm_csv_cleaner.dedupe import group_by_keys
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
from crm_csv_cleaner.readers import read_table
from crm_csv_cleaner.report import DoubtfulMerge, FileInfo, Report, RowIssue, mask_contact

SOURCE_FILES = "source_files"
COUNT = "apariciones"
LABELS = {"telefono": "teléfono", "email": "email"}


@dataclass
class Record:
    values: dict[str, str]
    source: str
    row: int
    order: int = -1  # posición global en el orden de lectura canónico


@dataclass
class Result:
    columns: list[str]
    rows: list[dict[str, str]]
    report: Report


def canonical_order(paths: Iterable[Path]) -> list[Path]:
    return sorted((Path(p) for p in paths), key=lambda p: sort_key(p.name, str(p)))


def run(paths: Iterable[Path], config: Config) -> Result:
    report = Report()
    records: list[Record] = []
    for path in canonical_order(paths):
        table = read_table(path)
        mapping, ignored, notes = config.column_map(path.name, table.headers)
        report.files.append(
            FileInfo(path.name, len(table.rows), table.encoding, table.delimiter, ignored)
        )
        report.notes += [f"{path.name}: {n}" for n in notes]
        for i, raw in enumerate(table.rows):
            report.rows_read += 1
            record = _normalize_row(raw, mapping, config, path.name, i + 2, report)
            if record is not None:
                record.order = len(records)
                records.append(record)

    groups = group_by_keys([_keys(r, config) for r in records])
    merged_rows = []
    for group in groups:
        members = [records[i] for i in group]
        merged = _merge(members, config.recency_field)
        if doubtful := _doubtful(members, config):
            report.doubtful_merges.append(doubtful)
        merged[SOURCE_FILES] = "|".join(sorted({m.source for m in members}, key=sort_key))
        merged[COUNT] = str(len(members))
        merged_rows.append(merged)

    merged_rows.sort(
        key=lambda r: sort_key(r.get("apellidos", ""), r.get("nombre", ""), r.get("email", ""))
    )
    columns = [*config.output_columns.values(), SOURCE_FILES, COUNT]
    rows = [
        {
            **{header: m.get(fld, "") for fld, header in config.output_columns.items()},
            SOURCE_FILES: m[SOURCE_FILES],
            COUNT: m[COUNT],
        }
        for m in merged_rows
    ]
    report.duplicates = len(records) - len(groups)
    report.output_rows = len(rows)
    return Result(columns=columns, rows=rows, report=report)


def write_output(result: Result, path: Path) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=result.columns)
        writer.writeheader()
        writer.writerows(result.rows)


# --- Pasos internos --------------------------------------------------------------------------


def _normalize_row(
    raw: dict[str, str],
    mapping: dict[str, str],
    config: Config,
    source: str,
    row: int,
    report: Report,
) -> Record | None:
    if all(is_blank(v) for v in raw.values()):
        report.discarded.append(RowIssue(source, row, "fila vacía"))
        return None

    values: dict[str, str] = {}
    issues: list[RowIssue] = []
    for header, fld in mapping.items():
        value = raw.get(header, "")
        if is_blank(value):
            values[fld] = ""
            continue
        value = str(value).strip()
        normalized = _normalize_value(fld, value, config)
        if normalized is None:
            reason = f"{LABELS[fld]} inválido" if fld in LABELS else "fecha inválida"
            issues.append(RowIssue(source, row, reason, fld, value))
            normalized = ""
        values[fld] = normalized

    if values.get("nombre_completo"):
        first, last = split_full_name(values["nombre_completo"])
        values["nombre"] = values.get("nombre") or first
        values["apellidos"] = values.get("apellidos") or last

    if not any(values.get(f) for f in CONTACT_FIELDS):
        invalid = [i for i in issues if i.field in CONTACT_FIELDS]
        invalid_fields = {i.field for i in invalid}
        if not invalid:
            reason = "sin " + " ni ".join(LABELS[f] for f in CONTACT_FIELDS)
        else:
            missing = [f"sin {LABELS[f]}" for f in CONTACT_FIELDS if f not in invalid_fields]
            reason = " y ".join([i.reason for i in invalid] + missing)
        shown = invalid[0] if invalid else RowIssue(source, row, "")
        report.discarded.append(RowIssue(source, row, reason, shown.field, shown.value))
        return None

    report.warnings += issues
    return Record(values=values, source=source, row=row)


def _normalize_value(fld: str, value: str, config: Config) -> str | None:
    if fld == "telefono":
        return normalize_phone(value, config.default_region)
    if fld == "email":
        return normalize_email(value)
    if fld in config.date_fields:
        return parse_date(value, config.dayfirst)
    if fld in NAME_FIELDS:
        return normalize_name(value)
    return " ".join(value.split())


def _keys(record: Record, config: Config) -> set[tuple[str, str]]:
    return {(k, record.values[k]) for k in config.dedupe_keys if record.values.get(k)}


def _merge(members: list[Record], recency_field: str) -> dict[str, str]:
    # "" (sin fecha) < cualquier fecha ISO; a igual fecha, gana el último leído (mayor order).
    newest_first = sorted(members, key=lambda r: (r.values.get(recency_field, ""), r.order))[::-1]
    fields = dict.fromkeys(f for r in members for f in r.values)
    return {f: next((r.values[f] for r in newest_first if r.values.get(f)), "") for f in fields}


def _doubtful(members: list[Record], config: Config) -> DoubtfulMerge | None:
    """Fusión dudosa: dos registros del grupo sin ningún nombre ni apellido en común."""
    named = [(m, t) for m in members if (t := _name_tokens(m))]
    if all(a & b for (_, a), (_, b) in combinations(named, 2)):
        return None
    names = dict.fromkeys(
        " ".join(x for x in (m.values.get("nombre", ""), m.values.get("apellidos", "")) if x)
        for m, _ in named
    )
    shared = sorted({mask_contact(v) for m in members for _, v in _keys(m, config)})
    files = sorted({f"{m.source}:{m.row}" for m in members}, key=sort_key)
    return DoubtfulMerge(names=list(names), files=files, keys=shared)


def _name_tokens(record: Record) -> set[str]:
    full = f"{record.values.get('nombre', '')} {record.values.get('apellidos', '')}"
    return set(fold(full).split())
