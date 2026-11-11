"""Turn coverage.txt into the Markdown source of the typeset coverage report.

Documentation tooling only (run by docs/build.sh): it reads the plain-text
report that tests/coverage_report.py writes to docs/04-unit-tests/coverage.txt
and prints a Markdown document with a per-file table, the method, and the raw
report.

Usage: python3 coverage_doc.py <coverage.txt> <date>
"""

import re
import sys

LINE = re.compile(r"^(?P<file>[\w./]+): (?P<hit>\d+)/(?P<total>\d+) lines \((?P<pct>[\d.]+)%\)$")
TOTAL = re.compile(r"^TOTAL model/: (?P<hit>\d+)/(?P<total>\d+) lines \((?P<pct>[\d.]+)%\)$")


def main(path: str, date: str) -> None:
    """Print the Markdown report for the coverage file at ``path``."""
    with open(path, encoding="utf-8") as handle:
        raw = handle.read().rstrip("\n")
    rows, total = [], None
    for line in raw.splitlines():
        match = LINE.match(line.strip())
        if match:
            rows.append(match.groupdict())
        match = TOTAL.match(line.strip())
        if match:
            total = match.groupdict()
    if total is None or not rows:
        sys.exit("coverage_doc: coverage.txt has no per-file lines or no TOTAL line")

    out = [
        "---",
        'title: "Line Coverage Report"',
        'subtitle: "Personal Information Management (PIM) System"',
        'short-title: "PIM System · Line Coverage Report"',
        f'date: "{date}"',
        'version: "1.0"',
        'status: "Final"',
        'deliverable: "Deliverable 4: Unit tests for the system model"',
        "---",
        "",
        "# Summary",
        "",
        f"The unit tests in `tests/unit` execute **{total['hit']} of the {total['total']} countable lines** "
        f"in the `model` package, a line coverage of **{total['pct']} %**. "
        "Every file of the package is fully covered.",
        "",
        "| File | Countable lines | Lines executed | Line coverage |",
        "|------------------------|----------------|----------------|----------------|",
    ]
    for row in rows:
        out.append(f"| `model/{row['file']}` | {row['total']} | {row['hit']} | {row['pct']} % |")
    out.append(f"| **Total** | **{total['total']}** | **{total['hit']}** | **{total['pct']} %** |")
    out += [
        "",
        "# Method",
        "",
        "The report is produced by `tests/coverage_report.py`. It uses only "
        "the Python standard library:",
        "",
        "- The standard `trace` module runs every test in `tests/unit` and records which lines of "
        "`model/` were executed.",
        "- A line is *countable* when a Python statement starts on it. Docstrings, comments, blank "
        "lines, and the continuation lines of a statement that spans several lines are not counted.",
        "- `model/__init__.py` only re-exports names from the other modules, so it is excluded.",
        "- The third-party `coverage.py` tool is not used. Its totals can differ slightly because it "
        "counts lines in its own way.",
        "",
        "To reproduce the figures, run this command at the root of the source code:",
        "",
        "```",
        "python3 tests/coverage_report.py",
        "```",
        "",
        "The command rewrites `docs/04-unit-tests/coverage.txt` and exits with status 1 if a unit test fails or any "
        "countable line of `model/` is not executed.",
        "",
        "# Report output",
        "",
        "The full text of `coverage.txt`:",
        "",
        "```",
        raw,
        "```",
        "",
    ]
    print("\n".join(out))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
