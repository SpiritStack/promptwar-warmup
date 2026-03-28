"""
VisualLink — Centralized configuration via environment variables.
Copy .env.example to .env and fill in your values before running.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


class Settings:
    # ── Gemini ────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str   = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL:   str   = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

    # ── Google Cloud / Firebase ───────────────────────────────────────────
    GCP_PROJECT_ID:              str = os.environ.get("GCP_PROJECT_ID", "")
    GCS_BUCKET_NAME:             str = os.environ.get("GCS_BUCKET_NAME", "visuallink-media")
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.environ.get(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        str(Path(__file__).parent / "service_account.json"),
    )

    # ── Google Workspace ──────────────────────────────────────────────────
    GOOGLE_WORKSPACE_DELEGATED_USER: str = os.environ.get("GOOGLE_WORKSPACE_DELEGATED_USER", "")
    NOTIFICATION_SENDER_EMAIL:       str = os.environ.get("NOTIFICATION_SENDER_EMAIL", "")
    CASE_WORKER_EMAIL:               str = os.environ.get("CASE_WORKER_EMAIL", "")
    AUDIT_SHEET_ID:                  str = os.environ.get("AUDIT_SHEET_ID", "")

    # ── App ───────────────────────────────────────────────────────────────
    APP_ENV:    str = os.environ.get("APP_ENV", "development")
    LOG_LEVEL:  str = os.environ.get("LOG_LEVEL", "INFO")

    def __post_init__(self):
        import google.generativeai as genai
        if self.GEMINI_API_KEY:
            genai.configure(api_key=self.GEMINI_API_KEY)


settings = Settings()

# Configure Gemini globally on import
import google.generativeai as genai
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
