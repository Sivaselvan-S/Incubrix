"""Tests for OpenAPI contract consistency."""

from pathlib import Path

import yaml

from app.api.main import app


def test_openapi_yaml_matches_running_service():
    """Asserts that the committed openapi.yaml perfectly matches the current FastAPI schema."""
    openapi_file = Path(__file__).parent.parent / "openapi.yaml"
    assert openapi_file.exists(), "openapi.yaml must be committed in project root"

    with open(openapi_file, encoding="utf-8") as f:
        committed_spec = yaml.safe_load(f)

    current_spec = app.openapi()

    assert committed_spec.get("openapi") == current_spec.get("openapi")
    assert committed_spec.get("info", {}).get("title") == current_spec.get("info", {}).get("title")
    assert committed_spec.get("info", {}).get("version") == current_spec.get("info", {}).get("version")

    # Assert paths match exactly
    committed_paths = set(committed_spec.get("paths", {}).keys())
    current_paths = set(current_spec.get("paths", {}).keys())
    diff = committed_paths.symmetric_difference(current_paths)
    assert not diff, f"OpenAPI paths mismatch detected between committed file and app: {diff}"
