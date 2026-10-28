import argparse

from crm_csv_cleaner import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crm-csv-cleaner",
        description="Une, normaliza y deduplica CSV/Excel en un único CSV listo para un CRM.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0
