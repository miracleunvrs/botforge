from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_session
from .flow_engine import FlowError, run_step
from .models import BotUser, Message, Workflow
from .schemas import (
    FlowDefinition,
    SimulationRequest,
    SimulationResponse,
    TemplateInfo,
    WorkflowCreate,
    WorkflowPublishRequest,
    WorkflowRead,
)
from .templates import TEMPLATES

app = FastAPI(title="BotForge API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Telegram-Bot-Api-Secret-Token"],
)


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


@app.post("/api/workflows/{workflow_id}/publish", response_model=WorkflowRead)
async def publish_workflow(
    workflow_id: int, payload: WorkflowPublishRequest, session: AsyncSession = Depends(get_session)
) -> Workflow:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
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
    except Exception:
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
    except Exception:
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
    except Exception:
        return []


@app.post("/api/workflows/{workflow_id}/simulate", response_model=SimulationResponse)
async def simulate(
    workflow_id: int, payload: SimulationRequest, session: AsyncSession = Depends(get_session)
) -> SimulationResponse:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        flow = FlowDefinition.model_validate(workflow.definition)
        return run_step(flow, payload.message, payload.current_node_id)
    except FlowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/telegram/webhook", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool | str]:
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    if not update:
        return {"accepted": False}

    # Telegram update parsing (supports message and callback_query)
    msg = update.get("message") or update.get("edited_message") or {}
    if "callback_query" in update:
        cq = update["callback_query"]
        msg = cq.get("message") or {}
        # use callback data as text
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

    # find published workflow (first published, fallback to any with token)
    result = await session.scalars(select(Workflow).where(Workflow.is_published.is_(True)).order_by(Workflow.updated_at.desc()).limit(1))
    workflow = next(iter(list(result)), None)
    if workflow is None:
        return {"accepted": True}

    try:
        flow = FlowDefinition.model_validate(workflow.definition)
    except Exception:
        return {"accepted": True}

    # upsert bot_user
    bot_user = await session.scalar(select(BotUser).where(BotUser.workflow_id == workflow.id, BotUser.telegram_user_id == telegram_user_id))
    if bot_user is None:
        bot_user = BotUser(workflow_id=workflow.id, telegram_user_id=telegram_user_id, username=username, current_node_id=None)
        session.add(bot_user)
        await session.flush()

    # handle /start to reset
    current_node = bot_user.current_node_id
    if text == "/start":
        current_node = None
        bot_user.current_node_id = None

    # store incoming
    try:
        session.add(Message(workflow_id=workflow.id, bot_user_id=bot_user.id, telegram_user_id=telegram_user_id, direction="in", text=text or "(empty)", node_id=current_node))
    except Exception:
        pass

    try:
        response = run_step(flow, text, current_node)
    except FlowError:
        response = None
    except Exception:
        response = None

    if response is None:
        await session.commit()
        return {"accepted": True}

    bot_user.current_node_id = response.current_node_id
    bot_user.username = username or bot_user.username
    # store outgoing
    for out_text in response.messages:
        try:
            session.add(Message(workflow_id=workflow.id, bot_user_id=bot_user.id, telegram_user_id=telegram_user_id, direction="out", text=out_text, node_id=response.current_node_id))
        except Exception:
            pass
    await session.commit()

    # deliver to Telegram
    token = workflow.telegram_bot_token or settings.telegram_bot_token
    if token and response.messages:
        import httpx

        reply_markup = None
        if response.choices:
            reply_markup = {"keyboard": [[{"text": c} for c in response.choices]], "resize_keyboard": True, "one_time_keyboard": True}
        async with httpx.AsyncClient(timeout=5) as client:
            for out in response.messages:
                payload: dict = {"chat_id": chat_id, "text": out}
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                    reply_markup = None  # only first message gets keyboard
                try:
                    await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
                except Exception:
                    break
    return {"accepted": True}
