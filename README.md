<div align="center">
  <img src="docs/logo.svg" alt="Pulse News" width="400" />
</div>

<p align="center">
  <strong>A dead-simple, self-hosted AI newsletter platform. One operator, one container, one prompt per newsletter.</strong>
</p>

<p align="center">
  <a href="https://github.com/Jurel89/pulse-news/actions/workflows/ci.yml"><img src="https://github.com/Jurel89/pulse-news/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License" />
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker" />
</p>

---

## What it does

You configure an AI provider (OpenAI, Anthropic, Gemini, OpenRouter, Google, zai, or Kimi) and a Resend API key. You create a newsletter with a prompt like *"give me the last AI trends this week"*, a recipient list, and an email template. You click **Run Now** (or let the schedule fire it).

That's it. The backend calls the AI provider with your prompt, renders the generated subject, preheader, and body into the selected template, and ships the email via Resend. No drafts, no revisions, no preview workflows, no approval steps. One click, one send.

## Key features

- **One-prompt content generation** — the AI produces subject, preheader, and body from a single prompt. No separate fields to hand-author.
- **Multiple AI providers** — OpenAI, Anthropic, Gemini, Google, OpenRouter, zai, Kimi. All configured through the UI; credentials encrypted at rest.
- **Resend delivery** — bounces, complaints, and unsubscribe-driven suppressions handled through Resend webhooks.
- **Cron scheduling** — APScheduler for recurring sends, or "Run Now" for one-offs.
- **Single-container** — backend, scheduler, migrations, and the bundled React UI run in one Python container.
- **Audit log** — every mutation is recorded and viewable in-app.
- **Single-operator auth** — session-cookie login, bootstrapped on first run. No multi-tenant complexity.

## How it works

```
operator prompt   ───►  AI provider (litellm)  ───►  subject + preheader + body
                                                      │
                                                      ▼
                          email template (HTML)  ◄────┘
                                                      │
                                                      ▼
                                              Resend API  ───►  recipient inboxes
```

The full flow is a single HTTP call: `POST /api/newsletters/{id}/run` → generate → render → deliver. A generation failure returns HTTP 422 and sends nothing. No intermediate draft state.

## Quick start

### Prerequisites

- Docker with Compose v2 (local / prod), OR Python 3.13 + Node 20 (for dev)
- A Resend account and API key
- At least one AI provider API key (OpenAI, Anthropic, Gemini, OpenRouter, zai, or Kimi)

### Run with Docker (recommended)

```bash
git clone https://github.com/Jurel89/pulse-news.git
cd pulse-news
cp .env.example .env   # edit values
PORT=9876 make up      # builds + starts the container
```

Open `http://localhost:9876`. The first page prompts you to bootstrap the initial operator account.

Then, in the UI:

1. **API Keys** → add your AI provider key and your Resend key (with a verified Sender Email)
2. **Providers** → create a provider pointing at the key you just added, enable it, pick a default model
3. **Newsletters** → "New Newsletter" → fill in name, prompt, pick the provider + Resend key + template, paste recipient emails (one per line or comma-separated), save
4. Hit **Run Now** — or set a cron and let the scheduler handle it

### Local development

```bash
# Backend (Python 3.13)
cd backend
pip install -e ".[dev]"
PULSE_NEWS_ENVIRONMENT=development uvicorn app.main:app --app-dir . --reload --port 8000

# Frontend (Node 20) — separate terminal from repo root
cd frontend
npm install
npm run dev   # Vite dev server on 5173, proxies /api → :8000
```

## Environment variables

All runtime configuration uses the `PULSE_NEWS_` prefix.

| Variable | Purpose | Required | Default |
|---|---|---|---|
| `PULSE_NEWS_ENVIRONMENT` | `development` or `production` | No | `development` |
| `PULSE_NEWS_SECRET_KEY` | Session cookie signing key | Yes in production | `change-me-before-production` |
| `PULSE_NEWS_RESEND_API_KEY` | Optional fallback Resend key (per-newsletter keys stored in DB override it) | No | unset |
| `PULSE_NEWS_RESEND_FROM_EMAIL` | Optional fallback sender address | No | unset |
| `PULSE_NEWS_RESEND_WEBHOOK_SECRET` | Signing secret for incoming Resend webhooks | No | unset |
| `PULSE_NEWS_BOOTSTRAP_SECRET` | One-time secret required to create the initial operator, if set | No | unset |
| `PULSE_NEWS_DATA_DIR` | Directory for the SQLite DB | No | `/data` (Docker) / `./data` (dev) |

Provider credentials and Resend keys are stored in the database via the UI — environment variables for them are only a convenience fallback.

## Testing

```bash
# Backend unit/integration
cd backend && pytest

# Frontend type + build
cd frontend && npx tsc --noEmit && npm run build

# End-to-end (requires the Docker stack running on :9876)
PORT=9876 make up
cd frontend && npx playwright install chromium && npx playwright test --workers=1
```

CI runs all five jobs — `backend-lint`, `backend-test`, `frontend-build`, `frontend-typecheck`, `e2e` — on every PR.

## Deployment notes

- **Single-process**: one container, one worker. Do not scale horizontally — the SQLite DB and the in-process scheduler are not designed for concurrent writers.
- **Persistent data**: mount a volume at `/data` so your DB survives restarts (the provided `docker-compose.yml` already configures the `pulse-news-data` volume).
- **Backups**: `docker cp pulse-news:/data/pulse_news.db ./backup.db` while the container is stopped.
- **Health check**: `GET /api/health` returns `{"status":"ok"}`. The container image has this wired into its Docker HEALTHCHECK.

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Python 3.13 · FastAPI · SQLAlchemy 2.x · Alembic · APScheduler |
| AI gateway | litellm (OpenAI / Anthropic / Gemini / Google / OpenRouter / zai / Kimi) |
| Email | Resend REST API |
| Frontend | React 19 · TypeScript 5 · Vite |
| Database | SQLite (file-based) |
| Auth | Session cookies (itsdangerous-signed) |
| Container | Docker (single image) |

## License

MIT — see [LICENSE](LICENSE).
