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

from services.chat_prompt_service import (
    build_prompt_for_conversation,
    SUMMARY_TARGET_TOKENS
)

from db.messages import insert_message
from db.conversations import touch_conversation


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
            prompt_data = {
                "messages": final_messages,
                "tokens_estimate": estimate_tokens(final_messages),
                "token_budget": get_usable_prompt_budget(model),
                "history_limit": None,
                "summary_token_limit": None,
                "summary_was_trimmed": False
            }
        else:
            prompt_data = build_prompt_for_conversation(
                conversation_id=conversation_id,
                user_message=user_message,
                context=context,
                model=model
            )
            final_messages = prompt_data["messages"]

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

        touch_conversation(
            conversation_id
        )

        return jsonify({
            "reply": reply,
            "prompt_tokens_estimate": prompt_data.get("tokens_estimate"),
            "prompt_token_budget": prompt_data.get("token_budget"),
            "history_limit_used": prompt_data.get("history_limit"),
            "summary_token_limit_used": prompt_data.get("summary_token_limit"),
            "summary_was_trimmed": prompt_data.get("summary_was_trimmed")
        })

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
        preview["summary_token_limit"] = prompt_data.get("summary_token_limit")
        preview["summary_was_trimmed"] = prompt_data.get("summary_was_trimmed")

        return jsonify(preview)

    except Exception as e:
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500
