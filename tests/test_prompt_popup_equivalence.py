import unittest
from unittest.mock import patch

from services.prompt_builder import (
    build_messages_from_prompt_sections,
    build_prompt_for_conversation,
)


class PromptPopupEquivalenceTest(unittest.TestCase):
    def test_unedited_popup_rebuilds_exact_budgeted_prompt(self):
        memory = {
            "system": "System testowy",
            "summary": "Poprzednie ustalenia",
            "facts": "Fakt A",
            "decisions": "Decyzja B",
            "context": "FILE: app.py\nprint(1)",
            "history": [
                {"role": "user", "content": "Pytanie 1"},
                {"role": "assistant", "content": "Odpowiedź 1"},
            ],
            "user_message": "",
            "summarized_until_message_id": None,
            "source": "test_memory",
        }

        with patch(
            "services.prompt_builder.load_prompt_memory",
            return_value=memory,
        ):
            prompt_data = build_prompt_for_conversation(
                conversation_id=1,
                user_message="Aktualna wiadomość",
                context=memory["context"],
                model="llama-3.1-8b-instant",
            )

        rebuilt_messages = build_messages_from_prompt_sections(
            prompt_data["prompt_sections"]
        )

        self.assertEqual(rebuilt_messages, prompt_data["messages"])


if __name__ == "__main__":
    unittest.main()
