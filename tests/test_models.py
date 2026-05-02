"""
tests/test_models.py — Unit tests for models.py schema + query functions
=========================================================================
Uses a temporary SQLite file so tests are fast and isolated.
"""

import os
import tempfile

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


def test_new_columns_exist():
    """New columns (r2_image_url, r2_video_url, headshot_used, stage_durations, stage_costs) round-trip."""
    item_id = models.create_content_item("Test idea")

    models.update_content_item(
        item_id,
        r2_image_url="https://r2.example.com/img.png",
        r2_video_url="https://r2.example.com/vid.mp4",
        headshot_used=1,
        stage_durations='{"scrape": 1.2, "script": 3.4}',
        stage_costs='{"scrape": 0.01, "script": 0.05}',
    )

    item = models.get_content_item(item_id)
    assert item is not None
    assert item["r2_image_url"] == "https://r2.example.com/img.png"
    assert item["r2_video_url"] == "https://r2.example.com/vid.mp4"
    assert item["headshot_used"] == 1
    assert item["stage_durations"] == '{"scrape": 1.2, "script": 3.4}'
    assert item["stage_costs"] == '{"scrape": 0.01, "script": 0.05}'


def test_default_status_is_draft():
    """Newly created items default to status='draft'."""
    item_id = models.create_content_item("Another idea")
    item = models.get_content_item(item_id)
    assert item is not None
    assert item["status"] == "draft"


def test_list_by_statuses():
    """list_content_items_by_statuses filters to only the requested statuses."""
    id1 = models.create_content_item("Idea one")
    id2 = models.create_content_item("Idea two")
    id3 = models.create_content_item("Idea three")

    models.update_content_item(id1, status="ready")
    models.update_content_item(id2, status="failed")
    models.update_content_item(id3, status="draft")

    results = models.list_content_items_by_statuses(["ready", "failed"])
    assert len(results) == 2
    returned_statuses = {r["status"] for r in results}
    assert returned_statuses == {"ready", "failed"}


def test_calendar_counts():
    """get_calendar_counts groups items by date(scheduled_at) and status."""
    item_id = models.create_content_item("Calendar idea")
    models.update_content_item(
        item_id,
        status="ready",
        scheduled_at="2026-05-15 10:00:00",
    )

    counts = models.get_calendar_counts(2026, 5)
    assert "2026-05-15" in counts
    entry = counts["2026-05-15"]
    assert entry["count"] >= 1
    assert "ready" in entry["statuses"]
