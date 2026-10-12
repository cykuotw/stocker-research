"""Normalize observable payloads and redact configured credentials at the API boundary."""

import os

from fastapi.encoders import jsonable_encoder
from pydantic import JsonValue

SENSITIVE_KEYS = {
    "password",
    "db_password",
    "api_key",
    "google_api_key",
    "authorization",
    "access_token",
    "refresh_token",
    "database_uri",
    "secret",
    "credentials",
    "headers",
}


def public_data(value: object) -> JsonValue:
    encoded = jsonable_encoder(value)
    secrets = [
        v
        for k, v in os.environ.items()
        if v
        and len(v) >= 8
        and (k.endswith(("_KEY", "_PASSWORD")) or k == "DATABASE_URI")
    ]

    def redact(item):
        if isinstance(item, dict):
            return {
                str(k): "[redacted]" if str(k).lower() in SENSITIVE_KEYS else redact(v)
                for k, v in item.items()
            }
        if isinstance(item, list):
            return [redact(v) for v in item]
        if isinstance(item, str):
            for secret in secrets:
                item = item.replace(secret, "[redacted]")
        return item

    return redact(encoded)
