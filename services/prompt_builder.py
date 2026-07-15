from services.groq_service import (
    SYSTEM_PROMPT,
    estimate_tokens,
    get_usable_prompt_budget,
    trim_text_to_token_budget,
)

from db.messages import (
    get_recent_messages,
    get_messages_after_id,
    get_messages_for_manual_summary,
)

from db.conversations import get_conversation_summary
from db.prompt_memory import get_prompt_memory


MAX_HISTORY_WITHOUT_SUMMARY = 40
MAX_HISTORY_AFTER_SUMMARY = 40
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
    """Sekcje odpowiadające dokładnie promptowi przygotowanemu do wysyłki.

    Historia i summary mogą być wcześniej ograniczone przez budżet modelu.
    Dzięki temu niezmodyfikowany popup odtwarza tę samą listę messages,
    która zostałaby wysłana bez otwierania popupu.
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


def build_summary_prompt_sections(
    current_summary,
    messages_to_summarize,
    target_tokens
):
    return {
        "system": SUMMARY_SYSTEM_PROMPT,
        "summary": current_summary or "",
        "facts": "",
        "decisions": "",
        "context": "",
        "history": messages_to_summarize or [],
        "user_message": (
            "Połącz istniejące SUMMARY z wiadomościami widocznymi w HISTORY "
            "w jedno aktualne streszczenie. HISTORY występuje w prompcie tylko "
            "raz — nie przepisuj rozmowy, tylko zachowaj informacje potrzebne "
            "do dalszej pracy. Nie pomijaj faktów tylko dlatego, że wydają się "
            "drobne. Nie dopisuj informacji, których nie ma w materiale.\n\n"
            "Zwróć wyłącznie streszczenie w poniższej strukturze:\n"
            "## Aktualny stan projektu\n"
            "## Fakty i wymagania użytkownika\n"
            "## Podjęte decyzje\n"
            "## Architektura i istotne pliki\n"
            "## Wykonane poprawki i napotkane błędy\n"
            "## Otwarte zadania i następne kroki\n"
            "## Nierozstrzygnięte kwestie\n\n"
            "Jeżeli dla sekcji nie ma danych, wpisz: Brak. "
            f"Docelowa długość: maksymalnie około {target_tokens} tokenów."
        )
    }


def _build_summary_candidate(current_summary, history, target_tokens):
    sections = build_summary_prompt_sections(
        current_summary=current_summary,
        messages_to_summarize=history,
        target_tokens=target_tokens
    )
    messages = build_messages_from_prompt_sections(sections)
    return sections, messages, estimate_tokens(messages)


def _avoid_splitting_user_assistant_pair(selected, all_messages):
    if not selected or len(selected) >= len(all_messages):
        return selected

    last = selected[-1]
    next_message = all_messages[len(selected)]

    if last.get("role") == "user" and next_message.get("role") == "assistant":
        return selected[:-1]

    return selected


def select_summary_batch(current_summary, messages, model, target_tokens):
    """Wybiera największy początkowy fragment historii mieszczący się w budżecie."""
    token_budget = get_usable_prompt_budget(model)

    if not messages:
        return [], None, [], 0, token_budget

    low = 1
    high = len(messages)
    best_count = 0
    best_sections = None
    best_messages = []
    best_tokens = 0

    while low <= high:
        middle = (low + high) // 2
        sections, prompt_messages, tokens = _build_summary_candidate(
            current_summary=current_summary,
            history=messages[:middle],
            target_tokens=target_tokens
        )

        if tokens <= token_budget:
            best_count = middle
            best_sections = sections
            best_messages = prompt_messages
            best_tokens = tokens
            low = middle + 1
        else:
            high = middle - 1

    if best_count == 0:
        raise ValueError(
            "Nawet pierwsza wiadomość historii nie mieści się w budżecie "
            "promptu summary. Skróć istniejące SUMMARY albo wybierz model "
            "z większym limitem."
        )

    selected = _avoid_splitting_user_assistant_pair(
        messages[:best_count],
        messages
    )

    if not selected:
        selected = messages[:best_count]

    if len(selected) != best_count:
        best_sections, best_messages, best_tokens = _build_summary_candidate(
            current_summary=current_summary,
            history=selected,
            target_tokens=target_tokens
        )

    return selected, best_sections, best_messages, best_tokens, token_budget


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

    prompt_data["prompt_sections"] = build_prompt_sections(
        prompt_data=prompt_data,
        user_message=effective_user_message,
        context=prompt_data.get("context", "")
    )

    return prompt_data


def build_summary_prompt_for_conversation(
    conversation_id,
    model
):
    memory = load_prompt_memory(conversation_id)

    all_messages = get_messages_for_manual_summary(
        conversation_id=conversation_id,
        after_id=memory["summarized_until_message_id"]
    )

    if not all_messages:
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
            "summary_messages_remaining": 0,
            "summary_has_more": False,
            "model": model,
        }

    selected, prompt_sections, messages, tokens_estimate, token_budget = (
        select_summary_batch(
            current_summary=memory["summary"],
            messages=all_messages,
            model=model,
            target_tokens=SUMMARY_TARGET_TOKENS
        )
    )

    summary_until_message_id = selected[-1]["id"]
    remaining = len(all_messages) - len(selected)

    return {
        "messages": messages,
        "prompt_sections": prompt_sections,
        "history": selected,
        "summary": memory["summary"],
        "summary_until_message_id": summary_until_message_id,
        "tokens_estimate": tokens_estimate,
        "token_budget": token_budget,
        "prompt_source": "summary_prompt_builder_chunked",
        "summary_used": bool(memory["summary"]),
        "history_messages_loaded": len(all_messages),
        "history_messages_used": len(selected),
        "summary_messages_remaining": remaining,
        "summary_has_more": remaining > 0,
        "summary_batch_first_message_id": selected[0]["id"],
        "summary_batch_last_message_id": selected[-1]["id"],
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
