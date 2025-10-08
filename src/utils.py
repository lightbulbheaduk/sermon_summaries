import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

# Configure logging once for the whole app
def setup_logging():
    os.makedirs("logs", exist_ok=True)  # logs/ ignored by git
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/pipeline.log", mode="a", encoding="utf-8")
        ],
    )

def read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def write_json(path: str, data: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def slugify(text: str) -> str:
    # Simple slug for filenames/URLs
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"