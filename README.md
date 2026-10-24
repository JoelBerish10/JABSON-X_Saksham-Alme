# ServeLocal — Hyperlocal Services Marketplace

A two-sided hyperlocal marketplace connecting customers who need household services with
independent local workers (plumbers, electricians, maids, cooks, carpenters, etc.).

---

## ✨ Features

| Area | Details |
|---|---|
| **Auth** | Phone-based registration, bcrypt passwords, role-based access (customer / worker / admin) |
| **Customer** | Post jobs, compare offers, accept/reject offers, track booking status, leave reviews |
| **Worker** | Create profile, set skills & availability, browse matching jobs, submit offers, update booking status |
| **Admin** | Platform stats, worker verification queue, job/user management |
| **Design** | Dark-mode glassmorphism, gradient accents, micro-animations, mobile-first |

---

## 🏗 Project Structure

```
backend/
├── app/
│   ├── __init__.py         # App factory (Flask extensions + blueprints)
│   ├── models.py           # SQLAlchemy ORM models
│   ├── utils.py            # File upload, role decorator
│   ├── main/               # Homepage routes
│   ├── auth/               # Login + registration routes
│   ├── customer/           # Customer workflow routes
│   ├── worker/             # Worker workflow routes
│   └── admin/              # Admin panel routes
├── config.py               # Configuration (reads from .env)
├── run.py                  # Backend server entry point
├── seed.py                 # DB seed script
└── requirements.txt        # Backend dependencies

frontend/
├── static/
│   ├── css/style.css       # Complete dark-mode glassmorphic design system
│   ├── js/main.js          # Interactive UI scripts
│   └── uploads/            # Uploaded files and media
└── templates/
    ├── base.html           # Master layout with navigation & flash alerts
    ├── main/               # Homepage & static views
    ├── auth/               # Login & role-based registration
    ├── customer/           # Job post, dashboard, offer compare, booking, reviews
    ├── worker/             # Worker dashboard, job browsing, offers, profile, availability
    ├── admin/              # Admin overview, worker verification, jobs, users
    └── errors/             # Custom 403, 404, 500 error pages

run.py                      # Root launcher (runs backend server)
seed.py                     # Root seed script (populates DB)
requirements.txt            # Python dependencies
```

---

## 🚀 Quick Start

### 1. Clone & set up virtual environment

```bash
git clone <repo-url>
cd JABSON-X_Saksham-Alme
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL and SECRET_KEY
```

**SQLite (simplest, no Postgres needed):**
```
DATABASE_URL=sqlite:///hyperlocal.db
SECRET_KEY=change-me-in-production
```

**PostgreSQL:**
```
DATABASE_URL=postgresql://user:password@localhost:5432/hyperlocal_db
```

### 3. Initialize & seed the database

```bash
flask db init
flask db migrate -m "Initial schema"
flask db upgrade
python seed.py
```

### 4. Run the development server

```bash
python run.py
# or
flask run
```

Open [http://localhost:5000](http://localhost:5000)

---

## 🔑 Demo Accounts

After running `python seed.py`:

| Role | Phone | Password |
|---|---|---|
| Admin | `0000000000` | `Admin@1234` |
| Customer | `9000000001` | `Customer@1234` |
| Worker | `9000000002` | `Worker@1234` |

---

## 🔒 Security Notes

- Passwords hashed with `werkzeug.security` (PBKDF2-SHA256)
- Role-based access enforced server-side (`role_required` decorator)
- CSRF protection on all POST forms via Flask-WTF
- Exact customer addresses only revealed after booking confirmation
- Identity documents (if added) stored securely, never shown publicly

---

## 📝 Booking Status Flow

```
requested → matching → offers_received → confirmed → worker_on_the_way → in_progress → completed
                                                                        ↓
                                                                    cancelled / disputed
```

---

## 🗃 Database Schema

See `app/models.py` for full models:
`users · workers · service_categories · worker_skills · availability · jobs · offers · bookings · reviews`

---

## ⚠ Disclaimers

- ETA values are estimates only — never fabricated real-time location data.
- "Verified" status is only shown for checks that have actually been completed by an admin.
- Stats on homepage are live counts from the database; labelled as illustrative if the DB is empty.

---

## 📅 Roadmap

- [ ] Recurring bookings (daily/weekly maid/cook)
- [ ] Real-time notifications (Flask-SocketIO)
- [ ] Map integration (Leaflet + OpenStreetMap)
- [ ] Payment gateway
- [ ] Multi-language UI (Hindi, Kannada, etc.)
- [ ] Voice-based job posting