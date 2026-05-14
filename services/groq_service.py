import math
from utils.debug import debug
from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)


SYSTEM_PROMPT = (
    "Jesteś pomocnym asystentem programistycznym. "
    "Odpowiadaj krótko i konkretnie."
)


def get_models():
    model_list = client.models.list()
    return [m.id for m in model_list.data]


# =========================
# CORE BUILDER (WSPÓLNY)
# =========================
def build_messages(user_message, context, history):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    # context (assistant kodu / pliki / kontekst)
    if context:
        messages.append({
            "role": "system",
            "content": f"KONTEKST:\n{context}"
        })

    # historia rozmowy
    for msg in history:
        if msg.get("role") in ["user", "assistant"]:
            messages.append({
                "role": msg["role"],
                "content": msg.get("content", "")
            })

    # aktualna wiadomość
    messages.append({
        "role": "user",
        "content": user_message
    })

    return messages


# =========================
# CHAT (FINAL CALL)
# =========================
def send_chat(user_message, model, context, history):

    messages = build_messages(user_message, context, history)

    # DEBUG
    debug("SYSTEM PROMPT", SYSTEM_PROMPT)
    debug("USER MESSAGE", user_message)
    debug("CONTEXT", context)
    debug("HISTORY", history)
    debug("FINAL MESSAGES", messages)

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7
    )

    reply = completion.choices[0].message.content

    debug("GROQ RESPONSE", reply)

    return reply


# =========================
# PREVIEW (POPUP)
# =========================
def preview_context(user_message, context, history):

    messages = build_messages(user_message, context, history)

    return {
        "system_prompt": SYSTEM_PROMPT,
        "context": context,
        "history": history,
        "user_message": user_message,
        "messages": messages,
        "tokens_estimate": estimate_tokens(messages)
    }

def estimate_tokens(messages):

    total_chars = 0

    for m in messages:
        total_chars += len(m.get("content", ""))

    # heurystyka: ~4 znaki = 1 token (typowy LLM approximation)
    return math.ceil(total_chars / 4)
