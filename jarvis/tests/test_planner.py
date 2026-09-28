import unittest

from jarvis.agent.planner import make_plan, parse_next_action, next_action, PlanParseError
from jarvis.agent.task_state import TaskState


class PlannerTests(unittest.TestCase):
    def test_make_plan_parses_plain_lines(self):
        llm = lambda prompt: "Open browser\n1. Search query\n- Extract results\n"
        plan = make_plan("do a thing", [], llm)
        self.assertEqual(plan, ["Open browser", "Search query", "Extract results"])

    def test_make_plan_falls_back_to_goal_when_llm_empty(self):
        plan = make_plan("open calculator", [], lambda p: "")
        self.assertEqual(plan, ["open calculator"])

    def test_make_plan_falls_back_when_no_llm(self):
        plan = make_plan("open calculator", [], None)
        self.assertEqual(plan, ["open calculator"])

    def test_parse_next_action_plain_json(self):
        raw = '{"thought": "opening", "action": "win_open_application", "parameters": {"app_name": "calc"}}'
        data = parse_next_action(raw, [{"name": "win_open_application", "parameters": {"app_name": {"required": True}}}])
        self.assertEqual(data["action"], "win_open_application")
        self.assertEqual(data["parameters"]["app_name"], "calc")

    def test_parse_next_action_strips_code_fences(self):
        raw = '```json\n{"action": "TASK_COMPLETE", "final_message": "done"}\n```'
        data = parse_next_action(raw, [])
        self.assertEqual(data["action"], "TASK_COMPLETE")

    def test_parse_next_action_extracts_json_from_chatter(self):
        raw = 'Sure, here you go:\n{"action": "TASK_COMPLETE", "final_message": "done"}\nHope that helps!'
        data = parse_next_action(raw, [])
        self.assertEqual(data["action"], "TASK_COMPLETE")

    def test_parse_next_action_raises_on_garbage(self):
        with self.assertRaises(PlanParseError):
            parse_next_action("I have no idea what to do", [])

    def test_parse_next_action_raises_on_missing_action_field(self):
        with self.assertRaises(PlanParseError):
            parse_next_action('{"thought": "hmm"}', [])

    def test_next_action_raises_when_llm_unavailable(self):
        ts = TaskState(goal="test")
        with self.assertRaises(PlanParseError):
            next_action(ts, [], None)


if __name__ == "__main__":
    unittest.main()
