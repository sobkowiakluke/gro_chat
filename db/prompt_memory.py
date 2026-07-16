import json

from db.connection import get_conn


DURABLE_PROMPT_SECTIONS = (
    "system",
    "summary",
    "facts",
    "decisions",
    "context",
)

DEFAULT_PROMPT_MEMORY = {
    **{name: "" for name in DURABLE_PROMPT_SECTIONS},
    "overrides": {name: False for name in DURABLE_PROMPT_SECTIONS},
}


def _normalize_overrides(value):
    value = value or {}
    if isinstance(value, list):
        value = {name: True for name in value}
    if not isinstance(value, dict):
        value = {}
    return {name: bool(value.get(name, False)) for name in DURABLE_PROMPT_SECTIONS}


def normalize_prompt_memory(sections, overrides=None):
    sections = sections or {}
    normalized = {
        name: str(sections.get(name) or "").strip()
        for name in DURABLE_PROMPT_SECTIONS
    }
    normalized["overrides"] = _normalize_overrides(
        overrides if overrides is not None else sections.get("overrides")
    )
    return normalized


def _decode_metadata(row):
    raw = row.get("history_json") or ""
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        decoded = None

    if isinstance(decoded, dict) and decoded.get("version") == 2:
        return _normalize_overrides(decoded.get("overrides"))

    # Format legacy przechowywał tutaj kopię HISTORY. Historia jest od teraz
    # zawsze dynamiczna. Zachowujemy tylko niepuste trwałe sekcje jako nadpisania.
    return {
        "system": bool((row.get("system_prompt") or "").strip()),
        "summary": bool((row.get("summary") or "").strip()),
        "facts": bool((row.get("facts") or "").strip()),
        "decisions": bool((row.get("decisions") or "").strip()),
        "context": bool((row.get("context") or "").strip()),
    }


def get_prompt_memory(conversation_id):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                """
                SELECT *
                FROM conversation_prompt_memory
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            )
            row = cur.fetchone()
        finally:
            cur.close()
    finally:
        conn.close()

    if not row:
        return None

    return normalize_prompt_memory({
        "system": row.get("system_prompt") or "",
        "summary": row.get("summary") or "",
        "facts": row.get("facts") or "",
        "decisions": row.get("decisions") or "",
        "context": row.get("context") or "",
    }, overrides=_decode_metadata(row))


def save_prompt_memory(conversation_id, sections, overrides=None):
    memory = normalize_prompt_memory(sections, overrides=overrides)
    metadata = json.dumps({
        "version": 2,
        "overrides": memory["overrides"],
    }, ensure_ascii=False)

    conn = get_conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO conversation_prompt_memory (
                    conversation_id, system_prompt, summary, facts, decisions,
                    context, history_json, user_message
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, '')
                ON DUPLICATE KEY UPDATE
                    system_prompt = VALUES(system_prompt),
                    summary = VALUES(summary),
                    facts = VALUES(facts),
                    decisions = VALUES(decisions),
                    context = VALUES(context),
                    history_json = VALUES(history_json),
                    user_message = '',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    conversation_id, memory["system"], memory["summary"],
                    memory["facts"], memory["decisions"], memory["context"],
                    metadata,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()

    return memory


def delete_prompt_memory(conversation_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "DELETE FROM conversation_prompt_memory WHERE conversation_id = %s",
                (conversation_id,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()
