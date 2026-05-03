"""Application configuration from environment (see .env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


def _abs_path(p: str) -> str:
    if os.path.isabs(p):
        return p
    return str(ROOT / p)


DB_PATH = _abs_path(os.environ.get("DB_PATH", "agritech.db"))

_model_raw = os.environ.get("MODEL_PATH", "models").strip()
if os.path.isabs(_model_raw):
    MODEL_DIR = Path(_model_raw)
else:
    MODEL_DIR = ROOT / _model_raw.strip("/\\")


def _resolve_model_path(filename: str) -> str:
    primary = MODEL_DIR / filename
    if primary.is_file():
        return str(primary)
    fallback = ROOT / filename
    if fallback.is_file():
        return str(fallback)
    return str(primary)


VALIDATOR_MODEL_PATH = _resolve_model_path("plant_validator_model.h5")
DISEASE_MODEL_PATH = _resolve_model_path("crop_disease_model.h5")

SECRET_KEY = os.environ.get("SECRET_KEY", "changeme")
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
OPENWEATHER_KEY = os.environ.get("OPENWEATHER_KEY", "")

JWT_SECRET = os.environ.get("JWT_SECRET") or SECRET_KEY
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_HOURS = int(os.environ.get("JWT_EXPIRES_HOURS", "72"))

CONTACT_SMTP_HOST = os.environ.get("CONTACT_SMTP_HOST")
CONTACT_SMTP_USER = os.environ.get("CONTACT_SMTP_USER")
CONTACT_SMTP_PASSWORD = os.environ.get("CONTACT_SMTP_PASSWORD")
CONTACT_MAIL_TO = os.environ.get("CONTACT_MAIL_TO")
CONTACT_SMTP_PORT = int(os.environ.get("CONTACT_SMTP_PORT", "587"))

CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.65"))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
