from .schemas import FlowDefinition, SimulationResponse


class FlowError(ValueError):
    pass


def run_step(
    flow: FlowDefinition, message: str = "", current_node_id: str | None = None
) -> SimulationResponse:
    nodes = {node.id: node for node in flow.nodes}
    node_id = current_node_id or flow.start_id
    messages: list[str] = []

    for _ in range(len(nodes) + 1):
        node = nodes.get(node_id)
        if node is None:
            raise FlowError(f"Unknown node: {node_id}")

        if node.type == "message":
            if node.text:
                messages.append(node.text)
            if not node.next_id:
                return SimulationResponse(messages=messages, choices=[], current_node_id=None, complete=True)
            node_id = node.next_id
            continue

        if node.type == "choice":
            if not message:
                if node.text:
                    messages.append(node.text)
                return SimulationResponse(
                    messages=messages,
                    choices=[choice.label for choice in node.choices],
                    current_node_id=node.id,
                    complete=False,
                )
            selected = next((choice for choice in node.choices if choice.label.casefold() == message.casefold()), None)
            if selected is None:
                return SimulationResponse(
                    messages=["Choose one of the available options."],
                    choices=[choice.label for choice in node.choices],
                    current_node_id=node.id,
                    complete=False,
                )
            message = ""
            node_id = selected.next_id
            continue

        if node.type == "input":
            if not message:
                if node.text:
                    messages.append(node.text)
                return SimulationResponse(messages=messages, choices=[], current_node_id=node.id, complete=False)
            message = ""
            if not node.next_id:
                return SimulationResponse(messages=messages, choices=[], current_node_id=None, complete=True)
            node_id = node.next_id
            continue

        if node.type == "condition":
            if not message:
                if node.text:
                    messages.append(node.text)
                return SimulationResponse(messages=messages, choices=[], current_node_id=node.id, complete=False)
            contains = (node.condition_value or "").casefold()
            is_match = contains and contains in message.casefold()
            # empty condition_value => always false branch
            next_id = node.true_next_id if is_match else node.false_next_id
            if not next_id:
                return SimulationResponse(messages=messages, choices=[], current_node_id=None, complete=True)
            message = ""
            node_id = next_id
            continue

        if node.text:
            messages.append(node.text)
        return SimulationResponse(messages=messages, choices=[], current_node_id=None, complete=True)

    raise FlowError("The workflow contains a cycle without user input")

