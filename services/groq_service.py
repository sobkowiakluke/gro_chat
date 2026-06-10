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


STRUCTURED_SUMMARY_PROMPT = (
    "Jesteś mechanizmem kompresji pamięci rozmowy technicznej. "
    "Masz przepisać streszczenie do zwartej, uporządkowanej formy, bez utraty informacji potrzebnych do kontynuacji pracy. "
    "Użyj krótkich sekcji: STAN, PLIKI, DECYZJE, BŁĘDY, TODO, PREFERENCJE. "
    "Usuń powtórzenia, zachowaj nazwy plików, endpointów, funkcji i ustaleń. "
    "Nie dopisuj faktów, których nie ma w danych wejściowych."
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
# TOKEN / BUDGET HELPERS
# =========================

# To są bezpieczne budżety robocze, a nie oficjalne limity modeli.
# Estymator jest celowo konserwatywny, bo API dolicza narzut struktury messages.
MODEL_PROMPT_BUDGETS = {
    "allam2-7b": 2000,
    "openai/gpt-oss-120b": 20000,
    "openai/gpt-oss-20b": 12000,
    "llama-3.1-8b-instant": 9000,
    "llama-3.3-70b-versatile": 20000,
}
DEFAULT_PROMPT_BUDGET = 12000
RESPONSE_TOKEN_RESERVE = 1200
MESSAGE_OVERHEAD_TOKENS = 12
PROMPT_SAFETY_RATIO = 0.75

HISTORY_LIMIT_CANDIDATES = [
    40,
    30,
    20,
    12,
    8,
    4,
    2,
    0,
]


SUMMARY_TOKEN_CANDIDATES = [
    6000,
    4000,
    2500,
    1500,
    900,
    500,
    250,
    0,
]


def estimate_text_tokens(text):
    return math.ceil(len(str(text or "")) / 4)


def estimate_tokens(messages):
    total = 0

    for m in messages:
        total += MESSAGE_OVERHEAD_TOKENS
        total += estimate_text_tokens(m.get("role", ""))
        total += estimate_text_tokens(m.get("content", ""))

    return total


def get_prompt_budget(model):
    return MODEL_PROMPT_BUDGETS.get(
        model,
        DEFAULT_PROMPT_BUDGET
    )


def get_usable_prompt_budget(model):
    raw_budget = MODEL_PROMPT_BUDGETS.get(
        model,
        DEFAULT_PROMPT_BUDGET
    )

    usable_budget = int(
        (raw_budget - RESPONSE_TOKEN_RESERVE) * PROMPT_SAFETY_RATIO
    )

    return max(
        usable_budget,
        1000
    )

def trim_text_to_token_budget(text, token_budget):
    text = str(text or "")

    if token_budget <= 0:
        return ""

    if estimate_text_tokens(text) <= token_budget:
        return text

    max_chars = max(
        0,
        token_budget * 4
    )

    if max_chars <= 0:
        return ""

    return (
        text[:max_chars].rstrip() +
        "\n\n[STRESZCZENIE SKRÓCONE DO BUDŻETU PROMPTU]"
    )


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


def build_messages_within_budget(
    model,
    user_message,
    context,
    history,
    summary=""
):
    usable_budget = get_usable_prompt_budget(model)

    for summary_limit in SUMMARY_TOKEN_CANDIDATES:
        trimmed_summary = trim_text_to_token_budget(
            summary,
            summary_limit
        )

        for history_limit in HISTORY_LIMIT_CANDIDATES:
            selected_history = (
                history[-history_limit:]
                if history_limit > 0
                else []
            )

            messages = build_messages(
                user_message=user_message,
                context=context,
                history=selected_history,
                summary=trimmed_summary
            )

            token_estimate = estimate_tokens(messages)

            if token_estimate <= usable_budget:
                return {
                    "messages": messages,
                    "history": selected_history,
                    "summary": trimmed_summary,
                    "tokens_estimate": token_estimate,
                    "token_budget": usable_budget,
                    "history_limit": history_limit,
                    "summary_token_limit": summary_limit,
                    "summary_was_trimmed": trimmed_summary != (summary or "")
                }

    fallback_messages = build_messages(
        user_message=user_message,
        context=context,
        history=[],
        summary=""
    )

    token_estimate = estimate_tokens(fallback_messages)

    if token_estimate <= usable_budget:
        return {
            "messages": fallback_messages,
            "history": [],
            "summary": "",
            "tokens_estimate": token_estimate,
            "token_budget": usable_budget,
            "history_limit": 0,
            "summary_token_limit": 0,
            "summary_was_trimmed": bool(summary)
        }

    raise ValueError(
        "Prompt jest nadal za długi mimo usunięcia historii i streszczenia. "
        "Skróć kontekst albo załącz mniejszy fragment kodu. "
        f"Estymacja: {token_estimate} tokenów, budżet: {usable_budget}."
    )


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
    messages,
    target_tokens=2500
):
    if not messages:
        return previous_summary

    conversation_text = build_summary_text(messages)

    summary_input = (
        "Dotychczasowe streszczenie rozmowy:\n"
        f"{previous_summary or '(brak)'}\n\n"
        "Nowy starszy fragment rozmowy do włączenia do streszczenia:\n"
        f"{conversation_text}\n\n"
        "Zwróć jedno aktualne, uporządkowane streszczenie całej starszej części rozmowy. "
        f"Cel: maksymalnie około {target_tokens} tokenów."
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


def restructure_summary(
    model,
    summary,
    target_tokens=1500
):
    if not summary:
        return ""

    summary_input = (
        "Aktualne streszczenie rozmowy:\n"
        f"{summary}\n\n"
        "Przepisz je do bardziej zwartej i strukturalnej formy. "
        f"Cel: maksymalnie około {target_tokens} tokenów."
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": STRUCTURED_SUMMARY_PROMPT
            },
            {
                "role": "user",
                "content": summary_input
            }
        ],
        temperature=0.1
    )

    structured_summary = completion.choices[0].message.content

    debug("STRUCTURED CONVERSATION SUMMARY", structured_summary)

    return structured_summary


# =========================
# POPUP PREVIEW
# =========================

def preview_context(
    user_message,
    context,
    history,
    summary="",
    model=None
):
    if model:
        budget_result = build_messages_within_budget(
            model=model,
            user_message=user_message,
            context=context,
            history=history,
            summary=summary
        )

        messages = budget_result["messages"]
    else:
        messages = build_messages(
            user_message=user_message,
            context=context,
            history=history,
            summary=summary
        )

        budget_result = {
            "tokens_estimate": estimate_tokens(messages),
            "token_budget": None,
            "history_limit": len(history),
            "summary_token_limit": None,
            "summary_was_trimmed": False
        }

    return {
        "system_prompt": SYSTEM_PROMPT,
        "summary": budget_result.get("summary", summary),
        "context": context,
        "history": budget_result.get("history", history),
        "user_message": user_message,
        "messages": messages,
        "tokens_estimate": budget_result["tokens_estimate"],
        "token_budget": budget_result["token_budget"],
        "history_limit": budget_result["history_limit"],
        "summary_token_limit": budget_result["summary_token_limit"],
        "summary_was_trimmed": budget_result["summary_was_trimmed"]
    }
