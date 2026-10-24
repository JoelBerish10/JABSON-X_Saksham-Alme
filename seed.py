"""
Seed the database with initial service categories and a demo admin account.
Run once after `flask db upgrade`:
    python seed.py
"""
import sys
import os

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import create_app, db
from app.models import ServiceCategory, User, Worker, WorkerSkill, Availability
from datetime import time as dtime

CATEGORIES = [
    {"name": "Plumbing",               "icon": "🔧", "description": "Leaking taps, blocked drains, pipe fitting, tank installation."},
    {"name": "Electrical Services",    "icon": "⚡", "description": "Wiring, fan/light installation, fuse issues, inverter fitting."},
    {"name": "Maid & House Cleaning",  "icon": "🧹", "description": "Sweeping, mopping, deep cleaning, kitchen/bathroom cleaning."},
    {"name": "Cooks & Kitchen Help",   "icon": "🍳", "description": "Daily meals, meal prep, vegetarian/non-veg cooking, event catering."},
    {"name": "Carpentry",              "icon": "🪚", "description": "Door repairs, furniture fix, shelves, custom woodwork."},
    {"name": "Appliance Repair",       "icon": "🔌", "description": "Washing machines, fridges, ACs, water purifiers, microwaves."},
    {"name": "Painting & Renovation",  "icon": "🎨", "description": "Wall painting, putty work, crack repair, waterproofing."},
    {"name": "AC & Cooling Services",  "icon": "❄️", "description": "Servicing, installation, filter cleaning, cooling faults."},
    {"name": "Gardening",              "icon": "🌿", "description": "Lawn care, plant maintenance, garden design."},
    {"name": "Pest Control",           "icon": "🐛", "description": "Insect and rodent control for homes and offices."},
]

app = create_app()

with app.app_context():
    db.create_all()

    # Seed categories
    for cat_data in CATEGORIES:
        if not ServiceCategory.query.filter_by(name=cat_data["name"]).first():
            cat = ServiceCategory(**cat_data)
            db.session.add(cat)
    db.session.commit()
    print("✓ Service categories seeded.")

    # Demo admin
    if not User.query.filter_by(phone="0000000000").first():
        admin = User(
            full_name="Platform Admin",
            phone="0000000000",
            email="admin@hyperlocal.dev",
            role="admin",
        )
        admin.set_password("Admin@1234")
        db.session.add(admin)
        db.session.commit()
        print("✓ Admin account created  |  phone: 0000000000  |  password: Admin@1234")

    # Demo customer
    if not User.query.filter_by(phone="9000000001").first():
        customer = User(
            full_name="Riya Sharma",
            phone="9000000001",
            email="riya@example.com",
            role="customer",
        )
        customer.set_password("Customer@1234")
        db.session.add(customer)
        db.session.commit()
        print("✓ Demo customer created  |  phone: 9000000001  |  password: Customer@1234")

    # Demo worker
    if not User.query.filter_by(phone="9000000002").first():
        w_user = User(
            full_name="Ramesh Kumar",
            phone="9000000002",
            email="ramesh@example.com",
            role="worker",
        )
        w_user.set_password("Worker@1234")
        db.session.add(w_user)
        db.session.flush()

        plumbing_cat = ServiceCategory.query.filter_by(name="Plumbing").first()
        electrical_cat = ServiceCategory.query.filter_by(name="Electrical Services").first()

        worker = Worker(
            user_id=w_user.id,
            bio="5 years of experience in plumbing and electrical work. Available for urgent calls.",
            experience_years=5,
            service_radius_km=15,
            city="Bengaluru",
            verification_status="unverified",
        )
        db.session.add(worker)
        db.session.flush()

        for cat in [plumbing_cat, electrical_cat]:
            if cat:
                db.session.add(WorkerSkill(worker_id=worker.id, category_id=cat.id, skill_name=cat.name, rate_description="₹300–₹800 per visit"))

        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
            db.session.add(Availability(worker_id=worker.id, day_of_week=day, start_time=dtime(8, 0), end_time=dtime(19, 0), is_available=True))

        db.session.commit()
        print("✓ Demo worker created    |  phone: 9000000002  |  password: Worker@1234")

    print("\nSeeding complete!")
