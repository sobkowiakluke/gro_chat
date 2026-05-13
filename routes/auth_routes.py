from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from werkzeug.security import check_password_hash

from services.auth_service import load_user

auth_bp = Blueprint(
    "auth",
    __name__
)


@auth_bp.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    error = None

    if request.method == "POST":

        username_input = request.form.get(
            "username"
        )

        password_input = request.form.get(
            "password"
        )

        username, password_hash = load_user()

        if (
            username_input == username
            and
            check_password_hash(
                password_hash,
                password_input
            )
        ):

            session["logged_in"] = True

            return redirect(
                url_for("home")
            )

        error = "Błędny login lub hasło"

    return render_template(
        "login.html",
        error=error
    )


@auth_bp.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("auth.login")
    )
