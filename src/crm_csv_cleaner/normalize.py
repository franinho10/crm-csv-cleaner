"""Normalizadores de campos. Funciones puras: devuelven el valor limpio o None si es inválido."""

import math
import re
import unicodedata
from datetime import date, datetime, timedelta

import phonenumbers

NAME_PARTICLES = {"de", "del", "la", "las", "los", "y", "e", "da", "das", "do", "dos", "van", "von"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")
EXCEL_EPOCH = date(1899, 12, 30)

MONTHS = {
    "ene": 1, "enero": 1, "jan": 1, "january": 1,
    "feb": 2, "febrero": 2, "february": 2,
    "mar": 3, "marzo": 3, "march": 3,
    "abr": 4, "abril": 4, "apr": 4, "april": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6, "june": 6,
    "jul": 7, "julio": 7, "july": 7,
    "ago": 8, "agosto": 8, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "septiembre": 9, "setiembre": 9, "september": 9,
    "oct": 10, "octubre": 10, "october": 10,
    "nov": 11, "noviembre": 11, "november": 11,
    "dic": 12, "diciembre": 12, "dec": 12, "december": 12,
}  # fmt: skip

# Se aplican sobre texto ya plegado con fold() (minúsculas): la "T" ISO llega como "t".
ISO_DATE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ t]\d{1,2}:\d{2}(?::\d{2})?.*)?$")
NUMERIC_DATE = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})$")
TEXT_MONTH_DATE = re.compile(
    r"^(\d{1,2})[\s/.-]+(?:de\s+)?([a-z]+)\.?[\s/.-]+(?:de\s+)?(\d{2}|\d{4})$"
)


def is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and value.strip() in {"", "nan", "NaN", "None", "NaT"}


def fold(text: str) -> str:
    """Quita tildes y pasa a minúsculas sin depender del locale ("Ñúñez" -> "nunez")."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def sort_key(*parts: str) -> tuple[str, ...]:
    """Clave de orden de la salida: compara sin tildes ni mayúsculas y desempata con el original.

    La usan el pipeline y examples/generate_fake_data.py, para que el orden sea siempre el mismo.
    """
    return tuple(fold(p) for p in parts) + tuple(parts)


def normalize_phone(value: object, region: str = "ES") -> str | None:
    """Teléfono en E.164 (+34600000123), o None si falta o no es válido para la región."""
    if is_blank(value):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # Excel guarda los teléfonos sin prefijo como número
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    try:
        number = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(number):
        return None
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def normalize_email(value: object) -> str | None:
    """Email en minúsculas y sin espacios, o None si falta o no tiene forma de email."""
    if is_blank(value):
        return None
    text = str(value).strip().lower()
    text = text.removeprefix("mailto:")
    if not EMAIL_RE.fullmatch(text) or ".." in text:
        return None
    return text


def parse_date(value: object, dayfirst: bool = True) -> str | None:
    """Fecha en ISO AAAA-MM-DD, o None si falta o no existe (p. ej. 2025-02-30).

    Acepta datetime/date, número de serie de Excel, ISO (con o sin hora), d/m/a o m/d/a según
    `dayfirst` (separadores / - .) y mes en texto en español o inglés ("3-abr-25", "3 de abril de
    2025"). Años de 2 dígitos: 00–69 -> 2000–2069, 70–99 -> 1970–1999.
    """
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, int | float) and not isinstance(value, bool):
        return _from_excel_serial(value)

    text = fold(str(value).strip())
    if m := ISO_DATE.fullmatch(text):
        y, mo, d = (int(g) for g in m.groups())
        return _safe_date(y, mo, d)
    if m := NUMERIC_DATE.fullmatch(text):
        a, b, y = int(m[1]), int(m[2]), _full_year(m[3])
        d, mo = (a, b) if dayfirst else (b, a)
        return _safe_date(y, mo, d)
    if m := TEXT_MONTH_DATE.fullmatch(text):
        mo = MONTHS.get(m[2])
        return _safe_date(_full_year(m[3]), mo, int(m[1])) if mo else None
    if re.fullmatch(r"\d{8}", text):  # AAAAMMDD
        return _safe_date(int(text[:4]), int(text[4:6]), int(text[6:]))
    if re.fullmatch(r"\d{5}(?:\.0)?", text):  # número de serie de Excel exportado como texto
        return _from_excel_serial(float(text))
    return None


def _full_year(text: str) -> int:
    year = int(text)
    if len(text) == 2:
        year += 2000 if year < 70 else 1900
    return year


def _safe_date(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _from_excel_serial(serial: float) -> str | None:
    # Rango razonable: 1954-10-14 (20000) a 2119-01-11 (80000).
    if not 20000 <= serial <= 80000:
        return None
    return (EXCEL_EPOCH + timedelta(days=int(serial))).isoformat()


def normalize_name(value: object) -> str:
    """Espacios colapsados y capitalización: "  lucía   FERRÁN " -> "Lucía Ferrán".

    Solo recapitaliza palabras enteramente en minúsculas o mayúsculas, así que respeta formas
    mixtas como "McDonald". Las partículas (de, del, la...) van en minúscula salvo al inicio.
    """
    if is_blank(value):
        return ""
    words = str(value).split()
    out = []
    for i, word in enumerate(words):
        if i > 0 and word.lower() in NAME_PARTICLES:
            out.append(word.lower())
        elif word.islower() or word.isupper():
            out.append(_capitalize(word))
        else:
            out.append(word)
    return " ".join(out)


def _capitalize(word: str) -> str:
    # Capitaliza cada parte separada por guion o apóstrofo: "ana-maría" -> "Ana-María".
    return re.sub(r"[^\W\d_]+", lambda m: m[0][0].upper() + m[0][1:].lower(), word)


def split_full_name(value: object) -> tuple[str, str]:
    """Separa "Nombre Apellido1 Apellido2" en (nombre, apellidos) por la primera palabra.

    Limitación: los nombres compuestos ("José Luis") quedan partidos; si la fuente tiene columnas
    separadas de nombre y apellidos, mejor mapearlas directamente.
    """
    name = normalize_name(value)
    first, _, last = name.partition(" ")
    return first, last
