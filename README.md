<img src="docs/logo.svg" alt="Pulse News" width="200" />

# Pulse News

[![CI](https://img.shields.io/github/actions/workflow/status/Jurel89/pulse-news/ci.yml?branch=main&style=flat-square&logo=github&label=CI)](https://github.com/Jurel89/pulse-news/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/Jurel89/pulse-news?style=flat-square)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)

Pulse News is a self-hosted newsletter operations platform designed for a single operator who needs complete control over content creation, scheduling, and delivery. Built around the philosophy that one person should be able to run multiple newsletters reliably without juggling separate tools for AI content generation, email sending, and performance tracking.

Whether you are curating weekly digests or running automated content newsletters, Pulse News gives you a unified control panel to generate content with your preferred AI provider, schedule sends with flexible cron expressions, and track every delivery through to the inbox.

## Key Features

- **AI-Assisted Content Generation** — Generate newsletter content using any LLM provider through LiteLLM (OpenAI, Anthropic, Gemini, OpenRouter, and 100+ more)
- **Flexible Scheduling** — Schedule newsletters with cron expressions using APScheduler, run on-demand, or set up recurring sends
- **Reusable Email Templates** — Create and manage reusable templates with consistent branding across all your newsletters
- **Audience Management** — Track subscribers with unsubscribe handling and bounce management via Resend webhooks
- **Delivery Tracking** — Monitor send progress and delivery status through Resend webhooks with full audit trails
- **Single-Container Deployment** — One Docker image runs everything: backend, scheduler, database, and frontend
- **Operator-First Auth** — Simple single-user authentication designed for solo operators, no multi-user complexity

## Architecture

Pulse News runs as a unified service with clear internal boundaries:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Pulse News Container                         │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │   FastAPI    │◄──►│   SQLite     │    │   APScheduler    │   │
│  │   Backend    │    │   Database   │◄──►│   (Job Queue)    │   │
│  └──────┬───────┘    └──────────────┘    └────────┬─────────┘   │
│         │                                          │              │
│         │         ┌──────────────┐                 │              │
│         └────────►│   React 19   │◄────────────────┘              │
│                   │   Frontend   │                                │
│                   └──────────────┘                                │
│                                                                  │
│  External Services:                                              │
│         │                  │                  │                  │
│         ▼                  ▼                  ▼                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │    Resend    │    │   LiteLLM    │    │   Webhook    │       │
│  │   (Email)    │    │  (AI/LLM)    │    │  Callbacks   │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

The backend handles API requests, database operations, and job scheduling all within a single process. The scheduler manages newsletter send jobs and tracks execution history. LiteLLM provides a unified interface to multiple AI providers without vendor lock-in.

## Quick Start

### Prerequisites

- Python 3.12 or higher
- Node.js 20 or higher (for development)
- Docker (for containerized deployment)
- Resend account with API key
- AI provider API key (OpenAI, Anthropic, or other supported provider)

### Clone and Run (Development)

```bash
# Clone the repository
git clone https://github.com/Jurel89/pulse-news.git
cd pulse-news

# Backend setup
cd backend
pip install -e ".[dev]"

# Frontend setup (in a separate terminal, from the repo root)
cd frontend
npm install
npm run dev

# Start the backend (in another terminal, from backend directory)
cd backend
PULSE_NEWS_ENVIRONMENT=development uvicorn app.main:app --app-dir . --reload --port 8000
```

The backend serves on `http://localhost:8000` and the frontend dev server on `http://localhost:5173`.

### Docker Deployment

```bash
# Build the image
docker build -t pulse-news .

# Run with required environment variables
docker run -p 8000:8000 \
  -e PULSE_NEWS_SECRET_KEY=your-secret-key \
  -e PULSE_NEWS_RESEND_API_KEY=re_xxx \
  -e PULSE_NEWS_RESEND_FROM_EMAIL=newsletter@yourdomain.com \
  -v pulse-news-data:/data \
  pulse-news
```

## Environment Variables

All configuration uses the `PULSE_NEWS_` prefix:

| Variable | Purpose | Required | Default |
|----------|---------|----------|---------|
| `PULSE_NEWS_ENVIRONMENT` | Runtime environment (`development` or `production`) | Yes | `development` |
| `PULSE_NEWS_SECRET_KEY` | Session signing key for auth | Production only | `change-me-before-production` |
| `PULSE_NEWS_RESEND_API_KEY` | Resend API key for email delivery | Yes | None |
| `PULSE_NEWS_RESEND_FROM_EMAIL` | Verified sender email address | Yes | None |
| `PULSE_NEWS_RESEND_WEBHOOK_SECRET` | Secret for validating Resend webhooks | No | None |
| `PULSE_NEWS_DATA_DIR` | Data directory for SQLite | No | `./data` |
| `PULSE_NEWS_DATABASE_PATH` | Explicit SQLite database path | No | Auto-derived |

## AI Provider Configuration

Pulse News uses LiteLLM to support multiple AI providers through a unified interface. Configure your providers by setting the appropriate API key environment variables:

| Provider | Environment Variable | Notes |
|----------|---------------------|-------|
| OpenAI | `OPENAI_API_KEY` | GPT-4, GPT-4o, GPT-3.5 |
| Anthropic | `ANTHROPIC_API_KEY` | Claude 3.5 Sonnet, Claude 3 Opus |
| Google | `GEMINI_API_KEY` | Gemini Pro, Gemini Ultra |
| OpenRouter | `OPENROUTER_API_KEY` | Access to multiple providers |

LiteLLM supports 100+ providers. Refer to the [LiteLLM documentation](https://docs.litellm.ai/) for the complete list.

## Development

### Backend Development

```bash
cd backend

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Linting
ruff check .
ruff format .

# Start development server
PULSE_NEWS_ENVIRONMENT=development uvicorn app.main:app --app-dir . --reload --port 8000
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Type checking
npx tsc --noEmit

# Build for production
npm run build
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

### Linting

```bash
# Python (backend)
cd backend
ruff check .
ruff check . --fix
ruff format .

# TypeScript (frontend)
cd frontend
npx tsc --noEmit
```

## Deployment

### Docker

The recommended deployment method is Docker. The container includes everything needed: backend, frontend, scheduler, and database.

```bash
# Build
docker build -t pulse-news:latest .

# Run with persistent volume
docker run -d \
  --name pulse-news \
  -p 8000:8000 \
  -e PULSE_NEWS_ENVIRONMENT=production \
  -e PULSE_NEWS_SECRET_KEY=$(openssl rand -hex 32) \
  -e PULSE_NEWS_RESEND_API_KEY=re_xxx \
  -e PULSE_NEWS_RESEND_FROM_EMAIL=newsletter@yourdomain.com \
  -e PULSE_NEWS_RESEND_WEBHOOK_SECRET=your-webhook-secret \
  -v pulse-news-data:/data \
  --restart unless-stopped \
  pulse-news:latest
```

### Important Deployment Notes

**Single Process Design**: Pulse News is intentionally designed to run as a single process. Do not scale to multiple workers or instances. The scheduler and database are not designed for concurrent access from multiple processes.

**Data Persistence**: Always mount a persistent volume to `/data` to ensure your database survives container restarts. Without this, data will be lost when the container is removed.

**Backups**: The SQLite database is stored in the data directory. To create a backup:

```bash
# Stop the container
docker stop pulse-news

# Backup the database
docker cp pulse-news:/data/pulse_news.db ./pulse_news.db.backup

# Restart the container
docker start pulse-news
```

**Health Checks**: The container includes a health check endpoint at `/api/health`. Docker will automatically restart the container if it becomes unresponsive.

## Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Runtime | Python | 3.13+ | Backend runtime |
| API Framework | FastAPI | 0.135 | HTTP API, async endpoints |
| Database | SQLite | 3.x | Single-file persistence |
| ORM | SQLAlchemy | 2.0 | Database abstraction |
| Scheduler | APScheduler | 3.11 | Job scheduling, cron support |
| AI Gateway | LiteLLM | 1.83 | Multi-provider LLM access |
| Frontend | React | 19 | UI components, state management |
| Build Tool | Vite | 8.0 | Frontend bundling, dev server |
| Type Safety | TypeScript | 5.9 | Frontend type checking |
| Email | Resend API | Latest | Transactional email delivery |
| Auth | itsdangerous | 2.2 | Session signing, secure cookies |
| Container | Docker | Latest | Deployment packaging |

## License

MIT License — see [LICENSE](LICENSE) for details.
