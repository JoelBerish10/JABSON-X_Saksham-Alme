from flask import Blueprint

customer_bp = Blueprint("customer", __name__)

from app.customer import routes  # noqa: F401, E402
