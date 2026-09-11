# BotForge — Visual no-code platform for building, testing and managing Telegram bots

> **SE Theme №4** · `botforge` · `Visual no-code platform for building, testing and managing Telegram bots.`
> **v0.1.0** — visual editor + one working bot end-to-end (editor → API → engine → Telegram).

[![CI](https://github.com/your-org/botforge/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/botforge/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688)
![React 19](https://img.shields.io/badge/React-19-61dafb)
![Postgres 17](https://img.shields.io/badge/Postgres-17-336791)

---

## What is this?

BotForge lets a non-technical editor assemble a Telegram bot as a graph of blocks, test it instantly in a built-in phone simulator, publish it with a BotFather token, and watch users/messages/analytics — without writing code. The flow engine is isolated from HTTP and DB, so the same definition powers both the simulator and real Telegram delivery.

**Spec coverage (SE №4):**

- [x] visual scenario editor
- [x] blocks: **Сообщение / Message**, **Кнопки / Buttons**, **Условие / Condition**, **Запрос данных / Input** (+ `Завершение`)
- [x] Telegram bot connection by token (per-workflow, stored in `workflows.telegram_bot_token`)
- [x] publish / stop scenario (`POST /publish`, `POST /stop`, `is_published` flag)
- [x] users & dialog history (`bot_users`, `messages`)
- [x] analytics: messages & activity (`GET /analytics`, 7-day chart data)
- [x] templates: **FAQ**, **Заявка (Lead)**, **Запись (Booking)**, **Обратная связь (Feedback)**
- [x] test mode without publishing (`POST /simulate`)

## Screenshots

> Add PNGs to `docs/screenshots/` and they will render here. Placeholders for portfolio reviewers.

| Editor + palette | Test phone | Analytics |
|---|---|---|
| ![editor](docs/screenshots/editor.png) | ![phone](docs/screenshots/phone.png) | ![analytics](docs/screenshots/analytics.png) |

*If screenshots are not yet generated: `frontend/dist` builds a production bundle; run `npm run dev` at `http://localhost:5173` to capture them (Flow → Test → Analytics).*

## Demo scenario (Northwind, 60 sec)

1. Open `http://localhost:5173` → palette shows 5 blocks.
2. Click **Шаблоны → FAQ** → canvas loads 7 nodes (`Приветствие → Меню → ... → Завершение`).
3. Select node **Условие** (`condition_value="спасибо"`) → edit to `"доставка"` → set `Иначе → Возврат`.
4. **Сохранить** → `POST /api/workflows` returns `id=1`.
5. Tab **Тест** → send `Доставка` → engine follows choice/condition and replies `Доставляем за 1-3 дня…`.
6. **Telegram** card → paste token `123:ABC` → **Опубликовать** → `is_published=true`.
7. In Telegram write `/start` to your bot → bot replies via webhook → history appears in **Аналитика**.

Video/GIF: `docs/demo.gif` (optional).

## Architecture

```text
                    ┌─────────────────────┐
                    │  React 19 + TS +     │
                    │  Vite + lucide-react │
                    │  (canvas / inspector │
                    │   / phone simulator) │
                    └─────────┬───────────┘
                              │ REST /api/*  (CORS: 5173,3000)
                    ┌─────────▼───────────┐
                    │  FastAPI 0.116       │
                    │  ┌───────────────┐  │
        ┌───────────┤  │ flow_engine   │  │  deterministic, no I/O
        │           │  │ run_step()    │◄─┼── pure function, unit-tested
        │           │  └───────┬───────┘  │
        │           │  ┌───────▼───────┐  │
        │           │  │ Telegram      │  │  webhook → users/messages → sendMessage
        │           │  │ adapter       │──┼──► https://api.telegram.org/bot{token}/sendMessage
        │           │  └───────┬───────┘  │
        │           └─────────┼───────────┘
        │                     │ SQLAlchemy 2 (asyncpg)
        │           ┌─────────▼───────────┐
        └──────────►│ PostgreSQL 17       │
                    │ workflows (jsonb)   │
                    │ bot_users           │
                    │ messages            │
                    └─────────────────────┘
```

*Why isolated engine?* `backend/app/flow_engine.py:8` has zero FastAPI/SQLAlchemy imports → testable with `pytest` without DB, swappable for WhatsApp/Viber.

## Stack

| Layer | Tech | Notes |
|---|---|---|
| Frontend | React 19, TypeScript 7.0.2, Vite 8.3, lucide-react 1.44 | pinned versions, no `latest` |
| Backend | Python 3.12, FastAPI 0.116, SQLAlchemy 2 async, asyncpg, httpx | |
| DB | PostgreSQL 17 (jsonb + GIN-ready, `bot_users`, `messages` indexed) | |
| Infra | Docker Compose (api + web/nginx + db + migrate), GitHub Actions CI | |

## Blocks (ТЗ → implementation)

| Spec | `type` | UI title | Behaviour |
|---|---|---|---|
| Сообщение | `message` | Сообщение | Sends `text`, auto-advances via `next_id`; if `next_id=null` → `complete` |
| Кнопки | `choice` | Кнопки | Shows `text` + `choices[]`; waits for user label (case-insensitive) |
| Условие | `condition` | Условие | Checks `message` contains `condition_value` (casefold). `true_next_id` / `false_next_id` |
| Запрос данных | `input` | Запрос данных | Prompts `text`, captures any `message`, advances via `next_id` |
| — | `end` | Завершение | Terminal node, returns accumulated `messages` with `complete=true` |

Engine loop: `for _ in range(len(nodes)+1)` prevents cycles without user input → `FlowError`.

## Templates

`GET /api/templates` (see `backend/app/templates.py:1`)

| id | Title | Nodes | Purpose |
|---|---|---|---|
| `faq` | FAQ бот | 7 | `message → choice(Доставка/Оплата/Возврат) → message* → choice(Да/Нет) → end` |
| `lead` | Сбор заявок | 6 | `message → input(имя) → input(телефон) → condition(contains "+") → end` |
| `booking` | Запись на услугу | 4 | `message → choice(10:00/14:00/18:00) → input(имя) → end` |
| `feedback` | Обратная связь | 5 | `message → input(отзыв) → condition(спасибо) → end*2` |

Load in UI: **Палитра → Шаблоны** → replaces canvas. Then **Сохранить**.

## API

Base `http://localhost:8000`, docs `http://localhost:8000/docs`

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | liveness |
| `GET` | `/api/templates` | list 4 templates |
| `GET` | `/api/workflows` | list workflows |
| `POST` | `/api/workflows` | create (`WorkflowCreate`) |
| `GET` | `/api/workflows/{id}` | get one |
| `PUT` | `/api/workflows/{id}` | update definition/name |
| `POST` | `/api/workflows/{id}/publish` | `{telegram_bot_token?}` → `is_published=true` |
| `POST` | `/api/workflows/{id}/stop` | `is_published=false` |
| `POST` | `/api/workflows/{id}/simulate` | `{message, current_node_id}` → `{messages, choices, current_node_id, complete}` (test mode) |
| `GET` | `/api/workflows/{id}/analytics` | `{users_total, messages_total, recent_messages, activity_7d, is_published, has_token}` |
| `GET` | `/api/workflows/{id}/users` | list `bot_users` |
| `GET` | `/api/workflows/{id}/messages?limit=100` | history |
| `POST` | `/api/telegram/webhook` | Telegram update, header `X-Telegram-Bot-Api-Secret-Token` |

Pydantic schemas: `backend/app/schemas.py:12` (`FlowNode`, `FlowDefinition`, `WorkflowRead`, `Simulation*`).

## Database

`backend/migrations/001_initial.sql:1`

- `workflows(id bigint, name text, description text, definition jsonb, is_published bool, telegram_bot_token text, telegram_bot_username varchar, created_at timestamptz, updated_at timestamptz)` — index `idx_workflows_updated_at`
- `bot_users(id, workflow_id, telegram_user_id, username, first_seen_at, last_seen_at, current_node_id)` — unique `(workflow_id, telegram_user_id)`
- `messages(id, workflow_id, bot_user_id, telegram_user_id, direction in ('in','out'), text, node_id, created_at)` — indexes on `(workflow_id, created_at)` and `telegram_user_id`

`definition` is `jsonb` (validated by Pydantic), ready for `GIN` if searching flows.

## Run locally

### Option A — full Docker (recommended for GitHub)

```bash
cp .env.example .env   # set TELEGRAM_WEBHOOK_SECRET, optionally TELEGRAM_BOT_TOKEN
docker compose up --build
# web  → http://localhost:3000  (nginx serving frontend/dist)
# api  → http://localhost:8000/docs
# db   → localhost:5432 (botforge/botforge)
```

### Option B — dev (hot reload)

```bash
cp .env.example .env
docker compose up db migrate -d
cd backend && python -m pip install -e '.[dev]' && uvicorn app.main:app --reload --port 8000 &
cd frontend && npm ci && npm run dev   # http://localhost:5173
```

Env (`backend/app/config.py:4`):

```
DATABASE_URL=postgresql+asyncpg://botforge:botforge@localhost:5432/botforge
TELEGRAM_BOT_TOKEN=          # fallback if workflow has no token
TELEGRAM_WEBHOOK_SECRET=change-me
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
VITE_API_URL=http://localhost:8000  # frontend
```

## Telegram connection

1. Create bot via `@BotFather` → `/newbot` → copy token `123:ABC`.
2. In BotForge: save workflow → **Telegram** card → paste token → **Опубликовать**.
3. Set webhook (local via `ngrok` or public host):

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://<your-host>/api/telegram/webhook","secret_token":"change-me"}'
# header name is X-Telegram-Bot-Api-Secret-Token (validated in app.main:telegram_webhook)
```

4. Send `/start` to bot → webhook stores user in `bot_users`, runs `flow_engine.run_step`, replies via `sendMessage` (with `keyboard` if `choice`).

Never commit `.env` — `.gitignore:1` already excludes it.

## Tests & checks

```bash
cd backend
python -m pip install -e '.[dev]'
pytest -v                    # 8 tests: choice, condition, input, cycle guard
# backend/tests/test_flow_engine.py:25

cd ../frontend
npm ci
npm run build                # tsc -b && vite build  → dist/
```

CI: `.github/workflows/ci.yml:1` runs both jobs on `push`/`pull_request` (Python 3.12, Node 22).

## Project structure

```
botforge/
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI + publish/stop/analytics/users/messages/webhook
│   │   ├── flow_engine.py # pure run_step, condition branch
│   │   ├── schemas.py     # Pydantic FlowNode (message|choice|input|condition|end)
│   │   ├── models.py      # Workflow + BotUser + Message
│   │   ├── templates.py   # 4 presets (faq/lead/booking/feedback)
│   │   └── config.py
│   ├── migrations/001_initial.sql
│   └── tests/test_flow_engine.py
├── frontend/
│   ├── src/App.tsx        # palette, canvas, inspector, phone, analytics
│   ├── src/styles.css
│   ├── Dockerfile + nginx.conf
│   └── package.json (pinned: react 19.3.0, vite 8.3.0, etc.)
├── docker-compose.yml     # db + api + web + migrate
└── README.md
```

## Production hardening (beyond v0.1.0)

Current v0.1.0 is intentionally single-tenant, no auth — perfect for portfolio demo with one bot. Hardening checklist: per-workspace RBAC + JWT, encrypted `telegram_bot_token` (e.g. `pgcrypto`/`Fernet`), rate limits, background worker with retries for `sendMessage`, audit log, webhook signature replay protection, GIN index on `definition`, pagination for `messages`.

## License

MIT — `LICENSE:1`
