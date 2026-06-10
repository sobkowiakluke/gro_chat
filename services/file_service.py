import os
import ast


PROJECT_ROOT = os.path.abspath(os.getcwd())


def resolve_safe_path(path):

    if not path:
        raise ValueError("Brak ścieżki")

    normalized_path = os.path.normpath(path)

    if os.path.isabs(normalized_path):
        requested_path = normalized_path
    else:
        requested_path = os.path.abspath(
            os.path.join(
                PROJECT_ROOT,
                normalized_path
            )
        )

    if os.path.commonpath([
        PROJECT_ROOT,
        requested_path
    ]) != PROJECT_ROOT:
        raise PermissionError("Niedozwolona ścieżka")

    if not os.path.isfile(requested_path):
        raise FileNotFoundError("Plik nie istnieje")

    return requested_path


def get_relative_path(path):

    return os.path.relpath(
        path,
        PROJECT_ROOT
    )


def read_file(path):

    safe_path = resolve_safe_path(path)

    with open(
        safe_path,
        "r",
        encoding="utf-8"
    ) as f:
        content = f.read()

    return {
        "path": get_relative_path(safe_path),
        "content": content
    }


def read_function(path, function_name):

    if not function_name:
        raise ValueError("Brak nazwy funkcji")

    safe_path = resolve_safe_path(path)

    with open(
        safe_path,
        "r",
        encoding="utf-8"
    ) as f:
        source = f.read()

    tree = ast.parse(source)

    lines = source.splitlines()

    for node in ast.walk(tree):

        if not isinstance(node, ast.FunctionDef):
            continue

        if node.name != function_name:
            continue

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
            "path": get_relative_path(safe_path)
        }

    return {
        "error": "Function not found"
    }
