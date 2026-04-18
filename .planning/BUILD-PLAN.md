# Build Plan — Content Automation Demo

## Build Order
All phases built tonight. 3 parallel workstreams, then integration.

## Workstream 1: Backend Core
- `app.py` — Flask app factory, routes, SSE streaming, auth
- `models.py` — SQLite with context manager (content_items, pipeline_logs, settings, schedule_slots)
- `pipeline.py` — Pipeline orchestrator that emits SSE events per stage
- `seed.py` — Demo data
- `requirements.txt`, `Procfile`, `.env.example`

## Workstream 2: Service Integrations
- `services/__init__.py`
- `services/openrouter.py` — LLM text generation (script + captions + image prompts)
- `services/firecrawl.py` — URL → markdown article
- `services/kie_ai.py` — Image gen (Nano Banana Pro) + Video gen (Veo 3.1) with polling
- `services/getlate.py` — Multi-platform publishing

## Workstream 3: Frontend (Templates + CSS)
- `static/css/custom.css` — Full dark gold brand system
- `templates/base.html` — Root layout + sidebar + CDN deps
- `templates/dashboard.html` — Content library grid with status badges
- `templates/create.html` — URL/idea input + platform selector + pipeline X-ray
- `templates/content_detail.html` — Single item view with full pipeline log
- `templates/calendar.html` — Monthly publishing calendar
- `templates/settings.html` — API keys + model config

## Interface Contract (shared between workstreams)

### Routes
| Method | Route | Template/Response |
|--------|-------|-------------------|
| GET | `/` | dashboard.html |
| GET | `/create` | create.html |
| GET | `/content/<id>` | content_detail.html |
| GET | `/calendar` | calendar.html |
| GET | `/settings` | settings.html |
| POST | `/api/generate` | SSE stream |
| GET | `/api/stream/<id>` | SSE stream (reconnect) |
| GET | `/api/content` | JSON list |
| GET | `/api/content/<id>` | JSON detail + logs |
| DELETE | `/api/content/<id>` | JSON success |
| POST | `/api/settings` | JSON success |
| POST | `/api/publish/<id>` | SSE stream |
| GET | `/api/health` | JSON status |
| POST | `/login` | redirect |
| GET | `/logout` | redirect |

### Database Schema
```sql
content_items: id, input_text, input_type, platform, article_text, article_title,
    word_count, script, captions, image_prompt, image_url, image_task_id,
    video_prompt, video_url, video_task_id, include_video, status, cost_total,
    scheduled_at, published_at, created_at, updated_at

pipeline_logs: id, content_id, stage, status, message, detail, created_at

settings: key, value

schedule_slots: id, content_id, scheduled_datetime, platform, status,
    published_at, error_message, created_at
```

### Status Flow
draft → scraping → scraped → scripting → scripted → imaging → imaged →
videoing → videoed → ready → scheduled → publishing → published | error

### Pipeline Stages
1. scrape — FireCrawl (skip if input_type='idea')
2. script — OpenRouter LLM
3. image — Kie.ai Nano Banana Pro (async poll)
4. video — Kie.ai Veo 3.1 (async poll, optional)
5. caption — OpenRouter LLM (platform-specific)
6. publish — GetLate.dev

### SSE Event Format
```json
{"stage": "script", "status": "started", "message": "Sending to OpenRouter...", "timestamp": "23:14:03"}
{"stage": "script", "status": "progress", "message": "Streaming response... 156 tokens", "detail": {"tokens_in": 847}}
{"stage": "script", "status": "complete", "message": "Script generated (312 tokens)", "detail": {"duration": 2.1, "cost": 0.002}}
{"stage": "image", "status": "polling", "message": "Polling Kie.ai... status: processing", "detail": {"attempt": 3}}
```

### Template Variables
All templates receive: `current_page` (str), `settings` (dict)
dashboard.html: `items` (list of content_items)
create.html: (empty — Alpine.js handles state)
content_detail.html: `item` (content_item dict), `logs` (list of pipeline_logs)
calendar.html: `slots` (list of schedule_slots with content), `current_month`, `current_year`
settings.html: `settings` (dict of key-value pairs)
