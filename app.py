from flask import (
    Flask,
    redirect,
    url_for,
    session,
    render_template,
    request,
    jsonify
)

from config import SECRET_KEY

from routes.auth_routes import auth_bp
from routes.chat_routes import chat_bp
from routes.file_routes import file_bp
from routes.git_routes import git_bp
from routes.conversation_routes import conversation_bp


app = Flask(__name__)
app.secret_key = SECRET_KEY


def wants_json_response():
    return (
        request.path.startswith("/chat")
        or request.path.startswith("/models")
        or request.path.startswith("/prompt-context")
        or request.path.startswith("/file")
        or request.path.startswith("/function")
        or request.path.startswith("/git-tree")
        or request.path.startswith("/conversations")
        or request.accept_mimetypes["application/json"]
        >= request.accept_mimetypes["text/html"]
    )


@app.before_request
def require_login():

    allowed_endpoints = {
        "auth.login",
        "auth.logout",
        "static"
    }

    if request.endpoint in allowed_endpoints:
        return None

    if session.get("logged_in"):
        return None

    if wants_json_response():
        return jsonify({
            "error": "Brak autoryzacji. Zaloguj się ponownie."
        }), 401

    return redirect(
        url_for("auth.login")
    )


@app.route("/")
def home():

    return render_template("home.html")


app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(file_bp)
app.register_blueprint(git_bp)
app.register_blueprint(conversation_bp)


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
