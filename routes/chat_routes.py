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
    build_messages,
    summarize_conversation_chunk
)

from db.messages import (
    insert_message,
    get_recent_messages,
    get_old_messages_for_summary
)

from db.conversations import (
    touch_conversation,
    get_conversation_summary,
    update_conversation_summary
)


chat_bp = Blueprint(
    "chat",
    __name__
)


RECENT_HISTORY_LIMIT = 10


def build_prompt_for_conversation(
    conversation_id,
    user_message,
    context
):
    summary_data = get_conversation_summary(
        conversation_id
    )

    history = get_recent_messages(
        conversation_id=conversation_id,
        limit=RECENT_HISTORY_LIMIT
    )

    messages = build_messages(
        user_message=user_message,
        context=context,
        history=history,
        summary=summary_data["summary"]
    )

    return messages, history, summary_data["summary"]


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
        keep_last=RECENT_HISTORY_LIMIT
    )

    if not old_messages:
        return

    new_summary = summarize_conversation_chunk(
        model=model,
        previous_summary=summary_data["summary"],
        messages=old_messages
    )

    last_summarized_id = old_messages[-1]["id"]

    update_conversation_summary(
        conv_id=conversation_id,
        summary=new_summary,
        summarized_until_message_id=last_summarized_id
    )


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

        if edited_messages:
            final_messages = edited_messages
        else:
            final_messages, _, _ = build_prompt_for_conversation(
                conversation_id=conversation_id,
                user_message=user_message,
                context=context
            )

        # WAŻNE:
        # Do tego momentu nic nie jest zapisane w bazie.
        # Jeżeli Groq zwróci błąd, user_message nie trafi do historii.
        reply = send_chat(
            model=model,
            messages=final_messages
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

        try:
            update_summary_if_needed(
                conversation_id=conversation_id,
                model=model
            )
        except Exception as summary_error:
            print("Błąd aktualizacji streszczenia:")
            print(str(summary_error))
            print(traceback.format_exc())

        touch_conversation(
            conversation_id
        )

        return jsonify({
            "reply": reply
        })

    except Exception as e:
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "reply": "Błąd API Groq.",
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

        user_message = data.get(
            "message",
            ""
        )

        context = data.get(
            "context",
            ""
        )

        _, history, summary = build_prompt_for_conversation(
            conversation_id=conversation_id,
            user_message=user_message,
            context=context
        )

        return jsonify(
            preview_context(
                user_message=user_message,
                context=context,
                history=history,
                summary=summary
            )
        )

    except Exception as e:
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "error": "preview failed"
        }), 500
