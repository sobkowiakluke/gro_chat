import os

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "zmien_to_na_cos_losowego"
)

CONFIG_FILE = "config.txt"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

DEBUG = True


# =========================
# DATABASE
# =========================

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "flaskuser")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Dwiemiarki32!")
DB_NAME = os.environ.get("DB_NAME", "flaskchat")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
