"""Summarise wn-validate JSON reports in build/validation/.

Prints a table of check-code × language counts, followed by totals.
Run after bash build.sh (or build.sh --lmf-only).

Usage:
    uv run python scripts/validation_summary.py
"""

import json
import sys
from pathlib import Path

VALDIR = Path("build/validation")


def main() -> None:
    """Print a cross-language summary of validation check counts."""
    reports = sorted(VALDIR.glob("tufs-*.json"))
    if not reports:
        print(f"No validation reports found in {VALDIR}/", file=sys.stderr)
        sys.exit(1)

    # Collect: {check_code: {message, {lang: count}}}
    checks: dict[str, dict] = {}
    langs: list[str] = []

    for path in reports:
        lang = path.stem.removeprefix("tufs-")
        langs.append(lang)
        data: dict = json.loads(path.read_text())
        for code, info in data.items():
            if code not in checks:
                checks[code] = {"message": info["message"], "counts": {}}
            checks[code]["counts"][lang] = len(info.get("items", {}))

    if not checks:
        print("All files passed validation — no issues found.")
        return

    # Print header
    col = 6
    header = f"{'Code':<6}  {'Message':<48}  " + "  ".join(f"{l:>{col}}" for l in langs) + f"  {'Total':>{col}}"
    print(header)
    print("-" * len(header))

    totals_by_lang: dict[str, int] = {l: 0 for l in langs}
    grand_total = 0

    for code, info in sorted(checks.items()):
        row_counts = [info["counts"].get(l, 0) for l in langs]
        row_total = sum(row_counts)
        grand_total += row_total
        for l, c in zip(langs, row_counts):
            totals_by_lang[l] += c
        cells = "  ".join(f"{c:>{col}}" if c else f"{'':>{col}}" for c in row_counts)
        print(f"{code:<6}  {info['message']:<48}  {cells}  {row_total:>{col}}")

    print("-" * len(header))
    totals = "  ".join(f"{totals_by_lang[l]:>{col}}" for l in langs)
    print(f"{'Total':<6}  {'':48}  {totals}  {grand_total:>{col}}")


if __name__ == "__main__":
    main()
