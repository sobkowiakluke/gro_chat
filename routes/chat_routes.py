from flask import (
    Blueprint,
    request,
    jsonify
)

import json
import traceback

from services.groq_service import (
    send_chat,
    get_models,
    estimate_tokens,
    get_usable_prompt_budget
)

from services.prompt_builder import (
    build_prompt_for_conversation,
    build_summary_prompt_for_conversation,
    extract_summary_from_messages
)

from db.messages import (
    insert_message,
    get_last_message_id
)

from db.conversations import (
    touch_conversation,
    update_conversation_summary
)


chat_bp = Blueprint(
    "chat",
    __name__
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
        "prompt_source": prompt_data.get("prompt_source"),
        "summarized_until_message_id": prompt_data.get("summarized_until_message_id"),
        "summary_until_message_id": prompt_data.get("summary_until_message_id"),
        "model": prompt_data.get("model")
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


# =========================
# CHAT / SUMMARY EXECUTOR
# =========================
@chat_bp.route(
    "/chat",
    methods=["POST"]
)
def chat():
    try:
        data = request.json or {}

        conversation_id = data.get("conversation_id")

        if not conversation_id:
            return jsonify({
                "reply": "Brak aktywnego chatu."
            }), 400

        model = data.get(
            "model",
            "llama-3.1-8b-instant"
        )

        user_message = (
            data.get("message") or ""
        ).strip()

        context = data.get("context", "")
        edited_messages = data.get("messages")
        summary_mode = bool(data.get("summary_mode"))

        if not user_message and edited_messages:
            user_message = get_last_user_message(edited_messages)

        if not user_message:
            return jsonify({
                "reply": "Brak wiadomości do wysłania."
            }), 400

        last_message_id_before_send = get_last_message_id(
            conversation_id
        )

        if edited_messages:
            final_messages = edited_messages
            prompt_data = {
                "messages": final_messages,
                "tokens_estimate": estimate_tokens(final_messages),
                "token_budget": get_usable_prompt_budget(model),
                "history_limit": None,
                "history_messages_loaded": None,
                "history_messages_used": None,
                "summary_token_limit": None,
                "summary_was_trimmed": False,
                "summary_used": bool(
                    extract_summary_from_messages(final_messages)
                ),
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

        # Do tego momentu nic nie jest zapisane w historii wiadomości.
        # Jeżeli Groq zwróci błąd, user_message nie trafi do historii.
        reply = send_chat(
            model=model,
            messages=final_messages
        )

        if summary_mode:
            summary_until_message_id = data.get(
                "summary_until_message_id"
            )

            if summary_until_message_id is None:
                return jsonify({
                    "error": "Brak summary_until_message_id dla trybu summary."
                }), 400

            update_conversation_summary(
                conv_id=conversation_id,
                summary=reply,
                summarized_until_message_id=summary_until_message_id
            )

            touch_conversation(conversation_id)

            response = {
                "reply": reply,
                "summary_updated": True,
                "summary_until_message_id": summary_until_message_id
            }
            response.update(build_prompt_meta(prompt_data))

            return jsonify(response)

        summary_persisted = False

        if edited_messages:
            summary_persisted = persist_visible_summary_if_present(
                conversation_id=conversation_id,
                messages=final_messages,
                summarized_until_message_id=last_message_id_before_send
            )

        insert_message(
            conversation_id=conversation_id,
            role="user",
            content=user_message
        )

        insert_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
            raw_prompt=json.dumps(
                final_messages,
                ensure_ascii=False
            )
        )

        touch_conversation(
            conversation_id
        )

        response = {
            "reply": reply,
            "summary_persisted": summary_persisted
        }
        response.update(build_prompt_meta(prompt_data))

        return jsonify(response)

    except Exception as e:
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

        model = data.get(
            "model",
            "llama-3.1-8b-instant"
        )

        prompt_data = build_summary_prompt_for_conversation(
            conversation_id=conversation_id,
            model=model
        )

        if not prompt_data.get("messages"):
            return jsonify({
                "error": "Brak starszej historii do streszczenia."
            }), 400

        response = {
            "messages": prompt_data["messages"],
            "summary_mode": True
        }
        response.update(build_prompt_meta(prompt_data))

        return jsonify(response)

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

        model = data.get(
            "model",
            "llama-3.1-8b-instant"
        )

        user_message = data.get(
            "message",
            ""
        )

        context = data.get(
            "context",
            ""
        )

        prompt_data = build_prompt_for_conversation(
            conversation_id=conversation_id,
            user_message=user_message,
            context=context,
            model=model
        )

        response = {
            "system_prompt": None,
            "summary": prompt_data.get("summary", ""),
            "context": context,
            "history": prompt_data.get("history", []),
            "user_message": user_message,
            "messages": prompt_data["messages"],
        }
        response.update(build_prompt_meta(prompt_data))

        return jsonify(response)

    except Exception as e:
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500
