# PulseNotify ✈️🔔

PulseNotify is an asynchronous, event-driven flight price monitoring and alert notification system built using **Django REST Framework (DRF)**, **Celery**, **Redis**, and **PostgreSQL**.

The system allows users to set price alerts for flight routes. A background periodic worker queries live flight pricing and automatically logs/dispatches alerts when prices drop below the user-specified threshold.

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph CLIENT["👤 Client Layer"]
        Postman["Postman / Browser / cURL"]
    end

    subgraph DJANGO["🌐 Django REST API  —  Port 9000"]
        direction TB
        Auth["🔐 Auth Module\n/api/auth/register/\n/api/auth/login/"]
        Alerts["📋 Alert CRUD\n/api/alerts/\n/api/alerts/&lt;id&gt;/"]
        Flights["✈️ Flight Price Feed\n/api/flights/price/?route="]
        Admin["🛡️ Admin Dashboard\n/api/admin/summary/"]
        JWT["SimpleJWT\nToken Verification"]
        Perms["IsAdminUser\nPermission Guard"]
    end

    subgraph DATA["🗄️ PostgreSQL Database"]
        direction LR
        UserProfile[("UserProfile\n— user (FK)\n— role: admin | user")]
        PriceAlert[("PriceAlert\n— origin, destination\n— threshold_price\n— status: active | triggered | inactive")]
        NotifLog[("NotificationLog\n— alert (FK)\n— triggered_price\n— message\n— notified_at")]
    end

    subgraph ASYNC["⚙️ Celery Async Pipeline"]
        direction LR
        Beat["🕐 Celery Beat\nScheduler\n(every 60s)"]
        Redis[("Redis\nMessage Broker\nPort 6379")]
        Worker["🔧 Celery Worker"]
    end

    subgraph TASKS["📦 Task Execution Detail"]
        direction TB
        T1["1️⃣ check_prices\nQuery all ACTIVE alerts\nFetch price per route"]
        T2{"price ≤\nthreshold?"}
        T3["2️⃣ send_notification\nLog to NotificationLog\nMark alert TRIGGERED"]
        Skip["Skip — no action"]
    end

    %% Client to Django
    Postman -->|"HTTP Request\n+ Bearer JWT Token"| Auth
    Postman -->|"HTTP Request\n+ Bearer JWT Token"| Alerts
    Postman -->|"HTTP GET\n(no auth required)"| Flights
    Postman -->|"HTTP Request\n+ Admin JWT Token"| Admin

    %% Django internal auth flow
    Auth -->|"Issue / Validate Token"| JWT
    Alerts -->|"Verify Token"| JWT
    Admin -->|"Verify Token"| JWT
    Admin -->|"Check role=admin"| Perms

    %% Django to Database
    Auth -->|"Create User +\nauto-create UserProfile (signal)"| UserProfile
    Alerts -->|"Create / List / Deactivate"| PriceAlert
    Admin -->|"Aggregate stats:\nCount, Q filters"| PriceAlert
    Admin -->|"Count notifications"| NotifLog

    %% Celery pipeline
    Beat -->|"Dispatch\ncheck_prices task"| Redis
    Redis -->|"Deliver task"| Worker
    Worker --> T1
    T1 -->|"GET /api/flights/price/"| Flights
    T1 -->|"Read ACTIVE alerts"| PriceAlert
    T1 --> T2
    T2 -->|"Yes"| T3
    T2 -->|"No"| Skip
    T3 -->|"Insert row"| NotifLog
    T3 -->|"Update status → TRIGGERED"| PriceAlert

    %% Styling
    style CLIENT fill:#e8f4fd,stroke:#2196F3,stroke-width:2px,color:#000
    style DJANGO fill:#fff3e0,stroke:#FF9800,stroke-width:2px,color:#000
    style DATA fill:#e8f5e9,stroke:#4CAF50,stroke-width:2px,color:#000
    style ASYNC fill:#fce4ec,stroke:#E91E63,stroke-width:2px,color:#000
    style TASKS fill:#f3e5f5,stroke:#9C27B0,stroke-width:2px,color:#000
    style T2 fill:#fff9c4,stroke:#F9A825,stroke-width:2px,color:#000
```

### How It Works — Step by Step:

1. **User Registration & Login** — Client sends credentials to `/api/auth/register/` or `/api/auth/login/`. Django validates them, creates a `UserProfile` (via a `post_save` signal), and returns a **JWT access token**.

2. **Creating Price Alerts** — Authenticated users `POST` to `/api/alerts/` with a route (`origin`→`destination`) and a `threshold_price`. The alert is stored as `ACTIVE` in PostgreSQL.

3. **Background Price Monitoring (Celery Beat → Worker)** — Every **60 seconds**, Celery Beat pushes a `check_prices` task into the **Redis** message broker. A Celery Worker picks it up and:
   - Queries all `ACTIVE` alerts from the database.
   - Groups them by route and fetches the current price from the **mock flight price feed** (`/api/flights/price/`).
   - Compares `current_price` against each alert's `threshold_price`.

4. **Triggering Notifications** — When `price ≤ threshold`, the worker dispatches `send_notification`, which:
   - Creates an immutable record in `NotificationLog` with the triggered price and message.
   - Updates the alert's status from `ACTIVE` → `TRIGGERED`.

5. **Admin Dashboard** — Users with `role=admin` in their `UserProfile` can call `/api/admin/summary/` to see aggregate statistics (total/active/triggered alerts, notification count, top 5 monitored routes).

6. **Alert Deactivation** — Users can manually `DELETE /api/alerts/<id>/` to set an alert to `INACTIVE`, removing it from future price checks.

---

## 📁 Project Structure

```text
PulseNotify/
├── config/                     # Project configuration & settings
│   ├── settings/
│   │   ├── base.py             # Core settings, Celery & DRF config
│   │   ├── local.py            # Local development settings
│   │   └── production.py       # Production security settings
│   ├── celery.py               # Celery application initialization
│   ├── urls.py                 # Root URL configuration
│   └── wsgi.py
├── pulse/                      # Core application
│   ├── models.py               # UserProfile, PriceAlert, NotificationLog
│   ├── serializers.py          # DRF serializers (Registration, Alerts)
│   ├── views.py                # Auth, Alerts, Flight Mock, Admin Summary
│   ├── permissions.py          # IsAdminUser custom permission class
│   ├── tasks.py                # Celery tasks (check_prices, send_notification)
│   ├── signals.py              # Automatic UserProfile creation on User save
│   ├── tests.py                # Unit and integration test suite
│   └── urls.py                 # App routing
├── docker-compose.yml          # Container configuration for Redis & Postgres
├── manage.py                   # Django management script
├── postman_collection.json     # Postman collection for all 12 test scenarios
├── pyproject.toml              # Dependencies & project metadata
└── README.md
```

---

## 🛠️ Tech Stack & Dependencies

- **Language:** Python 3.13+
- **Web Framework:** Django 6.1 + Django REST Framework
- **Authentication:** SimpleJWT (JSON Web Tokens)
- **Task Queue & Scheduler:** Celery + Celery Beat
- **Message Broker:** Redis
- **Database:** PostgreSQL (production / local)
- **HTTP Client:** Requests

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have the following installed and running:
- Python 3.12 or 3.13
- PostgreSQL
- Redis Server (or via Docker: `docker compose up -d`)

### 2. Environment Setup
Create a `.env` file in the project root:
```env
DJANGO_SETTINGS_MODULE=config.settings.local
SECRET_KEY=your-secure-secret-key-here
DB_NAME=pulsenotify
DB_USER=pulseuser
DB_PASSWORD=pulse_dev_password
DB_HOST=localhost
DB_PORT=5432
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 3. Install Dependencies & Run Migrations
```bash
# Activate virtual environment
.\.venv\Scripts\activate   # Windows
# source .venv/bin/activate # Linux/macOS

# Apply migrations
python manage.py migrate
```

---

## ⚙️ Running the System

You need three terminal processes running concurrently:

### Terminal 1: Django API Server
```bash
python manage.py runserver 9000
```

### Terminal 2: Celery Worker
```bash
# On Windows, use --pool=solo
celery -A config worker --loglevel=info --pool=solo

# On Linux/macOS
celery -A config worker --loglevel=info
```

### Terminal 3: Celery Beat (Scheduler)
```bash
celery -A config beat --loglevel=info
```

---

## 📡 API Endpoints Reference

| # | Endpoint | Method | Auth | Description |
|---|---|---|---|---|
| 1 | `/api/auth/register/` | `POST` | None | Register new user; returns JWT access token |
| 2 | `/api/auth/login/` | `POST` | None | Authenticate; returns JWT access token & user role |
| 3 | `/api/alerts/` | `GET` | Bearer Token | List all alerts belonging to the authenticated user |
| 4 | `/api/alerts/` | `POST` | Bearer Token | Create an alert (`origin`, `destination`, `threshold_price`) |
| 5 | `/api/alerts/<id>/` | `DELETE` | Bearer Token | Deactivate an alert |
| 6 | `/api/flights/price/?route=<R>` | `GET` | None | Mock flight price feed (e.g. `DEL-BOM`, `BLR-HYD`) |
| 7 | `/api/admin/summary/` | `GET` | Admin Token | Metrics: active/triggered alerts, notifications & top routes |

---

## 🧪 Testing & Postman Collection

### 1. Django Automated Tests
Run unit tests verifying models, permissions, scoping, and threshold evaluation:
```bash
python manage.py test
```

### 2. Postman Collection
The file [`postman_collection.json`](./postman_collection.json) is pre-configured with all 12 validation scenarios.

To run via Newman CLI:
```bash
npx -y newman run postman_collection.json
```
All 12 scenarios (24 assertions) will execute and pass against `http://127.0.0.1:9000`.

### 3. Verifying Asynchronous Notifications in PGAdmin (Scenario 13)
To verify background Celery execution:
1. Open **PGAdmin** and connect to the `pulsenotify` database.
2. Open the Query Tool and run:
   ```sql
   SELECT * FROM pulse_notificationlog;
   ```
3. A row will be visible with `triggered_price`, `message`, and timestamp when Celery processes an alert whose threshold condition was satisfied.
