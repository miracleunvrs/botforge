from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Choice(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    next_id: str


class FlowNode(BaseModel):
    id: str
    type: Literal["message", "choice", "input", "end", "condition"]
    title: str = Field(min_length=1, max_length=80)
    text: str = Field(default="", max_length=1000)
    next_id: str | None = None
    choices: list[Choice] = Field(default_factory=list)
    # condition block: branch by substring in user message
    condition_value: str = Field(default="", max_length=200)
    true_next_id: str | None = None
    false_next_id: str | None = None


class FlowDefinition(BaseModel):
    start_id: str
    nodes: list[FlowNode]


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    definition: FlowDefinition


class WorkflowRead(WorkflowCreate):
    id: int
    is_published: bool
    created_at: datetime
    updated_at: datetime
    telegram_bot_token: str | None = None
    model_config = ConfigDict(from_attributes=True)


class WorkflowPublishRequest(BaseModel):
    telegram_bot_token: str | None = Field(default=None, max_length=120)


class TemplateInfo(BaseModel):
    id: str
    title: str
    description: str
    definition: FlowDefinition


class SimulationRequest(BaseModel):
    message: str = Field(default="", max_length=1000)
    current_node_id: str | None = None


class SimulationResponse(BaseModel):
    messages: list[str]
    choices: list[str]
    current_node_id: str | None
    complete: bool
