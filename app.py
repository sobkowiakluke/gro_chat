from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
from flask import render_template

import traceback
from flask import jsonify, request
from groq import Groq
import os


app = Flask(__name__)
app.secret_key = "zmien_to_na_cos_losowego"

CONFIG_FILE = "config.txt"

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
print("GROQ_API_KEY loaded:", bool(os.environ.get("GROQ_API_KEY")))


def load_user():
    with open(CONFIG_FILE) as f:
        line = f.readline().strip()
        username, password_hash = line.split(":", 1)
        return username, password_hash


@app.route("/", methods=["GET"])
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username_input = request.form.get("username")
        password_input = request.form.get("password")

        username, password_hash = load_user()

        if username_input == username and check_password_hash(password_hash, password_input):
            session["logged_in"] = True
            return redirect(url_for("home"))
        else:
            error = "Błędny login lub hasło"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))



@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "")
    model = data.get("model", "llama-3.1-8b-instant")
    print("\n=== GROQ REQUEST ===")
    print("MODEL USED:", model)
    print("USER:", user_message)

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Jesteś pomocnym asystentem."},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7
        )

        print("=== GROQ RAW RESPONSE ===")
        print(completion)

        reply = completion.choices[0].message.content

        print("=== GROQ PARSED ===")
        print(reply)

        return jsonify({"reply": reply})

    except Exception as e:
        print("=== GROQ ERROR ===")
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "reply": "Błąd API Groq (sprawdź konsolę serwera)."
        }), 500


@app.route("/models")
def models():
    try:
        model_list = client.models.list()

        models = []
        for m in model_list.data:
            models.append(m.id)

        return jsonify(models)

    except Exception as e:
        print("MODEL LIST ERROR:", str(e))
        return jsonify([])


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
