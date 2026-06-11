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
    build_messages_within_budget,
    summarize_conversation_chunk,
    restructure_summary,
    estimate_tokens,
    get_usable_prompt_budget
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


MAX_HISTORY_FOR_DYNAMIC_PROMPT = 40
SUMMARY_RESTRUCTURE_THRESHOLD_RATIO = 0.80
SUMMARY_TARGET_TOKENS = 2500
SUMMARY_COMPACT_TARGET_TOKENS = 1500


def get_history_for_dynamic_prompt(conversation_id):
    return get_recent_messages(
        conversation_id=conversation_id,
        limit=MAX_HISTORY_FOR_DYNAMIC_PROMPT
    )


def build_prompt_for_conversation(
    conversation_id,
    user_message,
    context,
    model
):
    summary_data = get_conversation_summary(
        conversation_id
    )

    history = get_history_for_dynamic_prompt(
        conversation_id
    )

    prompt_data = build_messages_within_budget(
        model=model,
        user_message=user_message,
        context=context,
        history=history,
        summary=summary_data["summary"]
    )

    return prompt_data


def maybe_restructure_summary(
    conversation_id,
    model,
    prompt_data
):
    summary = prompt_data.get("summary") or ""

    if not summary:
        return

    token_budget = prompt_data.get("token_budget") or 0
    token_estimate = prompt_data.get("tokens_estimate") or 0

    if not token_budget:
        return

    used_ratio = token_estimate / token_budget

    should_restructure = (
        used_ratio >= SUMMARY_RESTRUCTURE_THRESHOLD_RATIO
        or prompt_data.get("summary_was_trimmed")
    )

    if not should_restructure:
        return

    structured_summary = restructure_summary(
        model=model,
        summary=summary,
        target_tokens=SUMMARY_COMPACT_TARGET_TOKENS
    )

    current_summary_data = get_conversation_summary(
        conversation_id
    )

    update_conversation_summary(
        conv_id=conversation_id,
        summary=structured_summary,
        summarized_until_message_id=current_summary_data[
            "summarized_until_message_id"
        ]
    )


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
        keep_last=MAX_HISTORY_FOR_DYNAMIC_PROMPT
    )

    if not old_messages:
        return

    new_summary = summarize_conversation_chunk(
        model=model,
        previous_summary=summary_data["summary"],
        messages=old_messages,
        target_tokens=SUMMARY_TARGET_TOKENS
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

        try:
            update_summary_if_needed(
                conversation_id=conversation_id,
                model=model
            )

            if not edited_messages:
                maybe_restructure_summary(
                    conversation_id=conversation_id,
                    model=model,
                    prompt_data=prompt_data
                )

        except Exception as summary_error:
            print("Błąd aktualizacji streszczenia:")
            print(str(summary_error))
            print(traceback.format_exc())

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
