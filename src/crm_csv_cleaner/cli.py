import argparse
import json
import sys
from pathlib import Path

from crm_csv_cleaner import __version__
from crm_csv_cleaner.config import Config, ConfigError, load_config
from crm_csv_cleaner.pipeline import run, write_output, write_rejects
from crm_csv_cleaner.readers import CSV_SUFFIXES, EXCEL_SUFFIXES, ReaderError

EXIT_OK = 0
EXIT_ERROR = 1  # entrada, configuración o salida
EXIT_USAGE = 2  # argumentos


class UsageError(Exception):
    pass


class CliError(Exception):
    pass


class SpanishParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = SpanishParser(
        prog="crm-csv-cleaner",
        description="Une, normaliza y deduplica CSV/Excel en un único CSV listo para un CRM.",
        epilog="Ejemplo: crm-csv-cleaner examples/input -c examples/mapping.yaml -o limpio.csv",
        add_help=False,
    )
    parser.add_argument("inputs", nargs="*", metavar="ARCHIVO", help="CSV/XLSX o carpetas")
    parser.add_argument("-c", "--config", type=Path, help="mapeo YAML (por defecto, el integrado)")
    parser.add_argument("-o", "--output", type=Path, help="CSV limpio de salida")
    parser.add_argument(
        "--rejects",
        type=Path,
        metavar="CSV",
        help="CSV con las filas descartadas y su motivo. ATENCIÓN: contiene los datos "
        "originales SIN enmascarar (teléfonos y emails completos); no lo compartas",
    )
    parser.add_argument(
        "--report", type=Path, metavar="JSON", help="informe en JSON (contactos enmascarados)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="procesa e informa sin escribir ningún archivo"
    )
    parser.add_argument("--force", action="store_true", help="sobrescribe archivos existentes")
    parser.add_argument("-h", "--help", action="help", help="muestra esta ayuda y sale")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}", help="muestra la versión"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        inputs = expand_inputs(args.inputs)
        outputs = check_outputs(args, inputs)
        config = load_config(args.config) if args.config else Config()
        result = run(inputs, config)
    except UsageError as exc:
        print(f"error: {exc}\nUsa --help para ver las opciones.", file=sys.stderr)
        return EXIT_USAGE
    except (CliError, ConfigError, ReaderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(result.report.format_text())
    if args.dry_run:
        print("\nModo --dry-run: no se ha escrito ningún archivo.")
        for label, path in outputs:
            print(f"  se escribiría {label} en {path}")
        return EXIT_OK

    try:
        for label, path in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            if label == "salida":
                write_output(result, path)
            elif label == "rechazados":
                write_rejects(result, path)
            else:
                path.write_text(
                    json.dumps(result.report.to_dict(), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            print(f"Escrito {label}: {path}")
    except OSError as exc:
        print(f"error: no se pudo escribir {exc.filename}: {exc.strerror}", file=sys.stderr)
        return EXIT_ERROR
    if args.rejects and result.report.discarded:
        print("Aviso: el archivo de rechazados contiene datos sin enmascarar; no lo compartas.")
    return EXIT_OK


def expand_inputs(raw: list[str]) -> list[Path]:
    if not raw:
        raise UsageError("indica al menos un archivo CSV/XLSX o una carpeta")
    paths: list[Path] = []
    for item in map(Path, raw):
        if item.is_dir():
            found = sorted(
                p for p in item.iterdir() if p.suffix.lower() in CSV_SUFFIXES | EXCEL_SUFFIXES
            )
            if not found:
                raise CliError(f"{item}: la carpeta no contiene archivos CSV/XLSX")
            paths += found
        elif item.is_file():
            paths.append(item)
        else:
            raise CliError(f"{item}: el archivo no existe")
    return paths


def check_outputs(args: argparse.Namespace, inputs: list[Path]) -> list[tuple[str, Path]]:
    outputs = [
        (label, path)
        for label, path in (
            ("salida", args.output),
            ("rechazados", args.rejects),
            ("informe", args.report),
        )
        if path is not None
    ]
    if not args.output and not args.dry_run:
        raise UsageError("indica el archivo de salida con -o o usa --dry-run")
    resolved = [p.resolve() for _, p in outputs]
    if len(set(resolved)) != len(resolved):
        raise UsageError("-o, --rejects y --report deben ser archivos distintos")
    clashes = set(resolved) & {p.resolve() for p in inputs}
    if clashes:
        raise UsageError(f"un archivo de salida coincide con una entrada: {clashes.pop()}")
    if not args.dry_run and not args.force:
        existing = [str(p) for _, p in outputs if p.exists()]
        if existing:
            raise CliError(f"ya existe {', '.join(existing)}; usa --force para sobrescribir")
    return outputs
