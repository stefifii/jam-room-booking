
import os
from datetime import date

import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="Zote Jam Room API")

# Allow requests from the local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# Connect to MySQL
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "zote_jam_room"),
    )


# Home endpoint
@app.get("/")
def home():
    return {
        "message": "Welcome to Zote Jam Room API!",
        "status": "running",
    }


# Booking request structure
class Booking(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    booking_date: date
    time_slot: str
    members: int = Field(ge=1, le=8)
    band: str = Field(default="", max_length=100)


# Save booking in MySQL
@app.post("/bookings")
def create_booking(booking: Booking):
    today = date.today()

    if booking.booking_date < today:
        raise HTTPException(
            status_code=400,
            detail="You cannot book a date in the past.",
        )

    if booking.booking_date.weekday() == 6:
        raise HTTPException(
            status_code=400,
            detail="Zote Jam Room is closed on Sundays.",
        )

    allowed_slots = {
        "11 AM – 12 PM",
        "12 PM – 1 PM",
        "1 PM – 2 PM",
        "2 PM – 3 PM",
        "3 PM – 4 PM",
        "4 PM – 5 PM",
        "5 PM – 6 PM",
        "6 PM – 7 PM",
        "7 PM – 8 PM",
        "8 PM – 9 PM",
        "9 PM – 10 PM",
        "10 PM – 11 PM",
        "11 PM – 12 AM",
    }

    if booking.time_slot not in allowed_slots:
        raise HTTPException(
            status_code=400,
            detail="Please select a valid one-hour time slot.",
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO bookings
                (name, phone, booking_date, time_slot, members, band)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        values = (
            booking.name.strip(),
            booking.phone,
            booking.booking_date,
            booking.time_slot,
            booking.members,
            booking.band.strip(),
        )

        cursor.execute(query, values)
        connection.commit()

        return {
            "message": "Booking details saved successfully!",
            "booking_id": cursor.lastrowid,
            "booking": booking.model_dump(mode="json"),
            "price": 400,
        }

    except mysql.connector.IntegrityError:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=409,
            detail="This time slot is already booked. Please choose another.",
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not save your booking. Please try again.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
