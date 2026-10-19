import os
import hmac
import hashlib
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from pathlib import Path
from typing import Literal
import mysql.connector
import razorpay
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi.middleware.cors import CORSMiddleware
 
 
# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------
 
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)
 
app = FastAPI(title="Zote Jam Room API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
 
app.add_middleware(
    CORSMiddleware,
    
allow_origins=[
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "https://jam-room-booking-frontend-42lgyri88-steffanie.vercel.app",
],

    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
)
 
 

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "zote_jam_room"),
        ssl_disabled=False,
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
# TIME slotS
# --------------------------------------------------
 
TIME_slotS = {
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
 
    for label, times in TIME_slotS.items():
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
            FROM room
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
            FROM booking b
            JOIN booking_slot bs
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
            FROM slot
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
 
    except Exception as e:
     print("AVAILABILITY DATABASE ERROR:", repr(e), flush=True)
     raise HTTPException(
        status_code=500,
        detail="Could not retrieve availability from the database."
    )
 
    finally:
        if cursor:
            cursor.close()
 
        if connection and connection.is_connected():
            connection.close()
 
 
 
# --------------------------------------------------
# CREATE RAZORPAY ORDER AND TEMPORARY booking
# --------------------------------------------------
 
@app.post("/payments/create-order")
def create_payment_order(booking: BookingRequest):
    if booking.booking_date < date.today():
        raise HTTPException(400, "You cannot book a date in the past.")
 
    if booking.booking_date.weekday() == 6:
        raise HTTPException(400, "Zote Jam Room is closed on Sundays.")
 
    if booking.time_slot not in TIME_slotS:
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
            FROM room
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
 
        start_time, end_time = TIME_slotS[booking.time_slot]
 
        cursor.execute(
            """
            SELECT Slot_ID
            FROM slot
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
            FROM booking b
            JOIN booking_slot bs ON bs.Booking_ID = b.Booking_ID
            WHERE b.Room_ID = %s
              AND b.Booking_Date = %s
              AND bs.Slot_ID = %s
              AND (
                  b.Status = 'confirmed'
                  OR (
                      b.Status = 'pending_payment'
                      AND b.Payment_Expires_At IS NOT NULL
                      AND b.Payment_Expires_At > NOW()
                  )
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
            FROM customer
            WHERE Phone = %s
            LIMIT 1
            """,
            (booking.phone,),
        )
        customer = cursor.fetchone()
 
        if customer:
            customer_id = customer["Customer_ID"]
        else:
            cursor.execute(
                """
                INSERT INTO customer (Name, Phone, Password)
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
            INSERT INTO booking
                (Booking_Date, Total_Amount, Status, Customer_ID,
                 Customer_Name, Room_ID, Members, Payment_Expires_At)
            VALUES (%s, %s, %s, %s, %s, %s, %s,
                    DATE_ADD(NOW(), INTERVAL 15 MINUTE))
            """,
            (
                booking.booking_date,
                amount,
                "pending_payment",
                customer_id,
                booking.name.strip(),
                room["Room_ID"],
                booking.members,
            ),
        )
        booking_id = cursor.lastrowid
 
        cursor.execute(
            """
            INSERT INTO booking_slot (Booking_ID, Slot_ID)
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
            INSERT INTO payment
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
# payment RECONCILIATION HELPERS
# --------------------------------------------------
def _payment_matches_booking(payment_entity, booking_id, order_id, expected_amount_paise):
    """Validate gateway payment details against the server-side booking/order."""
    try:
        return (
            str(payment_entity.get("order_id") or "") == str(order_id)
            and int(payment_entity.get("amount", -1)) == int(expected_amount_paise)
            and str(payment_entity.get("currency") or "").upper() == "INR"
            and str(payment_entity.get("status") or "").lower() == "captured"
        )
    except (TypeError, ValueError):
        return False


def _record_captured_payment(booking_id, order_id, payment_id, amount_paise, currency):
    """Record a captured payment; only confirm if its slot is still safe to allocate.

    If the hold expired, the booking was cancelled, or the slot has since been taken,
    the payment is still recorded as paid but the booking is not confirmed. That case
    needs studio review/refund rather than silently double-booking the slot.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        # Read the room ID, then take the same room lock used during order creation.
        cursor.execute("SELECT Room_ID FROM booking WHERE Booking_ID = %s", (booking_id,))
        initial = cursor.fetchone()
        if not initial:
            raise HTTPException(404, "Booking not found for this payment.")

        cursor.execute(
            "SELECT Room_ID FROM room WHERE Room_ID = %s FOR UPDATE",
            (initial["Room_ID"],),
        )
        if not cursor.fetchone():
            raise HTTPException(500, "The room linked to this booking was not found.")

        cursor.execute(
            """
            SELECT b.Booking_ID, b.Room_ID, b.Booking_Date, b.Status AS booking_status,
                   b.Payment_Expires_At, b.Total_Amount, p.Payment_Status,
                   p.Razorpay_Order_ID, p.Transaction_ID
            FROM booking b
            JOIN payment p ON p.Booking_ID = b.Booking_ID
            WHERE b.Booking_ID = %s
            FOR UPDATE
            """,
            (booking_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Booking or payment record not found.")
        if str(row["Razorpay_Order_ID"] or "") != str(order_id):
            raise HTTPException(400, "Payment order does not match this booking.")
        expected_amount = int(Decimal(str(row["Total_Amount"])).quantize(Decimal("0.01")) * 100)
        if int(amount_paise) != expected_amount or str(currency).upper() != "INR":
            raise HTTPException(400, "Payment amount or currency does not match this booking.")

        # Repeated checkout callbacks/webhooks are safe and idempotent.
        if row["Payment_Status"] == "paid" and row["booking_status"] == "confirmed":
            connection.commit()
            return {"booking_id": booking_id, "status": "confirmed", "payment_status": "paid"}

        cursor.execute(
            """
            UPDATE payment
            SET Payment_Status = 'paid', Payment_Date = COALESCE(Payment_Date, NOW()),
                Transaction_ID = %s
            WHERE Booking_ID = %s AND Razorpay_Order_ID = %s
            """,
            (payment_id, booking_id, order_id),
        )

        can_confirm = row["booking_status"] == "pending_payment"
        if can_confirm:
            cursor.execute(
                "SELECT (Payment_Expires_At IS NOT NULL AND Payment_Expires_At > NOW()) AS hold_valid "
                "FROM booking WHERE Booking_ID = %s",
                (booking_id,),
            )
            hold = cursor.fetchone()
            can_confirm = bool(hold and hold["hold_valid"])

        if can_confirm:
            cursor.execute(
                """
                SELECT 1
                FROM booking b
                JOIN booking_slot bs ON bs.Booking_ID = b.Booking_ID
                JOIN booking_slot own_bs ON own_bs.Slot_ID = bs.Slot_ID
                WHERE own_bs.Booking_ID = %s
                  AND b.Booking_ID <> %s
                  AND b.Room_ID = %s
                  AND b.Booking_Date = %s
                  AND (
                    b.Status = 'confirmed'
                    OR (b.Status = 'pending_payment' AND b.Payment_Expires_At > NOW())
                  )
                LIMIT 1
                """,
                (booking_id, booking_id, row["Room_ID"], row["Booking_Date"]),
            )
            can_confirm = cursor.fetchone() is None

        if can_confirm:
            cursor.execute(
                "UPDATE booking SET Status = 'confirmed', Payment_Expires_At = NULL "
                "WHERE Booking_ID = %s AND Status = 'pending_payment'",
                (booking_id,),
            )
            if cursor.rowcount == 1:
                connection.commit()
                return {"booking_id": booking_id, "status": "confirmed", "payment_status": "paid"}

        # Never confirm a stale/cancelled/conflicting booking. Keep the captured
        # payment visible for manual contact/refund; release any remaining hold.
        if row["booking_status"] == "pending_payment":
            cursor.execute(
                "UPDATE booking SET Status = 'cancelled', Payment_Expires_At = NULL "
                "WHERE Booking_ID = %s AND Status = 'pending_payment'",
                (booking_id,),
            )
        connection.commit()
        return {
            "booking_id": booking_id,
            "status": "needs_review",
            "payment_status": "paid",
            "message": "Payment was captured, but the booking could not be safely confirmed. Contact the studio for resolution.",
        }
    except HTTPException:
        if connection and connection.is_connected():
            connection.rollback()
        raise
    except mysql.connector.Error as exc:
        if connection and connection.is_connected():
            connection.rollback()
        print("Record captured payment database error:", repr(exc))
        raise HTTPException(500, "Could not reconcile the captured payment.")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# VERIFY payment SIGNATURE AND GATEWAY STATUS
# --------------------------------------------------
@app.post("/payments/verify")
def verify_payment(payment: PaymentVerification):
    client = get_razorpay_client()
    message = f"{payment.razorpay_order_id}|{payment.razorpay_payment_id}".encode("utf-8")
    expected_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, payment.razorpay_signature):
        raise HTTPException(400, "Payment signature verification failed.")

    try:
        # A valid checkout signature alone is not enough: ask Razorpay for the
        # payment record and compare order, amount, currency, and captured status.
        gateway_payment = client.payment.fetch(payment.razorpay_payment_id)
    except Exception as exc:
        print("Razorpay payment fetch error:", repr(exc))
        raise HTTPException(502, "Could not confirm payment status with Razorpay. Please retry shortly.")

    if str(gateway_payment.get("order_id") or "") != payment.razorpay_order_id:
        raise HTTPException(400, "Razorpay payment belongs to a different order.")

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT Total_Amount FROM booking WHERE Booking_ID = %s",
            (payment.booking_id,),
        )
        booking_row = cursor.fetchone()
        if not booking_row:
            raise HTTPException(404, "Booking not found.")
        expected_amount_paise = int(Decimal(str(booking_row["Total_Amount"])).quantize(Decimal("0.01")) * 100)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    if not _payment_matches_booking(
        gateway_payment, payment.booking_id, payment.razorpay_order_id, expected_amount_paise
    ):
        status = str(gateway_payment.get("status") or "unknown")
        raise HTTPException(
            409,
            f"Razorpay has not confirmed a captured payment for this booking (gateway status: {status}).",
        )

    result = _record_captured_payment(
        payment.booking_id,
        payment.razorpay_order_id,
        payment.razorpay_payment_id,
        gateway_payment.get("amount"),
        gateway_payment.get("currency"),
    )
    if result["status"] == "needs_review":
        # Return a conflict so the frontend doesn't display a success/confirmed state.
        raise HTTPException(409, detail=result)
    return {"message": "Payment verified and booking confirmed.", **result}


# --------------------------------------------------
# RAZORPAY WEBHOOK (configure this URL in Razorpay dashboard)
# --------------------------------------------------
@app.post("/payments/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
):
    if not RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(503, "Razorpay webhook is not configured.")
    raw_body = await request.body()
    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    if not x_razorpay_signature or not hmac.compare_digest(expected, x_razorpay_signature):
        raise HTTPException(400, "Invalid Razorpay webhook signature.")

    import json
    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(400, "Invalid webhook payload.")

    # Process only captured payments. Other events do not prove that money was captured.
    if event.get("event") != "payment.captured":
        return {"received": True, "processed": False}
    entity = (event.get("payload") or {}).get("payment", {}).get("entity") or {}
    payment_id = entity.get("id")
    order_id = entity.get("order_id")
    if not payment_id or not order_id:
        raise HTTPException(400, "Webhook is missing payment/order identifiers.")

    try:
        client = get_razorpay_client()
        gateway_payment = client.payment.fetch(payment_id)
    except Exception as exc:
        print("Razorpay webhook payment fetch error:", repr(exc))
        raise HTTPException(502, "Could not reconcile webhook payment with Razorpay.")

    if str(gateway_payment.get("order_id") or "") != str(order_id):
        raise HTTPException(400, "Webhook payment/order mismatch.")

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT b.Booking_ID, b.Total_Amount FROM booking b "
            "JOIN payment p ON p.Booking_ID = b.Booking_ID "
            "WHERE p.Razorpay_Order_ID = %s LIMIT 1",
            (order_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "No booking matches this Razorpay order.")
        booking_id = row["Booking_ID"]
        expected_amount_paise = int(Decimal(str(row["Total_Amount"])).quantize(Decimal("0.01")) * 100)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    if not _payment_matches_booking(
        gateway_payment, booking_id, order_id, expected_amount_paise
    ):
        raise HTTPException(409, "Webhook payment is not a matching captured INR payment.")

    result = _record_captured_payment(
        booking_id, order_id, payment_id,
        gateway_payment.get("amount"), gateway_payment.get("currency"),
    )
    return {"received": True, "processed": True, **result}


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
            FROM booking b JOIN payment p ON p.Booking_ID = b.Booking_ID
            WHERE b.Booking_ID = %s FOR UPDATE
            """,
            (data.booking_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Booking or payment record not found.")
        if row["Razorpay_Order_ID"] != data.razorpay_order_id:
            raise HTTPException(400, "Payment order does not match this booking.")
        if row["Payment_Status"] == "paid":
            raise HTTPException(409, "This payment is already recorded as paid.")

        # This endpoint is called by the browser's checkout-dismiss handler. A
        # dismissal does not prove payment failed, so don't mark payment failed.
        # Release the slot hold; a delayed captured payment is handled by verify/webhook
        # and will be recorded as paid but flagged for manual resolution if stale.
        if row["Status"] == "pending_payment":
            cursor.execute(
                "UPDATE booking SET Status = 'cancelled', Payment_Expires_At = NULL "
                "WHERE Booking_ID = %s AND Status = 'pending_payment'",
                (data.booking_id,),
            )
        connection.commit()
        return {"message": "Checkout closed. Any delayed payment will be reconciled safely.", "booking_id": data.booking_id}
    except HTTPException:
        if connection and connection.is_connected():
            connection.rollback()
        raise
    except mysql.connector.Error as exc:
        if connection and connection.is_connected():
            connection.rollback()
        print("Cancel checkout database error:", repr(exc))
        raise HTTPException(500, "Could not close this checkout.")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# ADMIN AUTHENTICATION - COOKIE SESSION
# --------------------------------------------------

ADMIN_SESSION_COOKIE = "zote_admin_session"
ADMIN_SESSION_MAX_AGE = 30 * 60  # 30 minutes
ADMIN_ALLOWED_ORIGINS = {
    "http://127.0.0.1:5500",
    "http://localhost:5500",
}


class AdminLoginRequest(BaseModel):
    username: str
    password: str


def get_admin_serializer():
    secret = os.getenv("ADMIN_SESSION_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="Admin session security is not configured.",
        )
    return URLSafeTimedSerializer(secret, salt="zote-admin-session-v1")


def verify_admin(request: Request):
    # Validate Origin on requests that change admin data.
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        origin = request.headers.get("origin", "")
        if origin not in ADMIN_ALLOWED_ORIGINS:
            raise HTTPException(status_code=403, detail="Invalid request origin.")

    token = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Please sign in.")

    try:
        payload = get_admin_serializer().loads(token, max_age=ADMIN_SESSION_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session.")
    except HTTPException:
        raise

    expected_username = os.getenv("ADMIN_USERNAME", "")
    if not expected_username or payload.get("username") != expected_username:
        raise HTTPException(status_code=401, detail="Invalid session.")
    return True


@app.post("/admin/login")
def admin_login(data: AdminLoginRequest, request: Request, response: Response):
    origin = request.headers.get("origin", "")
    if origin not in ADMIN_ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Invalid request origin.")

    expected_username = os.getenv("ADMIN_USERNAME", "")
    expected_password = os.getenv("ADMIN_PASSWORD", "")
    if not expected_username or not expected_password:
        raise HTTPException(status_code=503, detail="Admin authentication is not configured.")

    username_ok = secrets.compare_digest(data.username, expected_username)
    password_ok = secrets.compare_digest(data.password, expected_password)
    if not (username_ok and password_ok):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = get_admin_serializer().dumps({"username": expected_username})
    secure_cookie = os.getenv("ADMIN_COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=token,
        max_age=ADMIN_SESSION_MAX_AGE,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/",
    )
    return {"message": "Signed in successfully."}


@app.post("/admin/logout")
def admin_logout(request: Request, response: Response):
    origin = request.headers.get("origin", "")
    if origin not in ADMIN_ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Invalid request origin.")

    response.delete_cookie(
        key=ADMIN_SESSION_COOKIE,
        httponly=True,
        secure=os.getenv("ADMIN_COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        path="/",
    )
    return {"message": "Signed out successfully."}


# --------------------------------------------------
# ADMIN bookingS LIST
# --------------------------------------------------
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

        cursor.execute("""
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
            FROM booking
        """)

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
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

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
                COALESCE(b.Customer_Name, c.Name) AS customer_name,
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
            FROM booking b
            JOIN customer c ON b.Customer_ID = c.Customer_ID
            LEFT JOIN booking_slot bs ON b.Booking_ID = bs.Booking_ID
            LEFT JOIN slot s ON bs.Slot_ID = s.Slot_ID
            LEFT JOIN payment p ON p.Booking_ID = b.Booking_ID
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
# ADMIN UPDATE booking STATUS
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
            FROM booking b
            LEFT JOIN payment p ON p.Booking_ID = b.Booking_ID
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
                UPDATE booking
                SET Status = 'cancelled',
                    Payment_Expires_At = NULL
                WHERE Booking_ID = %s
                """,
                (booking_id,),
            )
        else:
            cursor.execute(
                """
                UPDATE booking
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
# customer feedback
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
                b.Booking_ID AS booking_id,
                b.Status AS status,
                b.Booking_Date AS booking_date,
                p.Payment_Status AS payment_status
            FROM booking b
            LEFT JOIN payment p
                ON p.Booking_ID = b.Booking_ID
            WHERE b.Booking_ID = %s
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
            INSERT INTO feedback
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
                c.Name AS customer_name
            FROM feedback f
            JOIN booking b
                ON b.Booking_ID = f.Booking_ID
            JOIN customer c
                ON c.Customer_ID = b.Customer_ID
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
 
 


