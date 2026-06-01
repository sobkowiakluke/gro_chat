from flask import (
    Blueprint,
    request,
    jsonify
)

import traceback

from services.groq_service import (
    send_chat,
    get_models,
    preview_context
)

chat_bp = Blueprint(
    "chat",
    __name__
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

        model = data.get(
            "model",
            "llama-3.1-8b-instant"
        )

        messages = data.get("messages") or []

        reply = send_chat(
            model=model,
            messages=messages
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
