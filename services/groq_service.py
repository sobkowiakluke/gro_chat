from utils.debug import debug
from groq import Groq

from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)


def get_models():

    model_list = client.models.list()

    return [m.id for m in model_list.data]


def send_chat(user_message, model, context, history):

    system_prompt = (
        "Jesteś pomocnym asystentem programistycznym. "
        "Odpowiadaj krótko i konkretnie."
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    # context jako dodatkowy system message
    if context:
        messages.append({
            "role": "system",
            "content": f"KONTEKST:\n{context}"
        })

    # historia
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

    # ======================
    # DEBUG INPUT
    # ======================
    debug("MODEL USED", model)
    debug("SYSTEM PROMPT", system_prompt)
    debug("USER MESSAGE", user_message)
    debug("CONTEXT", context)
    debug("HISTORY", history)

    debug("FINAL MESSAGES SENT TO GROQ", messages)

    # ======================
    # API CALL
    # ======================
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7
    )

    reply = completion.choices[0].message.content

    # ======================
    # DEBUG OUTPUT
    # ======================
    debug("GROQ RESPONSE", reply)

    return reply
