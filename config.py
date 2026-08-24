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
    "ENCRYPTION_KEY": ""  # Should come from ENCRYPTION_KEY env var
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

    # Ensure required directories exist
    os.makedirs(Path(config["DB_PATH"]).parent, exist_ok=True)
    os.makedirs(config["STORAGE_PATH"], exist_ok=True)
    os.makedirs(config["LOGS_DIR"], exist_ok=True)

    return config


def save_settings(new_settings):
    """Save updated non-sensitive settings to JSON file (excluding ENCRYPTION_KEY)."""
    current = load_settings()
    for key, value in new_settings.items():
        if key != "ENCRYPTION_KEY":  # Never save encryption key to disk
            current[key] = value

    to_save = {k: v for k, v in current.items() if k != "ENCRYPTION_KEY"}
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=4)
    return current
