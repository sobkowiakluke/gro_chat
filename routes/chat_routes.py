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
    preview_context,
    summarize_conversation_chunk,
    estimate_tokens,
    get_usable_prompt_budget
)

from services.chat_prompt_service import SUMMARY_TARGET_TOKENS

from services.prompt_builder import (
    build_prompt_for_conversation,
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
        "history_limit_used": prompt_data.get("history_limit"),
        "history_messages_loaded": prompt_data.get("history_messages_loaded"),
        "history_messages_used": prompt_data.get("history_messages_used"),
        "summary_token_limit_used": prompt_data.get("summary_token_limit"),
        "summary_was_trimmed": prompt_data.get("summary_was_trimmed"),
        "summary_used": prompt_data.get("summary_used"),
        "prompt_source": prompt_data.get("prompt_source"),
        "summarized_until_message_id": prompt_data.get("summarized_until_message_id")
    }


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
# CHAT
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

        if not user_message and edited_messages:
            for msg in reversed(edited_messages):
                if msg.get("role") == "user":
                    user_message = (
                        msg.get("content") or ""
                    ).strip()
                    break

        if not user_message:
            return jsonify({
                "reply": "Brak wiadomości do wysłania."
            }), 400

        last_message_id_before_send = get_last_message_id(
            conversation_id
        )

        summary_persisted = False

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
                "prompt_source": "edited_prompt_from_popup",
                "summarized_until_message_id": last_message_id_before_send
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
# COMPRESS HISTORY
# =========================
@chat_bp.route(
    "/compress-history",
    methods=["POST"]
)
def compress_history():
    try:
        data = request.json or {}

        model = data.get(
            "model",
            "llama-3.1-8b-instant"
        )

        messages = data.get(
            "messages",
            []
        )

        previous_summary = data.get(
            "summary",
            ""
        )

        if not messages:
            return jsonify({
                "error": "Brak wiadomości do streszczenia."
            }), 400

        summary = summarize_conversation_chunk(
            model=model,
            previous_summary=previous_summary,
            messages=messages,
            target_tokens=SUMMARY_TARGET_TOKENS
        )

        summary_message = [{
            "role": "system",
            "content": summary
        }]

        return jsonify({
            "summary": summary,
            "tokens_estimate": estimate_tokens(summary_message),
            "token_budget": get_usable_prompt_budget(model),
            "summary_token_limit": SUMMARY_TARGET_TOKENS
        })

    except Exception as e:
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500


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

        messages = prompt_data["messages"]

        preview = preview_context(
            user_message=user_message,
            context=context,
            history=prompt_data.get("history", []),
            summary=prompt_data.get("summary", ""),
            model=model
        )

        preview["messages"] = messages
        preview["tokens_estimate"] = prompt_data.get("tokens_estimate")
        preview["token_budget"] = prompt_data.get("token_budget")
        preview["history_limit"] = prompt_data.get("history_limit")
        preview["history_messages_loaded"] = prompt_data.get(
            "history_messages_loaded"
        )
        preview["history_messages_used"] = prompt_data.get(
            "history_messages_used"
        )
        preview["summary_token_limit"] = prompt_data.get(
            "summary_token_limit"
        )
        preview["summary_was_trimmed"] = prompt_data.get(
            "summary_was_trimmed"
        )
        preview["summary_used"] = prompt_data.get("summary_used")
        preview["prompt_source"] = prompt_data.get("prompt_source")
        preview["summarized_until_message_id"] = prompt_data.get(
            "summarized_until_message_id"
        )

        return jsonify(preview)

    except Exception as e:
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500
