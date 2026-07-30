import json

from db.connection import get_conn


def create_llm_request(
    conversation_id,
    provider,
    model,
    request_messages,
    request_kind="chat",
    prompt_source=None,
    tokens_estimate=None,
):
    """Create an audit record immediately before the external API call."""
    payload = json.dumps(request_messages, ensure_ascii=False)

    conn = get_conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO llm_requests (
                    conversation_id,
                    provider,
                    model,
                    request_kind,
                    prompt_source,
                    request_messages,
                    tokens_estimate,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                """,
                (
                    conversation_id,
                    provider,
                    model,
                    request_kind,
                    prompt_source,
                    payload,
                    tokens_estimate,
                ),
            )
            conn.commit()
            return cur.lastrowid
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def complete_chat_request(
    request_id,
    user_message,
    assistant_message,
    tokens_in=None,
    tokens_out=None,
    latency_ms=None,
    api_request_id=None,
):
    """Atomically finish a chat request and append its visible message pair."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT conversation_id
                FROM llm_requests
                WHERE id = %s
                FOR UPDATE
                """,
                (request_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Nie istnieje llm_request id={request_id}.")

            conversation_id = row[0]

            cur.execute(
                """
                UPDATE llm_requests
                SET
                    status = 'success',
                    tokens_in = %s,
                    tokens_out = %s,
                    latency_ms = %s,
                    api_request_id = %s,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND status = 'pending'
                """,
                (
                    tokens_in,
                    tokens_out,
                    latency_ms,
                    api_request_id,
                    request_id,
                ),
            )
            if cur.rowcount != 1:
                raise ValueError(
                    f"llm_request id={request_id} nie ma statusu pending."
                )

            cur.execute(
                """
                INSERT INTO messages (
                    conversation_id, request_id, role, content
                )
                VALUES (%s, %s, 'user', %s)
                """,
                (conversation_id, request_id, user_message),
            )
            user_message_id = cur.lastrowid

            cur.execute(
                """
                INSERT INTO messages (
                    conversation_id, request_id, role, content
                )
                VALUES (%s, %s, 'assistant', %s)
                """,
                (conversation_id, request_id, assistant_message),
            )
            assistant_message_id = cur.lastrowid

            cur.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (conversation_id,),
            )

            conn.commit()
            return {
                "user_message_id": user_message_id,
                "assistant_message_id": assistant_message_id,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def complete_llm_request(
    request_id,
    tokens_in=None,
    tokens_out=None,
    latency_ms=None,
    api_request_id=None,
):
    """Finish a non-chat request, for example conversation summarization."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE llm_requests
                SET
                    status = 'success',
                    tokens_in = %s,
                    tokens_out = %s,
                    latency_ms = %s,
                    api_request_id = %s,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND status = 'pending'
                """,
                (
                    tokens_in,
                    tokens_out,
                    latency_ms,
                    api_request_id,
                    request_id,
                ),
            )
            if cur.rowcount != 1:
                raise ValueError(
                    f"llm_request id={request_id} nie ma statusu pending."
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def fail_llm_request(
    request_id,
    error_message,
    error_type=None,
    error_code=None,
    latency_ms=None,
):
    """Mark a pending request as failed without adding anything to chat history."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE llm_requests
                SET
                    status = 'error',
                    error_type = %s,
                    error_code = %s,
                    error_message = %s,
                    latency_ms = %s,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND status = 'pending'
                """,
                (
                    error_type,
                    error_code,
                    str(error_message),
                    latency_ms,
                    request_id,
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
