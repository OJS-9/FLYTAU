# FLYTAU — Flight Board, Ticketing, and Ops Suite

FLYTAU is a full-stack flight management, ticketing, and reporting system built with Flask and MySQL. It lets guests find seats fast, keeps registered customers on top of their trips, and gives managers a cockpit for routes, crew, aircraft, and revenue insights — all aligned with the academic brief in `הנחיות פרויקט - בסיסי נתונים ומערכות מידע.pdf`.

## Why it matters
- Single experience for guests, registered flyers, and managers — no context switching.
- Seat-level booking with live availability and upfront pricing.
- Safety and governance baked in: managers cannot buy tickets, bookings lock 36h pre-departure, cancellations apply a clear 5% fee.
- Operations toolkit: add aircraft, pilots, attendants, build routes, schedule flights, and monitor occupancy and revenue trends.

## What’s inside
- **Multichannel access**
  - Guests sign in with email/name to search and buy.
  - Registered customers sign up (email/password, passport, DOB, phones) and get history + cancellation controls.
  - Managers log in with employee ID/password for administration only.
- **Flight shopping & booking**
  - Search by origin, destination, date, and passengers; pagination for future flights.
  - Seat map selection per cabin; dynamic pricing by class.
  - Booking summary and confirmation with order ID for later lookup.
  - Auto-rollover of completed orders on app start to keep statuses fresh.
- **Policy-aware cancellations**
  - Full-order cancellation (no partial) allowed up to 36h before departure with a fixed 5% fee; reflects in booking summary.
  - Role-scoped access so only the booking owner can view/manage their orders.
- **Manager cockpit**
  - Flight builder workflow: validate or create paths, pick aircraft by availability, set pricing, assign crew by required ratios, and publish.
  - Manage orders and cancel flights; view airport inventory and future capacity.
  - Add aircraft (auto-generate seats/classes), pilots, and stewards with certification rules for long-haul.
  - Built-in reports (Matplotlib) for employee hours, revenue by plane/class, flight occupancy, and cancellation rates.
- **Data & visuals**
  - MySQL schema aligned to the brief (customers, guests, managers, crew, planes, flights, orders, seats).
  - Seed expectations: ≥2 managers, 2 registered users, 2 guests, 10 pilots, 20 attendants, 6 planes, 4 active flights, 4 bookings; FLYTAU logo included in UI.
  - No real payment gateway — totals are for revenue tracking only.

## Experience by persona
- **Guest**: land → quick sign-in → search → seat selection → book → keep order code for display/cancel.
- **Registered customer**: login → search/book → seat map → confirmation → view history (active/completed/cancel) → cancel per policy.
- **Manager**: login with ID → add crew/aircraft → build routes and flights → monitor orders → run reports; purchase is blocked.

## Tech stack
- Flask + Flask-Session, MySQL (`mysql-connector-python`), Matplotlib for reports, `python-dotenv` for configuration.
- Templates and static assets served from `templates/` and `static/` (includes the FLYTAU logo).

## Setup & run
1) Install dependencies:
```bash
pip install -r requirements.txt
```
2) Create `.env` with DB credentials:
```
DB_HOST=your_host
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=flytau
FLASK_SECRET_KEY=replace_me
```
3) Initialize MySQL with the provided schema/seed script (see `Misc/FLYTAU.sql`).
4) Launch:
```bash
export FLASK_APP=main.py
flask run
```
5) Sanity checks: sign up/login, search and book, seat selection, cancel ≥36h with 5% fee, manager login, add a flight/crew/plane, view reports.

## Project structure (high level)
- `main.py` — Flask app, routes for auth, booking, cancellations, admin flows, and reports.
- `utils.py` — DB access layer (search, orders, seat maps, crew/plane creation, reporting queries).
- `templates/` — 29 HTML templates for user, guest, and manager journeys.
- `static/` — shared CSS and the FLYTAU logo.
- `Misc/FLYTAU.sql` — schema + seed data for required starting records.
- `requirements.txt` — Python dependencies.

