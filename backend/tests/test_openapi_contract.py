"""docs/openapi.json is the frontend's API contract; it must match the code."""

from __future__ import annotations

from app.main import create_app
from scripts.export_openapi import CONTRACT_PATH, render_contract

REGENERATE = "Run `python -m scripts.export_openapi` in backend/ and commit docs/openapi.json."


def test_committed_openapi_contract_matches_the_code() -> None:
    assert CONTRACT_PATH.exists(), f"docs/openapi.json is missing. {REGENERATE}"
    committed = CONTRACT_PATH.read_text(encoding="utf-8")

    assert committed == render_contract(), f"docs/openapi.json is out of date. {REGENERATE}"


def test_every_operation_has_a_summary_and_unique_operation_id() -> None:
    spec = create_app().openapi()
    operations = [op for path in spec["paths"].values() for op in path.values()]

    assert all(op.get("summary") for op in operations)
    ids = [op["operationId"] for op in operations]
    assert len(ids) == len(set(ids))
