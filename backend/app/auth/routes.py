from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Worker, ServiceCategory, WorkerSkill, Availability
from app.auth import auth_bp
from datetime import time as dtime


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_dashboard(current_user)

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        user = User.query.filter_by(phone=phone).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            flash("Welcome back, " + user.full_name + "!", "success")
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)
            return _redirect_dashboard(user)
        flash("Invalid phone number or password.", "danger")

    return render_template("auth/login.html")


# ---------------------------------------------------------------------------
# Register Customer
# ---------------------------------------------------------------------------

@auth_bp.route("/register/customer", methods=["GET", "POST"])
def register_customer():
    if current_user.is_authenticated:
        return _redirect_dashboard(current_user)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip() or None
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()
        lang = request.form.get("preferred_language", "en")

        errors = _validate_base_registration(full_name, phone, email, password, confirm)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register_customer.html", form_data=request.form)

        user = User(
            full_name=full_name,
            phone=phone,
            email=email,
            role="customer",
            preferred_language=lang,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Account created! Welcome, " + user.full_name + ".", "success")
        return redirect(url_for("customer.dashboard"))

    return render_template("auth/register_customer.html", form_data={})


# ---------------------------------------------------------------------------
# Register Worker
# ---------------------------------------------------------------------------

@auth_bp.route("/register/worker", methods=["GET", "POST"])
def register_worker():
    if current_user.is_authenticated:
        return _redirect_dashboard(current_user)

    categories = ServiceCategory.query.filter_by(is_active=True).all()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip() or None
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()
        lang = request.form.get("preferred_language", "en")
        bio = request.form.get("bio", "").strip()
        experience_years = int(request.form.get("experience_years", 0) or 0)
        service_radius = float(request.form.get("service_radius_km", 10) or 10)
        city = request.form.get("city", "").strip()
        address = request.form.get("address", "").strip()
        selected_categories = request.form.getlist("categories")

        errors = _validate_base_registration(full_name, phone, email, password, confirm)
        if not selected_categories:
            errors.append("Please select at least one service category.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register_worker.html", categories=categories, form_data=request.form)

        user = User(
            full_name=full_name,
            phone=phone,
            email=email,
            role="worker",
            preferred_language=lang,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # get user.id

        worker = Worker(
            user_id=user.id,
            bio=bio,
            experience_years=experience_years,
            service_radius_km=service_radius,
            city=city,
            address=address,
            verification_status="unverified",
        )
        db.session.add(worker)
        db.session.flush()  # get worker.id

        # Add selected skills
        for cat_id in selected_categories:
            cat = ServiceCategory.query.get(int(cat_id))
            if cat:
                skill = WorkerSkill(
                    worker_id=worker.id,
                    category_id=cat.id,
                    skill_name=cat.name,
                )
                db.session.add(skill)

        # Default availability Mon–Fri 9am–6pm
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            avail = Availability(
                worker_id=worker.id,
                day_of_week=day,
                start_time=dtime(9, 0),
                end_time=dtime(18, 0),
                is_available=True,
            )
            db.session.add(avail)

        db.session.commit()
        login_user(user)
        flash("Worker profile created! Complete your availability settings.", "success")
        return redirect(url_for("worker.dashboard"))

    return render_template("auth/register_worker.html", categories=categories, form_data={})


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_base_registration(full_name, phone, email, password, confirm):
    errors = []
    if not full_name or len(full_name) < 2:
        errors.append("Full name must be at least 2 characters.")
    if not phone or len(phone) < 7:
        errors.append("Please enter a valid phone number.")
    if User.query.filter_by(phone=phone).first():
        errors.append("This phone number is already registered.")
    if email and User.query.filter_by(email=email).first():
        errors.append("This email address is already registered.")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password != confirm:
        errors.append("Passwords do not match.")
    return errors


def _redirect_dashboard(user):
    if user.role == "worker":
        return redirect(url_for("worker.dashboard"))
    if user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("customer.dashboard"))
