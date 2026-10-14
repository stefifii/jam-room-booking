import secrets

from fastapi import Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import os
from datetime import date, datetime, time, timedelta

import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="Zote Jam Room API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------- DATABASE CONNECTION ----------------

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "zote_jam_room"),
    )


# ---------------- HOME ENDPOINT ----------------

@app.get("/")
def home():
    return {
        "message": "Welcome to Zote Jam Room API!",
        "status": "running",
    }


# ---------------- TIME SLOTS ----------------

TIME_SLOTS = {
    "11 AM – 12 PM": (time(11, 0), time(12, 0)),
    "12 PM – 1 PM": (time(12, 0), time(13, 0)),
    "1 PM – 2 PM": (time(13, 0), time(14, 0)),
    "2 PM – 3 PM": (time(14, 0), time(15, 0)),
    "3 PM – 4 PM": (time(15, 0), time(16, 0)),
    "4 PM – 5 PM": (time(16, 0), time(17, 0)),
    "5 PM – 6 PM": (time(17, 0), time(18, 0)),
    "6 PM – 7 PM": (time(18, 0), time(19, 0)),
    "7 PM – 8 PM": (time(19, 0), time(20, 0)),
    "8 PM – 9 PM": (time(20, 0), time(21, 0)),
    "9 PM – 10 PM": (time(21, 0), time(22, 0)),
    "10 PM – 11 PM": (time(22, 0), time(23, 0)),
    "11 PM – 12 AM": (time(23, 0), time(0, 0)),
}


def normalize_mysql_time(value):
    """Convert MySQL TIME values to Python time objects."""
    if isinstance(value, timedelta):
        return (datetime.min + value).time()

    return value


def format_time_slot(start, end):
    """Match database times to the labels used by the website."""
    start = normalize_mysql_time(start)
    end = normalize_mysql_time(end)

    for label, times in TIME_SLOTS.items():
        if times == (start, end):
            return label

    return f"{start.strftime('%I %p')} – {end.strftime('%I %p')}"


# ---------------- BOOKING REQUEST MODEL ----------------

class BookingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    booking_date: date
    time_slot: str
    members: int = Field(ge=1, le=8)
    band: str = Field(default="", max_length=100)


# ---------------- AVAILABILITY ENDPOINT ----------------

@app.get("/availability")
def get_availability(booking_date: date):
    if booking_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Please select today or a future date.",
        )

    if booking_date.weekday() == 6:
        return {
            "booking_date": booking_date.isoformat(),
            "closed": True,
            "slots": [],
        }

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT Room_ID
            FROM ROOM
            WHERE Room_Name = %s
            LIMIT 1
            """,
            ("Zote Jam Room",),
        )
        room = cursor.fetchone()

        if room is None:
            raise HTTPException(
                status_code=500,
                detail="Studio room has not been configured.",
            )

        cursor.execute(
            """
            SELECT DISTINCT bs.Slot_ID
            FROM BOOKING b
            JOIN BOOKING_SLOT bs
                ON b.Booking_ID = bs.Booking_ID
            WHERE b.Room_ID = %s
              AND b.Booking_Date = %s
              AND b.Status <> 'cancelled'
            """,
            (room["Room_ID"], booking_date),
        )

        booked_ids = {
            row["Slot_ID"] for row in cursor.fetchall()
        }

        cursor.execute(
            """
            SELECT Slot_ID, Start_Time, End_Time
            FROM SLOT
            """
        )
        database_slots = cursor.fetchall()

        slots = []

        for slot in database_slots:
            start = normalize_mysql_time(slot["Start_Time"])
            end = normalize_mysql_time(slot["End_Time"])

            slots.append({
                "slot_id": slot["Slot_ID"],
                "label": format_time_slot(start, end),
                "available": slot["Slot_ID"] not in booked_ids,
            })

        return {
            "booking_date": booking_date.isoformat(),
            "closed": False,
            "slots": slots,
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve availability from the database.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# ---------------- CREATE BOOKING ENDPOINT ----------------

@app.post("/bookings")
def create_booking(booking: BookingRequest):
    if booking.booking_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="You cannot book a date in the past.",
        )

    if booking.booking_date.weekday() == 6:
        raise HTTPException(
            status_code=400,
            detail="Zote Jam Room is closed on Sundays.",
        )

    if booking.time_slot not in TIME_SLOTS:
        raise HTTPException(
            status_code=400,
            detail="Please select a valid one-hour time slot.",
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        # Lock the room row to serialize booking attempts.
        cursor.execute(
            """
            SELECT Room_ID, Hourly_Rate, Capacity
            FROM ROOM
            WHERE Room_Name = %s
            LIMIT 1
            FOR UPDATE
            """,
            ("Zote Jam Room",),
        )
        room = cursor.fetchone()

        if room is None:
            raise HTTPException(
                status_code=500,
                detail="Studio room has not been configured.",
            )

        if booking.members > room["Capacity"]:
            raise HTTPException(
                status_code=400,
                detail="The number of people exceeds room capacity.",
            )

        start_time, end_time = TIME_SLOTS[booking.time_slot]

        cursor.execute(
            """
            SELECT Slot_ID
            FROM SLOT
            WHERE Start_Time = %s
              AND End_Time = %s
            LIMIT 1
            """,
            (start_time, end_time),
        )
        slot = cursor.fetchone()

        if slot is None:
            raise HTTPException(
                status_code=500,
                detail="The selected time slot is not configured.",
            )

        # Check the slot again inside the transaction.
        cursor.execute(
            """
            SELECT b.Booking_ID
            FROM BOOKING b
            JOIN BOOKING_SLOT bs
                ON bs.Booking_ID = b.Booking_ID
            WHERE b.Room_ID = %s
              AND b.Booking_Date = %s
              AND bs.Slot_ID = %s
              AND b.Status <> 'cancelled'
            LIMIT 1
            """,
            (
                room["Room_ID"],
                booking.booking_date,
                slot["Slot_ID"],
            ),
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="This time slot is already booked. Please choose another.",
            )

        # Find or create the customer using their phone number.
        cursor.execute(
            """
            SELECT Customer_ID
            FROM CUSTOMER
            WHERE Phone = %s
            LIMIT 1
            """,
            (booking.phone,),
        )
        customer = cursor.fetchone()

        if customer:
            customer_id = customer["Customer_ID"]

            cursor.execute(
                """
                UPDATE CUSTOMER
                SET Name = %s
                WHERE Customer_ID = %s
                """,
                (booking.name.strip(), customer_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO CUSTOMER (Name, Phone, Password)
                VALUES (%s, %s, NULL)
                """,
                (booking.name.strip(), booking.phone),
            )
            customer_id = cursor.lastrowid

        total_amount = room["Hourly_Rate"]

        cursor.execute(
    """
    INSERT INTO BOOKING
        (Booking_Date, Total_Amount, Status,
         Customer_ID, Room_ID, Members)
    VALUES (%s, %s, %s, %s, %s, %s)
    """,
    (
        booking_request.booking_date,
        hourly_rate,
        "pending",
        customer_id,
        room_id,
        booking_request.members,
    ),
)
        booking_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO BOOKING_SLOT (Booking_ID, Slot_ID)
            VALUES (%s, %s)
            """,
            (booking_id, slot["Slot_ID"]),
        )

        connection.commit()

        return {
            "message": "Booking saved successfully!",
            "booking_id": booking_id,
            "customer_id": customer_id,
            "booking_date": booking.booking_date.isoformat(),
            "time_slot": booking.time_slot,
            "total_amount": float(total_amount),
            "status": "pending",
        }

    except HTTPException:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error. Please try again.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

from typing import Literal

from pydantic import BaseModel


admin_security = HTTPBasic()


def verify_admin(
    credentials: HTTPBasicCredentials = Depends(admin_security),
):
    expected_username = os.getenv("ADMIN_USERNAME", "")
    expected_password = os.getenv("ADMIN_PASSWORD", "")

    username_ok = secrets.compare_digest(
        credentials.username,
        expected_username,
    )
    password_ok = secrets.compare_digest(
        credentials.password,
        expected_password,
    )

    if (
        not expected_username
        or not expected_password
        or not username_ok
        or not password_ok
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return True


class AdminStatusUpdate(BaseModel):
    status: Literal["confirmed", "cancelled"]


@app.get("/admin/stats")
def admin_stats(_: bool = Depends(verify_admin)):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_bookings,
                COALESCE(SUM(Status = 'pending'), 0)
                    AS pending_bookings,
                COALESCE(SUM(Status = 'confirmed'), 0)
                    AS confirmed_bookings,
                COALESCE(SUM(
                    Status IN ('pending', 'confirmed')
                    AND Booking_Date >= CURDATE()
                ), 0) AS upcoming_bookings
            FROM BOOKING
            """
        )

        result = cursor.fetchone()

        return {
            key: int(value or 0)
            for key, value in result.items()
        }

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve dashboard statistics.",
        )

    finally:
        cursor.close()
        connection.close()


@app.get("/admin/bookings")
def admin_bookings(_: bool = Depends(verify_admin)):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                b.Booking_ID AS booking_id,
                c.Name AS customer_name,
                c.Phone AS phone,
                b.Booking_Date AS booking_date,
                b.Total_Amount AS total_amount,
                b.Status AS status,
                b.Created_At AS created_at,
                b.Members AS members,
                s.Start_Time AS start_time,
                s.End_Time AS end_time
            FROM BOOKING b
            JOIN CUSTOMER c
                ON b.Customer_ID = c.Customer_ID
            LEFT JOIN BOOKING_SLOT bs
                ON b.Booking_ID = bs.Booking_ID
            LEFT JOIN SLOT s
                ON bs.Slot_ID = s.Slot_ID
            ORDER BY
                b.Booking_Date DESC,
                s.Start_Time DESC,
                b.Booking_ID DESC
            """
        )

        rows = cursor.fetchall()
        bookings = []

        for row in rows:
            booking_date = row["booking_date"]
            start_time = row["start_time"]
            end_time = row["end_time"]

            bookings.append({
                "booking_id": row["booking_id"],
                "customer_name": row["customer_name"],
                "phone": row["phone"],
                "booking_date": (
                    booking_date.isoformat()
                    if booking_date else None
                ),
                "time_slot": (
                    format_time_slot(start_time, end_time)
                    if start_time is not None
                    and end_time is not None
                    else "Slot unavailable"
                ),
                "members": row["members"],
                "total_amount": float(row["total_amount"] or 0),
                "status": row["status"],
                "created_at": (
                    row["created_at"].isoformat()
                    if row["created_at"] else None
                ),
            })

        return {"bookings": bookings}

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve bookings.",
        )

    finally:
        cursor.close()
        connection.close()


@app.patch("/admin/bookings/{booking_id}/status")
def update_booking_status(
    booking_id: int,
    update: AdminStatusUpdate,
    _: bool = Depends(verify_admin),
):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        cursor.execute(
            """
            SELECT Status
            FROM BOOKING
            WHERE Booking_ID = %s
            FOR UPDATE
            """,
            (booking_id,),
        )

        booking = cursor.fetchone()

        if not booking:
            connection.rollback()
            raise HTTPException(
                status_code=404,
                detail="Booking not found.",
            )

        current_status = booking["Status"].lower()
        new_status = update.status

        if current_status == "cancelled":
            connection.rollback()
            raise HTTPException(
                status_code=409,
                detail="A cancelled booking cannot be reopened here.",
            )

        cursor.execute(
            """
            UPDATE BOOKING
            SET Status = %s
            WHERE Booking_ID = %s
            """,
            (new_status, booking_id),
        )

        connection.commit()

        return {
            "message": f"Booking {booking_id} updated.",
            "booking_id": booking_id,
            "status": new_status,
        }

    except HTTPException:
        connection.rollback()
        raise

    except mysql.connector.Error:
        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not update booking status.",
        )

    finally:
        cursor.close()
        connection.close()            
