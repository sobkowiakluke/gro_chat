from db.connection import get_conn


def get_messages(conversation_id):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            id,
            role,
            content,
            created_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC, id ASC
    """, (conversation_id,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def get_recent_messages(
    conversation_id,
    limit=10,
    before_id=None
):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    params = [conversation_id]

    where_extra = ""

    if before_id:
        where_extra = "AND id < %s"
        params.append(before_id)

    params.append(limit)

    cur.execute(f"""
        SELECT
            id,
            role,
            content,
            created_at
        FROM messages
        WHERE conversation_id = %s
        {where_extra}
        ORDER BY id DESC
        LIMIT %s
    """, tuple(params))

    rows = cur.fetchall()
    rows.reverse()

    cur.close()
    conn.close()

    return rows


def get_messages_for_manual_summary(
    conversation_id,
    after_id=0
):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            id,
            role,
            content,
            created_at
        FROM messages
        WHERE conversation_id = %s
          AND id > %s
          AND role IN ('user', 'assistant')
        ORDER BY id ASC
    """, (
        conversation_id,
        after_id or 0
    ))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

def get_messages_after_id(
    conversation_id,
    after_id=0,
    limit=40
):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            id,
            role,
            content,
            created_at
        FROM messages
        WHERE conversation_id = %s
          AND id > %s
          AND role IN ('user', 'assistant')
        ORDER BY id DESC
        LIMIT %s
    """, (
        conversation_id,
        after_id or 0,
        limit
    ))

    rows = cur.fetchall()
    rows.reverse()

    cur.close()
    conn.close()

    return rows


def get_last_message_id(conversation_id):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT MAX(id) AS last_id
        FROM messages
        WHERE conversation_id = %s
    """, (conversation_id,))

    row = cur.fetchone() or {}

    cur.close()
    conn.close()

    return row.get("last_id") or 0



def count_messages_after_id(conversation_id, after_id=0):
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT COUNT(*)
            FROM messages
            WHERE conversation_id = %s
              AND id > %s
              AND role IN ('user', 'assistant')
        """, (
            conversation_id,
            after_id or 0
        ))

        row = cur.fetchone()
        return int(row[0] if row else 0)
    finally:
        cur.close()
        conn.close()
