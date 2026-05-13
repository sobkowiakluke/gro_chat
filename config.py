import os

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "zmien_to_na_cos_losowego"
)

CONFIG_FILE = "config.txt"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DEBUG = True
