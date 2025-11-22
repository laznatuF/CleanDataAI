import ast
import os
import re

# Módulos de la librería estándar que NO deben ir en requirements
STD_LIB = {
    "abc", "argparse", "asyncio", "base64", "collections", "contextlib",
    "copy", "csv", "datetime", "enum", "functools", "glob", "hashlib",
    "heapq", "importlib", "io", "itertools", "json", "logging", "math",
    "mimetypes", "os", "pathlib", "random", "re", "shutil", "statistics",
    "string", "subprocess", "sys", "tempfile", "textwrap", "time",
    "typing", "uuid", "zipfile"
}

def find_imports(root="."):
    modules = set()
    for dirpath, dirnames, filenames in os.walk(root):
        # Ignorar carpetas que no interesan
        dirnames[:] = [
            d for d in dirnames
            if d not in (".git", ".venv", "venv", "__pycache__", "node_modules", "frontend")
        ]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            full = os.path.join(dirpath, fname)
            try:
                with open(full, "r", encoding="utf-8") as f:
                    code = f.read()
                tree = ast.parse(code, filename=full)
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root_name = alias.name.split(".")[0]
                        modules.add(root_name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        root_name = node.module.split(".")[0]
                        modules.add(root_name)
    return modules

def read_requirements(path="requirements.txt"):
    pkgs = set()
    if not os.path.exists(path):
        print(f"No se encontró {path}")
        return pkgs

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # cortar en <, >, = para quedarnos con el nombre base
            name = re.split(r"[<=>]", line)[0].strip()
            if name:
                pkgs.add(name.lower())
    return pkgs


if __name__ == "__main__":
    imports = find_imports(".")
    reqs = read_requirements("requirements.txt")

    # Normalizar a minúsculas
    imports = {m.lower() for m in imports}

    # quitar stdlib
    third_party = {m for m in imports if m not in STD_LIB}

    # mapear módulos a paquetes pip cuando el nombre difiere
    alias_map = {
        "sklearn": "scikit-learn",
        "yaml": "pyyaml",
        "bs4": "beautifulsoup4",
    }

    normalized_reqs = set(reqs)
    for mod, pkg in alias_map.items():
        if pkg in reqs:
            normalized_reqs.add(mod)

    missing = sorted(third_party - normalized_reqs)

    print("Módulos importados de terceros (según el código):")
    print(sorted(third_party))
    print("\nNo encontrados en requirements.txt:")
    print(missing)
