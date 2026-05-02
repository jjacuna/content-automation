# CAM Interface Upgrade — Design Spec

## Overview

Upgrade the Content Automation Demo from a simple pipeline X-ray viewer to a production-style Content Automation Machine (CAM) interface. Students get a queue-based workflow with calendar scheduling, R2 storage, enhanced video generation (Veo 3.1 with optional headshot reference), and a visual stage-by-stage detail page showing costs and timing.

**Reference project:** Content Automation Machine 2.0 (CAM 2.0)
**Approach:** Incremental overlay — replace `/create` with `/cam`, enhance existing services and pages, keep flat file structure.

## Scope

### In Scope
- `/cam` interface: queue cards, mini-calendar, auto-detect textarea input
- Veo 3.1 video generation with optional headshot scene placement
- Nano Banana Pro image generation (explicit model)
- R2 Storage for permanent media URLs
- GetLate.dev scheduling with date/time picker
- Simple scheduling engine (background thread, 60s polling)
- Visual content detail page with stage breakdown, costs, timing
- Headshot upload + toggle in Settings
- R2 configuration in Settings
- Playwright + CMUX smoke testing

### Out of Scope
- No HN (Hacker News)
- No Eleven Labs / voice generation
- No B-roll / multi-video compositing
- No video editing / Shotstack
- No HeyGen avatars
- No complex scheduling engine (rate limits, platform queues)
- No carousel/multi-image posts

## Route & Page Structure

### Replaced
- `/create` replaced by `/cam` (new CAM interface — main page)
- `/calendar` removed (mini-calendar lives inside `/cam`)

### Kept & Enhanced
- `/` — Dashboard (content library grid, unchanged)
- `/content/<id>` — Detail page (major visual upgrade)
- `/settings` — Settings (add headshot upload, R2 config, headshot toggle)
- `/login`, `/logout` — unchanged

### New API Endpoints
- `GET /cam/api/queue` — polling endpoint for queue cards
- `GET /cam/api/calendar` — monthly content counts for mini-calendar
- `POST /cam/api/create` — submit new content (topic/URL)
- `POST /cam/api/approve/<id>` — approve + schedule with date/time
- `POST /cam/api/retry/<id>` — retry failed items
- `DELETE /cam/api/item/<id>` — delete item

### Kept API Endpoints
- `POST /api/generate` — SSE stream for active pipeline
- `GET /api/stream/<id>` — SSE reconnection

## `/cam` Interface Layout

### Left Side (Main Area)
- **Hero input** — textarea at top, auto-detects URL vs idea, submit button
- **Queue tabs** — "Processing" | "Completed" | "Failed"
- **Queue cards** — each shows:
  - Title, status badge, progress bar (0-100%)
  - Time ago (e.g. "3 min ago")
  - Action buttons: retry (failed), delete, approve (ready items)
  - Click card navigates to `/content/<id>`
- **Active processing card** — SSE log feed inline showing real-time stage updates

### Right Side (Sidebar)
- **Mini-calendar** — month view, daily content counts, prev/next navigation, color-coded days
- **Weekly summary** — total items this week

### Real-time Strategy
- SSE for the actively processing item (real-time stage updates)
- Polling every 5 seconds for queue list updates

## Content Detail Page (`/content/<id>`)

### Visual Stage Breakdown
- Pipeline timeline showing each stage with:
  - Stage name + icon
  - Status indicator (completed/failed/skipped)
  - Duration (e.g. "2.3s", "45s")
  - Cost (e.g. "$0.003", "$0.19")
- Total cost prominently displayed
- Total processing time from start to finish

### Output Panels
- Script (copyable text)
- Image preview (full size)
- Video player
- Captions (tabbed by platform)
- R2 storage URLs

### Actions
- Approve/Schedule (date/time picker) — if ready
- Retry — if failed
- Delete

## Pipeline

### 7-Stage Flow

| # | Stage | Service | Notes |
|---|-------|---------|-------|
| 1 | Scrape | FireCrawl | Skip if idea input |
| 2 | Script | OpenRouter LLM | No change |
| 3 | Image | Kie.ai Nano Banana Pro | 9:16 aspect ratio |
| 4 | Video | Kie.ai Veo 3.1 | Optional headshot reference |
| 5 | Captions | OpenRouter LLM | Multi-platform |
| 6 | R2 Upload | Cloudflare R2 | New — permanent URLs |
| 7 | Publish | GetLate.dev | Enhanced — scheduled |

### Headshot Toggle
- Enabled in Settings + headshot uploaded: Video stage sends headshot as reference image to Veo 3.1
- Disabled: normal text-to-video (no reference)

### Status Flow
```
idea -> scraping -> scripting -> imaging -> videoing -> captioning -> uploading -> ready -> scheduled -> published
```
Error states: `failed`, `blocked`

### Progress Mapping
| Status | Progress |
|--------|----------|
| idea | 0% |
| scraping | 10% |
| scripting | 25% |
| imaging | 40% |
| videoing | 60% |
| captioning | 75% |
| uploading | 85% |
| ready | 95% |
| scheduled | 97% |
| published | 100% |

## New Service: R2 Storage (`services/r2_storage.py`)

- `upload_image(image_url)` — download from Kie.ai temp URL, upload to R2
- `upload_video(video_url)` — download video, upload to R2
- `get_presigned_url(key)` — generate presigned URL for playback
- `test_connection()` — validate R2 credentials
- Uses boto3 S3-compatible client

### Folder Organization
- `images/` — generated images
- `videos/` — generated videos
- `headshots/` — uploaded headshots

## Updated Service: Kie.ai (`services/kie_ai.py`)

- Add Veo 3.1 endpoint (`/veo/generate` + `/veo/get-1080p-video`)
- Add reference video support (headshot as reference image for scene placement)
- Update image generation to explicitly use Nano Banana Pro model
- Clean prompts (remove markdown formatting)

## Updated Service: GetLate (`services/getlate.py`)

- Add `scheduled_at` parameter for future scheduling
- Use R2 URLs instead of temp Kie.ai URLs
- Parse scheduled time to UTC ISO 8601

## Database Schema Changes

### New Fields on `content_items`

| Field | Type | Purpose |
|-------|------|---------|
| `r2_image_url` | TEXT | Permanent R2 image URL |
| `r2_video_url` | TEXT | Permanent R2 video URL |
| `scheduled_at` | TIMESTAMP | When to publish |
| `headshot_used` | BOOLEAN | Whether headshot reference was used |
| `stage_durations` | TEXT | JSON: stage name -> seconds |
| `stage_costs` | TEXT | JSON: stage name -> dollar cost |

### Settings Additions
- `headshot_url` — uploaded headshot R2 URL
- `headshot_enabled` — toggle on/off (default off)
- `r2_account_id`, `r2_access_key_id`, `r2_secret_access_key`, `r2_bucket_name`, `r2_public_url`

### New Environment Variables
```
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_URL=
```

## Settings Page Updates

### New Sections
- **Headshot Upload:** file input (JPG/PNG), preview thumbnail, toggle switch
- **R2 Storage:** Account ID, Access Key ID, Secret Access Key, Bucket Name, Public URL, Test Connection button

### Existing Sections (unchanged)
- OpenRouter, FireCrawl, Kie.ai, GetLate API keys

## Simple Scheduling Engine

- Approve action opens date/time picker modal (defaults to "now")
- Stores `scheduled_at` on content item, sets status to `scheduled`
- Background thread polls every 60 seconds:
  - Queries `status = 'scheduled'` AND `scheduled_at <= now`
  - Calls GetLate.dev publish for each due item
  - Updates to `published` on success, `failed` on error
- No Celery, no cron — Flask background thread with timer loop
- Mini-calendar shows scheduled items on their target dates

## Testing Strategy

### Playwright E2E Tests
- Login flow
- `/cam` loads, textarea works, URL vs idea auto-detection
- Submit content, SSE stream fires, queue card appears with progress
- Queue polling updates cards
- Click card navigates to `/content/<id>`
- Detail page shows stage breakdown, costs, timing, outputs
- Approve flow with date/time picker schedules item
- Retry failed item
- Delete item
- Mini-calendar renders, shows scheduled items
- Settings: save API keys, upload headshot, toggle, configure R2

### CMUX Browser Smoke Tests
- App boots and serves pages
- All routes return 200
- No console errors
- CSS/JS loads correctly

### Demo Mode
- All tests work without API keys (demo fallbacks for every service)

## Design System

No changes — keep existing dark gold premium theme:
- Primary BG: `#0B0B0D`
- Card BG: `#17181C`
- Gold accent: `#C7A35A`
- Font: Inter
- Tailwind CSS (CDN) + Alpine.js (CDN)
