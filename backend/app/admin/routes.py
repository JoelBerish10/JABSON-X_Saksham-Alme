from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import User, Worker, Job, Booking, Review
from app.admin import admin_bp
from app.utils import role_required
from functools import wraps


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    stats = {
        "users": User.query.count(),
        "workers": Worker.query.count(),
        "jobs": Job.query.count(),
        "bookings": Booking.query.count(),
        "completed": Booking.query.filter_by(status="completed").count(),
    }
    recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(10).all()
    pending_workers = Worker.query.filter_by(verification_status="pending").all()
    return render_template("admin/dashboard.html", stats=stats, recent_jobs=recent_jobs, pending_workers=pending_workers)


@admin_bp.route("/workers")
@login_required
@admin_required
def workers():
    all_workers = Worker.query.join(User).order_by(User.full_name).all()
    return render_template("admin/workers.html", workers=all_workers)


@admin_bp.route("/worker/<int:worker_id>/verify", methods=["POST"])
@login_required
@admin_required
def verify_worker(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    status = request.form.get("status", "verified")
    worker.verification_status = status
    db.session.commit()
    flash(f"Worker verification status set to '{status}'.", "success")
    return redirect(url_for("admin.workers"))


@admin_bp.route("/jobs")
@login_required
@admin_required
def jobs():
    all_jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template("admin/jobs.html", jobs=all_jobs)


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/user/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    state = "activated" if user.is_active else "deactivated"
    flash(f"User {user.full_name} has been {state}.", "success")
    return redirect(url_for("admin.users"))
