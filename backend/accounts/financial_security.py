"""
Security helpers for the AccountFinancialDetails endpoint.

Centralizes:
- Deterministic redaction/masking of sensitive values.
- Minimal, scrubbed error response helpers.

This module is intentionally scoped to the accounts financial endpoint to avoid
altering API contracts elsewhere.
"""

from __future__ import annotations

from typing import Any

from rest_framework.exceptions import ErrorDetail


SENSITIVE_FIELD_NAMES = {
    # Current model fields that must be redacted
    "policy_number",
    # Future-proofing common secrets:
    "account_number",
    "routing_number",
    "iban",
    "swift",
    "ssn",
    "sin",
    "national_id",
}


# PUBLIC_INTERFACE
def mask_token(value: Any, *, keep_last: int = 4, min_mask: int = 8) -> str:
    """
    PUBLIC_INTERFACE
    Deterministically mask a token-like sensitive value.

    Behavior:
    - For falsy values (None/""), return empty string.
    - Keep only last `keep_last` characters, replace the rest with '*' characters.
    - Ensure the masked portion is at least `min_mask` chars when possible.

    This is intended for items like policy numbers / account numbers / SSN-like IDs.

    Args:
        value: Any value (typically str) to be masked.
        keep_last: Number of trailing characters to reveal.
        min_mask: Minimum number of '*' characters to show for non-empty inputs.

    Returns:
        Masked string.
    """
    if value is None:
        return ""
    s = str(value)
    if s == "":
        return ""
    if keep_last <= 0:
        keep_last = 0

    tail = s[-keep_last:] if keep_last and len(s) >= keep_last else (s if keep_last else "")
    mask_len = max(len(s) - len(tail), min_mask)
    return ("*" * mask_len) + tail


def _flatten_error_detail(detail: Any) -> Any:
    """
    Convert DRF ErrorDetail instances to their string form without leaking internals.
    """
    if isinstance(detail, ErrorDetail):
        return str(detail)
    return detail


# PUBLIC_INTERFACE
def scrub_serializer_errors(errors: Any) -> dict[str, Any]:
    """
    PUBLIC_INTERFACE
    Normalize and scrub DRF serializer error payloads.

    Goals:
    - Keep field-level messages (required for ADMIN PATCH validation).
    - Avoid echoing submitted sensitive values.
    - Avoid leaking schema hints beyond field names and human-readable messages.
    - Ensure the output is plain JSON (strings/lists/dicts only).

    Args:
        errors: serializer.errors from DRF.

    Returns:
        A JSON-safe dict of errors.
    """

    def scrub(node: Any, field_name: str | None = None) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for k, v in node.items():
                # Keep field name, but if it's a sensitive field, keep only messages.
                out[str(k)] = scrub(v, field_name=str(k))
            return out
        if isinstance(node, (list, tuple)):
            return [scrub(_flatten_error_detail(x), field_name=field_name) for x in node]
        # Scalar
        msg = str(_flatten_error_detail(node))

        # For sensitive fields, ensure we do not accidentally include the raw value
        # in the message. We can't reliably remove all possible echoes, but we can
        # avoid embedding long tokens by truncating and stripping quotes.
        if field_name and field_name in SENSITIVE_FIELD_NAMES:
            # Replace anything between quotes with a generic placeholder.
            # Keep it simple to avoid overfitting and potential false positives.
            msg = msg.replace("“", '"').replace("”", '"')
            if '"' in msg:
                parts = msg.split('"')
                # Replace odd-indexed sections (inside quotes)
                for i in range(1, len(parts), 2):
                    parts[i] = "[REDACTED]"
                msg = '"'.join(parts)

        # Remove any obvious python class/model hints if they ever appear.
        for token in ("Traceback", "DoesNotExist", "ValidationError", "AccountFinancialDetails"):
            if token in msg:
                msg = "Invalid input."
                break

        return msg

    scrubbed = scrub(errors)
    # DRF serializer.errors is typically a dict; enforce dict for response contract
    return scrubbed if isinstance(scrubbed, dict) else {"detail": "Invalid input."}


# PUBLIC_INTERFACE
def redact_financial_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    PUBLIC_INTERFACE
    Redact sensitive fields in a serialized AccountFinancialDetails payload.

    Adds:
      - redacted: true
      - redaction: {<field>: "masked_last4"} for fields that were masked

    Args:
        payload: Serializer output dict.

    Returns:
        A new dict with redactions applied.
    """
    out = dict(payload or {})
    redaction_meta: dict[str, str] = {}
    for field in list(out.keys()):
        if field in SENSITIVE_FIELD_NAMES and out.get(field) not in (None, ""):
            out[field] = mask_token(out.get(field))
            redaction_meta[field] = "masked_last4"

    out["redacted"] = True
    if redaction_meta:
        out["redaction"] = redaction_meta
    return out
