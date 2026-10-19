# Zote Jam Room — Studio Booking System

A full-stack web application for booking music studio sessions online. Zote Jam Room allows customers to check slot availability, reserve a session, and pay online, while administrators can manage bookings through a dedicated dashboard.

## Live Demo

- **Website:** https://jam-room-booking-frontend.vercel.app/
- **Backend API:** https://jam-room-booking.onrender.com/

> Payments currently use Razorpay Test Mode. No real payments are processed.

## Features

### Customer
- Browse studio information and equipment.
- Select a booking date and available one-hour time slot.
- View the session price of ₹400 per hour.
- Enter customer and group details.
- Complete a test payment through Razorpay.
- Receive booking confirmation after successful payment.
- Submit feedback.

### Admin
- Secure admin login.
- View booking statistics.
- Search bookings and filter by status.
- View customer, date, time, member count, booking status, and payment status.
- Confirm or cancel bookings.
- Review customer feedback.

### Booking Rules
- Open Monday to Saturday, 11:00 AM–12:00 AM.
- Closed on Sundays.
- One studio room.
- ₹400 per one-hour session.
- Availability is checked before booking to help prevent double-booking.
- Unpaid or cancelled bookings should release their slots.

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| Database | MySQL |
| Payment integration | Razorpay Test Mode |
| Frontend deployment | Vercel |
| Backend deployment | Render |
| Database hosting | Aiven MySQL |

## Project Structure

```text
jam-room-booking/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── README.md
└── frontend/
    ├── index.html
    ├── booking.html
    ├── equipment.html
    ├── feedback.html
    ├── location.html
    ├── admin-login.html
    ├── admin.html
    ├── script.js
    ├── admin.js
    ├── admin.css
    ├── feedback.js
    ├── feedback.css
    └── images/
```

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/steffiii/jam-room-booking.git
cd jam-room-booking
```

### 2. Set up the backend

Create and activate a Python virtual environment, then install the dependencies:

```bash
python -m venv .venv
```

On Windows:

```bash
.venv\Scripts\activate
```

Install the packages:

```bash
pip install -r backend/requirements.txt
```

Configure the required database, payment, and admin environment variables using your own credentials. Do not commit `.env` files or secrets to GitHub.

Start the API from the project root:

```bash
uvicorn main:app --reload
```

Run this command from the `backend` directory. The API documentation is available at `http://127.0.0.1:8000/docs`.

### 3. Run the frontend

Open the frontend using the VS Code Live Server extension, or serve the frontend directory with a local static web server. Configure the frontend API URL to point to the local backend during development.

## Database

The application uses MySQL to store booking and related records. The database design includes customers, rooms, time slots, bookings, payments, equipment, and feedback.

## Future Improvements

- Enable live payments when the studio is ready to accept real transactions.
- Add automated booking notifications.
- Improve booking history and reporting.
- Expand automated testing and monitoring.

## Author

Developed as a full-stack database-driven studio booking project.

**Repository:** [https://github.com/steffiii/jam-room-booking](https://github.com/stefifii/jam-room-booking.git)

