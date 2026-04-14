from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash
from groq import Groq
import os
import subprocess
import traceback

app = Flask(__name__)
app.secret_key = "zmien_to_na_cos_losowego"

CONFIG_FILE = "config.txt"

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
print("GROQ_API_KEY loaded:", bool(os.environ.get("GROQ_API_KEY")))


# ======================
# AUTH
# ======================

def load_user():
    with open(CONFIG_FILE) as f:
        line = f.readline().strip()
        username, password_hash = line.split(":", 1)
        return username, password_hash


@app.route("/file")
def get_file():
    path = request.args.get("path")

    try:
        if not path:
            return jsonify({"error": "Brak ścieżki"}), 400

        # zabezpieczenie przed ../
        safe_path = os.path.normpath(path)
        if safe_path.startswith(".."):
            return jsonify({"error": "Niedozwolona ścieżka"}), 403

        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()

        return jsonify({
            "path": safe_path,
            "content": content
        })

    except Exception as e:
        print("FILE READ ERROR:", e)
        return jsonify({"error": str(e)}), 500


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


# ======================
# GIT TREE (POPRAWIONE)
# ======================

def build_tree(root="."):
    tree = {}

    result = subprocess.check_output(["git", "ls-files"], cwd=root).decode()

    for path in result.splitlines():
        parts = path.split("/")
        node = tree

        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node.setdefault("_files", []).append(part)
            else:
                node = node.setdefault(part, {})

    return tree


@app.route("/git-tree")
def git_tree():
    try:
        tree = build_tree(".")
        return jsonify(tree)
    except Exception as e:
        print("GIT TREE ERROR:", str(e))
        return jsonify({})


# ======================
# CHAT (GROQ)
# ======================

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json or {}

    user_message = data.get("message", "")
    model = data.get("model", "llama-3.1-8b-instant")
    context = data.get("context", "")
    history = data.get("history", [])

    system_prompt = "Jesteś pomocnym asystentem programistycznym. Odpowiadaj krótko i konkretnie."

    print("\n" + "="*60)
    print("=== GROQ REQUEST ===")
    print("MODEL USED:", model)
    print("SYSTEM PROMPT:", system_prompt)
    print("USER MESSAGE:", user_message)
    print("CONTEXT:", context)

    print("\n=== HISTORY FROM FRONTEND ===")
    for h in history:
        print(h)

    print("="*60)

    try:
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # context jako dodatkowy system
        if context:
            messages.append({
                "role": "system",
                "content": f"KONTEKST:\n{context}"
            })

        # historia
        for msg in history:
            if msg.get("role") in ["user", "assistant"]:
                messages.append(msg)

        # aktualna wiadomość (NA KOŃCU!)
        messages.append({
            "role": "user",
            "content": user_message
        })

        print("\n=== FINAL MESSAGES SENT TO GROQ ===")
        for m in messages:
            print(f"[{m['role'].upper()}] {m['content']}")
        print("="*60)

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )

        reply = completion.choices[0].message.content

        print("\n=== GROQ RESPONSE ===")
        print(reply)
        print("="*60)

        return jsonify({"reply": reply})

    except Exception as e:
        print("\n=== GROQ ERROR ===")
        print(str(e))
        print(traceback.format_exc())

        return jsonify({
            "reply": "Błąd API Groq (sprawdź konsolę serwera)."
        }), 500

# ======================
# MODELS
# ======================

@app.route("/models")
def models():
    try:
        model_list = client.models.list()
        models = [m.id for m in model_list.data]
        return jsonify(models)

    except Exception as e:
        print("MODEL LIST ERROR:", str(e))
        return jsonify([])


# ======================
# RUN
# ======================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
