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
    preview_context
)

from db.messages import insert_message
from db.conversations import touch_conversation


chat_bp = Blueprint(
    "chat",
    __name__
)


def get_last_user_message(messages):
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")

    return ""


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

        messages = data.get("messages") or []

        if not messages:
            return jsonify({
                "reply": "Brak wiadomości do wysłania."
            }), 400

        user_message = get_last_user_message(
            messages
        )

        if user_message:
            insert_message(
                conversation_id=conversation_id,
                role="user",
                content=user_message
            )

        reply = send_chat(
            model=model,
            messages=messages
        )

        insert_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
            raw_prompt=json.dumps(
                messages,
                ensure_ascii=False
            )
        )

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
            "reply": "Błąd API Groq."
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

        user_message = data.get(
            "message",
            ""
        )

        context = data.get(
            "context",
            ""
        )

        history = data.get(
            "history",
            []
        )

        return jsonify(
            preview_context(
                user_message=user_message,
                context=context,
                history=history
            )
        )

    except Exception as e:

        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "error": "preview failed"
        }), 500
