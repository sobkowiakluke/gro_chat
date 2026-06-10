from flask import (
    Blueprint,
    jsonify,
    request
)

from services.file_service import (
    read_file,
    read_function
)


file_bp = Blueprint(
    "file",
    __name__
)


def handle_file_error(e):

    print(str(e))

    if isinstance(e, ValueError):
        status_code = 400

    elif isinstance(e, PermissionError):
        status_code = 403

    elif isinstance(e, FileNotFoundError):
        status_code = 404

    else:
        status_code = 500

    return jsonify({
        "error": str(e)
    }), status_code


@file_bp.route("/file")
def get_file():

    try:

        path = request.args.get("path")

        result = read_file(path)

        return jsonify(result)

    except Exception as e:

        return handle_file_error(e)


@file_bp.route("/function")
def get_function():

    try:

        path = request.args.get("path")
        name = request.args.get("name")

        result = read_function(
            path,
            name
        )

        if "error" in result:
            return jsonify(result), 404

        return jsonify(result)

    except Exception as e:

        return handle_file_error(e)
