import unittest
from unittest.mock import patch

from services.prompt_builder import load_prompt_memory


class PromptMemorySemanticsTests(unittest.TestCase):
    @patch("services.prompt_builder.get_prompt_memory")
    @patch("services.prompt_builder._load_dynamic_prompt_base")
    def test_history_is_always_dynamic(self, load_base, get_memory):
        load_base.return_value = {
            "system": "base", "summary": "db", "facts": "", "decisions": "",
            "context": "", "history": [{"role": "user", "content": "new"}],
            "summarized_until_message_id": 1, "source": "dynamic",
        }
        get_memory.return_value = {
            "system": "saved", "summary": "", "facts": "", "decisions": "",
            "context": "", "overrides": {"system": True, "summary": False,
            "facts": False, "decisions": False, "context": False},
        }
        result = load_prompt_memory(1)
        self.assertEqual(result["history"], [{"role": "user", "content": "new"}])
        self.assertEqual(result["system"], "saved")

    @patch("services.prompt_builder.get_prompt_memory")
    @patch("services.prompt_builder._load_dynamic_prompt_base")
    def test_explicit_empty_override_is_preserved(self, load_base, get_memory):
        load_base.return_value = {
            "system": "base", "summary": "db summary", "facts": "", "decisions": "",
            "context": "", "history": [], "summarized_until_message_id": 1,
            "source": "dynamic",
        }
        get_memory.return_value = {
            "system": "", "summary": "", "facts": "", "decisions": "",
            "context": "", "overrides": {"system": False, "summary": True,
            "facts": False, "decisions": False, "context": False},
        }
        result = load_prompt_memory(1)
        self.assertEqual(result["summary"], "")


if __name__ == "__main__":
    unittest.main()
