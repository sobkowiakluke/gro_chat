from flask import (
    Blueprint,
    jsonify,
    request
)

from services.file_service import read_file

file_bp = Blueprint(
    "file",
    __name__
)


@file_bp.route("/file")
def get_file():

    try:

        path = request.args.get("path")

        result = read_file(path)

        return jsonify(result)

    except Exception as e:

        print(str(e))

        return jsonify({
            "error": str(e)
        }), 500
