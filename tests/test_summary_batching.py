import unittest
from unittest.mock import patch

from services.prompt_builder import (
    build_messages_from_prompt_sections,
    build_summary_prompt_for_conversation,
    build_summary_prompt_sections,
    select_summary_batch,
)


class SummaryBatchingTest(unittest.TestCase):
    def test_history_is_not_duplicated_in_user_instruction(self):
        history = [
            {"id": 1, "role": "user", "content": "UNIKALNY_TEKST_ABC"},
            {"id": 2, "role": "assistant", "content": "Odpowiedź"},
        ]

        sections = build_summary_prompt_sections(
            current_summary="Poprzednie summary",
            messages_to_summarize=history,
            target_tokens=2500,
        )
        messages = build_messages_from_prompt_sections(sections)

        occurrences = sum(
            message["content"].count("UNIKALNY_TEKST_ABC")
            for message in messages
        )
        self.assertEqual(occurrences, 1)

    def test_batch_does_not_split_user_assistant_pair(self):
        history = [
            {"id": 1, "role": "user", "content": "A" * 900},
            {"id": 2, "role": "assistant", "content": "B" * 900},
            {"id": 3, "role": "user", "content": "C" * 900},
            {"id": 4, "role": "assistant", "content": "D" * 900},
        ]

        with patch(
            "services.prompt_builder.get_usable_prompt_budget",
            return_value=950,
        ):
            selected, _, _, _, _ = select_summary_batch(
                current_summary="",
                messages=history,
                model="test-model",
                target_tokens=2500,
            )

        self.assertEqual([m["id"] for m in selected], [1, 2])

    def test_summary_preview_reports_remaining_messages(self):
        memory = {
            "summary": "",
            "summarized_until_message_id": 0,
            "system": "",
            "facts": "",
            "decisions": "",
            "context": "",
            "history": [],
            "user_message": "",
            "source": "test",
        }
        history = [
            {"id": i, "role": "user" if i % 2 else "assistant", "content": "X" * 900}
            for i in range(1, 9)
        ]

        with patch("services.prompt_builder.load_prompt_memory", return_value=memory), \
             patch("services.prompt_builder.get_messages_for_manual_summary", return_value=history), \
             patch("services.prompt_builder.get_usable_prompt_budget", return_value=950):
            prompt_data = build_summary_prompt_for_conversation(
                conversation_id=1,
                model="test-model",
            )

        self.assertGreater(prompt_data["summary_messages_remaining"], 0)
        self.assertTrue(prompt_data["summary_has_more"])
        self.assertEqual(
            prompt_data["history_messages_loaded"],
            prompt_data["history_messages_used"] + prompt_data["summary_messages_remaining"],
        )


if __name__ == "__main__":
    unittest.main()
