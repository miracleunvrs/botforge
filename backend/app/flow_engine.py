from typing import Any

from .schemas import FlowDefinition, SimulationResponse


class FlowError(ValueError):
    pass


def validate_publishable_flow(flow: FlowDefinition) -> None:
    nodes = {node.id: node for node in flow.nodes}
    if not nodes:
        raise FlowError("The workflow has no nodes")
    if len(nodes) != len(flow.nodes):
        raise FlowError("Node IDs must be unique")
    if flow.start_id not in nodes:
        raise FlowError("The start node does not exist")

    for node in flow.nodes:
        targets: list[str] = []
        if node.next_id:
            targets.append(node.next_id)
        if node.type == "choice":
            if not node.choices:
                raise FlowError(f"Choice node '{node.title}' has no buttons")
            targets.extend(choice.next_id for choice in node.choices)
        if node.type == "condition":
            if not node.true_next_id or not node.false_next_id:
                raise FlowError(f"Condition node '{node.title}' needs both branches")
            targets.extend([node.true_next_id, node.false_next_id])
        missing = next((target for target in targets if target not in nodes), None)
        if missing:
            raise FlowError(f"Node '{node.title}' points to unknown node '{missing}'")


def interpolate_text(template: str, state: dict[str, Any]) -> str:
    if not template or not state:
        return template
    result = template
    for k, v in state.items():
        if k:
            result = result.replace(f"{{{{{k}}}}}", str(v)).replace(f"{{{k}}}", str(v))
    return result


def run_step(
    flow: FlowDefinition,
    message: str = "",
    current_node_id: str | None = None,
    state: dict[str, Any] | None = None,
) -> SimulationResponse:
    current_state = dict(state or {})
    nodes = {node.id: node for node in flow.nodes}
    node_id = current_node_id or flow.start_id

    # Fallback to start_id if node_id was deleted/missing
    if node_id not in nodes:
        node_id = flow.start_id

    messages: list[str] = []

    # If this is a fresh start (no current_node_id or command is /start), treat as start trigger
    is_start = current_node_id is None or message.strip() == "/start"
    current_msg = "" if is_start else message.strip()
    last_input_val = current_msg

    for _ in range(len(nodes) + 1):
        node = nodes.get(node_id)
        if node is None:
            raise FlowError(f"Unknown node: {node_id}")

        if node.type == "message":
            if node.text:
                messages.append(interpolate_text(node.text, current_state))
            if not node.next_id:
                return SimulationResponse(
                    messages=messages,
                    choices=[],
                    current_node_id=None,
                    complete=True,
                    state=current_state,
                )
            node_id = node.next_id
            continue

        if node.type == "choice":
            if not current_msg:
                if node.text:
                    messages.append(interpolate_text(node.text, current_state))
                return SimulationResponse(
                    messages=messages,
                    choices=[choice.label for choice in node.choices],
                    current_node_id=node.id,
                    complete=False,
                    state=current_state,
                )
            selected = next((choice for choice in node.choices if choice.label.casefold() == current_msg.casefold()), None)
            if selected is None:
                return SimulationResponse(
                    messages=messages + ["Choose one of the available options."],
                    choices=[choice.label for choice in node.choices],
                    current_node_id=node.id,
                    complete=False,
                    state=current_state,
                )
            if node.variable_name:
                current_state[node.variable_name] = selected.label
            current_msg = ""
            last_input_val = ""
            if not selected.next_id:
                return SimulationResponse(
                    messages=messages,
                    choices=[],
                    current_node_id=None,
                    complete=True,
                    state=current_state,
                )
            node_id = selected.next_id
            continue

        if node.type == "input":
            if not current_msg:
                if node.text:
                    messages.append(interpolate_text(node.text, current_state))
                return SimulationResponse(
                    messages=messages,
                    choices=[],
                    current_node_id=node.id,
                    complete=False,
                    state=current_state,
                )
            last_input_val = current_msg
            var_key = node.variable_name or node.id
            current_state[var_key] = last_input_val
            current_msg = ""
            if not node.next_id:
                return SimulationResponse(
                    messages=messages,
                    choices=[],
                    current_node_id=None,
                    complete=True,
                    state=current_state,
                )
            node_id = node.next_id
            continue

        if node.type == "condition":
            eval_text = current_msg or last_input_val
            if not eval_text:
                if node.text:
                    messages.append(interpolate_text(node.text, current_state))
                return SimulationResponse(
                    messages=messages,
                    choices=[],
                    current_node_id=node.id,
                    complete=False,
                    state=current_state,
                )
            contains = (node.condition_value or "").casefold()
            is_match = bool(contains and contains in eval_text.casefold())
            # empty condition_value => always false branch
            next_id = node.true_next_id if is_match else node.false_next_id
            current_msg = ""
            last_input_val = ""
            if not next_id:
                return SimulationResponse(
                    messages=messages,
                    choices=[],
                    current_node_id=None,
                    complete=True,
                    state=current_state,
                )
            node_id = next_id
            continue

        if node.text:
            messages.append(interpolate_text(node.text, current_state))
        return SimulationResponse(
            messages=messages,
            choices=[],
            current_node_id=None,
            complete=True,
            state=current_state,
        )

    raise FlowError("The workflow contains a cycle without user input")
