from flask import (
    Blueprint,
    jsonify,
    request
)

from db.conversations import (
    create_conversation,
    get_conversations,
    delete_conversation
)

from db.messages import (
    get_messages
)


conversation_bp = Blueprint(
    "conversation",
    __name__
)


@conversation_bp.route(
    "/conversations",
    methods=["GET"]
)
def list_conversations():

    rows = get_conversations()

    return jsonify({
        "conversations": rows
    })


@conversation_bp.route(
    "/conversations",
    methods=["POST"]
)
def create_new_conversation():

    data = request.json or {}

    title = data.get("title") or "Nowy chat"

    conv_id = create_conversation(
        title=title
    )

    return jsonify({
        "id": conv_id,
        "title": title
    })


@conversation_bp.route(
    "/conversations/<int:conversation_id>",
    methods=["DELETE"]
)
def remove_conversation(conversation_id):

    delete_conversation(conversation_id)

    return jsonify({
        "ok": True
    })


@conversation_bp.route(
    "/conversations/<int:conversation_id>/messages",
    methods=["GET"]
)
def get_conversation_messages(conversation_id):

    rows = get_messages(
        conversation_id
    )

    return jsonify({
        "messages": rows
    })
