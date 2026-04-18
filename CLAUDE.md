# Content Automation Demo — Claude Workshop Part 2

## Project Overview
Teaching-first content automation app. Students learn how APIs chain together by watching a real-time "Automation X-ray" pipeline visualization as content flows through stages: scrape → script → image → video → caption → publish.

## Tech Stack
- **Backend:** Flask 3.x (Python)
- **Database:** SQLite (file-based, zero-config)
- **Frontend:** Jinja2 + Tailwind CSS (CDN) + Alpine.js (CDN)
- **Real-time:** Server-Sent Events (SSE) — native Flask, no Redis
- **APIs:** OpenRouter (LLM), FireCrawl (scraping), Kie.ai (image/video), GetLate.dev (publishing)
- **Deployment:** Railway + gunicorn

## Design System
- **Theme:** Dark gold premium (matches CRM Demo Part 1)
- **Primary BG:** `#0B0B0D` | **Card BG:** `#17181C` | **Gold accent:** `#C7A35A`
- **Font:** Inter (Google Fonts CDN)
- **No build step** — everything via CDN or pip

## Key Principles
1. **Teaching > Features** — UI explains what's happening, not just does it
2. **Pipeline X-ray** — Every API call visible in real-time log feed
3. **Phased learning** — Each phase adds one concept
4. **Match CRM Part 1** — Same colors, components, layout patterns
5. **Zero-config for students** — SQLite, CDN deps, `pip install`, done

## Git Workflow
- `main` branch — production
- Clean commits per phase
- Push to: https://github.com/jjacuna/content-automation

## Environment Variables
See `.env.example` for full list. Required: `SECRET_KEY`, `OPENROUTER_API_KEY`.
