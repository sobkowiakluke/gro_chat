from config import CONFIG_FILE


def load_user():

    with open(CONFIG_FILE) as f:
        line = f.readline().strip()

    username, password_hash = line.split(":", 1)

    return username, password_hash
