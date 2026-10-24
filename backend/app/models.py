from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager


# ---------------------------------------------------------------------------
# User / Auth
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)          # customer | worker | admin
    preferred_language = db.Column(db.String(30), default="en")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    worker_profile = db.relationship("Worker", back_populates="user", uselist=False, cascade="all, delete-orphan")
    jobs = db.relationship("Job", back_populates="customer", foreign_keys="Job.customer_id")
    reviews_given = db.relationship("Review", back_populates="reviewer", foreign_keys="Review.reviewer_id")
    reviews_received = db.relationship("Review", back_populates="reviewee", foreign_keys="Review.reviewee_id")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.phone} [{self.role}]>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Service categories
# ---------------------------------------------------------------------------

class ServiceCategory(db.Model):
    __tablename__ = "service_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    icon = db.Column(db.String(50), default="🔧")       # emoji icon
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    skills = db.relationship("WorkerSkill", back_populates="category")
    jobs = db.relationship("Job", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"


# ---------------------------------------------------------------------------
# Worker profile & availability
# ---------------------------------------------------------------------------

class Worker(db.Model):
    __tablename__ = "workers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    bio = db.Column(db.Text)
    experience_years = db.Column(db.Integer, default=0)
    service_radius_km = db.Column(db.Float, default=10.0)
    verification_status = db.Column(db.String(30), default="unverified")
    # average_rating is derived via property for accuracy
    is_active = db.Column(db.Boolean, default=True)
    city = db.Column(db.String(100))
    address = db.Column(db.String(255))
    photo_filename = db.Column(db.String(200))

    user = db.relationship("User", back_populates="worker_profile")
    skills = db.relationship("WorkerSkill", back_populates="worker", cascade="all, delete-orphan")
    availability = db.relationship("Availability", back_populates="worker", cascade="all, delete-orphan")
    offers = db.relationship("Offer", back_populates="worker")

    @property
    def average_rating(self):
        reviews = Review.query.join(Booking).filter(
            Booking.worker_id == self.id
        ).all()
        if not reviews:
            return None
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def total_bookings(self):
        return Booking.query.filter_by(worker_id=self.id, status="completed").count()

    def __repr__(self):
        return f"<Worker user_id={self.user_id}>"


class WorkerSkill(db.Model):
    __tablename__ = "worker_skills"

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("service_categories.id"), nullable=False)
    skill_name = db.Column(db.String(150))
    rate_per_hour = db.Column(db.Numeric(10, 2), nullable=True)
    rate_description = db.Column(db.String(255))

    worker = db.relationship("Worker", back_populates="skills")
    category = db.relationship("ServiceCategory", back_populates="skills")


DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Availability(db.Model):
    __tablename__ = "availability"

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    day_of_week = db.Column(db.String(10), nullable=False)  # Monday … Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_available = db.Column(db.Boolean, default=True)

    worker = db.relationship("Worker", back_populates="availability")


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

JOB_STATUSES = [
    "requested", "matching", "offers_received", "confirmed",
    "worker_on_the_way", "in_progress", "completed", "cancelled", "disputed"
]

URGENCY_TYPES = ["urgent", "scheduled", "recurring"]


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("service_categories.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    # Location stored as display string; lat/lng optional
    location_text = db.Column(db.String(255))
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    budget_min = db.Column(db.Numeric(10, 2), nullable=True)
    budget_max = db.Column(db.Numeric(10, 2), nullable=True)
    urgency = db.Column(db.String(20), default="urgent")
    preferred_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(30), default="requested")
    photo_filename = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("User", back_populates="jobs", foreign_keys=[customer_id])
    category = db.relationship("ServiceCategory", back_populates="jobs")
    offers = db.relationship("Offer", back_populates="job", cascade="all, delete-orphan")
    booking = db.relationship("Booking", back_populates="job", uselist=False)

    def __repr__(self):
        return f"<Job #{self.id} [{self.status}]>"


# ---------------------------------------------------------------------------
# Offers
# ---------------------------------------------------------------------------

OFFER_STATUSES = ["pending", "accepted", "rejected", "countered", "withdrawn", "expired"]


class Offer(db.Model):
    __tablename__ = "offers"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    quoted_price = db.Column(db.Numeric(10, 2), nullable=False)
    estimated_arrival_minutes = db.Column(db.Integer, nullable=True)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    job = db.relationship("Job", back_populates="offers")
    worker = db.relationship("Worker", back_populates="offers")

    def __repr__(self):
        return f"<Offer job={self.job_id} worker={self.worker_id} [{self.status}]>"


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, unique=True)
    offer_id = db.Column(db.Integer, db.ForeignKey("offers.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    agreed_price = db.Column(db.Numeric(10, 2), nullable=False)
    agreed_scope = db.Column(db.Text)
    scheduled_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(30), default="confirmed")
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    job = db.relationship("Job", back_populates="booking")
    offer = db.relationship("Offer")
    customer = db.relationship("User", foreign_keys=[customer_id])
    worker = db.relationship("Worker", foreign_keys=[worker_id])
    review = db.relationship("Review", back_populates="booking", uselist=False)

    def __repr__(self):
        return f"<Booking #{self.id} [{self.status}]>"


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False, unique=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)   # 1–5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    booking = db.relationship("Booking", back_populates="review")
    reviewer = db.relationship("User", back_populates="reviews_given", foreign_keys=[reviewer_id])
    reviewee = db.relationship("User", back_populates="reviews_received", foreign_keys=[reviewee_id])

    def __repr__(self):
        return f"<Review booking={self.booking_id} rating={self.rating}>"
