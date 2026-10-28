"""Carga y valida la configuración YAML del mapeo de columnas."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from crm_csv_cleaner.normalize import fold

CONTACT_FIELDS = ("telefono", "email")
NAME_FIELDS = ("nombre_completo", "nombre", "apellidos")
TOP_LEVEL_KEYS = {"default_region", "date", "dedupe", "fields", "output_columns", "sources"}

DEFAULT_FIELDS: dict[str, tuple[str, ...]] = {
    "nombre_completo": ("nombre completo", "full name"),
    "nombre": ("nombre", "first name"),
    "apellidos": ("apellidos", "last name"),
    "email": ("email", "e-mail", "correo", "correo electronico"),
    "telefono": ("telefono", "movil", "tlf", "phone"),
    "fecha": ("fecha", "fecha reserva", "date"),
}
DEFAULT_OUTPUT = {
    "nombre": "First Name",
    "apellidos": "Last Name",
    "email": "Email",
    "telefono": "Phone",
    "fecha": "Date",
}


class ConfigError(ValueError):
    pass


def header_key(text: object) -> str:
    """Forma comparable de una cabecera: sin tildes, minúsculas y espacios colapsados."""
    return " ".join(fold(str(text)).split())


@dataclass
class Config:
    default_region: str = "ES"
    dayfirst: bool = True
    dedupe_keys: tuple[str, ...] = CONTACT_FIELDS
    recency_field: str = "fecha"
    fields: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict(DEFAULT_FIELDS))
    output_columns: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_OUTPUT))
    # header_key(nombre de archivo) -> {header_key(cabecera): campo}
    sources: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def date_fields(self) -> set[str]:
        return {"fecha", self.recency_field}

    def column_map(
        self, file_name: str, headers: Sequence[str]
    ) -> tuple[dict[str, str], list[str], list[str]]:
        """Devuelve ({cabecera: campo}, cabeceras ignoradas, notas) para un archivo."""
        overrides = self.sources.get(header_key(file_name), {})
        lookup = _synonym_lookup(self.fields)
        mapping: dict[str, str] = {}
        used: dict[str, str] = {}
        ignored: list[str] = []
        notes: list[str] = []
        for header in headers:
            key = header_key(header)
            target = overrides.get(key) or lookup.get(key)
            if target is None:
                ignored.append(header)
            elif target in used:
                notes.append(f"columna «{header}» ignorada: «{used[target]}» ya es {target}")
            else:
                mapping[header] = target
                used[target] = header
        return mapping, ignored, notes


def load_config(path: Path) -> Config:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"{path}: el archivo de configuración no existe") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path}: no se pudo leer la configuración ({exc})") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: YAML inválido: {exc}") from exc
    return config_from_dict(data or {})


def config_from_dict(data: object) -> Config:
    if not isinstance(data, dict):
        raise ConfigError("la configuración debe ser un diccionario YAML")
    unknown = set(data) - TOP_LEVEL_KEYS
    if unknown:
        raise ConfigError(f"claves desconocidas: {', '.join(sorted(map(str, unknown)))}")

    region = data.get("default_region", "ES")
    if not (isinstance(region, str) and len(region) == 2 and region.isalpha()):
        raise ConfigError("default_region debe ser un código de país de 2 letras (p. ej. ES)")

    date_cfg = _mapping(data, "date")
    dayfirst = date_cfg.get("dayfirst", True)
    if not isinstance(dayfirst, bool):
        raise ConfigError("date.dayfirst debe ser true o false")

    fields = DEFAULT_FIELDS
    if "fields" in data:
        fields = {
            str(name): _str_list(syns, f"fields.{name}")
            for name, syns in _mapping(data, "fields").items()
        }
    _synonym_lookup(fields)  # valida que no haya sinónimos repetidos

    dedupe_cfg = _mapping(data, "dedupe")
    keys = tuple(_str_list(dedupe_cfg.get("keys", list(CONTACT_FIELDS)), "dedupe.keys"))
    if not keys or set(keys) - set(CONTACT_FIELDS):
        raise ConfigError(f"dedupe.keys debe contener solo: {', '.join(CONTACT_FIELDS)}")
    missing = [k for k in keys if k not in fields]
    if missing:
        raise ConfigError(f"dedupe.keys usa campos no definidos en fields: {', '.join(missing)}")
    recency = dedupe_cfg.get("recency_field", "fecha")
    if recency not in fields:
        raise ConfigError(f"dedupe.recency_field «{recency}» no está definido en fields")

    available = set(fields)
    if "nombre_completo" in fields:
        available |= {"nombre", "apellidos"}
    output = DEFAULT_OUTPUT
    if "output_columns" in data:
        output = {str(k): str(v) for k, v in _mapping(data, "output_columns").items()}
    unknown_out = [k for k in output if k not in available]
    if unknown_out:
        raise ConfigError(f"output_columns usa campos desconocidos: {', '.join(unknown_out)}")
    if not output:
        raise ConfigError("output_columns no puede estar vacío")

    sources: dict[str, dict[str, str]] = {}
    raw_sources = data.get("sources") or []
    if not isinstance(raw_sources, list):
        raise ConfigError("sources debe ser una lista")
    for i, src in enumerate(raw_sources):
        if not isinstance(src, dict) or "file" not in src:
            raise ConfigError(f"sources[{i}] necesita «file»")
        columns = _mapping(src, "columns")
        bad = [str(v) for v in columns.values() if v not in fields]
        if bad:
            raise ConfigError(f"sources[{i}].columns usa campos desconocidos: {', '.join(bad)}")
        sources[header_key(src["file"])] = {header_key(h): str(f) for h, f in columns.items()}

    return Config(
        default_region=region.upper(),
        dayfirst=dayfirst,
        dedupe_keys=keys,
        recency_field=recency,
        fields=dict(fields),
        output_columns=dict(output),
        sources=sources,
    )


def _mapping(data: dict, key: str) -> dict:
    value = data.get(key) or {}
    if not isinstance(value, dict):
        raise ConfigError(f"{key} debe ser un diccionario")
    return value


def _str_list(value: object, where: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{where} debe ser una lista de textos")
    return tuple(value)


def _synonym_lookup(fields: dict[str, tuple[str, ...]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for name, synonyms in fields.items():
        for synonym in (name, *synonyms):
            key = header_key(synonym)
            if lookup.get(key, name) != name:
                raise ConfigError(f"la cabecera «{synonym}» está en {lookup[key]} y en {name}")
            lookup[key] = name
    return lookup
