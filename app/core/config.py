from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

APP_NAME = "CleanDataIA"
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".ods"}
