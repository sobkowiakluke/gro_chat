import math

from utils.debug import debug
from groq import Groq
from config import GROQ_API_KEY


client = Groq(api_key=GROQ_API_KEY)


SYSTEM_PROMPT = (
    "Jesteś pomocnym asystentem programistycznym. "
    "Odpowiadaj krótko i konkretnie."
)


SUMMARY_PROMPT = (
    "Jesteś mechanizmem pamięci rozmowy technicznej. "
    "Streszczasz starszą część rozmowy tak, aby kolejny model mógł kontynuować pracę nad projektem. "
    "Zachowaj konkrety: decyzje, strukturę plików, błędy, poprawki, ustalenia, TODO i preferencje użytkownika. "
    "Nie dopisuj faktów, których nie ma w rozmowie. Pisz po polsku, zwięźle, technicznie."
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
# PROMPT BUILDER
# =========================

def build_messages(
    user_message,
    context,
    history,
    summary=""
):
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    if summary:
        messages.append({
            "role": "system",
            "content": (
                "STRESZCZENIE STARSZEJ CZĘŚCI ROZMOWY:\n"
                f"{summary}"
            )
        })

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
# SUMMARY EXECUTOR
# =========================

def build_summary_text(messages):
    lines = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            label = "Użytkownik"
        elif role == "assistant":
            label = "Asystent"
        else:
            continue

        lines.append(f"{label}: {content}")

    return "\n\n".join(lines)


def summarize_conversation_chunk(
    model,
    previous_summary,
    messages
):
    if not messages:
        return previous_summary

    conversation_text = build_summary_text(messages)

    summary_input = (
        "Dotychczasowe streszczenie rozmowy:\n"
        f"{previous_summary or '(brak)'}\n\n"
        "Nowy starszy fragment rozmowy do włączenia do streszczenia:\n"
        f"{conversation_text}\n\n"
        "Zwróć jedno aktualne streszczenie całej starszej części rozmowy."
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": SUMMARY_PROMPT
            },
            {
                "role": "user",
                "content": summary_input
            }
        ],
        temperature=0.2
    )

    summary = completion.choices[0].message.content

    debug("UPDATED CONVERSATION SUMMARY", summary)

    return summary


# =========================
# POPUP PREVIEW
# =========================

def preview_context(
    user_message,
    context,
    history,
    summary=""
):
    messages = build_messages(
        user_message=user_message,
        context=context,
        history=history,
        summary=summary
    )

    return {
        "system_prompt": SYSTEM_PROMPT,
        "summary": summary,
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
