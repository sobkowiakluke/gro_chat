from flask import (
    Blueprint,
    request,
    jsonify
)

import time
import traceback

from services.groq_service import (
    send_chat,
    get_models,
    estimate_tokens,
    get_usable_prompt_budget,
    validate_chat_model
)

from services.prompt_builder import (
    build_prompt_for_conversation,
    build_summary_prompt_for_conversation,
    build_messages_from_prompt_sections,
    build_prompt_sections,
    extract_summary_from_messages
)

from db.prompt_memory import (
    save_prompt_memory,
    delete_prompt_memory
)

from db.messages import (
    get_last_message_id,
    count_messages_after_id
)

from db.llm_requests import (
    create_llm_request,
    complete_chat_request,
    complete_summary_request,
    fail_llm_request
)

from db.conversations import (
    update_conversation_summary,
    get_conversation_summary
)


chat_bp = Blueprint(
    "chat",
    __name__
)


def validate_prompt_messages(messages, model):
    if not isinstance(messages, list) or not messages:
        raise ValueError("Prompt jest pusty.")

    normalized = []

    for index, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise ValueError(
                f"Nieprawidłowa wiadomość promptu na pozycji {index}."
            )

        role = msg.get("role")
        content = str(msg.get("content") or "").strip()

        if role not in ["system", "user", "assistant"]:
            raise ValueError(
                f"Nieprawidłowa rola promptu na pozycji {index}: {role!r}."
            )

        if not content:
            continue

        normalized.append({
            "role": role,
            "content": content
        })

    if not normalized:
        raise ValueError("Prompt nie zawiera żadnej niepustej wiadomości.")

    tokens_estimate = estimate_tokens(normalized)
    token_budget = get_usable_prompt_budget(model)

    if tokens_estimate > token_budget:
        excess = tokens_estimate - token_budget
        error = ValueError(
            "Edytowany prompt przekracza bezpieczny budżet modelu. "
            f"Estymacja: {tokens_estimate} tokenów, budżet: {token_budget}, "
            f"przekroczenie: {excess}. Skróć HISTORY, SUMMARY, CONTEXT "
            "albo USER MESSAGE."
        )
        error.tokens_estimate = tokens_estimate
        error.token_budget = token_budget
        error.prompt_excess_tokens = excess
        raise error

    return normalized, tokens_estimate, token_budget


def validate_requested_model(data):
    return validate_chat_model(
        data.get("model", "llama-3.1-8b-instant")
    )


def build_prompt_meta(prompt_data):
    return {
        "prompt_tokens_estimate": prompt_data.get("tokens_estimate"),
        "prompt_token_budget": prompt_data.get("token_budget"),
        "tokens_estimate": prompt_data.get("tokens_estimate"),
        "token_budget": prompt_data.get("token_budget"),
        "history_limit_used": prompt_data.get("history_limit"),
        "history_messages_loaded": prompt_data.get("history_messages_loaded"),
        "history_messages_used": prompt_data.get("history_messages_used"),
        "history_tokens": prompt_data.get("history_tokens"),
        "summary_token_limit_used": prompt_data.get("summary_token_limit"),
        "summary_tokens": prompt_data.get("summary_tokens"),
        "summary_was_trimmed": prompt_data.get("summary_was_trimmed"),
        "summary_used": prompt_data.get("summary_used"),
        "context_tokens": prompt_data.get("context_tokens"),
        "facts_used": bool(prompt_data.get("facts")),
        "decisions_used": bool(prompt_data.get("decisions")),
        "prompt_source": prompt_data.get("prompt_source"),
        "summarized_until_message_id": prompt_data.get("summarized_until_message_id"),
        "summary_until_message_id": prompt_data.get("summary_until_message_id"),
        "model": prompt_data.get("model"),
        "prompt_over_budget": bool(prompt_data.get("prompt_over_budget")),
        "prompt_excess_tokens": prompt_data.get("prompt_excess_tokens"),
        "summary_messages_remaining": prompt_data.get("summary_messages_remaining"),
        "summary_has_more": bool(prompt_data.get("summary_has_more")),
        "summary_batch_first_message_id": prompt_data.get("summary_batch_first_message_id"),
        "summary_batch_last_message_id": prompt_data.get("summary_batch_last_message_id")
    }


def get_last_user_message(messages):
    if not isinstance(messages, list):
        return ""

    for msg in reversed(messages):
        if msg.get("role") == "user":
            return (msg.get("content") or "").strip()

    return ""


def persist_visible_summary_if_present(
    conversation_id,
    messages,
    summarized_until_message_id
):
    summary = extract_summary_from_messages(messages)

    if not summary:
        return False

    update_conversation_summary(
        conv_id=conversation_id,
        summary=summary,
        summarized_until_message_id=summarized_until_message_id
    )

    return True


def validate_summary_request(conversation_id, summary_until_message_id):
    try:
        marker = int(summary_until_message_id)
    except (TypeError, ValueError):
        raise ValueError("Nieprawidłowy summary_until_message_id.")

    summary_state = get_conversation_summary(conversation_id)
    current_marker = int(summary_state.get("summarized_until_message_id") or 0)
    last_message_id = int(get_last_message_id(conversation_id) or 0)

    if marker <= current_marker:
        raise ValueError(
            "Zakres summary nie zawiera nowych wiadomości albo został już zapisany."
        )

    if marker > last_message_id:
        raise ValueError(
            "Zakres summary wykracza poza aktualną historię rozmowy."
        )

    return marker


def validate_summary_reply(reply):
    reply = str(reply or "").strip()

    if not reply:
        raise ValueError("Model zwrócił puste summary.")

    required_headings = [
        "## Aktualny stan projektu",
        "## Fakty i wymagania użytkownika",
        "## Podjęte decyzje",
        "## Architektura i istotne pliki",
        "## Wykonane poprawki i napotkane błędy",
        "## Otwarte zadania i następne kroki",
        "## Nierozstrzygnięte kwestie",
    ]

    missing = [heading for heading in required_headings if heading not in reply]

    if missing:
        raise ValueError(
            "Model zwrócił summary w niepełnej strukturze. Brakuje sekcji: "
            + ", ".join(missing)
        )

    return reply


# =========================
# CHAT / SUMMARY EXECUTOR
# =========================
@chat_bp.route(
    "/chat",
    methods=["POST"]
)
def chat():
    llm_request_id = None
    llm_request_finalized = False
    llm_request_started_at = None

    try:
        data = request.json or {}

        conversation_id = data.get("conversation_id")

        if not conversation_id:
            return jsonify({
                "reply": "Brak aktywnego chatu."
            }), 400

        try:
            model = validate_requested_model(data)
        except ValueError as e:
            return jsonify({
                "error": str(e)
            }), 400

        user_message = (
            data.get("message") or ""
        ).strip()

        context = data.get("context", "")
        edited_messages = data.get("messages")
        prompt_sections = data.get("prompt_sections")
        summary_mode = bool(data.get("summary_mode"))

        if not user_message and edited_messages:
            user_message = get_last_user_message(edited_messages)

        if not user_message and not summary_mode:
            return jsonify({
                "reply": "Brak wiadomości do wysłania."
            }), 400

        if summary_mode and prompt_sections:
            summary_instruction = (
                prompt_sections.get("summary_instruction") or ""
            ).strip()
            if not summary_instruction:
                return jsonify({
                    "reply": "Brak instrukcji SUMMARY INSTRUCTION w prompcie."
                }), 400

        last_message_id_before_send = get_last_message_id(
            conversation_id
        )

        if prompt_sections:
            final_messages = build_messages_from_prompt_sections(prompt_sections)
            final_messages, tokens_estimate, token_budget = validate_prompt_messages(
                final_messages,
                model
            )
            prompt_data = {
                "messages": final_messages,
                "prompt_sections": prompt_sections,
                "tokens_estimate": tokens_estimate,
                "token_budget": token_budget,
                "history_limit": None,
                "history_messages_loaded": None,
                "history_messages_used": len(prompt_sections.get("history") or []),
                "summary_token_limit": None,
                "summary_was_trimmed": False,
                "summary_used": bool(prompt_sections.get("summary")),
                "prompt_over_budget": False,
                "prompt_source": (
                    "edited_summary_sections_from_popup"
                    if summary_mode
                    else "edited_sections_from_popup"
                ),
                "summarized_until_message_id": last_message_id_before_send,
                "summary_until_message_id": data.get(
                    "summary_until_message_id"
                ),
                "model": model
            }
        elif edited_messages:
            final_messages, tokens_estimate, token_budget = validate_prompt_messages(
                edited_messages,
                model
            )
            prompt_data = {
                "messages": final_messages,
                "tokens_estimate": tokens_estimate,
                "token_budget": token_budget,
                "history_limit": None,
                "history_messages_loaded": None,
                "history_messages_used": None,
                "summary_token_limit": None,
                "summary_was_trimmed": False,
                "summary_used": bool(
                    extract_summary_from_messages(final_messages)
                ),
                "prompt_over_budget": False,
                "prompt_source": (
                    "edited_summary_prompt_from_popup"
                    if summary_mode
                    else "edited_prompt_from_popup"
                ),
                "summarized_until_message_id": last_message_id_before_send,
                "summary_until_message_id": data.get(
                    "summary_until_message_id"
                ),
                "model": model
            }
        else:
            prompt_data = build_prompt_for_conversation(
                conversation_id=conversation_id,
                user_message=user_message,
                context=context,
                model=model
            )
            final_messages = prompt_data["messages"]

        summary_until_message_id = None

        if summary_mode:
            summary_until_message_id = validate_summary_request(
                conversation_id=conversation_id,
                summary_until_message_id=data.get("summary_until_message_id")
            )

        # Zapis prompt_memory jest świadomą operacją użytkownika i może nastąpić
        # przed wywołaniem Groq. Historia wiadomości nadal jest zapisywana dopiero
        # po poprawnej odpowiedzi modelu.
        if prompt_sections and data.get("persist_prompt_memory"):
            save_prompt_memory(
                conversation_id=conversation_id,
                sections=prompt_sections,
                overrides=data.get("prompt_memory_overrides") or {}
            )

        # Każde rzeczywiste wywołanie API otrzymuje własny rekord audytowy.
        # Dokładny prompt jest zapisywany przed wysłaniem, również gdy API zwróci błąd.
        llm_request_id = create_llm_request(
            conversation_id=conversation_id,
            provider="groq",
            model=model,
            request_messages=final_messages,
            request_kind="summary" if summary_mode else "chat",
            prompt_source=prompt_data.get("prompt_source"),
            tokens_estimate=prompt_data.get("tokens_estimate")
        )
        llm_request_started_at = time.monotonic()

        llm_result = send_chat(
            model=model,
            messages=final_messages
        )
        reply = llm_result["content"]

        if summary_mode:
            reply = validate_summary_reply(reply)

            # Summary, marker oraz zakończenie llm_request są zapisywane
            # atomowo w jednej transakcji.
            complete_summary_request(
                request_id=llm_request_id,
                summary=reply,
                summarized_until_message_id=summary_until_message_id,
                tokens_in=llm_result.get("tokens_in"),
                tokens_out=llm_result.get("tokens_out"),
                latency_ms=llm_result.get("latency_ms"),
                api_request_id=llm_result.get("api_request_id")
            )
            llm_request_finalized = True

            remaining_messages = count_messages_after_id(
                conversation_id=conversation_id,
                after_id=summary_until_message_id
            )

            response = {
                "summary": reply,
                "summary_updated": True,
                "summary_mode": True,
                "summary_until_message_id": summary_until_message_id,
                "summary_messages_remaining": remaining_messages,
                "summary_has_more": remaining_messages > 0
            }
            prompt_meta = build_prompt_meta(prompt_data)
            prompt_meta["summary_messages_remaining"] = remaining_messages
            prompt_meta["summary_has_more"] = remaining_messages > 0
            response.update(prompt_meta)

            return jsonify(response)

        # Ręczna edycja SUMMARY w zwykłym popupie dotyczy tylko tego requestu.
        # Trwałe SUMMARY zapisuje wyłącznie jawna pamięć promptu, natomiast
        # conversations.summary aktualizuje tylko tryb History → Summary.
        summary_persisted = False

        complete_chat_request(
            request_id=llm_request_id,
            user_message=user_message,
            assistant_message=reply,
            tokens_in=llm_result.get("tokens_in"),
            tokens_out=llm_result.get("tokens_out"),
            latency_ms=llm_result.get("latency_ms"),
            api_request_id=llm_result.get("api_request_id")
        )
        llm_request_finalized = True

        response = {
            "reply": reply,
            "summary_persisted": summary_persisted
        }
        response["prompt_memory_overrides"] = prompt_data.get(
            "prompt_memory_overrides", {}
        )
        response.update(build_prompt_meta(prompt_data))

        return jsonify(response)

    except ValueError as e:
        if llm_request_id and not llm_request_finalized:
            elapsed_ms = None
            if llm_request_started_at is not None:
                elapsed_ms = round((time.monotonic() - llm_request_started_at) * 1000)
            try:
                fail_llm_request(
                    request_id=llm_request_id,
                    error_message=e,
                    error_type=type(e).__name__,
                    latency_ms=elapsed_ms
                )
                llm_request_finalized = True
            except Exception:
                print(traceback.format_exc())

        response = {
            "reply": "Nie można wysłać promptu.",
            "error": str(e)
        }

        for field in [
            "tokens_estimate",
            "token_budget",
            "prompt_excess_tokens"
        ]:
            value = getattr(e, field, None)
            if value is not None:
                response[field] = value

        response["prompt_over_budget"] = bool(
            getattr(e, "prompt_excess_tokens", None)
        )

        return jsonify(response), 400

    except Exception as e:
        if llm_request_id and not llm_request_finalized:
            elapsed_ms = None
            if llm_request_started_at is not None:
                elapsed_ms = round((time.monotonic() - llm_request_started_at) * 1000)
            try:
                fail_llm_request(
                    request_id=llm_request_id,
                    error_message=e,
                    error_type=type(e).__name__,
                    error_code=getattr(e, "code", None),
                    latency_ms=elapsed_ms
                )
                llm_request_finalized = True
            except Exception:
                print(traceback.format_exc())

        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "reply": "Błąd API Groq.",
            "error": str(e)
        }), 500


# =========================
# SUMMARY PROMPT PREVIEW
# =========================
@chat_bp.route(
    "/summary-context",
    methods=["POST"]
)
def summary_context():
    try:
        data = request.json or {}

        conversation_id = data.get("conversation_id")

        if not conversation_id:
            return jsonify({
                "error": "Brak aktywnego chatu."
            }), 400

        try:
            model = validate_requested_model(data)
        except ValueError as e:
            return jsonify({
                "error": str(e)
            }), 400

        prompt_data = build_summary_prompt_for_conversation(
            conversation_id=conversation_id,
            model=model
        )

        if not prompt_data.get("messages"):
            return jsonify({
                "error": "Brak historii do streszczenia."
            }), 400

        response = {
            "messages": prompt_data["messages"],
            "prompt_sections": prompt_data.get("prompt_sections"),
            "prompt_kind": "summary",
            "summary_mode": True
        }
        response["prompt_memory_overrides"] = prompt_data.get(
            "prompt_memory_overrides", {}
        )
        response.update(build_prompt_meta(prompt_data))

        return jsonify(response)

    except Exception as e:
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500


# =========================
# PROMPT MEMORY SAVE / RESET
# =========================
@chat_bp.route(
    "/prompt-memory",
    methods=["POST"]
)
def prompt_memory_save():
    try:
        data = request.json or {}

        conversation_id = data.get("conversation_id")

        if not conversation_id:
            return jsonify({
                "error": "Brak aktywnego chatu."
            }), 400

        try:
            model = validate_requested_model(data)
        except ValueError as e:
            return jsonify({
                "error": str(e)
            }), 400

        prompt_sections = data.get("prompt_sections") or {}
        candidate_messages = build_messages_from_prompt_sections(prompt_sections)

        try:
            _, tokens_estimate, token_budget = validate_prompt_messages(
                candidate_messages,
                model
            )
        except ValueError as e:
            response = {
                "error": str(e),
                "prompt_over_budget": bool(
                    getattr(e, "prompt_excess_tokens", None)
                )
            }
            for field in [
                "tokens_estimate",
                "token_budget",
                "prompt_excess_tokens"
            ]:
                value = getattr(e, field, None)
                if value is not None:
                    response[field] = value
            return jsonify(response), 400

        overrides = data.get("prompt_memory_overrides") or {}
        saved = save_prompt_memory(
            conversation_id=conversation_id,
            sections=prompt_sections,
            overrides=overrides,
        )

        # Zapis pamięci nie zmienia bieżącej HISTORY ani USER MESSAGE.
        effective = build_prompt_for_conversation(
            conversation_id=conversation_id,
            user_message=prompt_sections.get("user_message", ""),
            context="",
            model=model,
        )
        final_messages = effective["messages"]

        return jsonify({
            "saved": True,
            "prompt_sections": effective["prompt_sections"],
            "prompt_memory_overrides": saved["overrides"],
            "messages": final_messages,
            "tokens_estimate": tokens_estimate,
            "token_budget": token_budget,
            "prompt_over_budget": False,
            "prompt_source": "saved_prompt_memory"
        })

    except Exception as e:
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500


@chat_bp.route(
    "/prompt-memory",
    methods=["DELETE"]
)
def prompt_memory_delete():
    try:
        data = request.json or {}

        conversation_id = data.get("conversation_id")

        if not conversation_id:
            return jsonify({
                "error": "Brak aktywnego chatu."
            }), 400

        delete_prompt_memory(conversation_id)

        return jsonify({
            "deleted": True
        })

    except Exception as e:
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500


# =========================
# OLD ENDPOINT BLOCKED
# =========================
@chat_bp.route(
    "/compress-history",
    methods=["POST"]
)
def compress_history():
    return jsonify({
        "error": (
            "Endpoint /compress-history nie wykonuje już ukrytego wywołania LLM. "
            "Użyj /summary-context, sprawdź payload w popupie i wyślij go jawnie."
        )
    }), 410


# =========================
# MODELS
# =========================
@chat_bp.route("/models")
def models():
    try:
        return jsonify(
            get_models()
        )

    except Exception as e:
        print(str(e))

        return jsonify([])


# =========================
# POPUP PREVIEW
# =========================
@chat_bp.route(
    "/prompt-context",
    methods=["POST"]
)
def prompt_context():
    try:
        data = request.json or {}

        conversation_id = data.get("conversation_id")

        if not conversation_id:
            return jsonify({
                "error": "Brak aktywnego chatu."
            }), 400

        try:
            model = validate_requested_model(data)
        except ValueError as e:
            return jsonify({
                "error": str(e)
            }), 400

        user_message = data.get(
            "message",
            ""
        )

        context = data.get(
            "context",
            ""
        )
        prompt_sections = data.get("prompt_sections")

        if prompt_sections is not None:
            final_messages = build_messages_from_prompt_sections(prompt_sections)
            tokens_estimate = estimate_tokens(final_messages)
            token_budget = get_usable_prompt_budget(model)
            prompt_data = {
                "messages": final_messages,
                "prompt_sections": prompt_sections,
                "system": prompt_sections.get("system", ""),
                "summary": prompt_sections.get("summary", ""),
                "facts": prompt_sections.get("facts", ""),
                "decisions": prompt_sections.get("decisions", ""),
                "context": prompt_sections.get("context", ""),
                "history": prompt_sections.get("history", []),
                "user_message": prompt_sections.get("user_message", ""),
                "tokens_estimate": tokens_estimate,
                "token_budget": token_budget,
                "history_messages_used": len(
                    prompt_sections.get("history") or []
                ),
                "summary_used": bool(prompt_sections.get("summary")),
                "prompt_over_budget": tokens_estimate > token_budget,
                "prompt_excess_tokens": max(
                    0,
                    tokens_estimate - token_budget
                ),
                "prompt_source": "edited_sections_preview",
                "model": model
            }
        else:
            prompt_data = build_prompt_for_conversation(
                conversation_id=conversation_id,
                user_message=user_message,
                context=context,
                model=model
            )

        response = {
            "prompt_kind": "chat",
            "system_prompt": None,
            "summary": prompt_data.get("summary", ""),
            "facts": prompt_data.get("facts", ""),
            "decisions": prompt_data.get("decisions", ""),
            "context": prompt_data.get("context", context),
            "history": prompt_data.get("history", []),
            "user_message": prompt_data.get("user_message", user_message),
            "messages": prompt_data["messages"],
            "prompt_sections": prompt_data.get(
                "prompt_sections"
            ) or build_prompt_sections(
                prompt_data=prompt_data,
                user_message=user_message,
                context=context
            ),
        }
        response["prompt_memory_overrides"] = prompt_data.get(
            "prompt_memory_overrides", {}
        )
        response.update(build_prompt_meta(prompt_data))

        return jsonify(response)

    except Exception as e:
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500
