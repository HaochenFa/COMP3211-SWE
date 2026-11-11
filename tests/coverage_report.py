#!/usr/bin/env python3
"""Write a line-coverage report for model/ using only the standard library.

Traces `tests/unit` only. Exit status is 1 if those tests fail or if any
executable line in model/ (except `__init__.py`) was not hit. Docstrings
and comments are not counted.

`--check` is for the pre-commit hook: same rules, and `coverage.txt` is
written only when the total is 100% so a failing gate does not dirty the
working tree with a miss list.

The report goes to `docs/04-unit-tests/coverage.txt`, the source of the
typeset `COVERAGE_REPORT.pdf` at the repository root.
"""

from __future__ import annotations

import ast
import sys
import traceback
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "model"
UNIT = ROOT / "tests" / "unit"
REPORT = ROOT / "docs" / "04-unit-tests" / "coverage.txt"

# Printed at the top of coverage.txt so a reader knows how "100%" was measured.
METHOD = [
    "Method: the standard-library `trace` module runs every test in tests/unit",
    "and records which lines of model/ executed. A line is countable when an AST",
    "statement starts on it; docstrings, comments, blank lines, and continuation",
    "lines of a multi-line statement are not counted. model/__init__.py holds",
    "re-exports only and is excluded. Third-party coverage.py is not used.",
]


def main() -> int:
    """Run unit tests under `trace` and report model/ line coverage."""
    check = "--check" in sys.argv
    import trace as trace_mod

    tracer = trace_mod.Trace(
        count=True,
        trace=False,
        ignoredirs=[sys.prefix, sys.exec_prefix],
    )

    def run_tests():
        # Discover inside the tracer so import of model/ is counted.
        loader = unittest.defaultTestLoader
        suite = loader.discover(str(UNIT), top_level_dir=str(ROOT))
        return unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)

    result = tracer.runfunc(run_tests)
    counts = defaultdict(dict)
    for (filename, lineno), n in tracer.results().counts.items():
        counts[str(Path(filename).resolve())][lineno] = n

    lines = ["Line coverage for model/ (stdlib trace, tests/unit)", "", *METHOD, ""]
    grand_hit = grand_total = 0
    for path in sorted(MODEL.glob("*.py")):
        if path.name == "__init__.py":
            # Re-exports only; trace does not attribute package import to this file.
            continue
        source = path.read_text(encoding="utf-8")
        countable = _countable_lines(source)
        executed = counts.get(str(path.resolve()), {})
        hit = total = 0
        missing = []
        for lineno in sorted(countable):
            total += 1
            if executed.get(lineno, 0) > 0:
                hit += 1
            else:
                missing.append(str(lineno))
        grand_hit += hit
        grand_total += total
        pct = (100.0 * hit / total) if total else 100.0
        lines.append(f"{path.name}: {hit}/{total} lines ({pct:.1f}%)")
        if missing:
            lines.append("  missed: " + ", ".join(missing))
    pct = (100.0 * grand_hit / grand_total) if grand_total else 100.0
    lines.append("")
    lines.append(f"TOTAL model/: {grand_hit}/{grand_total} lines ({pct:.1f}%)")
    report_text = "\n".join(lines) + "\n"
    complete = result.wasSuccessful() and grand_hit == grand_total and grand_total > 0
    if complete or not check:
        REPORT.write_text(report_text, encoding="utf-8")
        sys.stderr.write(f"Wrote {REPORT}\n")
    else:
        sys.stderr.write(report_text)
    if not result.wasSuccessful():
        sys.stderr.write("Unit tests failed.\n")
        return 1
    if grand_hit != grand_total:
        sys.stderr.write(
            f"model/ line coverage is {pct:.1f}%, required 100%.\n"
        )
        return 1
    return 0


def _countable_lines(source: str) -> set[int]:
    """Statement start lines in `source`, excluding docstrings.

    Multi-line imports and signatures are one statement: `trace` attributes
    execution to the first line, so continuation lines are not required.
    """
    tree = ast.parse(source)
    docstrings = _docstring_linenos(tree)
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and node.lineno in docstrings:
            continue
        if isinstance(node, (ast.stmt, ast.excepthandler)):
            lines.add(node.lineno)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                lines.add(decorator.lineno)
    return lines


def _docstring_linenos(tree: ast.AST) -> set[int]:
    """Line numbers of the first-statement docstring of a module, class, or function."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and _is_string_constant(first.value):
            lines.add(first.lineno)
    return lines


def _is_string_constant(value: ast.AST) -> bool:
    """True when `value` is a string literal expression."""
    return isinstance(value, ast.Constant) and isinstance(value.value, str)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
