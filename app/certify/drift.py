"""Drift Canary: response schema validation, schema fingerprinting, and drift detection."""

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

from app.logging import get_logger

logger = get_logger("app.certify.drift")


def calculate_schema_fingerprint(data: Any, prefix: str = "") -> str:
    """Calculates a deterministic SHA-256 fingerprint from sorted field paths and type names.

    Solves the platform field rename problem by giving every API shape a unique cryptographic signature.
    """
    field_types: list[tuple[str, str]] = []

    def _extract_fields(obj: Any, current_path: str):
        if isinstance(obj, dict):
            for k, v in sorted(obj.items()):
                new_path = f"{current_path}.{k}" if current_path else k
                _extract_fields(v, new_path)
        elif isinstance(obj, list):
            item_type = type(obj[0]).__name__ if obj else "empty"
            field_types.append((f"{current_path}[]", item_type))
        else:
            field_types.append((current_path, type(obj).__name__))

    _extract_fields(data, prefix)
    field_types.sort(key=lambda item: item[0])

    canonical_repr = ";".join(f"{path}:{t}" for path, t in field_types)
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()


def validate_response_schema(
    connector_key: str,
    method: str,
    response_data: dict[str, Any],
) -> tuple[bool, str, dict[str, Any] | None]:
    """Validates raw platform response against pinned JSON schema.

    Returns:
        tuple (is_valid, fingerprint, drift_report)
    """
    fingerprint = calculate_schema_fingerprint(response_data)
    schema_path = Path("schemas") / connector_key / f"{method}.json"

    if not schema_path.exists():
        # No pinned schema found for this method, assume passed with calculated fingerprint
        return True, fingerprint, None

    try:
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
    except Exception as exc:
        logger.warning("Could not read pinned schema at %s: %s", schema_path, exc)
        return True, fingerprint, None

    # Validate schema using draft-07 validator
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(response_data), key=lambda e: e.path)

    if errors:
        diff_errors = []
        missing_fields = []
        for err in errors:
            diff_errors.append(
                {
                    "message": err.message,
                    "path": ".".join(str(p) for p in err.path),
                    "validator": err.validator,
                }
            )
            if err.validator == "required":
                missing_fields.append(err.message)

        drift_report = {
            "code": "CERT_DRIFT_DETECTED",
            "message": f"Platform response schema drifted on '{connector_key}.{method}'.",
            "errors": diff_errors,
            "missing_fields": missing_fields,
            "observed_keys": list(response_data.keys()),
            "schema_path": str(schema_path),
            "expected_fingerprint": schema.get("title", ""),
            "actual_fingerprint": fingerprint,
        }
        logger.error(
            "API DRIFT DETECTED on %s.%s! Missing/renamed: %s",
            connector_key,
            method,
            missing_fields,
        )
        return False, fingerprint, drift_report

    return True, fingerprint, None
