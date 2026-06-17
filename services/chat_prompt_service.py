"""
Ten moduł zostaje tylko jako warstwa zgodności.

Automatyczne wywołania LLM do streszczania zostały wyłączone.
Summary ma teraz jawny flow:

1. /summary-context buduje payload summary przez services/prompt_builder.py
2. użytkownik widzi i może edytować payload w popupie
3. dopiero kliknięcie „Wyślij prompt” wykonuje jedno wywołanie LLM
4. odpowiedź LLM zostaje zapisana jako conversations.summary
"""

SUMMARY_TARGET_TOKENS = 2500
SUMMARY_COMPACT_TARGET_TOKENS = 1500


def maybe_restructure_summary(*args, **kwargs):
    return None


def update_summary_if_needed(*args, **kwargs):
    return None
