# Zote Jam Room — Studio Booking System

A full-stack web application for booking music studio sessions online. **Zote Jam Room** allows customers to explore studio equipment, check slot availability, book sessions, make online test payments, view their booking details, and submit feedback. Administrators can manage bookings and review customer feedback through a dedicated dashboard.

## Live Demo

- **Website:** https://jam-room-booking-frontend.vercel.app/
- **Backend API:** https://jam-room-booking.onrender.com/
- **API Documentation:** https://jam-room-booking.onrender.com/docs
- **GitHub Repository:** [https://github.com/steffiii/jam-room-booking](https://github.com/stefifii/jam-room-booking.git)

> **Payment Notice:** Razorpay is currently configured in Test Mode. No real payments are processed.

## Features

### Customer Features

- Browse studio information, equipment, and location.
- Check date-wise availability of one-hour booking slots.
- Select an available time slot and enter customer details.
- View the session price of ₹400 per hour.
- Make test payments using Razorpay Checkout.
- Receive booking confirmation after successful payment.
- Look up booking details using their name and phone number.
- Submit ratings and feedback.

### Admin Features

- Secure administrator login.
- View booking statistics, including total, pending, confirmed, and upcoming bookings.
- Search bookings and filter them by status.
- View customer details, booking dates, time slots, member count, and payment status.
- Confirm or cancel bookings.
- Review customer feedback.

### Booking Rules

- **Operating days:** Monday to Saturday.
- **Operating hours:** 11:00 AM–12:00 AM (midnight).
- **Closed:** Sundays.
- **Studio rooms:** One.
- **Price:** ₹400 per one-hour session.
- **Availability:** Slots are checked before booking to help prevent double-booking.
- **Payment handling:** Unpaid or cancelled bookings should not permanently block a slot.

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| API | REST API |
| Database | MySQL |
| Database hosting | Aiven MySQL |
| Payment integration | Razorpay Test Mode |
| Frontend deployment | Vercel |
| Backend deployment | Render |
| Development tools | VS Code, MySQL Workbench, Git, GitHub |

## Project Structure

```text
jam-room-booking/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── index.html
│   ├── booking.html
│   ├── my-bookings.html
│   ├── equipment.html
│   ├── feedback.html
│   ├── location.html
│   ├── admin-login.html
│   ├── admin.html
│   ├── script.js
│   ├── admin.js
│   ├── admin.css
│   ├── feedback.js
│   ├── feedback.css
│   └── images/
└── README.md
```

*Note: This structure represents the main project files; additional assets or configuration files may also be present.*

## Local Setup

### Prerequisites

Install the following before running the project:

- Python 3.11 or another Python version supported by the backend dependencies.
- MySQL database access.
- Git.
- Visual Studio Code (recommended).

### 1. Clone the Repository

```bash
git clone https://github.com/steffiii/jam-room-booking.git
cd jam-room-booking
```

### 2. Set Up the Backend

Create a virtual environment from the project root:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install the backend dependencies:

```bash
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables

Create a private `.env` file in the project root and configure the values required by the backend.

The configuration may include:

```env
DB_HOST=your_database_host
DB_PORT=your_database_port
DB_USER=your_database_username
DB_PASSWORD=your_database_password
DB_NAME=your_database_name

RAZORPAY_KEY_ID=your_razorpay_test_key_id
RAZORPAY_KEY_SECRET=your_razorpay_test_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password
ADMIN_SESSION_SECRET=your_long_random_secret
ADMIN_COOKIE_SECURE=false
```

Replace the example values with your own credentials. Use the variable names expected by the backend configuration and set the appropriate cookie security option for your environment.

**Important:** Never commit your `.env` file, database password, Razorpay secrets, or administrator credentials to GitHub. Configure production secrets through the environment-variable settings of the hosting services.

### 4. Start the Backend

Open a terminal in the `backend` directory:

```bash
cd backend
```

Start FastAPI:

```bash
uvicorn main:app --reload
```

The local API will be available at:

- **API:** http://127.0.0.1:8000/
- **Interactive API documentation:** http://127.0.0.1:8000/docs

Keep the backend running while testing the frontend locally.

### 5. Run the Frontend

Open the `frontend` folder in Visual Studio Code and launch `index.html` using the Live Server extension, or serve the folder with another local static web server.

Configure the frontend API URL to point to the local backend during development:

```text
http://127.0.0.1:8000
```

For the deployed website, use the production backend URL:

```text
https://jam-room-booking.onrender.com
```

Make sure the frontend API URL and backend CORS configuration match the environment you are testing.

## Database Design

The application uses a MySQL relational database to manage booking and related records.

The database design includes entities for customers, rooms, bookings, time slots, payments, equipment, and feedback, with relationships and constraints used to maintain data integrity.

The project demonstrates practical DBMS concepts, including:

- Entity–Relationship (ER) modeling.
- Relational schema design.
- Database normalization.
- Primary and foreign keys.
- SQL queries and constraints.
- Booking availability validation.
- Transaction handling and prevention of conflicting reservations.

## Deployment

The application is deployed using the following services:

- **Frontend:** Vercel
- **Backend:** Render
- **Database:** Aiven MySQL
- **Payments:** Razorpay Test Mode

The frontend communicates with the FastAPI backend through HTTP API requests, and the backend interacts with the MySQL database to manage booking information.

## Future Improvements

- Enable live payments when the studio is ready to accept real transactions.
- Add automated booking confirmation and reminder notifications.
- Improve booking history, reporting, and analytics.
- Expand automated testing and error monitoring.
- Strengthen customer verification for private booking information.

## Author

Developed as a full-stack, database-driven studio booking project.

**Repository:** [https://github.com/steffiii/jam-room-booking](https://github.com/stefifii/jam-room-booking.git)
