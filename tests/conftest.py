# tests/conftest.py
import os, sys
# añade la raíz del repo (el directorio padre de /tests) al PYTHONPATH
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
