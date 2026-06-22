import json

from db.connection import get_conn


DEFAULT_PROMPT_MEMORY = {
    "system": "",
    "summary": "",
    "facts": "",
    "decisions": "",
    "context": "",
    "history": [],
    "user_message": ""
}


def _normalize_history(history):
    if not isinstance(history, list):
        return []

    normalized = []

    for msg in history:
        if not isinstance(msg, dict):
            continue

        role = msg.get("role")
        content = (msg.get("content") or "").strip()

        if role in ["user", "assistant", "system"] and content:
            normalized.append({
                "role": role,
                "content": content
            })

    return normalized


def normalize_prompt_memory(sections):
    sections = sections or {}

    return {
        "system": str(sections.get("system") or "").strip(),
        "summary": str(sections.get("summary") or "").strip(),
        "facts": str(sections.get("facts") or "").strip(),
        "decisions": str(sections.get("decisions") or "").strip(),
        "context": str(sections.get("context") or "").strip(),
        "history": _normalize_history(sections.get("history") or []),
        "user_message": str(sections.get("user_message") or "").strip()
    }


def get_prompt_memory(conversation_id):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT *
        FROM conversation_prompt_memory
        WHERE conversation_id = %s
        """,
        (conversation_id,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return None

    try:
        history = json.loads(row.get("history_json") or "[]")
    except json.JSONDecodeError:
        history = []

    return normalize_prompt_memory({
        "system": row.get("system_prompt") or "",
        "summary": row.get("summary") or "",
        "facts": row.get("facts") or "",
        "decisions": row.get("decisions") or "",
        "context": row.get("context") or "",
        "history": history,
        "user_message": row.get("user_message") or ""
    })


def save_prompt_memory(conversation_id, sections):
    memory = normalize_prompt_memory(sections)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO conversation_prompt_memory (
            conversation_id,
            system_prompt,
            summary,
            facts,
            decisions,
            context,
            history_json,
            user_message
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            system_prompt = VALUES(system_prompt),
            summary = VALUES(summary),
            facts = VALUES(facts),
            decisions = VALUES(decisions),
            context = VALUES(context),
            history_json = VALUES(history_json),
            user_message = VALUES(user_message),
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            conversation_id,
            memory["system"],
            memory["summary"],
            memory["facts"],
            memory["decisions"],
            memory["context"],
            json.dumps(memory["history"], ensure_ascii=False),
            memory["user_message"]
        )
    )

    conn.commit()

    cur.close()
    conn.close()

    return memory


def delete_prompt_memory(conversation_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM conversation_prompt_memory
        WHERE conversation_id = %s
        """,
        (conversation_id,)
    )

    conn.commit()

    cur.close()
    conn.close()
