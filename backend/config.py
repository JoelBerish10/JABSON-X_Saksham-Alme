import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_UPLOADS = os.path.join(BASE_DIR, "frontend", "static", "uploads")
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "hyperlocal.db"))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-dev-key-please-change")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DB_PATH}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB upload limit
    UPLOAD_FOLDER = FRONTEND_UPLOADS if os.path.exists(os.path.dirname(FRONTEND_UPLOADS)) else os.path.join(os.path.dirname(__file__), "uploads")
    WTF_CSRF_ENABLED = True
