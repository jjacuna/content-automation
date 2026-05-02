"""Tests for R2 storage service."""

import os
import sys

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.r2_storage import is_configured, upload_image

R2_ENV_VARS = [
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
]


def _clear_r2_env():
    """Remove all R2 env vars."""
    for var in R2_ENV_VARS:
        os.environ.pop(var, None)


def test_is_configured_false_when_no_env():
    _clear_r2_env()
    assert is_configured() is False


def test_is_configured_true_when_env_set():
    try:
        for var in R2_ENV_VARS:
            os.environ[var] = "test"
        assert is_configured() is True
    finally:
        _clear_r2_env()


def test_upload_image_returns_demo_when_not_configured():
    _clear_r2_env()
    result = upload_image("https://example.com/image.jpg")
    assert result["demo"] is True
    assert result["url"] == "https://example.com/image.jpg"
