# Pulse News

Self-hosted newsletter operations app for a single operator. Create, schedule, run, review, and delete newsletters with AI-assisted content generation, reusable email templates, audience targeting, execution logs, and delivery history.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (for containerized deployment)

### Development

```bash
# Backend
cd backend
pip install -e ".[dev]"
PULSE_NEWS_ENVIRONMENT=development uvicorn app.main:app --app-dir . --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

The backend serves on `http://localhost:8000` and the frontend dev server on `http://localhost:5173`.

### Environment Variables

All configuration uses the `PULSE_NEWS_` prefix:

| Variable | Purpose | Default |
|----------|---------|---------|
| `PULSE_NEWS_ENVIRONMENT` | `development` or `production` | `development` |
| `PULSE_NEWS_SECRET_KEY` | Session signing key | `change-me-before-production` (must change in production) |
| `PULSE_NEWS_RESEND_API_KEY` | Resend API key for email delivery | None |
| `PULSE_NEWS_RESEND_FROM_EMAIL` | Sender email address | None |
| `PULSE_NEWS_RESEND_WEBHOOK_SECRET` | Webhook signing secret | None |
| `PULSE_NEWS_DATA_DIR` | Data directory for SQLite DB | `./data` |
| `PULSE_NEWS_DATABASE_PATH` | Explicit path to SQLite database | Auto-derived from data dir |

### Running Tests

```bash
cd backend
pytest
```

### Docker

```bash
docker build -t pulse-news .
docker run -p 8000:8000 \
  -e PULSE_NEWS_SECRET_KEY=your-secret-key \
  -e PULSE_NEWS_RESEND_API_KEY=re_xxx \
  -e PULSE_NEWS_RESEND_FROM_EMAIL=you@domain.com \
  -v pulse-news-data:/data \
  pulse-news
```

**Important**: This app is designed to run as a single process. Do not scale to multiple workers.

## Architecture

- **Backend**: Python 3.13, FastAPI, SQLAlchemy, APScheduler
- **Frontend**: React 19, TypeScript, Vite
- **Database**: SQLite (single-container, single-user)
- **Email**: Resend API
- **AI**: LiteLLM (multi-provider LLM abstraction)

## Data and Backups

The SQLite database is stored in the data directory. To back up:

```bash
# Stop the container/app
cp data/pulse_news.db data/pulse_news.db.backup
```

## License

Private project.
