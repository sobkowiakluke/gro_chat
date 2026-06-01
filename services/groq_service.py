import math

from utils.debug import debug
from groq import Groq
from config import GROQ_API_KEY


client = Groq(api_key=GROQ_API_KEY)


SYSTEM_PROMPT = (
    "Jesteś pomocnym asystentem programistycznym. "
    "Odpowiadaj krótko i konkretnie."
)


# =========================
# MODEL FILTERING
# =========================

EXCLUDED_MODEL_KEYWORDS = [
    "tts",
    "whisper",
    "speech",
    "audio",
    "transcribe",
    "transcription",
    "distil-whisper",
    "playai",
]


def is_text_chat_model(model_id):
    model_id_lower = model_id.lower()

    for keyword in EXCLUDED_MODEL_KEYWORDS:
        if keyword in model_id_lower:
            return False

    return True


# =========================
# MODELS
# =========================

def get_models():
    model_list = client.models.list()

    models = [
        m.id
        for m in model_list.data
        if is_text_chat_model(m.id)
    ]

    return sorted(models)


# =========================
# PREVIEW BUILDER ONLY
# =========================

def build_messages(user_message, context, history):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    if context:
        messages.append({
            "role": "system",
            "content": f"KONTEKST:\n{context}"
        })

    for msg in history:
        if msg.get("role") in ["user", "assistant"]:
            messages.append({
                "role": msg["role"],
                "content": msg.get("content", "")
            })

    messages.append({
        "role": "user",
        "content": user_message
    })

    return messages


# =========================
# FINAL CHAT EXECUTOR
# =========================

def send_chat(model, messages):

    if not messages:
        raise ValueError("messages is empty")

    debug("FINAL MESSAGES SENT TO GROQ", messages)

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7
    )

    reply = completion.choices[0].message.content

    debug("GROQ RESPONSE", reply)

    return reply


# =========================
# POPUP PREVIEW
# =========================

def preview_context(user_message, context, history):

    messages = build_messages(
        user_message,
        context,
        history
    )

    return {
        "system_prompt": SYSTEM_PROMPT,
        "context": context,
        "history": history,
        "user_message": user_message,
        "messages": messages,
        "tokens_estimate": estimate_tokens(messages)
    }


# =========================
# SIMPLE TOKEN ESTIMATOR
# =========================

def estimate_tokens(messages):

    total_chars = 0

    for m in messages:
        total_chars += len(
            m.get("content", "")
        )

    return math.ceil(total_chars / 4)
