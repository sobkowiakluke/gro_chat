import os


def read_file(path):

    if not path:
        raise Exception("Brak ścieżki")

    safe_path = os.path.normpath(path)

    if safe_path.startswith(".."):
        raise Exception("Niedozwolona ścieżka")

    with open(safe_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "path": safe_path,
        "content": content
    }
