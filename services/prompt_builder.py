from services.groq_service import (
    SYSTEM_PROMPT,
    estimate_tokens,
    get_usable_prompt_budget,
    trim_text_to_token_budget,
)

from db.messages import (
    get_recent_messages,
    get_messages_after_id,
)

from db.conversations import get_conversation_summary


MAX_HISTORY_WITHOUT_SUMMARY = 40
MAX_HISTORY_AFTER_SUMMARY = 40

HISTORY_LIMIT_CANDIDATES = [
    40,
    30,
    20,
    12,
    8,
    4,
    2,
    0,
]

SUMMARY_TOKEN_CANDIDATES = [
    6000,
    4000,
    2500,
    1500,
    900,
    500,
    250,
    0,
]


def build_messages(
    user_message,
    context,
    history,
    summary=""
):
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    if summary:
        messages.append({
            "role": "system",
            "content": (
                "STRESZCZENIE STARSZEJ CZĘŚCI ROZMOWY:\n"
                f"{summary}"
            )
        })

    if context:
        messages.append({
            "role": "system",
            "content": f"KONTEKST:\n{context}"
        })

    for msg in history:
        if msg.get("role") in ["user", "assistant"]:
            messages.append({
                "role": msg["role"],
                "content": msg.get("content", "")
            })

    messages.append({
        "role": "user",
        "content": user_message
    })

    return messages


def load_prompt_memory(conversation_id):
    summary_data = get_conversation_summary(conversation_id)

    summary = summary_data["summary"]
    summarized_until_message_id = summary_data[
        "summarized_until_message_id"
    ]

    if summary:
        history = get_messages_after_id(
            conversation_id=conversation_id,
            after_id=summarized_until_message_id,
            limit=MAX_HISTORY_AFTER_SUMMARY
        )

        source = "summary_plus_messages_after_summary"
    else:
        history = get_recent_messages(
            conversation_id=conversation_id,
            limit=MAX_HISTORY_WITHOUT_SUMMARY
        )

        source = "recent_history_without_summary"

    return {
        "summary": summary,
        "summarized_until_message_id": summarized_until_message_id,
        "history": history,
        "source": source
    }


def build_prompt_within_budget(
    model,
    user_message,
    context,
    history,
    summary=""
):
    usable_budget = get_usable_prompt_budget(model)

    for summary_limit in SUMMARY_TOKEN_CANDIDATES:
        trimmed_summary = trim_text_to_token_budget(
            summary,
            summary_limit
        )

        for history_limit in HISTORY_LIMIT_CANDIDATES:
            selected_history = (
                history[-history_limit:]
                if history_limit > 0
                else []
            )

            messages = build_messages(
                user_message=user_message,
                context=context,
                history=selected_history,
                summary=trimmed_summary
            )

            token_estimate = estimate_tokens(messages)

            if token_estimate <= usable_budget:
                return {
                    "messages": messages,
                    "history": selected_history,
                    "summary": trimmed_summary,
                    "tokens_estimate": token_estimate,
                    "token_budget": usable_budget,
                    "history_limit": history_limit,
                    "summary_token_limit": summary_limit,
                    "summary_was_trimmed": trimmed_summary != (summary or ""),
                    "summary_used": bool(trimmed_summary),
                    "history_messages_loaded": len(history),
                    "history_messages_used": len(selected_history)
                }

    fallback_messages = build_messages(
        user_message=user_message,
        context=context,
        history=[],
        summary=""
    )

    token_estimate = estimate_tokens(fallback_messages)

    if token_estimate <= usable_budget:
        return {
            "messages": fallback_messages,
            "history": [],
            "summary": "",
            "tokens_estimate": token_estimate,
            "token_budget": usable_budget,
            "history_limit": 0,
            "summary_token_limit": 0,
            "summary_was_trimmed": bool(summary),
            "summary_used": False,
            "history_messages_loaded": len(history),
            "history_messages_used": 0
        }

    raise ValueError(
        "Prompt jest nadal za długi mimo usunięcia historii i streszczenia. "
        "Skróć kontekst albo załącz mniejszy fragment kodu. "
        f"Estymacja: {token_estimate} tokenów, budżet: {usable_budget}."
    )


def build_prompt_for_conversation(
    conversation_id,
    user_message,
    context,
    model
):
    memory = load_prompt_memory(conversation_id)

    prompt_data = build_prompt_within_budget(
        model=model,
        user_message=user_message,
        context=context,
        history=memory["history"],
        summary=memory["summary"]
    )

    prompt_data["prompt_source"] = memory["source"]
    prompt_data["summarized_until_message_id"] = memory[
        "summarized_until_message_id"
    ]

    return prompt_data


def extract_summary_from_messages(messages):
    if not isinstance(messages, list):
        return ""

    for msg in messages:
        if msg.get("role") != "system":
            continue

        content = msg.get("content") or ""

        if content.startswith("STRESZCZENIE STARSZEJ CZĘŚCI ROZMOWY:"):
            return content.replace(
                "STRESZCZENIE STARSZEJ CZĘŚCI ROZMOWY:\n",
                "",
                1
            ).strip()

        if content.startswith("STRESZCZENIE"):
            return content.strip()

    return ""
