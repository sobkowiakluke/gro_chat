def insert_message(conversation_id, role, content, raw_prompt=None):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO messages (conversation_id, role, content, raw_prompt)
        VALUES (%s, %s, %s, %s)
    """, (conversation_id, role, content, raw_prompt))

    conn.commit()
    cur.close()
    conn.close()

def get_messages(conversation_id):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT role, content
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC
    """, (conversation_id,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows
