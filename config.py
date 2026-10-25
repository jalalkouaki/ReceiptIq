import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / "app_config.json"

DEFAULT_CONFIG = {
    "DB_PATH": str(BASE_DIR / "data" / "receiptiq.db"),
    "STORAGE_PATH": str(BASE_DIR / "data" / "uploads"),
    "LOGS_DIR": str(BASE_DIR / "logs"),
    "PORT": 5000,
    "SECRET_KEY": "receiptiq-jwt-secret-local-only-key",
    "DEFAULT_ADMIN_USER": "admin",
    "DEFAULT_ADMIN_PASSWORD": "admin123",
    "OCR_LANGUAGE": "eng",
    "ENABLE_OLLAMA": False,
    "OLLAMA_URL": "http://localhost:11434",
    "THEME": "dark",
    "STORE_NAME": "ReceiptIQ Store",
    "ENCRYPTION_KEY": "ReceiptIQKey2026"
}


def load_settings():
    """Load settings from JSON config file if present, merged with defaults and env vars."""
    config = DEFAULT_CONFIG.copy()
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception:
            pass

    # Environment variable overrides
    if os.environ.get("DB_PATH"):
        config["DB_PATH"] = os.environ.get("DB_PATH")
    if os.environ.get("STORAGE_PATH"):
        config["STORAGE_PATH"] = os.environ.get("STORAGE_PATH")
    if os.environ.get("LOGS_DIR"):
        config["LOGS_DIR"] = os.environ.get("LOGS_DIR")
    if os.environ.get("PORT"):
        try:
            config["PORT"] = int(os.environ.get("PORT"))
        except ValueError:
            pass
    if os.environ.get("SECRET_KEY"):
        config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    if os.environ.get("ENCRYPTION_KEY"):
        config["ENCRYPTION_KEY"] = os.environ.get("ENCRYPTION_KEY")
    if os.environ.get("DEFAULT_ADMIN_USER"):
        config["DEFAULT_ADMIN_USER"] = os.environ.get("DEFAULT_ADMIN_USER")
    if os.environ.get("DEFAULT_ADMIN_PASSWORD"):
        config["DEFAULT_ADMIN_PASSWORD"] = os.environ.get("DEFAULT_ADMIN_PASSWORD")

    # Resolve relative paths against BASE_DIR to support portable configurations
    for path_key in ("DB_PATH", "STORAGE_PATH", "LOGS_DIR"):
        if config.get(path_key):
            p = Path(config[path_key])
            if not p.is_absolute():
                config[path_key] = str((BASE_DIR / p).resolve())

    # Ensure required directories exist
    os.makedirs(Path(config["DB_PATH"]).parent, exist_ok=True)
    os.makedirs(config["STORAGE_PATH"], exist_ok=True)
    os.makedirs(config["LOGS_DIR"], exist_ok=True)

    return config


def save_settings(new_settings):
    """Save updated settings to JSON file with portable relative paths."""
    current = load_settings()
    for key, value in new_settings.items():
        current[key] = value

    # Convert paths that are within BASE_DIR to relative paths to protect user privacy
    to_save = {}
    for k, v in current.items():
        if k in ("DB_PATH", "STORAGE_PATH", "LOGS_DIR") and isinstance(v, str):
            try:
                p = Path(v).resolve()
                if p.is_relative_to(BASE_DIR):
                    to_save[k] = p.relative_to(BASE_DIR).as_posix()
                    continue
            except (ValueError, TypeError):
                pass
        to_save[k] = v

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=4)
    return current
