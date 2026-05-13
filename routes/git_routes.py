from flask import (
    Blueprint,
    jsonify
)

from services.git_service import build_tree

git_bp = Blueprint(
    "git",
    __name__
)


@git_bp.route("/git-tree")
def git_tree():

    try:

        tree = build_tree(".")

        return jsonify(tree)

    except Exception as e:

        print(str(e))

        return jsonify({})
