# Content Automation Demo — PRD
## Claude Workshop Part 2: "The Content Engine"

**Version:** 1.0
**Date:** 2026-04-17
**GitHub:** https://github.com/jjacuna/content-automation
**Sibling Project:** CRM Demo (Part 1) — same brand system, same teaching philosophy

---

## 1. Vision & Purpose

### What This Is
A **teaching-first** content automation app that walks non-technical workshop students through the logic of how APIs chain together to automate complex workflows — specifically, turning a URL or idea into a finished social media post with text, images, and video.

### The Problem It Solves
Students have never used Zapier, Make.com, or n8n. They don't understand:
- How one API's output feeds into another API's input
- Why some API calls are instant and others require polling/waiting
- How a "simple" automation like content creation actually involves 5-7 coordinated services
- What's happening "under the hood" when they press a button

### The Core Differentiator: The Automation X-Ray
Unlike CAM 2.0 (the production app), this demo **shows its work**. Every API call, every stage transition, every polling cycle is visualized in real-time so students can SEE the automation happening. Think of it as an **automation X-ray** — the UI is the teacher.

### Teaching Philosophy (from CRM Part 1)
- **60% UI/UX Polish** — Premium dark gold aesthetic builds confidence
- **40% Functionality** — Core features that actually work
- **No build step** — CDN-only (Tailwind, Alpine.js), pip install, done
- **Phased learning** — Each phase adds one concept, students see it grow

---

## 2. Design System (Inherited from CRM Demo)

### Brand Colors — Dark Gold Premium Theme
| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#0B0B0D` | Page background |
| `--bg-card` | `#17181C` | Card surfaces |
| `--bg-card-hover` | `#1E2025` | Interactive hover |
| `--bg-tertiary` | `#111215` | Nested backgrounds |
| `--gold` | `#C7A35A` | Primary accent, buttons, active states |
| `--gold-hover` | `#B88933` | Button hover |
| `--gold-champagne` | `#E4D3A2` | Highlights, progress bars |
| `--gold-bronze` | `#87652C` | Deep accent |
| `--gold-tint` | `rgba(199,163,90,0.10)` | Subtle backgrounds |
| `--text-primary` | `#F5F0E8` | Main text (cream) |
| `--text-muted` | `#C8C0B4` | Secondary text |
| `--text-subtle` | `#9E978C` | Tertiary text |
| `--border` | `#31343C` | Card/input borders |
| `--success` | `#22c55e` | Stage complete |
| `--warning` | `#f59e0b` | Stage in-progress |
| `--danger` | `#ef4444` | Stage error |

### Typography
- **Font:** Inter (Google Fonts CDN)
- **Headings:** 600-700 weight
- **Body:** 500 weight, 14px base
- **Mono:** SF Mono / Consolas (for log output, stage labels)

### Components
- **Cards:** 12px radius, 20px padding, `#17181C` bg, `#31343C` border
- **Buttons:** 8px radius, gold primary, ghost secondary
- **Inputs:** 8px radius, `#0B0B0D` bg, gold focus border
- **Sidebar:** 200px fixed (collapses on mobile), `#17181C` bg
- **Toast:** Bottom-right, slide-in animation, auto-dismiss 4s
- **Badges:** Gold outline (pending), green (complete), red (error), amber (processing)

### CDN Dependencies (No Build Step)
```html
<!-- CSS -->
<link href="https://cdn.jsdelivr.net/npm/tailwindcss@3/dist/tailwind.min.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

<!-- JS -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
```

---

## 3. Architecture

### Tech Stack
| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Flask 3.x | Lightweight, teachable, matches CRM Part 1 |
| **Database** | SQLite (local) | Zero setup for students, file-based |
| **Templates** | Jinja2 | Server-rendered, no build step |
| **CSS** | Tailwind CSS (CDN) | Utility-first, matches CRM |
| **Interactivity** | Alpine.js (CDN) | Lightweight reactivity |
| **Real-time** | Server-Sent Events (SSE) | Native Flask, no Redis needed |
| **LLM** | OpenRouter API | Routes to Gemini 2.5 Flash / Claude Sonnet 4 |
| **Scraping** | FireCrawl API | URL → clean markdown in one call |
| **Images** | Kie.ai (Nano Banana Pro) | AI image generation with polling |
| **Video** | Kie.ai (Veo 3.1) | AI video generation with polling |
| **Publishing** | GetLate.dev API | Multi-platform scheduling |
| **Deployment** | Railway + gunicorn | One-click deploy, matches CRM |

### Future Roadmap (Not in class)
- **Cloudflare R2** — File storage for generated media
- **PostgreSQL** — Multi-user database on Railway
- **Voice/Avatar** — Fish.audio TTS + HeyGen avatar (from CAM 2.0)

### Directory Structure
```
content-automation-demo/
├── app.py                      # Flask app factory + config + SSE stream
├── models.py                   # SQLAlchemy: ContentItem, PipelineLog, Settings
├── pipeline.py                 # Pipeline orchestrator + stage definitions
├── services/
│   ├── openrouter.py           # LLM text generation
│   ├── firecrawl.py            # URL scraping
│   ├── kie_ai.py               # Image + video generation
│   └── getlate.py              # Social media publishing
├── seed.py                     # Demo data for fresh installs
├── requirements.txt            # pip dependencies
├── Procfile                    # Railway: web: gunicorn app:app
├── .env.example                # Env var template
├── templates/
│   ├── base.html               # Root layout + CDN scripts + sidebar
│   ├── dashboard.html          # Content list + pipeline overview
│   ├── create.html             # URL/idea input + platform selector
│   ├── content_detail.html     # Single item view + pipeline X-ray
│   ├── calendar.html           # Publishing schedule (Phase 5)
│   └── settings.html           # API keys + model selection
└── static/
    └── css/
        └── custom.css          # Full dark gold brand system
```

---

## 4. The Automation X-Ray (Core Innovation)

### What Students See
When content is being processed, the UI shows a **live pipeline visualization**:

```
┌─────────────────────────────────────────────────────────────┐
│  AUTOMATION PIPELINE                                         │
│                                                              │
│  ● Scrape Article ──→ ◉ Generate Script ──→ ○ Create Image  │
│    ✓ 2.1s              ⟳ Calling OpenRouter    Waiting...    │
│                         ├─ Model: gemini-2.5-flash           │
│                         ├─ Tokens: 847 in / 312 out         │
│                         └─ Cost: $0.002                      │
│                                                              │
│  ○ Generate Video ──→ ○ Create Captions ──→ ○ Schedule Post  │
│    Waiting...           Waiting...            Waiting...     │
│                                                              │
│  ┌─ LIVE LOG ──────────────────────────────────────────────┐ │
│  │ 23:14:02  [scrape] Sending URL to FireCrawl API...      │ │
│  │ 23:14:03  [scrape] Received 2,847 words of markdown     │ │
│  │ 23:14:03  [script] Sending to OpenRouter (gemini-2.5).. │ │
│  │ 23:14:05  [script] ⟳ Streaming response... 156 tokens   │ │
│  │ 23:14:07  [script] ✓ Script generated (312 tokens)      │ │
│  │ 23:14:07  [image]  Sending prompt to Kie.ai...          │ │
│  │ 23:14:08  [image]  Task created: task_abc123             │ │
│  │ 23:14:10  [image]  ⟳ Polling... status: processing      │ │
│  │ 23:14:12  [image]  ⟳ Polling... status: processing      │ │
│  │ 23:14:14  [image]  ✓ Image ready! Downloading...        │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### How It Works (SSE)
```
Browser (EventSource) ←──── Flask SSE endpoint (/api/stream/<item_id>)
                                    │
                            Pipeline Orchestrator
                              │    │    │    │
                           Scrape Script Image Video
                              ↓    ↓    ↓    ↓
                           Each step emits events:
                           - stage_start {stage, timestamp}
                           - stage_progress {stage, message, detail}
                           - stage_complete {stage, duration, cost}
                           - stage_error {stage, error, retry?}
                           - pipeline_complete {total_duration, total_cost}
```

### Visual Elements
1. **Stage Progress Bar** — Horizontal pipeline with nodes for each stage. Completed = green check, active = pulsing gold ring, waiting = gray circle, error = red X
2. **Live Log Feed** — Scrolling monospace log with timestamps, color-coded by stage. Auto-scrolls to bottom. Students can see exactly what's happening
3. **Stage Detail Cards** — Click any stage node to see: API called, request/response summary, tokens used, cost, duration
4. **Cost Ticker** — Running total of API costs for this item (educational: shows students what automation costs)

---

## 5. Features by Phase

### Phase 1: "The Typewriter" — Text Generation (Quick Win)
**Concept:** Paste a URL or idea → get a social media script
**What students learn:** How an LLM API call works, prompt engineering basics

**Features:**
- Single-page UI with URL/idea input textarea
- Platform selector (Instagram, TikTok, LinkedIn, X, YouTube, Facebook)
- "Generate" button → calls OpenRouter API
- **Pipeline X-ray shows:** Single stage (LLM call) with streaming tokens
- Output: Generated post text + platform-specific captions
- Copy button, character count vs platform limit
- SQLite storage: saves generated content with timestamps
- Settings page: API key input (OpenRouter key)

**Input Detection:**
- If input starts with `http` → flag as URL (used in Phase 2)
- Otherwise → treat as idea/topic, send directly to LLM

**Database (Phase 1):**
```sql
CREATE TABLE content_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_text TEXT NOT NULL,           -- URL or idea
    input_type TEXT DEFAULT 'idea',     -- 'url' or 'idea'
    platform TEXT DEFAULT 'instagram',
    script TEXT,                        -- generated post text
    captions TEXT,                      -- JSON: per-platform captions
    status TEXT DEFAULT 'draft',        -- draft, processing, complete, error
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pipeline_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER REFERENCES content_items(id),
    stage TEXT NOT NULL,                -- 'scrape', 'script', 'image', 'video', 'caption', 'publish'
    status TEXT NOT NULL,               -- 'started', 'progress', 'complete', 'error'
    message TEXT,                       -- human-readable log line
    detail TEXT,                        -- JSON: tokens, cost, duration, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

**Routes:**
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | Dashboard — content list |
| GET | `/create` | New content form |
| POST | `/api/generate` | Generate text (returns SSE stream) |
| GET | `/api/stream/<id>` | SSE endpoint for pipeline updates |
| GET | `/api/content` | List all content items |
| GET | `/api/content/<id>` | Single content item + logs |
| DELETE | `/api/content/<id>` | Delete content item |
| GET | `/settings` | Settings page |
| POST | `/api/settings` | Save API keys |
| GET | `/api/health` | Health check |

---

### Phase 2: "The Researcher" — URL Scraping + Smart Input
**Concept:** Paste a URL → FireCrawl fetches the article → LLM rewrites it as social content
**What students learn:** How APIs chain (output of API A = input of API B), web scraping

**New features:**
- Auto-detect URL vs idea in input field
- FireCrawl integration: URL → clean markdown article text
- **Pipeline X-ray shows:** TWO stages now (Scrape → Script) with data flowing between them
- Article preview: show scraped content before script generation
- Edit scraped content before generating (optional review step)
- Settings: add FireCrawl API key

**New columns on content_items:**
```sql
ALTER TABLE content_items ADD COLUMN article_text TEXT;      -- scraped article
ALTER TABLE content_items ADD COLUMN article_title TEXT;      -- extracted title
ALTER TABLE content_items ADD COLUMN word_count INTEGER;      -- article word count
```

---

### Phase 3: "The Artist" — Image Generation
**Concept:** After script is generated, auto-generate a matching image via Kie.ai
**What students learn:** Async APIs, polling patterns, task-based workflows

**New features:**
- After script generation, LLM generates an image prompt
- Kie.ai Nano Banana Pro creates the image (async: create task → poll → download)
- **Pipeline X-ray shows:** THREE stages with the polling pattern visible:
  - "Task created: task_abc123"
  - "Polling... status: processing" (repeating with pulse animation)
  - "Image ready! Downloading..."
- Image preview with editable prompt + regenerate button
- Download button for generated image
- Settings: add Kie.ai API key

**New columns:**
```sql
ALTER TABLE content_items ADD COLUMN image_prompt TEXT;
ALTER TABLE content_items ADD COLUMN image_url TEXT;
ALTER TABLE content_items ADD COLUMN image_task_id TEXT;
```

---

### Phase 4: "The Director" — Video Generation
**Concept:** Generate a short video clip to pair with the post
**What students learn:** Long-running async operations, extended polling, timeout handling

**New features:**
- After image, optionally generate a Veo 3.1 video via Kie.ai
- **Pipeline X-ray shows:** FOUR stages, with video polling taking longer (20s intervals)
- Students see the difference: image polls every 2s, video polls every 20s
- Video preview with download button
- Toggle: "Include video?" checkbox (not all posts need video)
- Cost display per stage (images ~$0.09, video ~$0.19)

**New columns:**
```sql
ALTER TABLE content_items ADD COLUMN video_prompt TEXT;
ALTER TABLE content_items ADD COLUMN video_url TEXT;
ALTER TABLE content_items ADD COLUMN video_task_id TEXT;
ALTER TABLE content_items ADD COLUMN include_video BOOLEAN DEFAULT 0;
```

---

### Phase 5: "The Calendar" — Content Library + Scheduling
**Concept:** Save content to a library, view in calendar, schedule for publishing
**What students learn:** Data persistence, CRUD operations, scheduling concepts

**New features:**
- Dashboard becomes a content library (card grid with status badges)
- Calendar view: monthly grid showing scheduled posts
- Content detail page: view all generated assets (text, image, video) together
- Edit/update generated content before publishing
- Status workflow: draft → processing → ready → scheduled → published
- Batch processing: queue multiple items

**New table:**
```sql
CREATE TABLE schedule_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER REFERENCES content_items(id),
    scheduled_datetime TIMESTAMP NOT NULL,
    platform TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, published, failed
    published_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### Phase 6: "The Publisher" — Multi-Platform Posting via GetLate.dev
**Concept:** One click → post goes live on Instagram, TikTok, LinkedIn, etc.
**What students learn:** OAuth flows, multi-platform APIs, webhook callbacks

**New features:**
- GetLate.dev integration: schedule posts to connected platforms
- **Pipeline X-ray shows:** FULL 6-stage pipeline (Scrape → Script → Image → Video → Caption → Publish)
- Per-platform status: see which platforms posted successfully
- Publishing queue with retry on failure
- Settings: add GetLate API key + connect social accounts

---

### Phase 7: "The One-Button Machine" — Full Automation
**Concept:** Paste URL → press one button → everything happens automatically
**What students learn:** End-to-end orchestration, the full picture

**New features:**
- "Auto-pilot" toggle: runs all stages without stopping for review
- Batch mode: paste multiple URLs (one per line) → processes all
- Dashboard stats: total posts, API costs, platform breakdown
- Cost summary per item and monthly aggregate
- Export content as CSV

---

## 6. API Integration Specs

### OpenRouter (LLM)
```python
# pip install openai
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    default_headers={"HTTP-Referer": os.getenv("APP_URL", "http://localhost:5000")}
)

# Model: google/gemini-2.5-flash (fast, cheap)
# Fallback: anthropic/claude-sonnet-4 (complex queries)
```

### FireCrawl (Scraping)
```python
# pip install firecrawl-py
from firecrawl import Firecrawl

fc = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))
result = fc.scrape(url, formats=["markdown"])
# Returns: {"markdown": "# Article Title\n\nArticle text..."}
```

### Kie.ai (Image + Video)
```python
# Image generation (Nano Banana Pro)
POST https://api.kie.ai/api/v1/jobs/createTask
{
    "model": "google/nano-banana-pro",
    "input": {"prompt": "...", "image_size": "1024x1024"}
}
# Returns: {"taskId": "abc123"}

# Poll for result
GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId=abc123
# Returns: {"state": "success", "results": {"url": "https://..."}}

# Video generation (Veo 3.1)
POST https://api.kie.ai/api/v1/veo/generate
{
    "prompt": "...",
    "aspect_ratio": "9:16",
    "model": "veo3_fast"
}
# Poll: GET https://api.kie.ai/api/v1/veo/get-1080p-video?taskId=xyz
```

### GetLate.dev (Publishing)
```python
# pip install late
# OR direct API calls
POST https://api.getlate.dev/v1/posts
{
    "content": "Post text...",
    "scheduled_for": "2026-04-20T12:00:00",
    "timezone": "America/Los_Angeles",
    "platforms": [{"platform": "instagram", "accountId": "acc_xyz"}]
}
```

---

## 7. Environment Variables

```env
# Required
SECRET_KEY=change-me-in-production
OPENROUTER_API_KEY=sk-or-...

# Phase 2
FIRECRAWL_API_KEY=fc-...

# Phase 3-4
KIE_API_KEY=...

# Phase 6
GETLATE_API_KEY=...

# Deployment
PORT=5000
DATABASE_PATH=content.db

# Optional
ADMIN_USER=admin
ADMIN_PASS=admin
APP_URL=http://localhost:5000
```

---

## 8. Dependencies

```txt
flask>=3.0
gunicorn>=21.0
openai>=1.0
firecrawl-py>=1.0
requests>=2.31
python-dotenv>=1.0
```

---

## 9. Deployment (Railway)

1. Push to `https://github.com/jjacuna/content-automation`
2. Railway > New Project > Deploy from GitHub
3. Set env vars in Railway dashboard
4. Procfile: `web: gunicorn app:app --bind 0.0.0.0:$PORT`
5. Auto-deploy on git push

---

## 10. What We're Building from CAM 2.0 (Simplified)

| CAM 2.0 Feature | Demo Version |
|------------------|-------------|
| 14 database tables | 3 tables (content_items, pipeline_logs, settings) |
| Huey + Redis task queue | Synchronous + SSE streaming (no Redis) |
| 10-stage pipeline | 6-stage pipeline (scrape, script, image, video, caption, publish) |
| HeyGen avatar + Shotstack compositing | Skipped (too complex for workshop) |
| Fish.audio TTS | Skipped |
| Business profile (50+ fields) | Simple settings page |
| ZapCap captions | Skipped |
| PostgreSQL + connection pooling | SQLite (upgrade path to Postgres noted) |
| Multi-format video (8 types) | Single format (image + optional video) |
| License/SaaS features | Session auth (admin/admin) |

---

## 11. Success Criteria

A student who completes all phases should be able to:
1. **Explain** how APIs chain together (output → input)
2. **Understand** sync vs async API patterns (instant response vs polling)
3. **Read** the pipeline log and know what each line means
4. **Customize** prompts to change the content output
5. **Deploy** their own version on Railway
6. **Extend** the app with new stages or APIs

---

## 12. Tonight's Build Plan

We're building the full app tonight (Phases 1-7), structured so each phase is a clean commit. Priority order:

1. **Phase 1** — Flask app + SQLite + text generation + pipeline X-ray UI
2. **Phase 2** — FireCrawl URL scraping + smart input detection
3. **Phase 3** — Kie.ai image generation with polling visualization
4. **Phase 4** — Kie.ai video generation with extended polling
5. **Phase 5** — Content library + calendar view
6. **Phase 6** — GetLate.dev publishing integration
7. **Phase 7** — One-button auto-pilot + batch mode + stats

Each phase builds on the previous, and the pipeline X-ray grows with each phase (1 stage → 2 → 3 → 4 → 5 → 6 stages).
