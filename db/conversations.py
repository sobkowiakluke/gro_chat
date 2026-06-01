from db.connection import get_conn

def create_conversation(title=None):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO conversations (title)
        VALUES (%s)
    """, (title,))

    conn.commit()
    conv_id = cur.lastrowid

    cur.close()
    conn.close()

    return conv_id

def get_conversations():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id, title, created_at
        FROM conversations
        WHERE is_deleted = FALSE
        ORDER BY updated_at DESC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def delete_conversation(conv_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE conversations
        SET is_deleted = TRUE
        WHERE id = %s
    """, (conv_id,))

    conn.commit()
    cur.close()
    conn.close()
