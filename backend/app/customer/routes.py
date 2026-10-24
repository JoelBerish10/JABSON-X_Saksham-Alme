import os
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from app import db
from app.models import (
    Job, ServiceCategory, Offer, Booking, Review,
    Worker, WorkerSkill, User, OFFER_STATUSES
)
from app.customer import customer_bp
from app.utils import save_uploaded_file, role_required


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@customer_bp.route("/dashboard")
@login_required
@role_required("customer")
def dashboard():
    jobs = Job.query.filter_by(customer_id=current_user.id).order_by(Job.created_at.desc()).limit(10).all()
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    return render_template("customer/dashboard.html", jobs=jobs, categories=categories)


# ---------------------------------------------------------------------------
# Post a job
# ---------------------------------------------------------------------------

@customer_bp.route("/post-job", methods=["GET", "POST"])
@login_required
@role_required("customer")
def post_job():
    categories = ServiceCategory.query.filter_by(is_active=True).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id")
        location_text = request.form.get("location_text", "").strip()
        budget_min = request.form.get("budget_min") or None
        budget_max = request.form.get("budget_max") or None
        urgency = request.form.get("urgency", "urgent")
        preferred_time_str = request.form.get("preferred_time", "").strip()
        preferred_time = None
        if preferred_time_str:
            try:
                preferred_time = datetime.strptime(preferred_time_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                pass

        errors = []
        if not title:
            errors.append("Please provide a job title.")
        if not description or len(description) < 10:
            errors.append("Please describe the work needed (at least 10 characters).")
        if not category_id:
            errors.append("Please choose a service category.")
        if not location_text:
            errors.append("Please enter the service location.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("customer/post_job.html", categories=categories, form_data=request.form)

        photo_filename = None
        if "photo" in request.files:
            photo_filename = save_uploaded_file(request.files["photo"])

        job = Job(
            customer_id=current_user.id,
            category_id=int(category_id),
            title=title,
            description=description,
            location_text=location_text,
            budget_min=float(budget_min) if budget_min else None,
            budget_max=float(budget_max) if budget_max else None,
            urgency=urgency,
            preferred_time=preferred_time,
            photo_filename=photo_filename,
            status="requested",
        )
        db.session.add(job)
        db.session.commit()

        # Run basic matching — notify eligible workers (status → matching)
        _run_matching(job)

        flash("Job posted! Matching you with available workers…", "success")
        return redirect(url_for("customer.view_job", job_id=job.id))

    return render_template("customer/post_job.html", categories=categories, form_data={})


# ---------------------------------------------------------------------------
# View a single job & its offers
# ---------------------------------------------------------------------------

@customer_bp.route("/job/<int:job_id>")
@login_required
@role_required("customer")
def view_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.customer_id != current_user.id:
        abort(403)
    offers = Offer.query.filter_by(job_id=job.id).order_by(Offer.quoted_price).all()
    booking = Booking.query.filter_by(job_id=job.id).first()
    return render_template("customer/view_job.html", job=job, offers=offers, booking=booking)


# ---------------------------------------------------------------------------
# Accept an offer → create booking
# ---------------------------------------------------------------------------

@customer_bp.route("/job/<int:job_id>/accept-offer/<int:offer_id>", methods=["POST"])
@login_required
@role_required("customer")
def accept_offer(job_id, offer_id):
    job = Job.query.get_or_404(job_id)
    if job.customer_id != current_user.id:
        abort(403)
    if job.status not in ("requested", "matching", "offers_received"):
        flash("This job cannot accept an offer at this stage.", "warning")
        return redirect(url_for("customer.view_job", job_id=job_id))

    offer = Offer.query.get_or_404(offer_id)
    if offer.job_id != job_id or offer.status != "pending":
        flash("Invalid or expired offer.", "danger")
        return redirect(url_for("customer.view_job", job_id=job_id))

    # Reject all other pending offers
    for other in job.offers:
        if other.id != offer_id and other.status == "pending":
            other.status = "rejected"

    offer.status = "accepted"
    job.status = "confirmed"

    booking = Booking(
        job_id=job.id,
        offer_id=offer.id,
        customer_id=current_user.id,
        worker_id=offer.worker_id,
        agreed_price=offer.quoted_price,
        agreed_scope=job.description,
    )
    db.session.add(booking)
    db.session.commit()

    flash("Offer accepted! Your booking is confirmed.", "success")
    return redirect(url_for("customer.booking_detail", booking_id=booking.id))


# ---------------------------------------------------------------------------
# Booking detail / tracker
# ---------------------------------------------------------------------------

@customer_bp.route("/booking/<int:booking_id>")
@login_required
@role_required("customer")
def booking_detail(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.customer_id != current_user.id:
        abort(403)
    return render_template("customer/booking_detail.html", booking=booking)


# ---------------------------------------------------------------------------
# Submit review
# ---------------------------------------------------------------------------

@customer_bp.route("/booking/<int:booking_id>/review", methods=["GET", "POST"])
@login_required
@role_required("customer")
def submit_review(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.customer_id != current_user.id:
        abort(403)
    if booking.status != "completed":
        flash("You can only review completed bookings.", "warning")
        return redirect(url_for("customer.booking_detail", booking_id=booking_id))
    if booking.review:
        flash("You have already submitted a review for this booking.", "info")
        return redirect(url_for("customer.booking_detail", booking_id=booking_id))

    if request.method == "POST":
        rating = int(request.form.get("rating", 0))
        comment = request.form.get("comment", "").strip()
        if rating < 1 or rating > 5:
            flash("Please select a rating between 1 and 5.", "danger")
            return render_template("customer/review_form.html", booking=booking)

        review = Review(
            booking_id=booking.id,
            reviewer_id=current_user.id,
            reviewee_id=booking.worker.user_id,
            rating=rating,
            comment=comment,
        )
        db.session.add(review)
        db.session.commit()
        flash("Thank you for your review!", "success")
        return redirect(url_for("customer.booking_detail", booking_id=booking_id))

    return render_template("customer/review_form.html", booking=booking)


# ---------------------------------------------------------------------------
# Cancel a job
# ---------------------------------------------------------------------------

@customer_bp.route("/job/<int:job_id>/cancel", methods=["POST"])
@login_required
@role_required("customer")
def cancel_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.customer_id != current_user.id:
        abort(403)
    if job.status in ("completed", "cancelled"):
        flash("This job cannot be cancelled.", "warning")
        return redirect(url_for("customer.view_job", job_id=job_id))
    job.status = "cancelled"
    # Withdraw all pending offers
    for offer in job.offers:
        if offer.status == "pending":
            offer.status = "withdrawn"
    db.session.commit()
    flash("Job cancelled.", "info")
    return redirect(url_for("customer.dashboard"))


# ---------------------------------------------------------------------------
# Matching helper
# ---------------------------------------------------------------------------

def _run_matching(job: Job):
    """Basic matching: find workers with the right skill who are active."""
    eligible_workers = (
        Worker.query
        .join(WorkerSkill)
        .filter(
            WorkerSkill.category_id == job.category_id,
            Worker.is_active == True,
        )
        .distinct()
        .all()
    )
    if eligible_workers:
        job.status = "matching"
        db.session.commit()
