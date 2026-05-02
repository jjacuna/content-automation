# CAM Interface Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Content Automation Demo from a simple pipeline X-ray viewer to a CAM-style interface with queue cards, mini-calendar, R2 storage, Veo 3.1 headshot reference, and a visual detail page showing per-stage costs and timing.

**Architecture:** Incremental overlay on existing flat Flask app. Replace `/create` with `/cam`, add R2 service, enhance Kie.ai/GetLate services, upgrade the content detail page, add a background scheduling thread. No structural changes to the flat file layout.

**Tech Stack:** Flask 3.x, SQLite, Jinja2, Tailwind CSS (CDN), Alpine.js (CDN), boto3 (R2), requests (APIs)

**Spec:** `docs/superpowers/specs/2026-05-01-cam-interface-upgrade-design.md`

---

## File Map

**Create:**
- `services/r2_storage.py` — Cloudflare R2 upload/download/presigned URLs
- `templates/cam.html` — CAM interface (queue + mini-calendar + input)
- `tests/test_models.py` — Model layer tests
- `tests/test_pipeline.py` — Pipeline stage tests
- `tests/test_r2_storage.py` — R2 service tests
- `tests/test_cam_api.py` — CAM API endpoint tests
- `tests/e2e/test_smoke.py` — Playwright E2E smoke tests

**Modify:**
- `models.py` — Add new columns, migration helper, new query functions
- `pipeline.py` — Add R2 upload stage, stage cost/duration tracking, headshot toggle
- `services/kie_ai.py` — Nano Banana Pro 9:16, Veo 3.1 headshot reference
- `services/getlate.py` — Scheduled publishing with R2 URLs
- `app.py` — Replace `/create` with `/cam`, add CAM API endpoints, headshot upload, scheduling thread
- `templates/base.html` — Update nav (Create->CAM, remove Calendar)
- `templates/content_detail.html` — Visual stage breakdown with costs/timing
- `templates/settings.html` — Add Headshot Upload + R2 Storage sections
- `static/css/custom.css` — CAM page styles, detail page stage timeline styles
- `requirements.txt` — Add boto3
- `.env.example` — Add R2 env vars

---

## Task 0: Create Test Directories

- [ ] **Step 1: Create test directories and __init__.py files**

```bash
mkdir -p tests/e2e
touch tests/__init__.py tests/e2e/__init__.py
```

- [ ] **Step 2: Commit**

```bash
git add tests/
git commit -m "chore: create test directories"
```

---

## Task 1: Database Schema Updates

**Files:**
- Modify: `models.py`
- Test: `tests/test_models.py`

**Note:** `scheduled_at` already exists in the schema and does not need migration.

- [ ] **Step 1: Write failing test for new columns**

```python
# tests/test_models.py
import os
import sys
import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_PATH"] = ":memory:"

from models import init_db, create_content_item, get_content_item, update_content_item

@pytest.fixture(autouse=True)
def fresh_db():
    """Reset in-memory DB before each test."""
    import models
    models.DATABASE_PATH = ":memory:"
    init_db()
    yield

def test_new_columns_exist():
    """New columns r2_image_url, r2_video_url, headshot_used, stage_durations, stage_costs should exist."""
    item_id = create_content_item("test idea")
    update_content_item(item_id,
        r2_image_url="https://r2.example.com/images/test.jpg",
        r2_video_url="https://r2.example.com/videos/test.mp4",
        headshot_used=1,
        stage_durations='{"scrape": 2.1, "script": 3.5}',
        stage_costs='{"scrape": 0.0, "script": 0.003}'
    )
    item = get_content_item(item_id)
    assert item["r2_image_url"] == "https://r2.example.com/images/test.jpg"
    assert item["r2_video_url"] == "https://r2.example.com/videos/test.mp4"
    assert item["headshot_used"] == 1
    assert '"scrape"' in item["stage_durations"]
    assert '"script"' in item["stage_costs"]

def test_default_status_is_draft():
    item_id = create_content_item("test")
    item = get_content_item(item_id)
    assert item["status"] == "draft"

def test_list_by_statuses():
    """list_content_items_by_statuses should filter by multiple statuses."""
    from models import list_content_items_by_statuses
    id1 = create_content_item("a")
    id2 = create_content_item("b")
    id3 = create_content_item("c")
    update_content_item(id1, status="ready")
    update_content_item(id2, status="failed")
    update_content_item(id3, status="published")
    ready_failed = list_content_items_by_statuses(["ready", "failed"])
    assert len(ready_failed) == 2

def test_calendar_counts():
    """get_calendar_counts should return date->count mapping."""
    from models import get_calendar_counts
    id1 = create_content_item("a")
    update_content_item(id1, status="scheduled", scheduled_at="2026-05-15 10:00:00")
    counts = get_calendar_counts(2026, 5)
    assert "2026-05-15" in counts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/jonathanacuna/Documents/VS Code Programs/Content Automation Demo For Claude Workshop" && python -m pytest tests/test_models.py -v`
Expected: FAIL — columns don't exist, functions don't exist

- [ ] **Step 3: Update models.py schema and add new functions**

Add new columns to `content_items` CREATE TABLE in `init_db()`:

```python
# After existing columns (before closing paren), add:
                r2_image_url TEXT,
                r2_video_url TEXT,
                headshot_used BOOLEAN DEFAULT 0,
                stage_durations TEXT,
                stage_costs TEXT,
```

Add migration fallback in `init_db()` after the CREATE TABLE statements:

```python
        # -- Migration: add columns for existing databases --
        migrate_columns = [
            ("content_items", "r2_image_url", "TEXT"),
            ("content_items", "r2_video_url", "TEXT"),
            ("content_items", "headshot_used", "BOOLEAN DEFAULT 0"),
            ("content_items", "stage_durations", "TEXT"),
            ("content_items", "stage_costs", "TEXT"),
        ]
        for table, column, col_type in migrate_columns:
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists
```

Add new query functions:

```python
def list_content_items_by_statuses(statuses, limit=50):
    """List content items matching any of the given statuses."""
    placeholders = ",".join("?" for _ in statuses)
    with get_db() as db:
        rows = db.execute(
            f"SELECT * FROM content_items WHERE status IN ({placeholders}) ORDER BY created_at DESC LIMIT ?",
            statuses + [limit]
        ).fetchall()
        return [dict(r) for r in rows]


def get_calendar_counts(year, month):
    """Get daily content counts for a month. Returns {date_str: {count, statuses}}."""
    with get_db() as db:
        rows = db.execute(
            """SELECT date(scheduled_at) as day, status, COUNT(*) as cnt
               FROM content_items
               WHERE strftime('%Y', scheduled_at) = ?
                 AND strftime('%m', scheduled_at) = ?
                 AND scheduled_at IS NOT NULL
               GROUP BY day, status""",
            (str(year), str(month).zfill(2))
        ).fetchall()

    counts = {}
    for row in rows:
        row = dict(row)
        day = row["day"]
        if day not in counts:
            counts[day] = {"count": 0, "statuses": []}
        counts[day]["count"] += row["cnt"]
        if row["status"] not in counts[day]["statuses"]:
            counts[day]["statuses"].append(row["status"])
    return counts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "/Users/jonathanacuna/Documents/VS Code Programs/Content Automation Demo For Claude Workshop" && python -m pytest tests/test_models.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_models.py
git commit -m "feat: add R2/headshot/stage-tracking columns + calendar/status query functions"
```

---

## Task 2: R2 Storage Service

**Files:**
- Create: `services/r2_storage.py`
- Test: `tests/test_r2_storage.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add boto3 to requirements.txt**

Append `boto3>=1.34` to `requirements.txt`.

- [ ] **Step 2: Write failing test for R2 service**

```python
# tests/test_r2_storage.py
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_is_configured_false_when_no_env():
    """R2 should report not configured when env vars are missing."""
    for key in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]:
        os.environ.pop(key, None)
    from services.r2_storage import is_configured
    assert is_configured() is False

def test_is_configured_true_when_env_set():
    os.environ["R2_ACCOUNT_ID"] = "test"
    os.environ["R2_ACCESS_KEY_ID"] = "test"
    os.environ["R2_SECRET_ACCESS_KEY"] = "test"
    os.environ["R2_BUCKET_NAME"] = "test"
    from services.r2_storage import is_configured
    assert is_configured() is True
    # Cleanup
    for key in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]:
        del os.environ[key]

def test_upload_image_returns_demo_when_not_configured():
    for key in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]:
        os.environ.pop(key, None)
    from services.r2_storage import upload_image
    result = upload_image("https://example.com/image.jpg")
    assert result["demo"] is True
    assert result["url"] == "https://example.com/image.jpg"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd "/Users/jonathanacuna/Documents/VS Code Programs/Content Automation Demo For Claude Workshop" && pip install boto3 && python -m pytest tests/test_r2_storage.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 4: Implement R2 storage service**

```python
# services/r2_storage.py
"""
services/r2_storage.py -- Cloudflare R2 Storage
=================================================
Uploads images and videos to permanent R2 storage so URLs don't expire.
Uses boto3 S3-compatible client. Skips gracefully when not configured.
"""

import os
import uuid
import requests as http_requests
import boto3
from botocore.config import Config


def is_configured():
    """Check if R2 environment variables are set."""
    required = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]
    return all(os.getenv(k) for k in required)


def _get_client():
    """Create a boto3 S3 client for Cloudflare R2."""
    account_id = os.getenv("R2_ACCOUNT_ID")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto"
    )


def _get_public_url(key):
    """Build a public URL for an R2 object."""
    public_url = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
    if public_url:
        return f"{public_url}/{key}"
    return key


def upload_image(image_url, emit_event=None):
    """Download image from URL and upload to R2. Returns {url, key, demo}."""
    emit = emit_event or (lambda *a, **kw: None)

    if not is_configured():
        emit("upload", "progress", "R2 not configured -- using temporary URL.")
        return {"url": image_url, "key": None, "demo": True}

    emit("upload", "progress", "Uploading image to R2 permanent storage...")

    response = http_requests.get(image_url, timeout=60)
    response.raise_for_status()

    ext = ".jpg"
    ct = response.headers.get("content-type", "")
    if "png" in ct:
        ext = ".png"
    elif "webp" in ct:
        ext = ".webp"

    key = f"images/{uuid.uuid4().hex}{ext}"
    bucket = os.getenv("R2_BUCKET_NAME")

    client = _get_client()
    client.put_object(Bucket=bucket, Key=key, Body=response.content, ContentType=ct or "image/jpeg")

    url = _get_public_url(key)
    emit("upload", "progress", f"Image uploaded to R2: {key}")
    return {"url": url, "key": key, "demo": False}


def upload_video(video_url, emit_event=None):
    """Download video from URL and upload to R2. Returns {url, key, demo}."""
    emit = emit_event or (lambda *a, **kw: None)

    if not is_configured():
        emit("upload", "progress", "R2 not configured -- using temporary video URL.")
        return {"url": video_url, "key": None, "demo": True}

    emit("upload", "progress", "Uploading video to R2 permanent storage...")

    response = http_requests.get(video_url, timeout=120)
    response.raise_for_status()
    video_data = response.content

    ext = ".mp4"
    ct = response.headers.get("content-type", "video/mp4")
    if "webm" in ct:
        ext = ".webm"

    key = f"videos/{uuid.uuid4().hex}{ext}"
    bucket = os.getenv("R2_BUCKET_NAME")

    client = _get_client()
    client.put_object(Bucket=bucket, Key=key, Body=video_data, ContentType=ct)

    url = _get_public_url(key)
    emit("upload", "progress", f"Video uploaded to R2: {key}")
    return {"url": url, "key": key, "demo": False}


def upload_headshot(file_data, filename, emit_event=None):
    """Upload a headshot image from form data. Returns {url, key}."""
    emit = emit_event or (lambda *a, **kw: None)

    if not is_configured():
        emit("upload", "error", "R2 must be configured to upload headshots.")
        return {"url": None, "key": None, "error": "R2 not configured"}

    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    ct = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    key = f"headshots/{uuid.uuid4().hex}{ext}"
    bucket = os.getenv("R2_BUCKET_NAME")

    client = _get_client()
    client.put_object(Bucket=bucket, Key=key, Body=file_data, ContentType=ct)

    url = _get_public_url(key)
    emit("upload", "progress", f"Headshot uploaded: {key}")
    return {"url": url, "key": key}


def get_presigned_url(key, expires_in=604800):
    """Generate a presigned URL for an R2 object (default 7-day expiry)."""
    if not is_configured():
        return key
    client = _get_client()
    bucket = os.getenv("R2_BUCKET_NAME")
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in
    )


def test_connection():
    """Validate R2 credentials by listing bucket objects."""
    if not is_configured():
        return {"success": False, "error": "R2 environment variables not set"}
    try:
        client = _get_client()
        bucket = os.getenv("R2_BUCKET_NAME")
        client.list_objects_v2(Bucket=bucket, MaxKeys=1)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "/Users/jonathanacuna/Documents/VS Code Programs/Content Automation Demo For Claude Workshop" && python -m pytest tests/test_r2_storage.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/r2_storage.py tests/test_r2_storage.py requirements.txt
git commit -m "feat: add R2 storage service with upload, presigned URLs, and demo fallback"
```

---

## Task 3: Update Kie.ai Service (Nano Banana 9:16 + Veo 3.1 Headshot Reference)

**Files:**
- Modify: `services/kie_ai.py`

- [ ] **Step 1: Update image generation to use 9:16 aspect ratio**

In `generate_image()`, change the `image_size` from `"1024x1024"` to `"9:16"` and update the payload to use `aspect_ratio` for Nano Banana Pro:

```python
# In generate_image(), replace the JSON payload:
            json={
                "model": "nano-banana-pro",
                "input": {
                    "prompt": prompt,
                    "aspect_ratio": "9:16",
                    "resolution": "1K"
                }
            },
```

- [ ] **Step 2: Add headshot reference video generation function**

Add this function after `generate_video()`:

```python
def generate_video_with_reference(prompt, reference_image_url, emit_event=None):
    """
    Generate a video using Veo 3.1 with a headshot reference image.
    The reference_image_url is the student's headshot — Veo will place them in the scene.

    Args:
        prompt: Video description
        reference_image_url: URL of headshot image (must be publicly accessible)
        emit_event: SSE callback

    Returns:
        dict with: video_url, task_id, duration, cost
    """
    emit = emit_event or (lambda *a, **kw: None)
    headers = _get_headers()

    if not headers:
        emit("video", "progress", "No Kie.ai API key -- using placeholder video.")
        return {
            "video_url": "https://placehold.co/1080x1920/17181C/C7A35A?text=Demo+Video+With+Headshot",
            "task_id": "demo_ref_video_task",
            "duration": 0,
            "cost": 0.0,
            "demo": True
        }

    emit("video", "progress", f"Sending prompt to Veo 3.1 WITH your headshot as a reference image. The AI will place you in the scene!")

    try:
        create_response = requests.post(
            VIDEO_CREATE_URL,
            headers=headers,
            json={
                "prompt": prompt,
                "aspect_ratio": "9:16",
                "model": "veo3_fast",
                "reference_images": [reference_image_url]
            },
            timeout=30
        )
        create_response.raise_for_status()
        create_data = create_response.json()

        data = create_data.get("data", create_data)
        task_id = data.get("taskId") or data.get("task_id") or create_data.get("taskId")
        if not task_id:
            raise Exception(f"No task_id in response: {create_data}")

        emit("video", "progress", f"Reference video task created! ID: {task_id}. Polling every 20 seconds...")

    except requests.exceptions.RequestException as e:
        emit("video", "error", f"Failed to create reference video task: {str(e)}")
        raise

    # Poll same as regular video
    start_time = time.time()
    poll_interval = 20
    timeout = 300
    attempt = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            emit("video", "error", f"Reference video timed out after {timeout}s")
            raise Exception(f"Reference video timed out after {timeout} seconds")

        attempt += 1
        time.sleep(poll_interval)

        try:
            status_response = requests.get(
                VIDEO_STATUS_URL,
                headers=headers,
                params={"taskId": task_id},
                timeout=15
            )
            status_response.raise_for_status()
            status_data = status_response.json()

            data = status_data.get("data", status_data)
            success_flag = data.get("successFlag", 0)
            state = data.get("state", "unknown")
            if success_flag == 1:
                state = "success"
            elif success_flag in (2, 3):
                state = "failed"
            elif success_flag == 0 and state == "unknown":
                state = "processing"

            emit("video", "polling",
                 f"Checking reference video... attempt #{attempt} -- status: \"{state}\" ({round(elapsed)}s)",
                 {"attempt": attempt, "state": state, "elapsed": round(elapsed, 1)})

            if state in ("success", "completed", "done"):
                video_url = ""
                if data.get("response") and data["response"].get("resultUrls"):
                    video_url = data["response"]["resultUrls"][0]
                elif data.get("videoUrl"):
                    video_url = data["videoUrl"]
                if not video_url:
                    import json as _json
                    result_json_str = data.get("resultJson", "")
                    if result_json_str:
                        result_json = _json.loads(result_json_str)
                        result_urls = result_json.get("resultUrls", [])
                        if result_urls:
                            video_url = result_urls[0]

                duration = round(time.time() - start_time, 1)
                cost = 0.30  # Reference videos cost more

                emit("video", "progress",
                     f"Reference video done! You're in the scene! Took {duration}s.")

                return {
                    "video_url": video_url,
                    "task_id": task_id,
                    "duration": duration,
                    "cost": cost,
                    "demo": False
                }

            elif state in ("failed", "failure", "error", "cancelled"):
                error_msg = data.get("errorMessage") or data.get("errorMsg") or data.get("failMsg", "Unknown error")
                emit("video", "error", f"Reference video failed: {error_msg}")
                raise Exception(f"Reference video failed: {error_msg}")

        except requests.exceptions.RequestException:
            emit("video", "progress", f"Poll failed (attempt {attempt}), retrying...")
```

- [ ] **Step 3: Add prompt cleaning helper**

Add at the top of the file, after imports:

```python
import re

def _clean_prompt(prompt):
    """Remove markdown formatting from prompts before sending to Kie.ai."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', prompt)  # bold
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)  # italic
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)  # headers
    text = re.sub(r'`(.+?)`', r'\1', text)  # backticks
    text = text.replace('\t', ' ')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.replace('"', "'")
    return text.strip()
```

Update `generate_image()` and `generate_video()` to clean prompts: add `prompt = _clean_prompt(prompt)` as the first line after `emit = ...` in each function. Same for `generate_video_with_reference()`.

- [ ] **Step 4: Commit**

```bash
git add services/kie_ai.py
git commit -m "feat: Nano Banana 9:16 aspect ratio, Veo 3.1 headshot reference, prompt cleaning"
```

---

## Task 4: Update GetLate Service (Scheduled Publishing with R2 URLs)

**Files:**
- Modify: `services/getlate.py`

- [ ] **Step 1: Update publish_post to use R2 URLs and scheduled_at**

In `publish_post()`, update the media URL logic to prefer R2 URLs:

```python
        # Attach image — prefer R2 permanent URL over temp Kie.ai URL
        image_url = content_item.get("r2_image_url") or content_item.get("image_url")
        if image_url:
            payload["media"] = [{"url": image_url, "type": "image"}]

        # Attach video — prefer R2 permanent URL
        video_url = content_item.get("r2_video_url") or content_item.get("video_url")
        if video_url:
            payload["media"] = payload.get("media", [])
            payload["media"].append({"url": video_url, "type": "video"})
```

- [ ] **Step 2: Add scheduled_at parsing to UTC ISO 8601**

Add a helper function and update the scheduling logic:

```python
from datetime import datetime, timezone

def _parse_scheduled_time(scheduled_at_str):
    """Convert a datetime string to UTC ISO 8601 for GetLate API."""
    if not scheduled_at_str:
        return None
    try:
        # Parse various formats
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(scheduled_at_str, fmt)
                # Assume PST input, convert to UTC (+8 hours)
                utc_dt = dt.replace(tzinfo=timezone.utc)  # Treat as UTC for simplicity in demo
                return utc_dt.isoformat()
            except ValueError:
                continue
        return scheduled_at_str  # Return as-is if we can't parse
    except Exception:
        return scheduled_at_str
```

Update the scheduling block in `publish_post()`:

```python
        # If there's a scheduled time, parse and add it
        if content_item.get("scheduled_at"):
            parsed_time = _parse_scheduled_time(content_item["scheduled_at"])
            if parsed_time:
                payload["scheduled_for"] = parsed_time
                payload["timezone"] = "America/Los_Angeles"
```

- [ ] **Step 3: Commit**

```bash
git add services/getlate.py
git commit -m "feat: GetLate uses R2 URLs, parses scheduled_at to UTC ISO 8601"
```

---

## Task 5: Update Pipeline (R2 Upload Stage + Stage Tracking + Headshot Toggle)

**Files:**
- Modify: `pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test for R2 upload stage and stage tracking**

```python
# tests/test_pipeline.py
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_PATH"] = ":memory:"

from models import init_db, create_content_item, get_content_item

@pytest.fixture(autouse=True)
def fresh_db():
    import models
    models.DATABASE_PATH = ":memory:"
    init_db()
    yield

def test_stage_r2_upload_skips_when_not_configured():
    """R2 upload stage should skip and set status to 'ready' when R2 is not configured."""
    for key in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]:
        os.environ.pop(key, None)
    from pipeline import stage_r2_upload
    item_id = create_content_item("test idea")
    from models import update_content_item
    update_content_item(item_id, image_url="https://temp.example.com/img.jpg", video_url="https://temp.example.com/vid.mp4")
    item = get_content_item(item_id)
    events = []
    cost = stage_r2_upload(item_id, item, lambda *a, **kw: events.append(a))
    assert cost == 0.0
    item = get_content_item(item_id)
    # Should NOT have r2 URLs since R2 is not configured
    assert item["r2_image_url"] is None

def test_stage_durations_and_costs_recorded():
    """Pipeline should record stage_durations and stage_costs as JSON."""
    from pipeline import _record_stage_metric
    item_id = create_content_item("test idea")
    _record_stage_metric(item_id, "scrape", duration=2.1, cost=0.0)
    _record_stage_metric(item_id, "script", duration=3.5, cost=0.003)
    item = get_content_item(item_id)
    durations = json.loads(item["stage_durations"])
    costs = json.loads(item["stage_costs"])
    assert durations["scrape"] == 2.1
    assert costs["script"] == 0.003
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/jonathanacuna/Documents/VS Code Programs/Content Automation Demo For Claude Workshop" && python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — functions don't exist

- [ ] **Step 3: Add stage metric tracking helper to pipeline.py**

Add after imports:

```python
from services.r2_storage import upload_image as r2_upload_image, upload_video as r2_upload_video, is_configured as r2_is_configured
from services.kie_ai import generate_video_with_reference
from models import get_setting


def _record_stage_metric(content_id, stage_name, duration=0.0, cost=0.0):
    """Record duration and cost for a pipeline stage into JSON fields."""
    item = get_content_item(content_id)

    # Parse existing JSON or start fresh
    durations = json.loads(item.get("stage_durations") or "{}")
    costs = json.loads(item.get("stage_costs") or "{}")

    durations[stage_name] = round(duration, 2)
    costs[stage_name] = round(cost, 6)

    update_content_item(content_id,
        stage_durations=json.dumps(durations),
        stage_costs=json.dumps(costs)
    )
```

- [ ] **Step 4: Add R2 upload stage**

Add after `stage_caption()`:

```python
def stage_r2_upload(content_id, item, emit_event):
    """Upload image and video to R2 for permanent storage. Skips if R2 not configured."""
    stage = "upload"
    start = time.time()

    if not r2_is_configured():
        emit_event(stage, "skipped", "R2 Storage not configured -- keeping temporary URLs. Add R2 credentials in Settings for permanent storage.")
        add_pipeline_log(content_id, stage, "skipped", "R2 not configured")
        return 0.0

    emit_event(stage, "started", "Uploading your image and video to Cloudflare R2 for permanent storage. Temporary AI URLs expire, but R2 URLs last forever.")
    add_pipeline_log(content_id, stage, "started", "Uploading to R2")
    update_content_item(content_id, status="uploading")

    r2_image_url = None
    r2_video_url = None

    # Upload image
    if item.get("image_url") and not item["image_url"].startswith("https://placehold"):
        result = r2_upload_image(item["image_url"], emit_event=emit_event)
        if not result.get("demo"):
            r2_image_url = result["url"]

    # Upload video
    if item.get("video_url") and not item["video_url"].startswith("https://placehold"):
        result = r2_upload_video(item["video_url"], emit_event=emit_event)
        if not result.get("demo"):
            r2_video_url = result["url"]

    duration = round(time.time() - start, 1)

    update_content_item(content_id, r2_image_url=r2_image_url, r2_video_url=r2_video_url)

    detail = {"duration": duration, "r2_image_url": r2_image_url, "r2_video_url": r2_video_url}
    emit_event(stage, "complete",
               f"Uploaded to R2 in {duration}s. Your media now has permanent URLs that won't expire.",
               detail)
    add_pipeline_log(content_id, stage, "complete", "R2 upload done", json.dumps(detail))

    return 0.0  # R2 storage cost is per-account
```

- [ ] **Step 5: Update run_pipeline to include R2 stage, headshot toggle, and metric tracking**

Update `run_pipeline()` to:
1. Add `_record_stage_metric()` calls after each stage
2. Add R2 upload as stage 6 (between caption and pipeline complete)
3. Use headshot toggle in video stage

Replace the video stage section in `run_pipeline()`:

```python
        # ==================================================================
        # STAGE 4: VIDEO — Generate video (with optional headshot reference)
        # ==================================================================
        cost = stage_video(content_id, item, emit_event)
        total_cost += cost
        item = get_content_item(content_id)
```

Update `stage_video()` to check headshot settings:

```python
def stage_video(content_id, item, emit_event):
    """Generate video via Kie.ai. Optionally uses headshot reference."""
    stage = "video"

    if not item.get("include_video"):
        emit_event(stage, "skipped", "Video generation skipped — you can enable it when creating content.")
        add_pipeline_log(content_id, stage, "skipped", "include_video is False")
        return 0.0

    start = time.time()
    update_content_item(content_id, status="videoing")

    video_prompt = item.get("image_prompt", item.get("script", ""))
    update_content_item(content_id, video_prompt=video_prompt)

    # Check headshot toggle
    headshot_enabled = get_setting("headshot_enabled", "false") == "true"
    headshot_url = get_setting("headshot_url", "")

    if headshot_enabled and headshot_url:
        emit_event(stage, "started", "Creating video with Veo 3.1 + your headshot! The AI will place you in the scene. This uses the reference_images feature.")
        add_pipeline_log(content_id, stage, "started", "Kie.ai Veo 3.1 with headshot reference")
        update_content_item(content_id, headshot_used=1)
        video_result = generate_video_with_reference(video_prompt, headshot_url, emit_event=emit_event)
    else:
        emit_event(stage, "started", "Creating a video with Kie.ai's Veo 3.1 model. Videos take longer than images — watch the polling!")
        add_pipeline_log(content_id, stage, "started", "Kie.ai Veo 3.1")
        video_result = generate_video(video_prompt, emit_event=emit_event)

    duration = round(time.time() - start, 1)

    update_content_item(
        content_id,
        status="videoed",
        video_url=video_result.get("video_url", ""),
        video_task_id=video_result.get("task_id", "")
    )

    cost = video_result.get("cost", 0.0)
    _record_stage_metric(content_id, "video", duration=duration, cost=cost)

    detail = {
        "duration": duration,
        "video_url": video_result.get("video_url", ""),
        "task_id": video_result.get("task_id", ""),
        "cost": cost,
        "demo": video_result.get("demo", False),
        "headshot_used": headshot_enabled and bool(headshot_url)
    }

    emit_event(stage, "complete",
               f"Video done in {duration}s! Cost: ${cost:.4f}." + (" (with your headshot!)" if headshot_enabled and headshot_url else ""),
               detail)
    add_pipeline_log(content_id, stage, "complete",
                     f"Video ready: {video_result.get('task_id', 'N/A')}", json.dumps(detail))

    return cost
```

Add `_record_stage_metric()` calls after each existing stage in `run_pipeline()` and add the R2 stage call:

```python
        # After each stage's cost = stage_xxx(...) line, add:
        _record_stage_metric(content_id, "scrape", duration=..., cost=cost)
        # (The duration needs to be captured in each stage function)

        # Add R2 stage between caption and pipeline complete:
        # ==================================================================
        # STAGE 6: R2 UPLOAD — Permanent storage
        # ==================================================================
        cost = stage_r2_upload(content_id, item, emit_event)
        total_cost += cost
        item = get_content_item(content_id)
```

Inside each stage function (`stage_scrape`, `stage_script`, `stage_image`, `stage_caption`), add a `_record_stage_metric(content_id, stage_name, duration=duration, cost=cost)` call just before the `return cost` line. Each function already has `duration` and `cost` as local variables. Do NOT call `_record_stage_metric` from `run_pipeline()` — it belongs inside each stage where duration/cost are available.

Update status transitions to match spec:
- `stage_caption` should set `status="captioning"` at start and `status="captioned"` on completion
- `stage_scrape` should transition properly through `scraping` -> next stage
- Fix `stage_caption()` bug: the first `emit_event` call references `platforms` variable before it is defined on line 332. Move the `platforms` definition before the emit call.

**IMPORTANT:** Update all `status="error"` to `status="failed"` throughout `pipeline.py`:
- In `run_pipeline()` except block (line 111): change `status="error"` to `status="failed"`
- In `stage_publish()` except block (line 411): change `status="error"` to `status="failed"`
- This matches the spec: `failed` replaces the old `error` status

- [ ] **Step 6: Run test to verify it passes**

Run: `cd "/Users/jonathanacuna/Documents/VS Code Programs/Content Automation Demo For Claude Workshop" && python -m pytest tests/test_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add pipeline.py tests/test_pipeline.py
git commit -m "feat: R2 upload stage, headshot toggle, per-stage cost/duration tracking"
```

---

## Task 6: Update App Routes (CAM API + Scheduling Thread + Headshot Upload)

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add CAM API endpoints and remove old routes**

Replace the `/create` and `/calendar` routes with `/cam`. Add all CAM API endpoints. Add headshot upload endpoint. Add scheduling background thread.

Key changes to `app.py`:

1. Remove `/create` route, replace with `/cam`
2. Remove `/calendar` route
3. Add `GET /cam/api/queue`
4. Add `GET /cam/api/calendar`
5. Add `POST /cam/api/create` (wraps `/api/generate`)
6. Add `POST /cam/api/approve/<id>`
7. Add `POST /cam/api/retry/<id>`
8. Add `DELETE /cam/api/item/<id>`
9. Add `POST /api/settings/headshot`
10. Add background scheduling thread

Replace the `/create` route:

```python
    @app.route("/cam")
    @login_required
    def cam():
        """CAM: Content Automation Machine — queue + mini-calendar interface."""
        return render_template("cam.html", current_page="cam")
```

Remove the `/calendar` route entirely.

Add CAM API endpoints:

```python
    # -------------------------------------------------------------------
    # CAM API ENDPOINTS
    # -------------------------------------------------------------------

    @app.route("/cam/api/queue")
    @login_required
    def cam_api_queue():
        """Queue data for CAM interface — processing, completed, failed items."""
        from models import list_content_items_by_statuses

        processing_statuses = ["draft", "scraping", "scripting", "scripted", "imaging", "imaged",
                               "videoing", "videoed", "captioning", "captioned", "uploading"]
        completed_statuses = ["ready", "scheduled", "published"]
        failed_statuses = ["failed"]

        processing = list_content_items_by_statuses(processing_statuses)
        completed = list_content_items_by_statuses(completed_statuses)
        failed = list_content_items_by_statuses(failed_statuses)

        # Add progress percentage to each item
        progress_map = {
            "draft": 0, "scraping": 10, "scripting": 20, "scripted": 25,
            "imaging": 40, "imaged": 50, "videoing": 55, "videoed": 70,
            "captioning": 75, "captioned": 80, "uploading": 85,
            "ready": 95, "scheduled": 97, "published": 100, "failed": 0
        }
        for item_list in [processing, completed, failed]:
            for item in item_list:
                item["progress"] = progress_map.get(item.get("status", "draft"), 0)

        return jsonify({
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "totals": {
                "processing": len(processing),
                "completed": len(completed),
                "failed": len(failed)
            }
        })

    @app.route("/cam/api/calendar")
    @login_required
    def cam_api_calendar():
        """Monthly content counts for mini-calendar."""
        from models import get_calendar_counts
        year = request.args.get("year", datetime.now().year, type=int)
        month = request.args.get("month", datetime.now().month, type=int)
        counts = get_calendar_counts(year, month)
        return jsonify(counts)

    @app.route("/cam/api/create", methods=["POST"])
    @login_required
    def cam_api_create():
        """Create content and start pipeline. Wraps /api/generate."""
        return api_generate()

    @app.route("/cam/api/approve/<int:item_id>", methods=["POST"])
    @login_required
    def cam_api_approve(item_id):
        """Approve a ready item and schedule it."""
        item = get_content_item(item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404
        if item["status"] not in ("ready", "captioned"):
            return jsonify({"error": f"Item must be ready to approve, currently: {item['status']}"}), 400

        data = request.json or {}
        scheduled_at = data.get("scheduled_at")  # ISO datetime string

        if scheduled_at:
            update_content_item(item_id, status="scheduled", scheduled_at=scheduled_at)
            return jsonify({"success": True, "message": f"Scheduled for {scheduled_at}"})
        else:
            # Publish immediately
            update_content_item(item_id, status="scheduled", scheduled_at=datetime.now().isoformat())
            return jsonify({"success": True, "message": "Publishing now"})

    @app.route("/cam/api/retry/<int:item_id>", methods=["POST"])
    @login_required
    def cam_api_retry(item_id):
        """Reset a failed item back to draft for reprocessing."""
        item = get_content_item(item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404
        update_content_item(item_id, status="draft")
        return jsonify({"success": True, "message": "Item reset to draft"})

    @app.route("/cam/api/item/<int:item_id>", methods=["DELETE"])
    @login_required
    def cam_api_delete(item_id):
        """Delete a content item (hard delete with CASCADE on logs)."""
        item = get_content_item(item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404
        delete_content_item(item_id)
        return jsonify({"success": True, "message": "Item deleted"})
```

Add headshot upload endpoint:

```python
    @app.route("/api/settings/headshot", methods=["POST"])
    @login_required
    def api_headshot_upload():
        """Upload headshot image to R2."""
        from services.r2_storage import upload_headshot, is_configured

        if not is_configured():
            return jsonify({"error": "R2 Storage must be configured first"}), 400

        if "headshot" not in request.files:
            return jsonify({"error": "No headshot file provided"}), 400

        file = request.files["headshot"]
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        result = upload_headshot(file.read(), file.filename)
        if result.get("error"):
            return jsonify({"error": result["error"]}), 500

        set_setting("headshot_url", result["url"])
        return jsonify({"success": True, "url": result["url"]})
```

Add scheduling background thread (inside `create_app()`, after `init_db()`):

```python
    # -- Background scheduling thread --
    def scheduling_loop():
        """Check for scheduled items that are due and publish them."""
        import time as _time
        while True:
            _time.sleep(60)  # Check every 60 seconds
            try:
                with app.app_context():
                    from models import list_content_items_by_statuses
                    scheduled = list_content_items_by_statuses(["scheduled"])
                    now = datetime.now().isoformat()
                    for item in scheduled:
                        if item.get("scheduled_at") and item["scheduled_at"] <= now:
                            try:
                                stage_publish(item["id"], lambda *a, **kw: None)
                            except Exception as e:
                                update_content_item(item["id"], status="failed")
            except Exception:
                pass  # Don't crash the thread

    scheduler_thread = threading.Thread(target=scheduling_loop, daemon=True)
    scheduler_thread.start()
```

Update the settings page route to include new settings:

```python
    @app.route("/settings")
    @login_required
    def settings_page():
        settings = {
            "openrouter_api_key": get_setting("openrouter_api_key", ""),
            "firecrawl_api_key": get_setting("firecrawl_api_key", ""),
            "kie_api_key": get_setting("kie_api_key", ""),
            "getlate_api_key": get_setting("getlate_api_key", ""),
            "default_model": get_setting("default_model", "google/gemini-2.5-flash"),
            "default_platform": get_setting("default_platform", "instagram"),
            "headshot_url": get_setting("headshot_url", ""),
            "headshot_enabled": get_setting("headshot_enabled", "false"),
            "r2_account_id": get_setting("r2_account_id", ""),
            "r2_access_key_id": get_setting("r2_access_key_id", ""),
            "r2_secret_access_key": get_setting("r2_secret_access_key", ""),
            "r2_bucket_name": get_setting("r2_bucket_name", ""),
            "r2_public_url": get_setting("r2_public_url", ""),
        }
        return render_template("settings.html", settings=settings, current_page="settings")
```

Also update `api_settings_save` to handle R2 and headshot env vars:

```python
            env_map = {
                "openrouter_api_key": "OPENROUTER_API_KEY",
                "firecrawl_api_key": "FIRECRAWL_API_KEY",
                "kie_api_key": "KIE_API_KEY",
                "getlate_api_key": "GETLATE_API_KEY",
                "r2_account_id": "R2_ACCOUNT_ID",
                "r2_access_key_id": "R2_ACCESS_KEY_ID",
                "r2_secret_access_key": "R2_SECRET_ACCESS_KEY",
                "r2_bucket_name": "R2_BUCKET_NAME",
                "r2_public_url": "R2_PUBLIC_URL",
            }
```

- [ ] **Step 2: Update content_detail route to parse captions and compute stage info**

```python
    @app.route("/content/<int:item_id>")
    @login_required
    def content_detail(item_id):
        item = get_content_item(item_id)
        if not item:
            flash("Content item not found", "error")
            return redirect(url_for("dashboard"))
        logs = get_pipeline_logs(item_id)

        # Parse captions JSON for template
        captions_parsed = {}
        if item.get("captions"):
            try:
                captions_parsed = json.loads(item["captions"])
            except (json.JSONDecodeError, TypeError):
                pass
        item["captions_parsed"] = captions_parsed

        # Parse stage durations and costs
        stage_durations = {}
        stage_costs = {}
        if item.get("stage_durations"):
            try:
                stage_durations = json.loads(item["stage_durations"])
            except (json.JSONDecodeError, TypeError):
                pass
        if item.get("stage_costs"):
            try:
                stage_costs = json.loads(item["stage_costs"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Build stage info for template
        stages = ["scrape", "script", "image", "video", "caption", "upload"]
        stage_info = []
        for s in stages:
            stage_info.append({
                "name": s,
                "duration": stage_durations.get(s, 0),
                "cost": stage_costs.get(s, 0),
            })

        # Compute completed/error/skipped stages from logs
        completed_stages = set()
        error_stages = set()
        skipped_stages = set()
        for log in logs:
            if log["status"] == "complete":
                completed_stages.add(log["stage"])
            elif log["status"] == "error":
                error_stages.add(log["stage"])
            elif log["status"] == "skipped":
                skipped_stages.add(log["stage"])

        return render_template("content_detail.html", item=item, logs=logs,
                               stage_info=stage_info,
                               completed_stages=completed_stages,
                               error_stages=error_stages,
                               skipped_stages=skipped_stages,
                               current_page="content")
```

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: CAM API routes, headshot upload, scheduling thread, enhanced detail route"
```

---

## Task 7: Update Navigation (base.html)

**Files:**
- Modify: `templates/base.html`

- [ ] **Step 1: Replace Create/Calendar links with CAM**

In `templates/base.html`, replace the nav section:

```html
                <a href="/cam"
                   class="sidebar-link {% if current_page == 'cam' %}active{% endif %}"
                   @click="sidebarOpen = false">
                    <i data-lucide="play-circle" class="sidebar-icon"></i>
                    CAM
                </a>
```

Remove the Calendar link entirely. Keep Dashboard and Settings.

- [ ] **Step 2: Commit**

```bash
git add templates/base.html
git commit -m "feat: replace Create/Calendar nav links with CAM"
```

---

## Task 8: CAM Template (cam.html)

**Files:**
- Create: `templates/cam.html`
- Modify: `static/css/custom.css`

- [ ] **Step 1: Create the CAM page template**

Create `templates/cam.html` with:
- Hero textarea input with auto-detect URL vs idea
- Queue tabs (Processing / Completed / Failed)
- Queue cards with progress bars, status badges, time ago, action buttons
- Active processing card with SSE log feed
- Mini-calendar sidebar with month navigation
- Weekly summary

The template uses Alpine.js for all interactivity:
- `camApp()` — main Alpine data function
- `refreshQueue()` — polls `/cam/api/queue` every 5 seconds
- `submitContent()` — creates content via `/cam/api/create`, opens SSE stream
- `renderCalendar()` — fetches and renders mini-calendar via `/cam/api/calendar`
- `approveItem(id)` — opens date/time modal, calls `/cam/api/approve/<id>`
- `retryItem(id)` — calls `/cam/api/retry/<id>`
- `deleteItem(id)` — calls `/cam/api/item/<id>` DELETE
- `timeAgo(date)` — relative time helper

Full template should follow the dark gold premium theme, matching existing design patterns in `custom.css`.

**IMPORTANT NOTE for implementer:** `/cam/api/create` returns an SSE stream (`text/event-stream`), not JSON. The Alpine.js `submitContent()` function must use `fetch` with a `ReadableStream` reader (or `EventSource`), NOT `fetch().then(r => r.json())`. Follow the same pattern used in the existing `create.html` template's `generateContent()` function.

- [ ] **Step 2: Add CAM-specific CSS to custom.css**

Add styles for:
- `.cam-layout` — grid layout (1fr 340px) for content + sidebar
- `.cam-hero` — textarea input area at top
- `.cam-tabs` — Processing/Completed/Failed tab bar
- `.cam-card` — queue card with progress bar
- `.cam-progress-bar` — gold progress bar
- `.cam-status-badge` — status badges
- `.cam-mini-cal` — mini-calendar container
- `.cam-cal-grid` — 7-column day grid
- `.cam-cal-day` — individual day cell with count
- `.cam-sse-log` — inline SSE log feed on active card
- `.cam-time-ago` — relative time display

- [ ] **Step 3: Commit**

```bash
git add templates/cam.html static/css/custom.css
git commit -m "feat: CAM interface — queue cards, mini-calendar, SSE log, auto-detect input"
```

---

## Task 9: Enhanced Content Detail Page

**Files:**
- Modify: `templates/content_detail.html`
- Modify: `static/css/custom.css`

- [ ] **Step 1: Rewrite content_detail.html with visual stage breakdown**

Replace the existing pipeline status card with a visual stage timeline showing:
- Each stage as a node with icon, name, duration, cost
- Color-coded: green (completed), red (error), gray (skipped/waiting), gold (active)
- Total cost and total time prominently displayed
- Connecting lines between stages

Update the cost breakdown card to show per-stage costs from `stage_info`.

Update status badges to handle new statuses (`failed` instead of `error`, `captioned`, `uploading`).

Add approve/schedule modal with date/time picker that calls `/cam/api/approve/<id>`.

Wire up retry button to call `/cam/api/retry/<id>`.

Add R2 storage URLs section showing permanent URLs when available.

- [ ] **Step 2: Add detail page stage timeline CSS**

Add to `custom.css`:
- `.stage-timeline` — horizontal flex layout for stages
- `.stage-node` — circle with icon
- `.stage-connector` — line between nodes
- `.stage-meta` — duration and cost labels below each node
- `.stage-total` — total cost/time display

- [ ] **Step 3: Commit**

```bash
git add templates/content_detail.html static/css/custom.css
git commit -m "feat: visual stage timeline on detail page with per-stage costs and timing"
```

---

## Task 10: Settings Page (Headshot Upload + R2 Config)

**Files:**
- Modify: `templates/settings.html`

- [ ] **Step 1: Add Headshot Upload section**

Add after the GetLate card:

```html
    <!-- Headshot Upload -->
    <div class="service-card">
        <div class="service-header">
            <div class="service-name">
                <span style="font-size: 20px;">&#128247;</span>
                Headshot
            </div>
        </div>
        <p class="service-desc">Upload your headshot photo. When enabled, Veo 3.1 will place you in video scenes using AI reference imaging.</p>

        <!-- Toggle -->
        <div class="mb-4 flex items-center gap-3">
            <label class="input-label mb-0">Use headshot in videos</label>
            <button class="toggle-switch"
                    :class="{ 'active': headshot.enabled }"
                    @click="headshot.enabled = !headshot.enabled; saveHeadshotToggle()">
                <span class="toggle-knob"></span>
            </button>
        </div>

        <!-- Current headshot preview -->
        <div x-show="headshot.url" class="mb-4">
            <img :src="headshot.url" class="rounded-lg" style="max-width: 120px; max-height: 120px; border: 2px solid var(--border);">
        </div>

        <!-- Upload -->
        <div class="mb-4">
            <label class="input-label">Upload Photo (JPG/PNG)</label>
            <input type="file" accept="image/jpeg,image/png" class="input"
                   @change="uploadHeadshot($event)">
        </div>
    </div>
```

- [ ] **Step 2: Add R2 Storage section**

```html
    <!-- R2 Storage -->
    <div class="service-card">
        <div class="service-header">
            <div class="service-name">
                <span style="font-size: 20px;">&#9729;</span>
                Cloudflare R2 Storage
            </div>
            <div class="service-status"
                 :class="services.r2.connected ? 'connected' : 'disconnected'">
                <!-- same connected/disconnected template -->
            </div>
        </div>
        <p class="service-desc">Permanent media storage. Without R2, AI-generated URLs expire. With R2, your images and videos are stored forever.</p>

        <!-- Fields: Account ID, Access Key, Secret Key, Bucket Name, Public URL -->
        <!-- Follow same pattern as other service cards -->
    </div>
```

- [ ] **Step 3: Add Alpine.js handlers for headshot upload and R2 save**

Add to `settingsApp()`:

```javascript
        headshot: {
            url: {{ (settings.get('headshot_url', '') if settings else '')|tojson }},
            enabled: {{ 'true' if settings and settings.get('headshot_enabled') == 'true' else 'false' }},
            uploading: false
        },
        services: {
            // ... existing services ...
            r2: {
                accountId: {{ (settings.get('r2_account_id', '') if settings else '')|tojson }},
                accessKeyId: {{ (settings.get('r2_access_key_id', '') if settings else '')|tojson }},
                secretAccessKey: {{ (settings.get('r2_secret_access_key', '') if settings else '')|tojson }},
                bucketName: {{ (settings.get('r2_bucket_name', '') if settings else '')|tojson }},
                publicUrl: {{ (settings.get('r2_public_url', '') if settings else '')|tojson }},
                connected: {{ 'true' if settings and settings.get('r2_account_id') else 'false' }},
                showKey: false,
                testing: false
            }
        },

        uploadHeadshot(event) {
            const file = event.target.files[0];
            if (!file) return;
            this.headshot.uploading = true;
            const formData = new FormData();
            formData.append('headshot', file);
            fetch('/api/settings/headshot', { method: 'POST', body: formData })
                .then(r => r.json())
                .then(data => {
                    this.headshot.uploading = false;
                    if (data.success) {
                        this.headshot.url = data.url;
                        showToast('Headshot uploaded!', 'success');
                    } else {
                        showToast(data.error || 'Upload failed', 'error');
                    }
                })
                .catch(() => { this.headshot.uploading = false; showToast('Upload failed', 'error'); });
        },

        saveHeadshotToggle() {
            fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ headshot_enabled: this.headshot.enabled ? 'true' : 'false' })
            }).then(() => showToast('Headshot toggle saved', 'success'));
        }
```

- [ ] **Step 4: Add toggle switch CSS**

```css
.toggle-switch {
    width: 44px; height: 24px;
    background: var(--bg-tertiary); border: 1px solid var(--border);
    border-radius: 12px; position: relative; cursor: pointer; transition: all 0.2s;
}
.toggle-switch.active { background: var(--gold); border-color: var(--gold); }
.toggle-knob {
    width: 18px; height: 18px; background: white; border-radius: 50%;
    position: absolute; top: 2px; left: 2px; transition: transform 0.2s;
}
.toggle-switch.active .toggle-knob { transform: translateX(20px); }
```

- [ ] **Step 5: Commit**

```bash
git add templates/settings.html static/css/custom.css
git commit -m "feat: headshot upload + R2 Storage config sections in Settings"
```

---

## Task 11: Update .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add R2 environment variables**

Append to `.env.example`:

```bash

# -- Cloudflare R2 Storage (permanent media URLs) --
# Get your keys at: https://dash.cloudflare.com/ > R2
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_URL=
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "feat: add R2 env vars to .env.example"
```

---

## Task 12: Playwright E2E Smoke Tests

**Files:**
- Create: `tests/e2e/test_smoke.py`

- [ ] **Step 1: Install Playwright**

```bash
pip install playwright pytest-playwright
playwright install chromium
```

- [ ] **Step 2: Write smoke tests**

```python
# tests/e2e/test_smoke.py
"""
Playwright E2E smoke tests for the Content Automation Demo.
Tests core UI flows in demo mode (no API keys required).
"""
import pytest
from playwright.sync_api import Page, expect


BASE_URL = "http://localhost:5000"


@pytest.fixture(autouse=True)
def login(page: Page):
    """Log in before each test."""
    page.goto(f"{BASE_URL}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{BASE_URL}/")
    yield


def test_dashboard_loads(page: Page):
    """Dashboard should load with content grid."""
    page.goto(BASE_URL)
    expect(page.locator("h1")).to_contain_text("Dashboard")


def test_cam_page_loads(page: Page):
    """CAM page should load with textarea and queue."""
    page.goto(f"{BASE_URL}/cam")
    expect(page.locator("textarea")).to_be_visible()


def test_cam_auto_detect_url(page: Page):
    """Typing a URL should auto-detect as URL input."""
    page.goto(f"{BASE_URL}/cam")
    page.fill("textarea", "https://example.com/article")
    # Should show URL indicator
    expect(page.locator('[data-input-type="url"]')).to_be_visible()


def test_cam_auto_detect_idea(page: Page):
    """Typing text should auto-detect as idea input."""
    page.goto(f"{BASE_URL}/cam")
    page.fill("textarea", "AI trends for 2026")
    expect(page.locator('[data-input-type="idea"]')).to_be_visible()


def test_cam_mini_calendar_renders(page: Page):
    """Mini calendar should be visible on CAM page."""
    page.goto(f"{BASE_URL}/cam")
    expect(page.locator(".cam-mini-cal")).to_be_visible()


def test_settings_page_has_headshot_section(page: Page):
    """Settings should have headshot upload section."""
    page.goto(f"{BASE_URL}/settings")
    expect(page.locator("text=Headshot")).to_be_visible()


def test_settings_page_has_r2_section(page: Page):
    """Settings should have R2 Storage section."""
    page.goto(f"{BASE_URL}/settings")
    expect(page.locator("text=Cloudflare R2")).to_be_visible()


def test_content_detail_has_stage_timeline(page: Page):
    """Content detail page should show stage timeline (if item exists)."""
    # Create an item first via API
    page.goto(f"{BASE_URL}/cam")
    page.fill("textarea", "Test idea for smoke test")
    page.click('button:has-text("Generate")')
    page.wait_for_timeout(3000)  # Wait for pipeline to start

    # Navigate to the item
    page.goto(BASE_URL)
    first_item = page.locator(".content-card").first
    if first_item.is_visible():
        first_item.click()
        expect(page.locator(".stage-timeline")).to_be_visible()


def test_no_console_errors(page: Page):
    """No JavaScript console errors on key pages."""
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    for path in ["/", "/cam", "/settings"]:
        page.goto(f"{BASE_URL}{path}")
        page.wait_for_timeout(1000)

    assert len(errors) == 0, f"Console errors found: {errors}"


def test_all_routes_return_200(page: Page):
    """All authenticated routes should return 200."""
    for path in ["/", "/cam", "/settings"]:
        response = page.goto(f"{BASE_URL}{path}")
        assert response.status == 200, f"{path} returned {response.status}"
```

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_smoke.py
git commit -m "test: Playwright E2E smoke tests for CAM interface, settings, and detail page"
```

---

## Task 13: CMUX Browser Smoke Test

- [ ] **Step 1: Run CMUX smoke test**

Use the cmux-browser-test skill to run a browser smoke test against `http://localhost:5000` verifying:
- Login page loads
- Can log in
- `/cam` page loads
- Settings page loads
- No console errors

- [ ] **Step 2: Fix any issues found**

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "fix: address issues found in CMUX smoke testing"
```

---

## Task 14: Final Verification

- [ ] **Step 1: Run all unit tests**

```bash
cd "/Users/jonathanacuna/Documents/VS Code Programs/Content Automation Demo For Claude Workshop"
python -m pytest tests/ -v --tb=short
```

- [ ] **Step 2: Run Playwright E2E tests**

```bash
cd "/Users/jonathanacuna/Documents/VS Code Programs/Content Automation Demo For Claude Workshop"
python app.py &  # Start server in background
sleep 2
python -m pytest tests/e2e/ -v --tb=short
kill %1  # Stop background server
```

- [ ] **Step 3: Manual verification checklist**

- [ ] App starts without errors
- [ ] Login works
- [ ] `/cam` loads with textarea, queue tabs, mini-calendar
- [ ] Submitting an idea shows SSE processing in queue card
- [ ] Queue refreshes via polling
- [ ] Click card navigates to `/content/<id>`
- [ ] Detail page shows visual stage timeline with costs/timing
- [ ] Settings has Headshot and R2 sections
- [ ] Nav bar shows CAM (not Create/Calendar)

- [ ] **Step 4: Commit any remaining fixes**

```bash
git add -A
git commit -m "fix: final verification fixes"
```
