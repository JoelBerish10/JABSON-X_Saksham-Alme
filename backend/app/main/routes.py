from flask import render_template
from flask_login import current_user
from app.main import main_bp
from app.models import ServiceCategory, Worker, Review, Booking


@main_bp.route("/")
def index():
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    # Stats for the hero section (real counts)
    worker_count = Worker.query.filter_by(is_active=True).count()
    booking_count = Booking.query.filter_by(status="completed").count()
    review_count = Review.query.count()
    return render_template(
        "main/index.html",
        categories=categories,
        worker_count=worker_count,
        booking_count=booking_count,
        review_count=review_count,
    )
