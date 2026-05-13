import os
import subprocess

from utils.ast_utils import extract_python_defs


def build_tree(root="."):

    tree = {}

    files = subprocess.check_output(
        ["git", "ls-files"],
        cwd=root
    ).decode().splitlines()

    for path in files:

        parts = path.split("/")

        node = tree

        current_path = ""

        for i, part in enumerate(parts):

            current_path = os.path.join(
                current_path,
                part
            )

            if i == len(parts) - 1:

                node.setdefault("_files", []).append(part)

                if part.endswith(".py"):

                    full_path = os.path.join(root, path)

                    funcs, classes = extract_python_defs(full_path)

                    if funcs:
                        node.setdefault(
                            "_functions",
                            []
                        ).extend([
                            {**f, "file": path}
                            for f in funcs
                        ])

                    if classes:
                        node.setdefault(
                            "_classes",
                            []
                        ).extend([
                            {**c, "file": path}
                            for c in classes
                        ])

            else:
                node = node.setdefault(part, {})

    return tree
