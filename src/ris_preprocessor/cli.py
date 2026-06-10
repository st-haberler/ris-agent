"""Thin CLI around the pipeline: `ris-preprocessor <Gesetzesnummer> [--out DIR]`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .loader import LoaderError, fetch_law
from .parser import parse_law


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ris-preprocessor",
        description="Fetch an Austrian law (Bundesrecht konsolidiert) from RIS.",
    )
    parser.add_argument("gesetzesnummer", help="RIS Gesetzesnummer, e.g. 10002531")
    parser.add_argument(
        "--out", default="data", help="output directory (default: data)"
    )
    parser.add_argument(
        "--fassung-vom", default=None, help="snapshot date YYYY-MM-DD (default: today)"
    )
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="skip fetching; re-parse the cached snapshot",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    law_dir = Path(args.out) / args.gesetzesnummer
    if not args.parse_only:
        try:
            law = fetch_law(
                args.gesetzesnummer, data_dir=args.out, fassung_vom=args.fassung_vom
            )
        except LoaderError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"{law.kurztitel} ({law.abkuerzung or '-'}): {len(law.units)} units")
    elif not (law_dir / "law.json").exists():
        print(f"error: no snapshot at {law_dir}", file=sys.stderr)
        return 1

    summary = parse_law(law_dir)
    print(f"parsed: {summary['units']} units, {summary['warnings']} warnings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
