"""Check the project settings and the subagent files that go with them."""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / ".claude/settings.json"
TEMPLATE = ROOT / "templates/AGENT.md"
LANE_INVESTIGATOR = ROOT / ".claude/agents/lane-investigator.md"
READ_ONLY_TOOLS = {"Read", "Grep", "Glob"}


def frontmatter(path):
    """The `key: value` lines between the opening and closing `---`, as a dict."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise AssertionError(f"{path.name} has no frontmatter")
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if line.strip() and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    raise AssertionError(f"{path.name} has no closing ---")


def tool_names(value):
    return {name.strip() for name in value.split(",") if name.strip()}


def command_patterns(rules, tool):
    """The patterns of the rules in one list that name `tool`, such as `Bash`."""
    matches = [re.fullmatch(tool + r"\((.*)\)", rule) for rule in rules]
    return {match.group(1) for match in matches if match}


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        self.permissions = self.settings.get("permissions", {})

    def rule_lists(self):
        for name in ("allow", "deny", "ask"):
            yield name, self.permissions.get(name, [])

    def test_settings_parse(self):
        self.assertIsInstance(self.settings, dict)
        for name, rules in self.rule_lists():
            with self.subTest(list=name):
                self.assertIsInstance(rules, list)

    def test_command_rules_come_in_pairs(self):
        for name, rules in self.rule_lists():
            with self.subTest(list=name):
                self.assertEqual(command_patterns(rules, "Bash"), command_patterns(rules, "PowerShell"))

    def test_rules_say_python(self):
        for name, rules in self.rule_lists():
            for rule in rules:
                with self.subTest(list=name, rule=rule):
                    self.assertNotIn("python3", rule)


class AgentTests(unittest.TestCase):
    def test_template_has_every_field(self):
        fields = frontmatter(TEMPLATE)
        for key in ("name", "description", "tools", "model"):
            with self.subTest(field=key):
                self.assertTrue(fields.get(key), f"templates/AGENT.md has no {key}")

    def test_template_tools_are_read_only(self):
        tools = tool_names(frontmatter(TEMPLATE).get("tools", ""))
        self.assertTrue(tools)
        self.assertLessEqual(tools, READ_ONLY_TOOLS)

    def test_lane_investigator(self):
        if not LANE_INVESTIGATOR.exists():
            self.skipTest("no .claude/agents/lane-investigator.md yet")
        fields = frontmatter(LANE_INVESTIGATOR)
        self.assertEqual(fields.get("name"), "lane-investigator")
        self.assertEqual(tool_names(fields.get("tools", "")), READ_ONLY_TOOLS)
        self.assertEqual(fields.get("model"), "sonnet")


if __name__ == "__main__":
    unittest.main()
