import pytest

from app.flow_engine import FlowError, run_step
from app.schemas import FlowDefinition


FLOW = FlowDefinition.model_validate(
    {
        "start_id": "welcome",
        "nodes": [
            {"id": "welcome", "type": "message", "title": "Welcome", "text": "Hello!", "next_id": "menu"},
            {
                "id": "menu",
                "type": "choice",
                "title": "Menu",
                "text": "How can we help?",
                "choices": [{"label": "Contact us", "next_id": "contact"}],
            },
            {"id": "contact", "type": "end", "title": "Done", "text": "We will reply soon."},
        ],
    }
)


def test_flow_waits_for_choice():
    result = run_step(FLOW)
    assert result.messages == ["Hello!", "How can we help?"]
    assert result.choices == ["Contact us"]
    assert result.current_node_id == "menu"


def test_flow_finishes_after_choice():
    result = run_step(FLOW, "Contact us", "menu")
    assert result.complete is True
    assert result.messages == ["We will reply soon."]


def test_unknown_node_is_rejected():
    with pytest.raises(FlowError):
        run_step(FLOW, current_node_id="missing")


FLOW_CONDITION = FlowDefinition.model_validate(
    {
        "start_id": "start",
        "nodes": [
            {"id": "start", "type": "message", "title": "Start", "text": "Hi", "next_id": "cond"},
            {"id": "cond", "type": "condition", "title": "Cond", "text": "check", "condition_value": "hello", "true_next_id": "yes", "false_next_id": "no"},
            {"id": "yes", "type": "end", "title": "Yes", "text": "yes branch"},
            {"id": "no", "type": "end", "title": "No", "text": "no branch"},
        ],
    }
)


def test_condition_waits_for_input():
    result = run_step(FLOW_CONDITION)
    assert result.messages == ["Hi", "check"]
    assert result.current_node_id == "cond"
    assert result.complete is False


def test_condition_true_branch():
    result = run_step(FLOW_CONDITION, "say hello world", "cond")
    assert result.complete is True
    assert result.messages == ["yes branch"]


def test_condition_false_branch():
    result = run_step(FLOW_CONDITION, "bye", "cond")
    assert result.messages == ["no branch"]


def test_condition_empty_value_goes_false():
    flow = FlowDefinition.model_validate(
        {
            "start_id": "c",
            "nodes": [
                {"id": "c", "type": "condition", "title": "C", "text": "t", "condition_value": "", "true_next_id": "yes", "false_next_id": "no"},
                {"id": "yes", "type": "end", "title": "Y", "text": "y"},
                {"id": "no", "type": "end", "title": "N", "text": "n"},
            ],
        }
    )
    result = run_step(flow, "anything", "c")
    assert result.messages == ["n"]


FLOW_INPUT = FlowDefinition.model_validate(
    {
        "start_id": "w",
        "nodes": [
            {"id": "w", "type": "message", "title": "W", "text": "welcome", "next_id": "ask"},
            {"id": "ask", "type": "input", "title": "Ask", "text": "enter", "next_id": "done"},
            {"id": "done", "type": "end", "title": "Done", "text": "done"},
        ],
    }
)


def test_input_preserves_prior_messages():
    result = run_step(FLOW_INPUT)
    assert result.messages == ["welcome", "enter"]
    assert result.current_node_id == "ask"

