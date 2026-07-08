from services.groq_service import (
    SYSTEM_PROMPT,
    estimate_tokens,
    get_usable_prompt_budget,
    trim_text_to_token_budget,
)

from db.messages import (
    get_recent_messages,
    get_messages_after_id,
    get_old_messages_for_summary,
    get_messages_for_manual_summary,
)

from db.conversations import get_conversation_summary
from db.prompt_memory import get_prompt_memory


MAX_HISTORY_WITHOUT_SUMMARY = 40
MAX_HISTORY_AFTER_SUMMARY = 40
SUMMARY_KEEP_LAST_MESSAGES = 10
SUMMARY_TARGET_TOKENS = 2500

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

SUMMARY_SYSTEM_PROMPT = (
    "Jesteś mechanizmem pamięci rozmowy technicznej. "
    "Streszczasz starszą część rozmowy tak, aby kolejny model mógł kontynuować pracę nad projektem. "
    "Zachowaj konkrety: decyzje, strukturę plików, błędy, poprawki, ustalenia, TODO i preferencje użytkownika. "
    "Nie dopisuj faktów, których nie ma w rozmowie. Pisz po polsku, zwięźle, technicznie."
)


def merge_runtime_context(saved_context, runtime_context):
    saved_context = (saved_context or "").strip()
    runtime_context = (runtime_context or "").strip()

    if saved_context and runtime_context:
        return (
            f"{saved_context}\n\n"
            "---\n"
            "BIEŻĄCY KONTEKST Z POLA CONTEXTBOX:\n"
            f"{runtime_context}"
        )

    return saved_context or runtime_context


def normalize_section_text(value):
    return str(value or "").strip()


def build_messages_from_prompt_sections(sections):
    sections = sections or {}

    messages = []

    system = normalize_section_text(sections.get("system"))
    summary = normalize_section_text(sections.get("summary"))
    facts = normalize_section_text(sections.get("facts"))
    decisions = normalize_section_text(sections.get("decisions"))
    context = normalize_section_text(sections.get("context"))
    history = sections.get("history") or []
    user_message = normalize_section_text(sections.get("user_message"))

    if system:
        for part in system.split("\n---\n"):
            part = part.strip()
            if part:
                messages.append({
                    "role": "system",
                    "content": part
                })

    if summary:
        if summary.startswith("STRESZCZENIE STARSZEJ CZĘŚCI ROZMOWY:"):
            summary_content = summary
        else:
            summary_content = (
                "STRESZCZENIE STARSZEJ CZĘŚCI ROZMOWY:\n"
                f"{summary}"
            )

        messages.append({
            "role": "system",
            "content": summary_content
        })

    if facts:
        messages.append({
            "role": "system",
            "content": f"FAKTY USTALONE W ROZMOWIE:\n{facts}"
        })

    if decisions:
        messages.append({
            "role": "system",
            "content": f"DECYZJE I ZAŁOŻENIA PROJEKTOWE:\n{decisions}"
        })

    if context:
        messages.append({
            "role": "system",
            "content": f"KONTEKST ROBOCZY / WORKSPACE:\n{context}"
        })

    for msg in history:
        role = msg.get("role")
        content = normalize_section_text(msg.get("content"))

        if role in ["user", "assistant", "system"] and content:
            messages.append({
                "role": role,
                "content": content
            })

    if user_message:
        messages.append({
            "role": "user",
            "content": user_message
        })

    return messages


def build_prompt_sections(prompt_data, user_message="", context=""):
    """
    Sekcje widoczne w popupie.

    Ważne: to NIE musi być dokładnie ta sama lista, która finalnie idzie do LLM.
    Popup ma pokazywać stan źródłowy pamięci rozmowy: summary, fakty,
    decyzje, kontekst i historię. Dopiero osobny etap buduje/przycina
    finalne messages do budżetu modelu.
    """
    return {
        "system": prompt_data.get("system") or SYSTEM_PROMPT,
        "summary": prompt_data.get("summary") or "",
        "facts": prompt_data.get("facts") or "",
        "decisions": prompt_data.get("decisions") or "",
        "context": prompt_data.get("context") or context or "",
        "history": prompt_data.get("history") or [],
        "user_message": user_message or prompt_data.get("user_message") or ""
    }


def build_visible_prompt_sections(memory, user_message=""):
    """
    Buduje sekcje przeznaczone do popupu z nieprzyciętej pamięci rozmowy.

    build_prompt_within_budget() może skrócić summary albo ograniczyć historię
    do zera. To jest poprawne dla wysyłki do LLM, ale błędne dla popupu,
    który ma być edytorem/podglądem całego dostępnego kontekstu rozmowy.
    """
    return {
        "system": memory.get("system") or SYSTEM_PROMPT,
        "summary": memory.get("summary") or "",
        "facts": memory.get("facts") or "",
        "decisions": memory.get("decisions") or "",
        "context": memory.get("context") or "",
        "history": memory.get("history") or [],
        "user_message": user_message or ""
    }


def build_summary_prompt_sections(
    current_summary,
    messages_to_summarize,
    target_tokens
):
    conversation_text = build_summary_text(messages_to_summarize)

    return {
        "system": SUMMARY_SYSTEM_PROMPT,
        "summary": current_summary or "",
        "facts": "",
        "decisions": "",
        "context": "",
        "history": messages_to_summarize or [],
        "user_message": (
            "Włącz widoczne elementy z pola SUMMARY oraz HISTORY do jednego "
            "aktualnego, uporządkowanego streszczenia starszej części rozmowy. "
            "Zachowaj decyzje, fakty, strukturę plików, błędy, poprawki, TODO "
            "i preferencje użytkownika. "
            f"Cel: maksymalnie około {target_tokens} tokenów.\n\n"
            "Tekst rozmowy do streszczenia znajduje się w sekcji HISTORY.\n\n"
            "Materiał pomocniczy z HISTORY w formie ciągłej:\n"
            f"{conversation_text}"
        )
    }


def build_messages(
    user_message,
    context,
    history,
    summary="",
    system=None,
    facts="",
    decisions=""
):
    return build_messages_from_prompt_sections({
        "system": system or SYSTEM_PROMPT,
        "summary": summary,
        "facts": facts,
        "decisions": decisions,
        "context": context,
        "history": history,
        "user_message": user_message
    })


def _load_dynamic_prompt_base(conversation_id, runtime_context=""):
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
        "system": SYSTEM_PROMPT,
        "summary": summary or "",
        "facts": "",
        "decisions": "",
        "context": runtime_context or "",
        "summarized_until_message_id": summarized_until_message_id,
        "history": history or [],
        "user_message": "",
        "source": source
    }


def load_prompt_memory(conversation_id, runtime_context=""):
    """
    Zwraca sekcje promptu do popupu.

    Ważne: zapisany prompt_memory jest nakładką na stan rozmowy z DB,
    a nie kompletnym zamiennikiem historii. Dzięki temu zapisanie samego
    SYSTEM nie powoduje zniknięcia HISTORY z popupu.

    Zasada:
    - system/facts/decisions: jeśli zapisane, nadpisują bazę,
    - summary: jeśli zapisane, nadpisuje summary rozmowy; jeśli puste,
      bierzemy aktualne summary z conversations,
    - context: zapisany context łączymy z bieżącym contextBox,
    - history: jeśli zapisana historia nie jest pusta, używamy jej;
      w przeciwnym razie bierzemy dynamiczną historię z messages,
    - user_message: nie pochodzi z pamięci; ustawia ją bieżące pole input
      w build_prompt_sections().
    """
    base = _load_dynamic_prompt_base(
        conversation_id=conversation_id,
        runtime_context=runtime_context
    )

    saved_memory = get_prompt_memory(conversation_id)

    if not saved_memory:
        return base

    saved_history = saved_memory.get("history") or []

    return {
        "system": saved_memory.get("system") or base["system"],
        "summary": saved_memory.get("summary") or base["summary"],
        "facts": saved_memory.get("facts") or base["facts"],
        "decisions": saved_memory.get("decisions") or base["decisions"],
        "context": merge_runtime_context(
            saved_memory.get("context"),
            runtime_context
        ) or base["context"],
        "history": saved_history or base["history"],
        "user_message": "",
        "summarized_until_message_id": base["summarized_until_message_id"],
        "source": "saved_prompt_memory_overlay"
    }

def build_prompt_within_budget(
    model,
    user_message,
    context,
    history,
    summary="",
    system=None,
    facts="",
    decisions=""
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
                summary=trimmed_summary,
                system=system,
                facts=facts,
                decisions=decisions
            )

            token_estimate = estimate_tokens(messages)

            if token_estimate <= usable_budget:
                return {
                    "messages": messages,
                    "system": system or SYSTEM_PROMPT,
                    "history": selected_history,
                    "summary": trimmed_summary,
                    "facts": facts,
                    "decisions": decisions,
                    "context": context,
                    "user_message": user_message,
                    "tokens_estimate": token_estimate,
                    "token_budget": usable_budget,
                    "history_limit": history_limit,
                    "summary_token_limit": summary_limit,
                    "summary_was_trimmed": trimmed_summary != (summary or ""),
                    "summary_used": bool(trimmed_summary),
                    "history_messages_loaded": len(history),
                    "history_messages_used": len(selected_history),
                    "context_tokens": estimate_tokens([
                        {
                            "role": "system",
                            "content": f"KONTEKST ROBOCZY / WORKSPACE:\n{context}"
                        }
                    ]) if context else 0,
                    "summary_tokens": estimate_tokens([
                        {
                            "role": "system",
                            "content": trimmed_summary
                        }
                    ]) if trimmed_summary else 0,
                    "history_tokens": estimate_tokens(selected_history),
                }

    fallback_messages = build_messages(
        user_message=user_message,
        context=context,
        history=[],
        summary="",
        system=system,
        facts=facts,
        decisions=decisions
    )

    token_estimate = estimate_tokens(fallback_messages)

    if token_estimate <= usable_budget:
        return {
            "messages": fallback_messages,
            "system": system or SYSTEM_PROMPT,
            "history": [],
            "summary": "",
            "facts": facts,
            "decisions": decisions,
            "context": context,
            "user_message": user_message,
            "tokens_estimate": token_estimate,
            "token_budget": usable_budget,
            "history_limit": 0,
            "summary_token_limit": 0,
            "summary_was_trimmed": bool(summary),
            "summary_used": False,
            "history_messages_loaded": len(history),
            "history_messages_used": 0,
            "context_tokens": estimate_tokens([
                {
                    "role": "system",
                    "content": f"KONTEKST ROBOCZY / WORKSPACE:\n{context}"
                }
            ]) if context else 0,
            "summary_tokens": 0,
            "history_tokens": 0,
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
    memory = load_prompt_memory(
        conversation_id=conversation_id,
        runtime_context=context
    )

    effective_user_message = user_message or memory.get("user_message") or ""

    prompt_data = build_prompt_within_budget(
        model=model,
        user_message=effective_user_message,
        context=memory["context"],
        history=memory["history"],
        summary=memory["summary"],
        system=memory["system"],
        facts=memory["facts"],
        decisions=memory["decisions"]
    )

    prompt_data["prompt_source"] = memory["source"]
    prompt_data["summarized_until_message_id"] = memory[
        "summarized_until_message_id"
    ]
    prompt_data["model"] = model

    # Sekcje do popupu muszą pochodzić z nieprzyciętej pamięci rozmowy.
    # prompt_data["history"] może być już przycięte do budżetu modelu.
    prompt_data["visible_prompt_sections"] = build_visible_prompt_sections(
        memory=memory,
        user_message=effective_user_message
    )

    return prompt_data


def build_summary_text(messages):
    lines = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            label = "Użytkownik"
        elif role == "assistant":
            label = "Asystent"
        else:
            continue

        lines.append(f"{label}: {content}")

    return "\n\n".join(lines)


def build_summary_prompt_for_conversation(
    conversation_id,
    model
):
    memory = load_prompt_memory(conversation_id)

    # Ręczny przycisk "History → Summary" powinien streszczać realną
    # historię rozmowy od ostatniego zapisanego summary, a nie tylko
    # wiadomości starsze niż ostatnie SUMMARY_KEEP_LAST_MESSAGES. Ten drugi
    # tryb jest dobry dla automatycznej kompresji, ale dla ręcznego przycisku
    # dawał mylące "Brak starszej historii" przy krótszych rozmowach.
    messages_to_summarize = get_messages_for_manual_summary(
        conversation_id=conversation_id,
        after_id=memory["summarized_until_message_id"]
    )

    if not messages_to_summarize:
        return {
            "messages": [],
            "history": [],
            "summary": memory["summary"],
            "summary_until_message_id": memory["summarized_until_message_id"],
            "tokens_estimate": 0,
            "token_budget": get_usable_prompt_budget(model),
            "prompt_source": "summary_not_needed",
            "summary_used": bool(memory["summary"]),
            "history_messages_loaded": 0,
            "history_messages_used": 0,
            "model": model,
        }

    summary_until_message_id = max(
        msg["id"] for msg in messages_to_summarize
    )

    prompt_sections = build_summary_prompt_sections(
        current_summary=memory["summary"],
        messages_to_summarize=messages_to_summarize,
        target_tokens=SUMMARY_TARGET_TOKENS
    )

    messages = build_messages_from_prompt_sections(prompt_sections)

    return {
        "messages": messages,
        "prompt_sections": prompt_sections,
        "history": messages_to_summarize,
        "summary": memory["summary"],
        "summary_until_message_id": summary_until_message_id,
        "tokens_estimate": estimate_tokens(messages),
        "token_budget": get_usable_prompt_budget(model),
        "prompt_source": "summary_prompt_builder",
        "summary_used": bool(memory["summary"]),
        "history_messages_loaded": len(messages_to_summarize),
        "history_messages_used": len(messages_to_summarize),
        "summary_token_limit": SUMMARY_TARGET_TOKENS,
        "model": model,
    }


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
