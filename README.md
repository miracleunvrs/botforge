# BotForge

**A visual no-code builder for Telegram bots.** Create conversation flows from blocks, test them in a built-in simulator, publish them to Telegram, and review users and messages from one interface.

[English](README.md) · [Русский](README.ru.md)

[![CI](https://github.com/miracleunvrs/botforge/actions/workflows/ci.yml/badge.svg)](https://github.com/miracleunvrs/botforge/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688)
![React](https://img.shields.io/badge/React-19-61DAFB)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1)

![BotForge editor](docs/screenshots/editor.png)

## Features

- Visual editor with message, choice, input, condition, and end blocks
- FAQ, lead collection, booking, and feedback templates
- Browser simulator for unsaved flows
- Variables such as `{{name}}` for personalized replies
- Per-workflow Telegram bot tokens and publish/stop controls
- Persistent conversation state and duplicate-update protection
- User, message, and seven-day activity analytics
- Docker Compose setup and GitHub Actions checks

## Tech stack

| Part | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Lucide |
| API | FastAPI, Pydantic, SQLAlchemy async |
| Database | PostgreSQL 17, JSONB |
| Integration | Telegram Bot API and webhooks |
| Delivery | Docker Compose, nginx, GitHub Actions |

## Quick start

Requirements: Docker Desktop and Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

- Editor: <http://localhost:3000>
- API overview: <http://localhost:8000>
- OpenAPI docs: <http://localhost:8000/docs>

For development with hot reload:

```bash
docker compose up db migrate -d
cd backend && python -m pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8000

# in another terminal
cd frontend && npm ci && npm run dev
```

## Telegram setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Save a workflow in BotForge, open **Telegram**, enter the token, and publish it.
3. Expose the API through HTTPS and register the workflow webhook:

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://<PUBLIC_HOST>/api/telegram/webhook/<WORKFLOW_ID>","secret_token":"<WEBHOOK_SECRET>"}'
```

Set the same value in `.env` as `TELEGRAM_WEBHOOK_SECRET`. Never commit a real token or `.env` file.

## How flows work

Flows are stored as JSONB graphs. The pure `run_step()` engine powers both the browser simulator and Telegram delivery. Input blocks can save values under a variable name; later messages interpolate `{{variable}}`. PostgreSQL keeps the current node and state for every Telegram user.

Workflow responses expose only `has_token`; the stored bot token is never returned by the API. Publishing also validates broken links and incomplete choice or condition blocks.

## Verification

```bash
cd backend && pytest -q
cd frontend && npm run build
```

CI runs both checks for every push and pull request.

## Project structure

```text
backend/app/          FastAPI routes, models, templates, flow engine
backend/migrations/   idempotent PostgreSQL migrations
backend/tests/        engine regression tests
frontend/src/         React editor, simulator, and analytics UI
docs/screenshots/     portfolio screenshots
docker-compose.yml    local application stack
```

## Security scope

BotForge is currently a single-operator portfolio application. Its management API has no account system, so deploy it only behind private network access or an authentication proxy. Before offering it as a public multi-user service, add workspace authorization, encrypt bot tokens at rest, rate-limit public endpoints, and move Telegram delivery to a retryable background queue.

## License

This repository is provided as a portfolio and educational project.
