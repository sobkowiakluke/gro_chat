import os
import ast

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

def read_function(path, function_name):

    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    lines = source.splitlines()

    for node in ast.walk(tree):

        if not isinstance(node, ast.FunctionDef):
            continue

        if node.name != function_name:
            continue

        # jeśli funkcja ma dekoratory,
        # zaczynamy od pierwszego @

        if node.decorator_list:

            start = min(
                d.lineno
                for d in node.decorator_list
            ) - 1

        else:

            start = node.lineno - 1

        end = node.end_lineno

        content = "\n".join(
            lines[start:end]
        )

        return {
            "name": node.name,
            "content": content,
            "path": path
        }

    return {
        "error": "Function not found"
    }
