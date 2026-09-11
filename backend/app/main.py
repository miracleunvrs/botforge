import html
import logging
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_session
from .flow_engine import FlowError, run_step, validate_publishable_flow
from .models import BotUser, Message, TelegramUpdate, Workflow
from .schemas import (
    FlowDefinition,
    SimulationRequest,
    SimulationResponse,
    StatelessSimulationRequest,
    TemplateInfo,
    WorkflowCreate,
    WorkflowPublishRequest,
    WorkflowRead,
)
from .templates import TEMPLATES

logger = logging.getLogger("botforge")

app = FastAPI(title="BotForge API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Telegram-Bot-Api-Secret-Token"],
)


@app.get("/", response_class=HTMLResponse)
async def root_dashboard(session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    db_status = "Connected"
    db_badge_class = "status-green"
    workflows_total = 0
    workflows_published = 0
    users_total = 0
    messages_total = 0
    recent_workflows: list[Workflow] = []

    try:
        workflows_total = await session.scalar(select(func.count(Workflow.id))) or 0
        workflows_published = (
            await session.scalar(select(func.count(Workflow.id)).where(Workflow.is_published.is_(True))) or 0
        )
        users_total = await session.scalar(select(func.count(BotUser.id))) or 0
        messages_total = await session.scalar(select(func.count(Message.id))) or 0
        result = await session.scalars(select(Workflow).order_by(Workflow.updated_at.desc()).limit(6))
        recent_workflows = list(result)
    except Exception as exc:
        logger.warning("Dashboard DB query error: %s", exc)
        db_status = "Disconnected / Error"
        db_badge_class = "status-red"

    rows_html = ""
    if recent_workflows:
        for wf in recent_workflows:
            status_badge = (
                '<span class="badge badge-success">● Опубликован</span>'
                if wf.is_published
                else '<span class="badge badge-draft">○ Черновик</span>'
            )
            has_token_badge = (
                '<span class="badge badge-info">Токен привязан</span>'
                if wf.telegram_bot_token
                else '<span class="badge badge-muted">Без токена</span>'
            )
            updated_str = wf.updated_at.strftime("%Y-%m-%d %H:%M") if wf.updated_at else "-"
            rows_html += f"""
            <tr>
                <td><strong>#{wf.id}</strong> {html.escape(wf.name)}</td>
                <td>{status_badge}</td>
                <td>{has_token_badge}</td>
                <td>{updated_str}</td>
            </tr>
            """
    else:
        rows_html = """
        <tr>
            <td colspan="4" style="text-align:center; color:#94a3b8; padding: 24px;">
                Сценарии пока не созданы. Перейдите в <a href="http://localhost:3000" class="link-inline">Visual Editor</a>, чтобы собрать первого бота!
            </td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BotForge API Control Center</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #090d16;
            --bg-card: #111827;
            --bg-card-hover: #172033;
            --border: #1f2937;
            --border-highlight: #374151;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --accent-primary: #6366f1;
            --accent-glow: rgba(99, 102, 241, 0.25);
            --success: #10b981;
            --warning: #f59e0b;
            --info: #3b82f6;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            background: radial-gradient(circle at 50% 0%, #171d33 0%, var(--bg-base) 70%);
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            min-height: 100vh;
            padding: 32px 16px;
            display: flex;
            justify-content: center;
        }}
        .container {{
            width: 100%;
            max-width: 1080px;
            display: flex;
            flex-direction: column;
            gap: 28px;
        }}
        .header {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .logo-box {{
            width: 46px;
            height: 46px;
            border-radius: 12px;
            background: linear-gradient(135deg, #6366f1, #a855f7);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            box-shadow: 0 0 20px var(--accent-glow);
        }}
        .brand-title {{
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(90deg, #ffffff, #c7d2fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .brand-subtitle {{
            font-size: 13px;
            color: var(--text-muted);
            margin-top: 2px;
        }}
        .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 600;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.25);
            color: #34d399;
        }}
        .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 10px #10b981;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.5; transform: scale(0.9); }}
        }}

        /* Quick Navigation Action Grid */
        .actions-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }}
        .action-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            text-decoration: none;
            color: var(--text-main);
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: all 0.2s ease;
        }}
        .action-card:hover {{
            background: var(--bg-card-hover);
            border-color: var(--border-highlight);
            transform: translateY(-2px);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .action-card.primary {{
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.15));
            border-color: rgba(99, 102, 241, 0.4);
        }}
        .action-card.primary:hover {{
            border-color: rgba(99, 102, 241, 0.8);
            box-shadow: 0 10px 30px var(--accent-glow);
        }}
        .action-info h3 {{
            font-size: 16px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .action-info p {{
            font-size: 13px;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        .action-arrow {{
            font-size: 20px;
            color: var(--text-muted);
            transition: transform 0.2s ease;
        }}
        .action-card:hover .action-arrow {{
            transform: translateX(4px);
            color: #fff;
        }}

        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
        }}
        .stat-box {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .stat-label {{
            font-size: 13px;
            font-weight: 500;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #ffffff;
        }}
        .stat-sub {{
            font-size: 12px;
            color: #6ee7b7;
        }}

        /* Section Layout */
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
        }}
        .card-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 18px;
        }}
        .card-title {{
            font-size: 17px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        /* Table */
        .table-container {{
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            text-align: left;
        }}
        th {{
            color: var(--text-muted);
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 12px 14px;
            border-bottom: 1px solid var(--border);
        }}
        td {{
            padding: 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            color: var(--text-main);
        }}
        tr:last-child td {{
            border-bottom: none;
        }}

        /* Badges */
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-success {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}
        .badge-draft {{
            background: rgba(156, 163, 175, 0.12);
            color: #9ca3af;
            border: 1px solid rgba(156, 163, 175, 0.2);
        }}
        .badge-info {{
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}
        .badge-muted {{
            background: rgba(255, 255, 255, 0.05);
            color: #6b7280;
        }}

        /* Code box */
        .code-box {{
            background: #060911;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 16px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            color: #a5b4fc;
            overflow-x: auto;
            position: relative;
        }}
        .copy-btn {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: #1e293b;
            border: 1px solid #334155;
            color: #cbd5e1;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 11px;
            cursor: pointer;
            transition: background 0.2s ease;
        }}
        .copy-btn:hover {{
            background: #334155;
            color: #fff;
        }}
        .link-inline {{
            color: #818cf8;
            text-decoration: none;
        }}
        .link-inline:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Top Header -->
        <header class="header">
            <div class="brand">
                <div class="logo-box">⚡</div>
                <div>
                    <h1 class="brand-title">BotForge API Engine</h1>
                    <p class="brand-subtitle">Visual No-Code Telegram Bot Builder · Backend Service</p>
                </div>
            </div>
            <div class="status-pill">
                <span class="status-dot"></span>
                <span>FastAPI 0.116 Online</span>
            </div>
        </header>

        <!-- Quick Actions Navigation -->
        <div class="actions-grid">
            <a href="http://localhost:3000" target="_blank" class="action-card primary">
                <div class="action-info">
                    <h3>🎨 Visual Flow Editor</h3>
                    <p>Открыть веб-интерфейс конструктора (порт 3000)</p>
                </div>
                <div class="action-arrow">↗</div>
            </a>

            <a href="/docs" class="action-card">
                <div class="action-info">
                    <h3>📖 Swagger UI (API Docs)</h3>
                    <p>Интерактивная документация и тестирование API</p>
                </div>
                <div class="action-arrow">→</div>
            </a>

            <a href="/redoc" class="action-card">
                <div class="action-info">
                    <h3>📚 ReDoc Specification</h3>
                    <p>Альтернативная документация схемы OpenAPI</p>
                </div>
                <div class="action-arrow">→</div>
            </a>
        </div>

        <!-- Live Statistics -->
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-label">
                    <span>Всего сценариев</span>
                    <span>📑</span>
                </div>
                <div class="stat-value">{workflows_total}</div>
                <div class="stat-sub">{workflows_published} активно в Telegram</div>
            </div>

            <div class="stat-box">
                <div class="stat-label">
                    <span>Пользователей в ботах</span>
                    <span>👥</span>
                </div>
                <div class="stat-value">{users_total}</div>
                <div class="stat-sub">сохранено в bot_users</div>
            </div>

            <div class="stat-box">
                <div class="stat-label">
                    <span>Обработано сообщений</span>
                    <span>💬</span>
                </div>
                <div class="stat-value">{messages_total}</div>
                <div class="stat-sub">входящих и исходящих</div>
            </div>

            <div class="stat-box">
                <div class="stat-label">
                    <span>База данных</span>
                    <span>🗄️</span>
                </div>
                <div class="stat-value" style="font-size: 20px; margin-top: 4px; color: #34d399;">PostgreSQL 17</div>
                <div class="stat-sub">{db_status}</div>
            </div>
        </div>

        <!-- Registered Workflows -->
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">📋 Сценарии в базе данных</h2>
                <a href="http://localhost:3000" target="_blank" class="link-inline" style="font-size: 13px; font-weight:600;">+ Создать в конструкторе</a>
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Название</th>
                            <th>Статус</th>
                            <th>Telegram токен</th>
                            <th>Обновлен</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Telegram Webhook Helper -->
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">🤖 Настройка Telegram Webhook</h2>
            </div>
            <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 14px; line-height: 1.5;">
                Чтобы Telegram пересылал сообщения на этот сервер, пробросьте порт через <code>ngrok http 8000</code> и зарегистрируйте адрес вебхука:
            </p>
            <div class="code-box" id="webhookCode">
curl -X POST "https://api.telegram.org/bot&lt;YOUR_BOT_TOKEN&gt;/setWebhook" \\
  -H "Content-Type: application/json" \\
  -d '{{"url":"https://&lt;YOUR_PUBLIC_URL&gt;/api/telegram/webhook","secret_token":"&lt;YOUR_WEBHOOK_SECRET&gt;"}}'
            </div>
        </div>
    </div>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/workflows", response_model=list[WorkflowRead])
async def list_workflows(session: AsyncSession = Depends(get_session)) -> list[Workflow]:
    result = await session.scalars(select(Workflow).order_by(Workflow.updated_at.desc()))
    return list(result)


@app.get("/api/templates", response_model=list[TemplateInfo])
async def list_templates() -> list[TemplateInfo]:
    return TEMPLATES


@app.post("/api/workflows", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
async def create_workflow(payload: WorkflowCreate, session: AsyncSession = Depends(get_session)) -> Workflow:
    workflow = Workflow(
        name=payload.name,
        description=payload.description,
        definition=payload.definition.model_dump(),
    )
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)
    return workflow


@app.get("/api/workflows/{workflow_id}", response_model=WorkflowRead)
async def get_workflow(workflow_id: int, session: AsyncSession = Depends(get_session)) -> Workflow:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@app.put("/api/workflows/{workflow_id}", response_model=WorkflowRead)
async def update_workflow(
    workflow_id: int, payload: WorkflowCreate, session: AsyncSession = Depends(get_session)
) -> Workflow:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow.name = payload.name
    workflow.description = payload.description
    workflow.definition = payload.definition.model_dump()
    await session.commit()
    await session.refresh(workflow)
    return workflow


@app.delete("/api/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(workflow_id: int, session: AsyncSession = Depends(get_session)) -> None:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await session.delete(workflow)
    await session.commit()


@app.post("/api/workflows/{workflow_id}/publish", response_model=WorkflowRead)
async def publish_workflow(
    workflow_id: int, payload: WorkflowPublishRequest, session: AsyncSession = Depends(get_session)
) -> Workflow:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        validate_publishable_flow(FlowDefinition.model_validate(workflow.definition))
    except (FlowError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.telegram_bot_token is not None:
        token = payload.telegram_bot_token.strip()
        if token and ":" not in token:
            raise HTTPException(status_code=422, detail="Invalid Telegram token format")
        workflow.telegram_bot_token = token or None
    workflow.is_published = True
    await session.commit()
    await session.refresh(workflow)
    return workflow


@app.post("/api/workflows/{workflow_id}/stop", response_model=WorkflowRead)
async def stop_workflow(workflow_id: int, session: AsyncSession = Depends(get_session)) -> Workflow:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow.is_published = False
    await session.commit()
    await session.refresh(workflow)
    return workflow


@app.get("/api/workflows/{workflow_id}/analytics")
async def get_analytics(workflow_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        from sqlalchemy import text

        msg_count = await session.execute(text("select count(*) from messages where workflow_id=:wid"), {"wid": workflow_id})
        messages_total = msg_count.scalar() or 0
        user_count = await session.execute(text("select count(*) from bot_users where workflow_id=:wid"), {"wid": workflow_id})
        users_total = user_count.scalar() or 0
        recent = await session.execute(
            text("select direction, text, created_at from messages where workflow_id=:wid order by created_at desc limit 20"),
            {"wid": workflow_id},
        )
        recent_rows = [{"direction": r[0], "text": r[1], "created_at": r[2].isoformat() if r[2] else None} for r in recent.fetchall()]
        # activity last 7 days
        daily = await session.execute(
            text(
                "select date_trunc('day', created_at)::date as d, count(*) from messages where workflow_id=:wid and created_at > now() - interval '7 days' group by d order by d"
            ),
            {"wid": workflow_id},
        )
        activity = [{"date": str(r[0]), "count": r[1]} for r in daily.fetchall()]
    except Exception as exc:
        logger.warning("Failed to calculate analytics for workflow %s: %s", workflow_id, exc)
        messages_total = 0
        users_total = 0
        recent_rows = []
        activity = []
    return {
        "workflow_id": workflow_id,
        "is_published": workflow.is_published,
        "has_token": bool(workflow.telegram_bot_token),
        "users_total": users_total,
        "messages_total": messages_total,
        "recent_messages": recent_rows,
        "activity_7d": activity,
    }


@app.get("/api/workflows/{workflow_id}/users")
async def list_users(workflow_id: int, session: AsyncSession = Depends(get_session)) -> list[dict]:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        result = await session.scalars(select(BotUser).where(BotUser.workflow_id == workflow_id).order_by(BotUser.last_seen_at.desc()).limit(100))
        return [
            {
                "id": u.id,
                "telegram_user_id": u.telegram_user_id,
                "username": u.username,
                "current_node_id": u.current_node_id,
                "first_seen_at": u.first_seen_at.isoformat() if u.first_seen_at else None,
                "last_seen_at": u.last_seen_at.isoformat() if u.last_seen_at else None,
            }
            for u in result
        ]
    except Exception as exc:
        logger.warning("Failed to fetch users for workflow %s: %s", workflow_id, exc)
        return []


@app.get("/api/workflows/{workflow_id}/messages")
async def list_messages(workflow_id: int, limit: int = 100, session: AsyncSession = Depends(get_session)) -> list[dict]:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        result = await session.scalars(
            select(Message).where(Message.workflow_id == workflow_id).order_by(Message.created_at.desc()).limit(min(limit, 200))
        )
        return [
            {
                "id": m.id,
                "direction": m.direction,
                "text": m.text,
                "telegram_user_id": m.telegram_user_id,
                "node_id": m.node_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in result
        ]
    except Exception as exc:
        logger.warning("Failed to fetch messages for workflow %s: %s", workflow_id, exc)
        return []


@app.post("/api/simulate", response_model=SimulationResponse)
async def simulate_stateless(payload: StatelessSimulationRequest) -> SimulationResponse:
    try:
        return run_step(payload.definition, payload.message, payload.current_node_id, payload.state)
    except FlowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/workflows/{workflow_id}/simulate", response_model=SimulationResponse)
async def simulate(
    workflow_id: int, payload: SimulationRequest, session: AsyncSession = Depends(get_session)
) -> SimulationResponse:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        flow = FlowDefinition.model_validate(workflow.definition)
        return run_step(flow, payload.message, payload.current_node_id, payload.state)
    except FlowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _handle_telegram_update(
    update: dict,
    workflow_id: int | None,
    session: AsyncSession,
) -> dict[str, bool | str]:
    if not update:
        return {"accepted": False}

    # Telegram update parsing (supports message and callback_query)
    cq_id = None
    msg = update.get("message") or update.get("edited_message") or {}
    if "callback_query" in update:
        cq = update["callback_query"]
        cq_id = cq.get("id")
        msg = cq.get("message") or {}
        text = (cq.get("data") or "").strip()
        from_user = cq.get("from") or {}
        chat = msg.get("chat") or {}
    else:
        text = (msg.get("text") or msg.get("caption") or "").strip()
        from_user = msg.get("from") or {}
        chat = msg.get("chat") or {}

    telegram_user_id = from_user.get("id") or chat.get("id")
    chat_id = chat.get("id") or telegram_user_id
    username = from_user.get("username") or from_user.get("first_name")

    if telegram_user_id is None or chat_id is None:
        return {"accepted": True}

    # Resolve target workflow
    if workflow_id is not None:
        workflow = await session.get(Workflow, workflow_id)
        if workflow is None or not workflow.is_published:
            return {"accepted": True, "detail": "Workflow not found or stopped"}
    else:
        result = await session.scalars(
            select(Workflow).where(Workflow.is_published.is_(True)).order_by(Workflow.updated_at.desc()).limit(1)
        )
        workflow = next(iter(list(result)), None)
        if workflow is None:
            return {"accepted": True, "detail": "No published workflow"}

    update_id = update.get("update_id")
    if isinstance(update_id, int):
        inserted = await session.scalar(
            insert(TelegramUpdate)
            .values(workflow_id=workflow.id, update_id=update_id)
            .on_conflict_do_nothing()
            .returning(TelegramUpdate.update_id)
        )
        if inserted is None:
            await session.rollback()
            return {"accepted": True, "detail": "Duplicate update"}

    try:
        flow = FlowDefinition.model_validate(workflow.definition)
    except Exception as exc:
        logger.error("Failed to parse flow definition for workflow %s: %s", workflow.id, exc)
        return {"accepted": True}

    # upsert bot_user
    bot_user = await session.scalar(
        select(BotUser).where(BotUser.workflow_id == workflow.id, BotUser.telegram_user_id == telegram_user_id)
    )
    if bot_user is None:
        bot_user = BotUser(
            workflow_id=workflow.id,
            telegram_user_id=telegram_user_id,
            username=username,
            current_node_id=None,
            state={},
        )
        session.add(bot_user)
        await session.flush()

    # handle /start to reset
    current_node = bot_user.current_node_id
    if text == "/start":
        current_node = None
        bot_user.current_node_id = None
        bot_user.state = {}

    # store incoming
    try:
        session.add(
            Message(
                workflow_id=workflow.id,
                bot_user_id=bot_user.id,
                telegram_user_id=telegram_user_id,
                direction="in",
                text=text or "(empty)",
                node_id=current_node,
            )
        )
    except Exception as exc:
        logger.warning("Failed to record incoming message: %s", exc)

    try:
        response = run_step(flow, text, current_node, bot_user.state)
    except FlowError as exc:
        logger.warning("Flow execution error in workflow %s: %s", workflow.id, exc)
        response = None
    except Exception as exc:
        logger.error("Unexpected error in run_step for workflow %s: %s", workflow.id, exc)
        response = None

    token = workflow.telegram_bot_token or settings.telegram_bot_token

    # acknowledge callback query immediately if token is available
    if token and cq_id:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=4) as client:
                callback_response = await client.post(
                    f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                    json={"callback_query_id": cq_id},
                )
                callback_response.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to answer callback query %s: %s", cq_id, exc)

    if response is None:
        await session.commit()
        return {"accepted": True}

    bot_user.current_node_id = response.current_node_id
    bot_user.state = response.state
    bot_user.username = username or bot_user.username

    # store outgoing
    for out_text in response.messages:
        try:
            session.add(
                Message(
                    workflow_id=workflow.id,
                    bot_user_id=bot_user.id,
                    telegram_user_id=telegram_user_id,
                    direction="out",
                    text=out_text,
                    node_id=response.current_node_id,
                )
            )
        except Exception as exc:
            logger.warning("Failed to record outgoing message: %s", exc)
    await session.commit()

    # deliver to Telegram
    if token and response.messages:
        import httpx

        # Group choices into rows of 2 for better UX on mobile
        reply_markup: dict[str, Any] | None = None
        if response.choices:
            keyboard = []
            for i in range(0, len(response.choices), 2):
                keyboard.append([{"text": c} for c in response.choices[i : i + 2]])
            reply_markup = {"keyboard": keyboard, "resize_keyboard": True, "one_time_keyboard": True}
        elif response.complete or response.current_node_id:
            reply_markup = {"remove_keyboard": True}

        async with httpx.AsyncClient(timeout=6) as client:
            for i, out in enumerate(response.messages):
                is_last_message = i == len(response.messages) - 1
                payload: dict[str, Any] = {"chat_id": chat_id, "text": out}
                if is_last_message and reply_markup is not None:
                    payload["reply_markup"] = reply_markup
                try:
                    telegram_response = await client.post(
                        f"https://api.telegram.org/bot{token}/sendMessage", json=payload
                    )
                    telegram_response.raise_for_status()
                except Exception as exc:
                    logger.error("Failed to deliver message to Telegram chat %s: %s", chat_id, exc)
                    break
    return {"accepted": True}


@app.post("/api/telegram/webhook", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook_global(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool | str]:
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    return await _handle_telegram_update(update, workflow_id=None, session=session)


@app.post("/api/telegram/webhook/{workflow_id}", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook_by_id(
    workflow_id: int,
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool | str]:
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    return await _handle_telegram_update(update, workflow_id=workflow_id, session=session)
