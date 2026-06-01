def get_workspace(conversation_id):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT *
        FROM workspace_items
        WHERE conversation_id = %s
        ORDER BY parent_id, created_at
    """, (conversation_id,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows
