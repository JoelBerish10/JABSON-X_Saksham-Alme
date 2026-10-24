from flask import Blueprint

worker_bp = Blueprint("worker", __name__)

from app.worker import routes  # noqa: F401, E402
