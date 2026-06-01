from flask import Flask, redirect, url_for, session, render_template

from config import SECRET_KEY

from routes.auth_routes import auth_bp
from routes.chat_routes import chat_bp
from routes.file_routes import file_bp
from routes.git_routes import git_bp
from routes.conversation_routes import conversation_bp


app = Flask(__name__)
app.secret_key = SECRET_KEY


@app.route("/")
def home():

    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

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
