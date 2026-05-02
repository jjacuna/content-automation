"""
tests/test_pipeline.py — Unit tests for pipeline.py stage helpers
==================================================================
Uses a temporary SQLite file so tests are fast and isolated.
"""

import json
import os

# Must set DATABASE_PATH before importing models
os.environ["DATABASE_PATH"] = ":memory:"

import pytest
import models


@pytest.fixture(autouse=True)
def reinit_db(tmp_path):
    """Reinitialize the database before every test (fresh schema)."""
    db_file = str(tmp_path / "test.db")
    models.DATABASE_PATH = db_file
    models.init_db()
    yield


def test_stage_r2_upload_skips_when_not_configured(monkeypatch):
    """stage_r2_upload returns cost 0.0 and leaves r2_image_url as None when R2 is not configured."""
    # Clear any R2 env vars that might be set
    for var in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "R2_PUBLIC_URL"]:
        monkeypatch.delenv(var, raising=False)

    from pipeline import stage_r2_upload

    item_id = models.create_content_item("Test idea")
    item = models.get_content_item(item_id)

    events = []

    def mock_emit(stage, status, message, detail=None):
        events.append((stage, status, message))

    cost = stage_r2_upload(item_id, item, mock_emit)

    assert cost == 0.0

    # Verify r2_image_url was not set
    updated_item = models.get_content_item(item_id)
    assert updated_item["r2_image_url"] is None

    # Verify a "skipped" event was emitted
    assert any(status == "skipped" for (_, status, _) in events)


def test_stage_durations_and_costs_recorded():
    """_record_stage_metric writes JSON that parses correctly and accumulates across calls."""
    from pipeline import _record_stage_metric

    item_id = models.create_content_item("Metric test idea")

    # Record two stages
    _record_stage_metric(item_id, "scrape", duration=1.5, cost=0.0)
    _record_stage_metric(item_id, "script", duration=3.2, cost=0.0042)

    item = models.get_content_item(item_id)

    durations = json.loads(item["stage_durations"])
    costs = json.loads(item["stage_costs"])

    assert durations["scrape"] == 1.5
    assert durations["script"] == 3.2
    assert costs["scrape"] == 0.0
    assert costs["script"] == 0.0042
    assert len(durations) == 2
    assert len(costs) == 2
