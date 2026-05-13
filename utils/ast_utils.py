import ast


def extract_python_defs(filepath):

    with open(
        filepath,
        "r",
        encoding="utf-8"
    ) as f:

        tree = ast.parse(f.read())

    functions = []
    classes = []

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.FunctionDef
        ):

            functions.append({
                "name": node.name,
                "line": node.lineno
            })

        if isinstance(
            node,
            ast.ClassDef
        ):

            classes.append({
                "name": node.name,
                "line": node.lineno
            })

    return functions, classes
