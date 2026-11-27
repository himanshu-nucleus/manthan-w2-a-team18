"""Render pytest JUnit XML as a Markdown test plan: one section per flow, one row per case.

    python -m scripts.test_plan reports/unit.xml [reports/startup.xml ...] --title "..."

Each test module is a flow; its title is the module docstring's first line. Each test
name becomes a readable case ("test_x_is_refused[emp]" -> "X is refused (emp)").
CI appends the output to $GITHUB_STEP_SUMMARY, so every run shows the plan and result.
"""

from __future__ import annotations

import argparse
import ast
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
RESULT_LABELS = {"passed": "✅ Pass", "failed": "❌ Fail", "skipped": "⏭️ Skipped"}


def flow_title(classname: str) -> str:
    """First line of the test module's docstring, or the module name."""
    module = BACKEND.joinpath(*classname.split(".")).with_suffix(".py")
    if module.is_file():
        doc = ast.get_docstring(ast.parse(module.read_text(encoding="utf-8")))
        if doc:
            return doc.strip().splitlines()[0].rstrip(".")
    return classname.rsplit(".", 1)[-1]


def case_title(name: str) -> str:
    base, _, params = name.partition("[")
    words = base.removeprefix("test_").replace("_", " ")
    title = words[:1].upper() + words[1:]
    return f"{title} ({params.rstrip(']')})" if params else title


def outcome(testcase: ET.Element) -> str:
    if testcase.find("failure") is not None or testcase.find("error") is not None:
        return "failed"
    if testcase.find("skipped") is not None:
        return "skipped"
    return "passed"


def render(paths: list[Path], title: str) -> str:
    flows: dict[str, list[tuple[str, str]]] = defaultdict(list)
    totals: dict[str, int] = defaultdict(int)
    for path in paths:
        for testcase in ET.parse(path).getroot().iter("testcase"):
            result = outcome(testcase)
            totals[result] += 1
            flows[testcase.get("classname", "")].append(
                (case_title(testcase.get("name", "")), result)
            )

    lines = [
        f"## {title}",
        "",
        f"**{sum(totals.values())} cases** - {totals['passed']} passed, "
        f"{totals['failed']} failed, {totals['skipped']} skipped",
        "",
        "| Flow | Cases | Passed | Failed |",
        "|---|---:|---:|---:|",
    ]
    for classname, cases in flows.items():
        passed = sum(1 for _, r in cases if r == "passed")
        failed = sum(1 for _, r in cases if r == "failed")
        lines.append(f"| {flow_title(classname)} | {len(cases)} | {passed} | {failed} |")

    for classname, cases in flows.items():
        lines += ["", f"<details><summary><b>{flow_title(classname)}</b></summary>", ""]
        lines += ["| # | Test case | Result |", "|---:|---|---|"]
        lines += [
            f"| {number} | {case} | {RESULT_LABELS[result]} |"
            for number, (case, result) in enumerate(cases, start=1)
        ]
        lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("reports", nargs="+", type=Path, help="pytest --junitxml files")
    parser.add_argument("--title", default="Test plan and results")
    args = parser.parse_args(argv)
    existing = [p for p in args.reports if p.is_file()]
    if not existing:
        print(f"## {args.title}\n\nNo test report was produced.")
        return 0
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(render(existing, args.title))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
