"""Informe del proceso. Teléfonos y emails siempre enmascarados al mostrarlos."""

from dataclasses import asdict, dataclass, field

MASK = "•"
CONTACT_FIELDS = {"telefono", "email"}
MAX_LISTED = 20


def mask_contact(value: str) -> str:
    """'+34600000123' -> '+34•••••••23'; 'lucia@example.com' -> 'l***@example.com'."""
    value = value.strip()
    if not value:
        return ""
    if "@" in value:
        local, _, domain = value.rpartition("@")
        return f"{local[:1]}***@{domain}"
    digit_positions = [i for i, c in enumerate(value) if c.isdigit()]
    if len(digit_positions) < 3:
        return f"{value[:1]}***"
    keep = set(digit_positions[-2:])
    if value.startswith("+"):
        keep |= set(digit_positions[:2])  # prefijo de país
    hidden = set(digit_positions) - keep
    return "".join(MASK if i in hidden else c for i, c in enumerate(value))


@dataclass
class FileInfo:
    name: str
    rows: int
    encoding: str | None
    delimiter: str | None
    ignored_columns: list[str]


@dataclass
class RowIssue:
    file: str
    row: int  # fila de la hoja (la cabecera es la 1)
    reason: str
    field: str = ""
    value: str = ""

    def shown_value(self) -> str:
        return mask_contact(self.value) if self.field in CONTACT_FIELDS else self.value


@dataclass
class DoubtfulMerge:
    names: list[str]
    files: list[str]
    keys: list[str]  # claves compartidas, ya enmascaradas


@dataclass
class Report:
    files: list[FileInfo] = field(default_factory=list)
    rows_read: int = 0
    duplicates: int = 0
    output_rows: int = 0
    discarded: list[RowIssue] = field(default_factory=list)
    warnings: list[RowIssue] = field(default_factory=list)
    doubtful_merges: list[DoubtfulMerge] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Versión serializable (para --report en JSON), con contactos enmascarados."""
        data = asdict(self)
        for key in ("discarded", "warnings"):
            for issue, raw in zip(data[key], getattr(self, key), strict=True):
                issue["value"] = raw.shown_value()
        return data

    def format_text(self) -> str:
        lines = ["Archivos:"]
        for f in self.files:
            meta = ", ".join(x for x in (f.encoding, _delimiter_name(f.delimiter)) if x) or "Excel"
            lines.append(f"  {f.name}: {f.rows} filas ({meta})")
            if f.ignored_columns:
                lines.append(f"    columnas ignoradas: {', '.join(f.ignored_columns)}")
        lines += [f"  nota: {n}" for n in self.notes]
        lines += [
            "",
            f"Filas leídas:          {self.rows_read}",
            f"Duplicados fusionados: {self.duplicates}",
            f"Filas descartadas:     {len(self.discarded)}",
            f"Avisos:                {len(self.warnings)}",
            f"Fusiones dudosas:      {len(self.doubtful_merges)}",
            f"Filas en la salida:    {self.output_rows}",
        ]
        lines += _issue_section("Descartadas", self.discarded)
        lines += _issue_section("Avisos (la fila se conserva con la celda vacía)", self.warnings)
        if self.doubtful_merges:
            lines += ["", "Fusiones dudosas (sin ningún nombre ni apellido en común; revísalas):"]
            for m in self.doubtful_merges[:MAX_LISTED]:
                lines.append(
                    f"  {' / '.join(m.names)}  [{', '.join(m.keys)}]  en {', '.join(m.files)}"
                )
            lines += _more(self.doubtful_merges)
        return "\n".join(lines)


def _issue_section(title: str, issues: list[RowIssue]) -> list[str]:
    if not issues:
        return []
    lines = ["", f"{title}:"]
    for issue in issues[:MAX_LISTED]:
        shown = issue.shown_value()
        suffix = f" ({shown})" if shown else ""
        lines.append(f"  {issue.file} fila {issue.row}: {issue.reason}{suffix}")
    return lines + _more(issues)


def _more(items: list) -> list[str]:
    extra = len(items) - MAX_LISTED
    return [f"  … y {extra} más"] if extra > 0 else []


def _delimiter_name(delimiter: str | None) -> str | None:
    names = {";": "separador ;", ",": "separador ,", "\t": "separador tabulador"}
    return names.get(delimiter) if delimiter else None
