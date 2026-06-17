from services.groq_service import (
    summarize_conversation_chunk,
    restructure_summary
)

from services.prompt_builder import (
    build_prompt_for_conversation,
    MAX_HISTORY_WITHOUT_SUMMARY
)

from db.messages import get_old_messages_for_summary

from db.conversations import (
    get_conversation_summary,
    update_conversation_summary
)


SUMMARY_RESTRUCTURE_THRESHOLD_RATIO = 0.80
SUMMARY_TARGET_TOKENS = 2500
SUMMARY_COMPACT_TARGET_TOKENS = 1500


def maybe_restructure_summary(
    conversation_id,
    model,
    prompt_data
):
    summary = prompt_data.get("summary") or ""

    if not summary:
        return

    token_budget = prompt_data.get("token_budget") or 0
    token_estimate = prompt_data.get("tokens_estimate") or 0

    if not token_budget:
        return

    used_ratio = token_estimate / token_budget

    should_restructure = (
        used_ratio >= SUMMARY_RESTRUCTURE_THRESHOLD_RATIO
        or prompt_data.get("summary_was_trimmed")
    )

    if not should_restructure:
        return

    structured_summary = restructure_summary(
        model=model,
        summary=summary,
        target_tokens=SUMMARY_COMPACT_TARGET_TOKENS
    )

    current_summary_data = get_conversation_summary(
        conversation_id
    )

    update_conversation_summary(
        conv_id=conversation_id,
        summary=structured_summary,
        summarized_until_message_id=current_summary_data[
            "summarized_until_message_id"
        ]
    )


def update_summary_if_needed(
    conversation_id,
    model
):
    summary_data = get_conversation_summary(
        conversation_id
    )

    old_messages = get_old_messages_for_summary(
        conversation_id=conversation_id,
        summarized_until_message_id=summary_data[
            "summarized_until_message_id"
        ],
        keep_last=MAX_HISTORY_WITHOUT_SUMMARY
    )

    if not old_messages:
        return

    new_summary = summarize_conversation_chunk(
        model=model,
        previous_summary=summary_data["summary"],
        messages=old_messages,
        target_tokens=SUMMARY_TARGET_TOKENS
    )

    last_summarized_id = old_messages[-1]["id"]

    update_conversation_summary(
        conv_id=conversation_id,
        summary=new_summary,
        summarized_until_message_id=last_summarized_id
    )
