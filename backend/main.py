
import os
import hmac
import hashlib
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal

import mysql.connector
import razorpay
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv()

app = FastAPI(title="Zote Jam Room API")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

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


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "zote_jam_room"),
    )


def get_razorpay_client():
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Payment gateway is not configured.",
        )

    return razorpay.Client(
        auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
    )


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Welcome to Zote Jam Room API!",
        "status": "running",
    }


# --------------------------------------------------
# TIME SLOTS
# --------------------------------------------------

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
    if isinstance(value, timedelta):
        return (datetime.min + value).time()
    return value


def format_time_slot(start, end):
    start = normalize_mysql_time(start)
    end = normalize_mysql_time(end)

    for label, times in TIME_SLOTS.items():
        if times == (start, end):
            return label

    return f"{start.strftime('%I %p')} – {end.strftime('%I %p')}"


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class BookingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    booking_date: date
    time_slot: str
    members: int = Field(ge=1, le=8)
    band: str = Field(default="", max_length=100)


class PaymentVerification(BaseModel):
    booking_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentCancellation(BaseModel):
    booking_id: int
    razorpay_order_id: str


class AdminStatusUpdate(BaseModel):
    status: Literal["confirmed", "cancelled"]


# --------------------------------------------------
# AVAILABILITY
# --------------------------------------------------


@app.get("/availability")
def get_availability(booking_date: date):
    if booking_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Please select today or a future date.",
        )

    # Studio is closed on Sundays
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

        # Find the studio room
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

        if not room:
            raise HTTPException(
                status_code=500,
                detail="Studio room has not been configured.",
            )

        # Only confirmed bookings and active payment holds
        # should make a slot unavailable.
        # Cancelled bookings must not block slots.
        cursor.execute(
            """
            SELECT DISTINCT bs.Slot_ID
            FROM BOOKING b
            JOIN BOOKING_SLOT bs
                ON bs.Booking_ID = b.Booking_ID
            WHERE b.Room_ID = %s
              AND b.Booking_Date = %s
              AND (
                  b.Status = 'confirmed'
                  OR (
                      b.Status = 'pending_payment'
                      AND b.Payment_Expires_At IS NOT NULL
                      AND b.Payment_Expires_At > NOW()
                  )
              )
            """,
            (room["Room_ID"], booking_date),
        )

        booked_ids = {
            row["Slot_ID"] for row in cursor.fetchall()
        }

        # Retrieve all available time slots
        cursor.execute(
            """
            SELECT Slot_ID, Start_Time, End_Time
            FROM SLOT
            ORDER BY Start_Time
            """
        )

        database_slots = cursor.fetchall()

        slots = []

        for slot in database_slots:
            start = normalize_mysql_time(slot["Start_Time"])
            end = normalize_mysql_time(slot["End_Time"])

            slots.append(
                {
                    "slot_id": slot["Slot_ID"],
                    "label": format_time_slot(start, end),
                    "available": slot["Slot_ID"] not in booked_ids,
                }
            )

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
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()



# --------------------------------------------------
# CREATE RAZORPAY ORDER AND TEMPORARY BOOKING
# --------------------------------------------------

@app.post("/payments/create-order")
def create_payment_order(booking: BookingRequest):
    if booking.booking_date < date.today():
        raise HTTPException(400, "You cannot book a date in the past.")

    if booking.booking_date.weekday() == 6:
        raise HTTPException(400, "Zote Jam Room is closed on Sundays.")

    if booking.time_slot not in TIME_SLOTS:
        raise HTTPException(400, "Please select a valid one-hour time slot.")

    client = get_razorpay_client()
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        # Serialize booking attempts for this room.
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

        if not room:
            raise HTTPException(500, "Studio room has not been configured.")

        if booking.members > room["Capacity"]:
            raise HTTPException(
                400,
                "The number of people exceeds room capacity.",
            )

        start_time, end_time = TIME_SLOTS[booking.time_slot]

        cursor.execute(
            """
            SELECT Slot_ID
            FROM SLOT
            WHERE Start_Time = %s AND End_Time = %s
            LIMIT 1
            """,
            (start_time, end_time),
        )
        slot = cursor.fetchone()

        if not slot:
            raise HTTPException(
                500,
                "The selected time slot is not configured.",
            )

        # Recheck availability while the room row is locked.
        cursor.execute(
            """
            SELECT b.Booking_ID
            FROM BOOKING b
            JOIN BOOKING_SLOT bs ON bs.Booking_ID = b.Booking_ID
            WHERE b.Room_ID = %s
              AND b.Booking_Date = %s
              AND bs.Slot_ID = %s
              AND (
                  b.Status NOT IN ('cancelled', 'pending_payment')
                  OR b.Payment_Expires_At IS NULL
                  OR b.Payment_Expires_At > NOW()
              )
            LIMIT 1
            """,
            (room["Room_ID"], booking.booking_date, slot["Slot_ID"]),
        )

        if cursor.fetchone():
            raise HTTPException(
                409,
                "This time slot is already booked. Please choose another.",
            )

        # Find or create the customer.
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

        amount = Decimal(str(room["Hourly_Rate"])).quantize(
            Decimal("0.01")
        )
        amount_paise = int(amount * 100)

        cursor.execute(
            """
            INSERT INTO BOOKING
                (Booking_Date, Total_Amount, Status, Customer_ID,
                 Room_ID, Members, Payment_Expires_At)
            VALUES (%s, %s, %s, %s, %s, %s,
                    DATE_ADD(NOW(), INTERVAL 15 MINUTE))
            """,
            (
                booking.booking_date,
                amount,
                "pending_payment",
                customer_id,
                room["Room_ID"],
                booking.members,
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

        # The amount is calculated on the server, not supplied by the browser.
        order = client.order.create(
            data={
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"booking-{booking_id}",
                "notes": {"booking_id": str(booking_id)},
            }
        )

        cursor.execute(
            """
            INSERT INTO PAYMENT
                (Booking_ID, Amount, Payment_Method, Payment_Status,
                 Razorpay_Order_ID)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (booking_id, amount, "Razorpay", "pending", order["id"]),
        )

        connection.commit()

        return {
            "booking_id": booking_id,
            "order_id": order["id"],
            "key_id": RAZORPAY_KEY_ID,
            "amount": amount_paise,
            "currency": "INR",
            "total_amount": float(amount),
            "booking_date": booking.booking_date.isoformat(),
            "time_slot": booking.time_slot,
            "customer_name": booking.name.strip(),
            "phone": booking.phone,
        }

    except HTTPException:
        if connection and connection.is_connected():
            connection.rollback()
        raise
    except Exception as exc:
        if connection and connection.is_connected():
            connection.rollback()
        print("Create payment order error:", repr(exc))
        raise HTTPException(
            status_code=502,
            detail="Could not create the payment order. Please try again.",
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# VERIFY PAYMENT SIGNATURE
# --------------------------------------------------

@app.post("/payments/verify")
def verify_payment(payment: PaymentVerification):
    if not RAZORPAY_KEY_SECRET:
        raise HTTPException(503, "Payment gateway is not configured.")

    message = (
        f"{payment.razorpay_order_id}|{payment.razorpay_payment_id}"
    ).encode("utf-8")

    expected_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        expected_signature,
        payment.razorpay_signature,
    ):
        raise HTTPException(400, "Payment signature verification failed.")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                b.Booking_ID,
                b.Status AS booking_status,
                b.Payment_Expires_At,
                p.Payment_Status,
                p.Razorpay_Order_ID
            FROM BOOKING b
            JOIN PAYMENT p ON p.Booking_ID = b.Booking_ID
            WHERE b.Booking_ID = %s
            FOR UPDATE
            """,
            (payment.booking_id,),
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(404, "Booking or payment record not found.")

        if row["Razorpay_Order_ID"] != payment.razorpay_order_id:
            raise HTTPException(400, "Payment order does not match this booking.")

        if (
            row["Payment_Status"] == "paid"
            and row["booking_status"] == "confirmed"
        ):
            connection.commit()
            return {
                "message": "Payment already verified.",
                "booking_id": payment.booking_id,
                "status": "confirmed",
            }

        if row["booking_status"] != "pending_payment":
            raise HTTPException(
                409,
                "This booking is no longer awaiting payment.",
            )

        # Confirm only if the temporary hold is still valid.
        cursor.execute(
            """
            SELECT Payment_Expires_At > NOW() AS hold_valid
            FROM BOOKING
            WHERE Booking_ID = %s
            """,
            (payment.booking_id,),
        )
        hold = cursor.fetchone()

        if not hold or not hold["hold_valid"]:
            raise HTTPException(
                409,
                "The payment hold has expired. Contact the studio before retrying.",
            )

        cursor.execute(
            """
            UPDATE PAYMENT
            SET Payment_Status = 'paid',
                Payment_Date = NOW(),
                Transaction_ID = %s
            WHERE Booking_ID = %s
              AND Razorpay_Order_ID = %s
            """,
            (
                payment.razorpay_payment_id,
                payment.booking_id,
                payment.razorpay_order_id,
            ),
        )

        if cursor.rowcount != 1:
            raise HTTPException(400, "Could not update payment record.")

        cursor.execute(
            """
            UPDATE BOOKING
            SET Status = 'confirmed',
                Payment_Expires_At = NULL
            WHERE Booking_ID = %s
              AND Status = 'pending_payment'
            """,
            (payment.booking_id,),
        )

        if cursor.rowcount != 1:
            raise HTTPException(409, "Could not confirm this booking.")

        connection.commit()

        return {
            "message": "Payment verified and booking confirmed.",
            "booking_id": payment.booking_id,
            "status": "confirmed",
        }

    except HTTPException:
        if connection and connection.is_connected():
            connection.rollback()
        raise
    except mysql.connector.Error:
        if connection and connection.is_connected():
            connection.rollback()
        raise HTTPException(
            500,
            "Could not verify payment in the database.",
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# CANCEL AN UNCOMPLETED CHECKOUT
# --------------------------------------------------

@app.post("/payments/cancel")
def cancel_payment_checkout(data: PaymentCancellation):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT b.Status, p.Payment_Status, p.Razorpay_Order_ID
            FROM BOOKING b
            JOIN PAYMENT p ON p.Booking_ID = b.Booking_ID
            WHERE b.Booking_ID = %s
            FOR UPDATE
            """,
            (data.booking_id,),
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(404, "Booking or payment record not found.")

        if row["Razorpay_Order_ID"] != data.razorpay_order_id:
            raise HTTPException(400, "Payment order does not match this booking.")

        if row["Payment_Status"] == "paid":
            raise HTTPException(
                409,
                "This payment is already recorded as paid.",
            )

        if row["Status"] == "pending_payment":
            cursor.execute(
                """
                UPDATE BOOKING
                SET Status = 'cancelled',
                    Payment_Expires_At = NULL
                WHERE Booking_ID = %s
                """,
                (data.booking_id,),
            )
            cursor.execute(
                """
                UPDATE PAYMENT
                SET Payment_Status = 'failed'
                WHERE Booking_ID = %s
                  AND Payment_Status <> 'paid'
                """,
                (data.booking_id,),
            )

        connection.commit()
        return {"message": "Checkout cancelled.", "booking_id": data.booking_id}

    except HTTPException:
        if connection and connection.is_connected():
            connection.rollback()
        raise
    except mysql.connector.Error:
        if connection and connection.is_connected():
            connection.rollback()
        raise HTTPException(500, "Could not cancel this checkout.")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# ADMIN AUTHENTICATION
# Keep this BEFORE all routes that use verify_admin.
# --------------------------------------------------

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


# --------------------------------------------------
# ADMIN STATISTICS
# --------------------------------------------------

@app.get("/admin/stats")
def admin_stats(_: bool = Depends(verify_admin)):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_bookings,
                COALESCE(SUM(
                    Status IN ('pending', 'pending_payment')
                ), 0) AS pending_bookings,
                COALESCE(SUM(Status = 'confirmed'), 0)
                    AS confirmed_bookings,
                COALESCE(SUM(
                    Status IN ('pending', 'confirmed', 'pending_payment')
                    AND Booking_Date >= CURDATE()
                ), 0) AS upcoming_bookings
            FROM BOOKING
            """
        )

        result = cursor.fetchone()
        return {key: int(value or 0) for key, value in result.items()}

    except mysql.connector.Error:
        raise HTTPException(
            500,
            "Could not retrieve dashboard statistics.",
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# ADMIN BOOKINGS LIST
# --------------------------------------------------

@app.get("/admin/bookings")
def admin_bookings(_: bool = Depends(verify_admin)):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

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
                s.End_Time AS end_time,
                p.Payment_Status AS payment_status,
                p.Transaction_ID AS transaction_id
            FROM BOOKING b
            JOIN CUSTOMER c ON b.Customer_ID = c.Customer_ID
            LEFT JOIN BOOKING_SLOT bs ON b.Booking_ID = bs.Booking_ID
            LEFT JOIN SLOT s ON bs.Slot_ID = s.Slot_ID
            LEFT JOIN PAYMENT p ON p.Booking_ID = b.Booking_ID
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
            created_at = row["created_at"]

            bookings.append({
                "booking_id": row["booking_id"],
                "customer_name": row["customer_name"],
                "phone": row["phone"],
                "booking_date": (
                    booking_date.isoformat() if booking_date else None
                ),
                "time_slot": (
                    format_time_slot(start_time, end_time)
                    if start_time is not None and end_time is not None
                    else "Slot unavailable"
                ),
                "members": row["members"],
                "total_amount": float(row["total_amount"] or 0),
                "status": row["status"],
                "payment_status": row["payment_status"],
                "transaction_id": row["transaction_id"],
                "created_at": created_at.isoformat() if created_at else None,
            })

        return {"bookings": bookings}

    except mysql.connector.Error:
        raise HTTPException(500, "Could not retrieve bookings.")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# ADMIN UPDATE BOOKING STATUS
# --------------------------------------------------

@app.patch("/admin/bookings/{booking_id}/status")
def update_booking_status(
    booking_id: int,
    update: AdminStatusUpdate,
    _: bool = Depends(verify_admin),
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                b.Status,
                p.Payment_Status
            FROM BOOKING b
            LEFT JOIN PAYMENT p ON p.Booking_ID = b.Booking_ID
            WHERE b.Booking_ID = %s
            FOR UPDATE
            """,
            (booking_id,),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(404, "Booking not found.")

        current_status = (booking["Status"] or "").lower()
        new_status = update.status

        if current_status == "cancelled":
            raise HTTPException(
                409,
                "A cancelled booking cannot be reopened here.",
            )

        # A booking must never be manually confirmed without payment.
        if new_status == "confirmed":
            if (
                current_status == "pending_payment"
                or booking["Payment_Status"] != "paid"
            ):
                raise HTTPException(
                    409,
                    "This booking cannot be confirmed until payment is verified.",
                )

        if new_status == "cancelled":
            cursor.execute(
                """
                UPDATE BOOKING
                SET Status = 'cancelled',
                    Payment_Expires_At = NULL
                WHERE Booking_ID = %s
                """,
                (booking_id,),
            )
        else:
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
        if connection and connection.is_connected():
            connection.rollback()
        raise
    except mysql.connector.Error:
        if connection and connection.is_connected():
            connection.rollback()
        raise HTTPException(500, "Could not update booking status.")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# CUSTOMER FEEDBACK
# --------------------------------------------------

class FeedbackRequest(BaseModel):
    booking_id: int = Field(gt=0)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)



@app.post("/feedback")
def submit_feedback(feedback: FeedbackRequest):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                b.booking_id,
                b.status,
                b.booking_date,
                p.Payment_Status AS payment_status
            FROM BOOKINGS b
            LEFT JOIN PAYMENT p
                ON p.Booking_ID = b.booking_id
            WHERE b.booking_id = %s
            FOR UPDATE
            """,
            (feedback.booking_id,),
        )

        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(404, "Booking not found.")

        if (
            booking["status"] != "confirmed"
            or booking["payment_status"] != "paid"
        ):
            raise HTTPException(
                400,
                "Feedback is only allowed for confirmed, paid bookings.",
            )

        if booking["booking_date"] >= date.today():
            raise HTTPException(
                400,
                "Feedback can only be submitted after the booking date.",
            )

        cursor.execute(
            """
            INSERT INTO FEEDBACK
                (Booking_ID, Rating, Comment, Feedback_Date)
            VALUES (%s, %s, %s, NOW())
            """,
            (
                feedback.booking_id,
                feedback.rating,
                feedback.comment.strip() if feedback.comment else None,
            ),
        )

        connection.commit()

        return {
            "message": "Thank you for your feedback!",
            "booking_id": feedback.booking_id,
        }

    except HTTPException:
        if connection and connection.is_connected():
            connection.rollback()
        raise

    except mysql.connector.IntegrityError as exc:
        if connection and connection.is_connected():
            connection.rollback()

        if getattr(exc, "errno", None) == 1062:
            raise HTTPException(
                409,
                "Feedback has already been submitted for this booking.",
            )

        raise HTTPException(500, "Could not save feedback.")

    except mysql.connector.Error:
        if connection and connection.is_connected():
            connection.rollback()
        raise HTTPException(500, "Could not save feedback.")

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()




@app.get("/admin/feedback")
def get_feedback(_: bool = Depends(verify_admin)):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                f.Feedback_ID AS feedback_id,
                f.Booking_ID AS booking_id,
                f.Rating AS rating,
                f.Comment AS comment,
                f.Feedback_Date AS feedback_date,
                b.name AS customer_name
            FROM FEEDBACK f
            JOIN BOOKINGS b
                ON b.booking_id = f.Booking_ID
            ORDER BY f.Feedback_Date DESC
            """
        )

        rows = cursor.fetchall()

        return {
            "feedback": [
                {
                    **row,
                    "feedback_date": (
                        row["feedback_date"].isoformat()
                        if row["feedback_date"]
                        else None
                    ),
                }
                for row in rows
            ]
        }

    except mysql.connector.Error:
        raise HTTPException(500, "Could not retrieve feedback.")

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

