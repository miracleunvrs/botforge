import unittest

from app.flow_engine import FlowError, run_step, validate_publishable_flow
from app.schemas import FlowDefinition
from app.templates import TEMPLATES


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


class TestFlowEngine(unittest.TestCase):
    def test_flow_waits_for_choice(self):
        result = run_step(FLOW)
        self.assertEqual(result.messages, ["Hello!", "How can we help?"])
        self.assertEqual(result.choices, ["Contact us"])
        self.assertEqual(result.current_node_id, "menu")
        self.assertFalse(result.complete)

    def test_start_command_does_not_break_choice(self):
        result = run_step(FLOW, "/start", None)
        self.assertEqual(result.messages, ["Hello!", "How can we help?"])
        self.assertEqual(result.choices, ["Contact us"])
        self.assertEqual(result.current_node_id, "menu")
        self.assertFalse(result.complete)

    def test_flow_finishes_after_choice(self):
        result = run_step(FLOW, "Contact us", "menu")
        self.assertTrue(result.complete)
        self.assertEqual(result.messages, ["We will reply soon."])

    def test_unknown_node_restarts_from_beginning(self):
        result = run_step(FLOW, current_node_id="missing")
        self.assertEqual(result.messages, ["Hello!", "How can we help?"])
        self.assertEqual(result.current_node_id, "menu")

    def test_input_state_is_available_to_later_messages(self):
        flow = FlowDefinition.model_validate(
            {
                "start_id": "ask",
                "nodes": [
                    {"id": "ask", "type": "input", "title": "Name", "text": "Your name?", "variable_name": "name", "next_id": "done"},
                    {"id": "done", "type": "end", "title": "Done", "text": "Hello, {{name}}!"},
                ],
            }
        )
        first = run_step(flow)
        second = run_step(flow, "Ada", first.current_node_id, first.state)
        self.assertEqual(second.messages, ["Hello, Ada!"])
        self.assertEqual(second.state, {"name": "Ada"})

    def test_publish_validation_rejects_missing_choice_targets(self):
        broken = FlowDefinition.model_validate(
            {"start_id": "menu", "nodes": [{"id": "menu", "type": "choice", "title": "Menu", "choices": []}]}
        )
        with self.assertRaises(FlowError):
            validate_publishable_flow(broken)

    def test_condition_waits_for_input_when_no_prior_message(self):
        result = run_step(FLOW_CONDITION)
        self.assertEqual(result.messages, ["Hi", "check"])
        self.assertEqual(result.current_node_id, "cond")
        self.assertFalse(result.complete)

    def test_condition_true_branch(self):
        result = run_step(FLOW_CONDITION, "say hello world", "cond")
        self.assertTrue(result.complete)
        self.assertEqual(result.messages, ["yes branch"])

    def test_condition_false_branch(self):
        result = run_step(FLOW_CONDITION, "bye", "cond")
        self.assertTrue(result.complete)
        self.assertEqual(result.messages, ["no branch"])

    def test_condition_empty_value_goes_false(self):
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
        self.assertEqual(result.messages, ["n"])
        self.assertTrue(result.complete)

    def test_input_preserves_prior_messages(self):
        result = run_step(FLOW_INPUT)
        self.assertEqual(result.messages, ["welcome", "enter"])
        self.assertEqual(result.current_node_id, "ask")
        self.assertFalse(result.complete)

    def test_lead_template_flow_with_condition(self):
        lead_template = next(t for t in TEMPLATES if t.id == "lead")
        flow = lead_template.definition

        # 1. Start
        r1 = run_step(flow, "/start", None)
        self.assertEqual(r1.current_node_id, "ask_name")
        self.assertEqual(r1.messages, ["Здравствуйте! Оставьте заявку и мы перезвоним.", "Как к вам обращаться?"])

        # 2. Provide name
        r2 = run_step(flow, "Алексей", "ask_name")
        self.assertEqual(r2.current_node_id, "ask_phone")
        self.assertEqual(r2.messages, ["Укажите номер телефона:"])

        # 3. Provide valid phone with + -> evaluates condition and goes to success
        r3 = run_step(flow, "+79991234567", "ask_phone")
        self.assertTrue(r3.complete)
        self.assertIn("Спасибо! Заявка принята.", r3.messages[0])

        # 4. Provide phone without + -> evaluates condition to retry
        r4 = run_step(flow, "89991234567", "ask_phone")
        self.assertTrue(r4.complete)
        self.assertEqual(len(r4.messages), 2)
        self.assertIn("без кода страны", r4.messages[0])
        self.assertIn("Спасибо! Заявка принята.", r4.messages[1])

    def test_feedback_template_flow(self):
        fb_template = next(t for t in TEMPLATES if t.id == "feedback")
        flow = fb_template.definition

        # 1. Start
        r1 = run_step(flow)
        self.assertEqual(r1.current_node_id, "ask_text")

        # 2. Positive feedback -> goes to thanks_pos
        r2 = run_step(flow, "Большое спасибо, всё супер!", "ask_text")
        self.assertTrue(r2.complete)
        self.assertIn("Спасибо за тёплые слова", r2.messages[0])


if __name__ == "__main__":
    unittest.main()
