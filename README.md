# ✈️ FLYTAU — Your Complete Flight Management & Booking Platform

**Transform how you manage flights, serve customers, and grow your airline business.**

FLYTAU is a powerful, all-in-one flight management system that delivers seamless booking experiences for travelers while giving managers complete control over operations, crew, and revenue insights. Built with modern web technologies, it's designed to scale from startup to enterprise—all while keeping your data secure and your workflows intuitive.

---

## 🎯 Why FLYTAU Stands Out

### For Your Customers
- **Lightning-fast booking** — Guests can search and book in minutes, no account required
- **Smart seat selection** — Interactive seat maps show real-time availability with instant pricing
- **Flexible cancellation** — Clear policies: cancel up to 36 hours before departure with a transparent 5% fee
- **Complete travel history** — Registered users track all their flights in one place, filtered by status

### For Your Team
- **One unified platform** — Manage flights, crew, aircraft, and orders from a single dashboard
- **Intelligent flight builder** — Step-by-step wizard ensures every flight meets safety and capacity requirements
- **Real-time insights** — Beautiful visual reports reveal revenue trends, occupancy rates, and crew performance
- **Built-in safeguards** — Managers can't purchase tickets, preventing conflicts of interest automatically

---

## 🚀 What You Get

### **Three User Experiences, One Powerful System**

#### 👤 Guest Experience
Perfect for one-time travelers. Simply enter your email and name, search flights, pick your seats, and book instantly. Your order code is your ticket to view or cancel anytime.

#### 👥 Registered Customer Experience
Create an account once, and your details auto-fill for every booking. Access your complete travel history, filter by status (active, completed, cancelled), and manage all your reservations from one dashboard.

#### 👔 Manager Experience
Your command center for operations. Add aircraft and crew members, build new routes, schedule flights with intelligent resource allocation, monitor bookings, and generate actionable business reports—all while the system prevents you from purchasing tickets.

---

## 💎 Key Features That Make a Difference

### **Intelligent Flight Search & Booking**
- Search by origin, destination, date, and passenger count
- Real-time seat availability with visual seat maps
- Dynamic pricing by class (Economy & Business)
- Instant booking confirmation with unique order IDs
- Automatic order status updates (active → completed)

### **Smart Cancellation Management**
- Full-order cancellation (no partial cancellations)
- 36-hour cancellation window with clear 5% fee policy
- Role-based access ensures customers only see their own bookings
- Transparent cancellation summaries with refund calculations

### **Complete Operations Management**
- **Aircraft Management**: Add planes with automatic seat generation
- **Crew Management**: Add pilots and stewards with certification tracking for long-haul flights
- **Route Builder**: Create new flight paths or use existing ones with timezone support
- **Flight Scheduling**: Multi-step wizard ensures proper resource allocation (planes, crew, timing)
- **Order Oversight**: View and manage all bookings with powerful filtering

### **Business Intelligence Dashboard**
Four comprehensive reports powered by beautiful visualizations:
- **Employee Flight Hours** — Track crew workload and prevent fatigue
- **Revenue Analysis** — Break down earnings by plane size, manufacturer, and class
- **Flight Occupancy** — Identify underperforming routes and optimize capacity
- **Cancellation Trends** — Monitor cancellation rates by month to spot patterns

---

## 🛠️ Technology Stack

Built with industry-standard tools for reliability and performance:

- **Backend**: Flask (Python) with session management
- **Database**: MySQL with optimized queries and relationships
- **Visualizations**: Matplotlib for professional business reports
- **Architecture**: Clean separation of concerns (routes, utilities, templates)

---

## ⚡ Quick Start Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Your Environment
Create a `.env` file in the project root:
```env
DB_HOST=your_host
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=flytau
FLASK_SECRET_KEY=your_secret_key_here
```

### 3. Initialize Your Database
Run the provided SQL script (`Misc/FLYTAU.sql`) to create the schema and load seed data:
- 2 managers, 2 registered users, 2 guests
- 10 pilots, 20 flight attendants
- 6 aircraft with full seat configurations
- 4 active flights, 4 sample bookings

### 4. Launch the Application
```bash
export FLASK_APP=main.py
flask run
```

### 5. Start Exploring
- **As a Guest**: Visit the homepage → Quick sign-in → Search flights → Book seats
- **As a Customer**: Sign up → Login → Browse your dashboard → Book or view history
- **As a Manager**: Login with employee ID → Access admin dashboard → Add resources → Create flights → View reports

---

## 📁 Project Structure

```
Code/
├── main.py              # Flask application with all routes and business logic
├── utils.py             # Database layer with optimized queries and helpers
├── templates/           # 29 HTML templates for all user journeys
├── static/              # CSS styles and FLYTAU branding assets
├── requirements.txt     # Python dependencies
└── sessions/            # Session storage directory

Misc/
└── FLYTAU.sql          # Complete database schema and seed data
```

---

## ✅ Full Compliance with Project Requirements

This system fully implements all requirements from the academic brief (`הנחיות פרויקט - בסיסי נתונים ומערכות מידע.pdf`):

✓ User authentication and registration  
✓ Flight search and booking with seat selection  
✓ Order management and cancellation policies  
✓ Manager restrictions (no ticket purchases)  
✓ Complete flight administration workflow  
✓ Comprehensive management reports  
✓ Required seed data and branding  

---

## 🎨 Design Philosophy

FLYTAU was built with **user experience first**. Every feature is designed to be:
- **Intuitive** — No training required, just start using it
- **Fast** — Optimized queries and efficient workflows
- **Secure** — Role-based access and data protection built-in
- **Scalable** — Clean architecture ready for growth

---

**Ready to transform your flight operations?** Get started in minutes and experience the difference a well-designed system makes.
