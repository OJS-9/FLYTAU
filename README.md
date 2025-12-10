# FLYTAU Flight Management & Ticketing

Project overview and runbook for the FLYTAU flight board and ticketing system (Flask + MySQL).

## Table of Contents
- Overview
- Required Functionality
- Project Structure
- Setup & Run
- Environment Variables
- Typical User Flows
- Submission Criteria
- Current Status

## Overview
- Stack: Python 3, Flask, MySQL (Workbench for schema), `mysql-connector-python`, `python-dotenv`.
- Goal: end-to-end management of flights, bookings, users, and crew with authentication, booking, cancellation, and reporting.
- Audiences: guests, registered customers, admins/managers.

## Required Functionality (from brief)
- **Auth & registration**: user sign-up with personal details; registered user login via email+password; admin login via ID+password.
- **Search & purchase**: search flights by date/origin/destination; pick seats by availability; no extra passenger details needed when buying 2+ seats in one order.
- **Bookings management**: view upcoming tickets; cancel an entire booking up to 36 hours before departure with a 5% fee (no partial cancellation); registered users can view purchase history filtered by status (active/completed/customer-cancel/system-cancel).
- **Manager restrictions**: managers cannot purchase tickets (even as guests).
- **Flight management**: add flights per the operational process; cancel existing flights.
- **Reports**: show statistical/management reports.
- **Seed data required**: at least 2 managers, 2 registered users, 2 guests, 10 pilots, 20 flight attendants, 6 aircraft, 4 active flights, 4 bookings. Include the company logo in the UI.

## Project Structure (current and planned)
- `test.py` — sample MySQL connection and query.
- `requirements.txt` — Python deps.
- `.env` — to be created locally (not committed) for DB credentials.
- To add: `main.py`, Flask app package (`app/` with blueprints/templates/static), SQL script for schema + seed data.

## Setup & Run
1) Install deps:
```bash
pip install -r requirements.txt
```
2) Create a `.env` file (see Environment Variables).
3) Prepare the database:
   - Run the SQL script to create schema/tables and seed required data (crew, users, flights, bookings).
4) Run the Flask app (example):
```bash
export FLASK_APP=main.py
export FLASK_ENV=development  # optional
flask run
```
5) Quick checks:
   - User signup and login.
   - Search flight, buy ticket, view active booking.
   - Cancel booking ≥36h before departure with 5% fee.
   - Admin login, add/cancel flight, view reports; ensure admin cannot purchase.

## Environment Variables (`.env`)
```
DB_HOST=your_host
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=flytau
```
Add more as needed (e.g., `FLASK_SECRET_KEY`, report config, etc.).

## Typical User Flows
- Guest: search flights → choose flight/seats → finalize booking → receive booking code + email for later display/cancel.
- Registered user: login → search/book → view history or cancel per policy.
- Manager: login with ID+password → add crew/flights, cancel flights, view reports; purchasing blocked.

## Submission Criteria (from brief)
- Features implemented: 70%
- Code readability & docs: 10%
- UX/usability: 10%
- Design/visuals: 10%
- Submission: `Group_XX.zip` with app code (incl. `main.py`), SQL script, and a text file with deployed site URL + two accounts (regular + manager).

## Current Status
Repo currently has only a basic MySQL connection sample (`test.py`). Need to add the full Flask app, SQL schema, and seed data per the brief.
