from datetime import datetime, time as dtime
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import (
    Worker, WorkerSkill, Availability, Job, Offer,
    Booking, ServiceCategory, Review, DAYS_OF_WEEK
)
from app.worker import worker_bp
from app.utils import role_required


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@worker_bp.route("/dashboard")
@login_required
@role_required("worker")
def dashboard():
    worker = current_user.worker_profile
    if not worker:
        flash("Worker profile not found.", "danger")
        return redirect(url_for("main.index"))

    # Jobs matching this worker's skills
    skill_cat_ids = [s.category_id for s in worker.skills]
    available_jobs = []
    if skill_cat_ids:
        available_jobs = (
            Job.query
            .filter(
                Job.category_id.in_(skill_cat_ids),
                Job.status.in_(["requested", "matching"]),
            )
            .order_by(Job.created_at.desc())
            .limit(20)
            .all()
        )
        # Exclude jobs the worker already offered on
        offered_job_ids = {o.job_id for o in worker.offers}
        available_jobs = [j for j in available_jobs if j.id not in offered_job_ids]

    my_offers = Offer.query.filter_by(worker_id=worker.id).order_by(Offer.created_at.desc()).limit(10).all()
    my_bookings = Booking.query.filter_by(worker_id=worker.id).order_by(Booking.created_at.desc()).limit(10).all()

    return render_template(
        "worker/dashboard.html",
        worker=worker,
        available_jobs=available_jobs,
        my_offers=my_offers,
        my_bookings=my_bookings,
    )


# ---------------------------------------------------------------------------
# View available job & submit offer
# ---------------------------------------------------------------------------

@worker_bp.route("/job/<int:job_id>")
@login_required
@role_required("worker")
def view_job(job_id):
    job = Job.query.get_or_404(job_id)
    worker = current_user.worker_profile
    existing_offer = Offer.query.filter_by(job_id=job_id, worker_id=worker.id).first()
    return render_template("worker/view_job.html", job=job, existing_offer=existing_offer)


@worker_bp.route("/job/<int:job_id>/submit-offer", methods=["POST"])
@login_required
@role_required("worker")
def submit_offer(job_id):
    job = Job.query.get_or_404(job_id)
    worker = current_user.worker_profile

    if job.status not in ("requested", "matching"):
        flash("This job is no longer accepting offers.", "warning")
        return redirect(url_for("worker.dashboard"))

    existing = Offer.query.filter_by(job_id=job_id, worker_id=worker.id).first()
    if existing:
        flash("You have already submitted an offer for this job.", "info")
        return redirect(url_for("worker.view_job", job_id=job_id))

    quoted_price = request.form.get("quoted_price", "").strip()
    message = request.form.get("message", "").strip()
    eta = request.form.get("estimated_arrival_minutes", "").strip()

    if not quoted_price:
        flash("Please enter a price quote.", "danger")
        return redirect(url_for("worker.view_job", job_id=job_id))

    offer = Offer(
        job_id=job_id,
        worker_id=worker.id,
        quoted_price=float(quoted_price),
        message=message,
        estimated_arrival_minutes=int(eta) if eta else None,
        status="pending",
    )
    db.session.add(offer)
    job.status = "offers_received"
    db.session.commit()
    flash("Offer submitted successfully!", "success")
    return redirect(url_for("worker.dashboard"))


# ---------------------------------------------------------------------------
# Booking management
# ---------------------------------------------------------------------------

@worker_bp.route("/booking/<int:booking_id>")
@login_required
@role_required("worker")
def booking_detail(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    worker = current_user.worker_profile
    if booking.worker_id != worker.id:
        abort(403)
    return render_template("worker/booking_detail.html", booking=booking)


@worker_bp.route("/booking/<int:booking_id>/update-status", methods=["POST"])
@login_required
@role_required("worker")
def update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    worker = current_user.worker_profile
    if booking.worker_id != worker.id:
        abort(403)

    new_status = request.form.get("status")
    allowed_transitions = {
        "confirmed": ["worker_on_the_way", "cancelled"],
        "worker_on_the_way": ["in_progress", "cancelled"],
        "in_progress": ["completed"],
    }
    current_status = booking.status
    if new_status not in allowed_transitions.get(current_status, []):
        flash("Invalid status transition.", "danger")
        return redirect(url_for("worker.booking_detail", booking_id=booking_id))

    booking.status = new_status
    booking.job.status = new_status
    if new_status == "completed":
        booking.completed_at = datetime.utcnow()
    db.session.commit()
    flash(f"Booking status updated to '{new_status}'.", "success")
    return redirect(url_for("worker.booking_detail", booking_id=booking_id))


# ---------------------------------------------------------------------------
# Worker profile edit
# ---------------------------------------------------------------------------

@worker_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("worker")
def edit_profile():
    worker = current_user.worker_profile
    categories = ServiceCategory.query.filter_by(is_active=True).all()

    if request.method == "POST":
        worker.bio = request.form.get("bio", "").strip()
        worker.experience_years = int(request.form.get("experience_years", 0) or 0)
        worker.service_radius_km = float(request.form.get("service_radius_km", 10) or 10)
        worker.city = request.form.get("city", "").strip()

        # Update skills
        selected_cats = request.form.getlist("categories")
        # Remove existing and re-add
        WorkerSkill.query.filter_by(worker_id=worker.id).delete()
        for cat_id in selected_cats:
            cat = ServiceCategory.query.get(int(cat_id))
            if cat:
                skill = WorkerSkill(
                    worker_id=worker.id,
                    category_id=cat.id,
                    skill_name=cat.name,
                    rate_description=request.form.get(f"rate_{cat_id}", ""),
                )
                db.session.add(skill)

        db.session.commit()
        flash("Profile updated!", "success")
        return redirect(url_for("worker.edit_profile"))

    my_cat_ids = {s.category_id for s in worker.skills}
    return render_template("worker/edit_profile.html", worker=worker, categories=categories, my_cat_ids=my_cat_ids)


# ---------------------------------------------------------------------------
# Availability management
# ---------------------------------------------------------------------------

@worker_bp.route("/availability", methods=["GET", "POST"])
@login_required
@role_required("worker")
def manage_availability():
    worker = current_user.worker_profile

    if request.method == "POST":
        # Delete existing and recreate
        Availability.query.filter_by(worker_id=worker.id).delete()
        for day in DAYS_OF_WEEK:
            is_avail = request.form.get(f"avail_{day}") == "on"
            if is_avail:
                start_str = request.form.get(f"start_{day}", "09:00")
                end_str = request.form.get(f"end_{day}", "18:00")
                try:
                    sh, sm = map(int, start_str.split(":"))
                    eh, em = map(int, end_str.split(":"))
                    avail = Availability(
                        worker_id=worker.id,
                        day_of_week=day,
                        start_time=dtime(sh, sm),
                        end_time=dtime(eh, em),
                        is_available=True,
                    )
                    db.session.add(avail)
                except (ValueError, AttributeError):
                    pass
        db.session.commit()
        flash("Availability updated!", "success")
        return redirect(url_for("worker.manage_availability"))

    avail_map = {a.day_of_week: a for a in worker.availability}
    return render_template("worker/availability.html", worker=worker, days=DAYS_OF_WEEK, avail_map=avail_map)


# ---------------------------------------------------------------------------
# Public worker profile
# ---------------------------------------------------------------------------

@worker_bp.route("/profile/<int:worker_id>")
def public_profile(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    reviews = (
        Review.query
        .join(Booking)
        .filter(Booking.worker_id == worker.id)
        .order_by(Review.created_at.desc())
        .all()
    )
    return render_template("worker/public_profile.html", worker=worker, reviews=reviews)
