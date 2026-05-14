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


@chat_bp.route(
    "/chat",
    methods=["POST"]
)
def chat():

    try:

        data = request.json or {}

        user_message = data.get("message", "")
        model = data.get("model", "llama-3.1-8b-instant")
        context = data.get("context", "")
        history = data.get("history", [])

        reply = send_chat(
            user_message=user_message,
            model=model,
            context=context,
            history=history
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


@chat_bp.route("/models")
def models():

    try:
        return jsonify(get_models())

    except Exception as e:
        print(str(e))
        return jsonify([])


# =========================
# POPUP: PREVIEW PROMPTU
# =========================
@chat_bp.route("/prompt-context", methods=["POST"])
def prompt_context():

    try:

        data = request.json or {}

        user_message = data.get("message", "")
        context = data.get("context", "")
        history = data.get("history", [])

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
