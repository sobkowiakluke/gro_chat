import math
import time

from groq import Groq

from config import GROQ_API_KEY
from utils.debug import debug


client = Groq(api_key=GROQ_API_KEY)


MODEL_CACHE_TTL_SECONDS = 300
_model_cache = {
    "loaded_at": 0.0,
    "models": []
}


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

def get_models(force_refresh=False):
    now = time.monotonic()
    cached_models = _model_cache["models"]
    cache_is_fresh = (
        cached_models
        and now - _model_cache["loaded_at"] < MODEL_CACHE_TTL_SECONDS
    )

    if cache_is_fresh and not force_refresh:
        return list(cached_models)

    model_list = client.models.list()

    models = sorted(
        m.id
        for m in model_list.data
        if is_text_chat_model(m.id)
    )

    _model_cache["models"] = models
    _model_cache["loaded_at"] = now

    return list(models)


def validate_chat_model(model):
    model = str(model or "").strip()

    if not model:
        raise ValueError("Nie wybrano modelu.")

    if not is_text_chat_model(model):
        raise ValueError(
            f"Model {model!r} nie jest dozwolonym modelem tekstowym."
        )

    available_models = get_models()

    if model not in available_models:
        raise ValueError(
            f"Model {model!r} nie jest obecnie dostępny w Groq."
        )

    return model


# =========================
# TOKEN / BUDGET HELPERS
# =========================

# To są bezpieczne budżety robocze, a nie oficjalne limity modeli.
# Estymator jest celowo konserwatywny, bo API dolicza narzut struktury messages.
MODEL_PROMPT_BUDGETS = {
    "allam2-7b": 2000,
    "openai/gpt-oss-120b": 8000,
    "openai/gpt-oss-20b": 12000,
    "llama-3.1-8b-instant": 9000,
    "llama-3.3-70b-versatile": 20000,
}

DEFAULT_PROMPT_BUDGET = 12000
RESPONSE_TOKEN_RESERVE = 1200
MESSAGE_OVERHEAD_TOKENS = 12
PROMPT_SAFETY_RATIO = 0.75


def estimate_text_tokens(text):
    return math.ceil(len(str(text or "")) / 4)


def estimate_tokens(messages):
    total = 0

    for m in messages or []:
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
# FINAL CHAT EXECUTOR
# =========================

def send_chat(model, messages):
    if not messages:
        raise ValueError("messages is empty")

    debug("FINAL MESSAGES SENT TO GROQ", messages)

    started_at = time.monotonic()
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7
    )
    latency_ms = round((time.monotonic() - started_at) * 1000)

    reply = completion.choices[0].message.content or ""
    usage = getattr(completion, "usage", None)

    tokens_in = getattr(usage, "prompt_tokens", None) if usage else None
    tokens_out = getattr(usage, "completion_tokens", None) if usage else None
    api_request_id = getattr(completion, "id", None)

    print("RAW REPLY:", repr(reply))
    print("NEWLINES:", reply.count("\n"))
    print("CODE FENCES:", reply.count("```"))

    debug("GROQ RESPONSE", reply)

    return {
        "content": reply,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency_ms,
        "api_request_id": api_request_id,
    }
