"""Write the API contract to docs/openapi.json - the frontend's single source for the API.

Run from backend/ after any endpoint change, and commit the result:

    .\\.venv\\Scripts\\python.exe -m scripts.export_openapi

tests/test_openapi_contract.py fails if the committed file is out of date.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.main import create_app

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def render_contract() -> str:
    """The OpenAPI document exactly as it is written to disk."""
    spec: dict[str, Any] = create_app().openapi()
    return json.dumps(spec, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    CONTRACT_PATH.write_text(render_contract(), encoding="utf-8", newline="\n")
    print(f"Wrote {CONTRACT_PATH}")


if __name__ == "__main__":
    main()
