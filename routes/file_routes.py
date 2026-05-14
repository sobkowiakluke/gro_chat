from flask import (
    Blueprint,
    jsonify,
    request
)

from services.file_service import (
    read_file,
    read_function
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


@file_bp.route("/function")
def get_function():

    path = request.args.get("path")
    name = request.args.get("name")

    if not path or not name:
        return jsonify({
            "error": "missing params"
        }), 400

    result = read_function(
        path,
        name
    )

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)
