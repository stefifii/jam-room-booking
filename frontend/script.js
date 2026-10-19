console.log("ZOTE SCRIPT LOADED — VERSION CHECK 1");
const API_URL = "https://jam-room-booking.onrender.com";

function isSlotInPast(slotLabel, dateString) {
    const now = new Date();
    const today = [
        now.getFullYear(),
        String(now.getMonth() + 1).padStart(2, "0"),
        String(now.getDate()).padStart(2, "0")
    ].join("-");

    if (dateString !== today) return false;

    const match = slotLabel.match(
        /(\d{1,2})\s*(AM|PM)\s*[-–—]\s*(\d{1,2})\s*(AM|PM)/i
    );

    if (!match) return false;

    let endHour = parseInt(match[3], 10);
    const endPeriod = match[4].toUpperCase();

    if (endPeriod === "AM" && endHour === 12) {
        endHour = 0;
    } else if (endPeriod === "PM" && endHour !== 12) {
        endHour += 12;
    }

    const slotEnd = new Date(dateString + "T00:00:00");
    slotEnd.setHours(endHour, 0, 0, 0);

    return slotEnd <= now;
}

const bookingDate = document.getElementById("booking-date");

if (bookingDate) {
    const summaryDate = document.getElementById("summary-date");
    const summaryTime = document.getElementById("summary-time");

    const timeSlots = Array.from(
        document.querySelectorAll(".time-slot")
    );

    const nameInput = document.getElementById("name");
    const phoneInput = document.getElementById("phone");
    const bandInput = document.getElementById("band");
    const membersInput = document.getElementById("members");

    const confirmButton = document.querySelector(".confirm-button");
    const availabilityMessage = document.querySelector(
        ".availability-message"
    );

    let availabilityLoadedFor = null;
    let requestNumber = 0;
    let isLoadingAvailability = false;
    let bookingInProgress = false;

    // ----------------------------------------
    // DATE HELPERS
    // ----------------------------------------

    function getLocalDateString() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");

        return `${year}-${month}-${day}`;
    }

    function formatDate(dateString) {
        if (!dateString) return "";

        const parts = dateString.split("-");

        if (parts.length !== 3) return dateString;

        const date = new Date(
            Number(parts[0]),
            Number(parts[1]) - 1,
            Number(parts[2])
        );

        return date.toLocaleDateString("en-IN", {
            day: "numeric",
            month: "long",
            year: "numeric"
        });
    }

    function isSunday(dateString) {
        if (!dateString) return false;

        const [year, month, day] = dateString
            .split("-")
            .map(Number);

        return new Date(year, month - 1, day).getDay() === 0;
    }

    // ----------------------------------------
    // MESSAGE HELPERS
    // ----------------------------------------

    function showAvailabilityMessage(message) {
        if (availabilityMessage) {
            availabilityMessage.textContent = message;
        }
    }

    function clearSelectedSlot() {
        timeSlots.forEach(slot => {
            slot.classList.remove("selected");
        });

        if (summaryTime) {
            summaryTime.textContent = "Not selected";
        }
    }

    function resetSlots(message = "Select a date to see availability.") {
        timeSlots.forEach(slot => {
            slot.disabled = true;
            slot.classList.remove("selected");
            slot.dataset.available = "false";
        });

        availabilityLoadedFor = null;

        if (summaryTime) {
            summaryTime.textContent = "Not selected";
        }

        showAvailabilityMessage(message);
    }

    // ----------------------------------------
    // TIME SLOT HELPERS
    // ----------------------------------------

    function normalizeSlotLabel(label) {
    return String(label || "")
        .replace(/[–—−]/g, "-")
        .replace(/\s+/g, " ")
        .replace(/\s*-\s*/g, "-")
        .trim()
        .toUpperCase();
}

    function updateSlotSelection(selectedSlot) {
        timeSlots.forEach(slot => {
            slot.classList.remove("selected");
        });

        selectedSlot.classList.add("selected");

        if (summaryTime) {
            summaryTime.textContent =
                selectedSlot.textContent.trim();
        }
    }

    
const slotsContainer = document.querySelector(".time-slots");

if (slotsContainer) {
    slotsContainer.addEventListener("click", event => {
        const slot = event.target.closest(".time-slot");

        if (!slot || !slotsContainer.contains(slot)) {
            return;
        }

        if (
            slot.disabled ||
            slot.dataset.available !== "true" ||
            isLoadingAvailability
        ) {
            return;
        }

        if (
            !bookingDate.value ||
            availabilityLoadedFor !== bookingDate.value
        ) {
            alert("Please select a date and reload availability.");
            return;
        }

        updateSlotSelection(slot);
    });
}


    // ----------------------------------------
// LOAD AVAILABILITY FROM FASTAPI
// ----------------------------------------

async function loadAvailability(dateString) {
    const currentRequest = ++requestNumber;

    clearSelectedSlot();

    if (!dateString) {
        resetSlots();
        return;
    }

    // Prevent booking past dates.
    if (dateString < getLocalDateString()) {
        resetSlots("Past dates cannot be booked.");
        return;
    }

    // Studio is closed on Sundays.
    if (isSunday(dateString)) {
        resetSlots("The studio is closed on Sundays.");
        return;
    }

    isLoadingAvailability = true;
    availabilityLoadedFor = null;

    timeSlots.forEach(slot => {
        slot.disabled = true;
        slot.classList.remove("selected");
        slot.dataset.available = "false";
    });

    showAvailabilityMessage("Loading available time slots...");

    try {
        // Fetch availability from the backend.
        const response = await fetch(
            `${API_URL}/availability?booking_date=${encodeURIComponent(dateString)}`
        );

        const data = await response.json();

        // Ignore outdated requests if the user changes dates quickly.
        if (currentRequest !== requestNumber) {
            return;
        }

        if (!response.ok) {
            throw new Error(
                data.detail || "Could not load availability."
            );
        }


let availableCount = 0;

timeSlots.forEach(button => {
    const buttonLabel = normalizeSlotLabel(
        button.textContent
    );

    const matchingSlot = data.slots.find(slot => {
        return normalizeSlotLabel(slot.label) === buttonLabel;
    });

    const available = matchingSlot
        ? matchingSlot.available === true
        : false;

    const alreadyPassed = isSlotInPast(
        button.textContent.trim(),
        dateString
    );

    const canBook = available && !alreadyPassed;

    button.dataset.available = String(canBook);
    button.disabled = !canBook;

    if (canBook) {
        availableCount++;
    }
});


        availabilityLoadedFor = dateString;

        if (availableCount === 0) {
            showAvailabilityMessage(
                "No time slots are currently available."
            );
        } else {
            showAvailabilityMessage(
                `${availableCount} time slot(s) available.`
            );
        }

    } catch (error) {
        if (currentRequest !== requestNumber) {
            return;
        }

        console.error("Availability error:", error);

        resetSlots(
            "Could not load availability. Please refresh and try again."
        );

    } finally {
        if (currentRequest === requestNumber) {
            isLoadingAvailability = false;
        }
    }
}

    // ----------------------------------------
    // DATE INPUT
    // ----------------------------------------

    // Prevent selecting any date before today.
bookingDate.setAttribute("min", getLocalDateString());
bookingDate.value = bookingDate.value && bookingDate.value < getLocalDateString()
    ? getLocalDateString()
    : bookingDate.value;

    bookingDate.addEventListener("change", async () => {
        const selectedDate = bookingDate.value;

        if (summaryDate) {
            summaryDate.textContent = selectedDate
                ? formatDate(selectedDate)
                : "Not selected";
        }

        clearSelectedSlot();

        await loadAvailability(selectedDate);
    });

    // ----------------------------------------
    // RAZORPAY CHECKOUT
    // ----------------------------------------

    if (confirmButton) {
        confirmButton.addEventListener("click", async () => {
            if (bookingInProgress) {
                return;
            }

            // Validate date.
            if (!bookingDate.value) {
                alert("Please select a date.");
                bookingDate.focus();
                return;
            }

            const dateString = bookingDate.value;

            if (dateString < getLocalDateString()) {
                alert("You cannot book a date in the past.");
                return;
            }

            if (isSunday(dateString)) {
                alert("Zote Jam Room is closed on Sundays.");
                return;
            }

            // Validate selected slot.
            const selectedSlot = document.querySelector(
                ".time-slot.selected"
            );

            if (!selectedSlot) {
                alert("Please select an available time slot.");
                return;
            }

            if (
                selectedSlot.disabled ||
                selectedSlot.dataset.available !== "true" ||
                availabilityLoadedFor !== dateString ||
                isLoadingAvailability
            ) {
                alert("Please select a currently available time slot.");
                return;
            }

            // Validate customer details.
            const name = nameInput.value.trim();
            const phone = phoneInput.value.trim();
            const members = membersInput.value;

            if (!name) {
                alert("Please enter your full name.");
                nameInput.focus();
                return;
            }

            if (!/^[6-9]\d{9}$/.test(phone)) {
                alert(
                    "Please enter a valid 10-digit Indian mobile number."
                );
                phoneInput.focus();
                return;
            }

            if (
                !members ||
                Number(members) < 1 ||
                Number(members) > 8
            ) {
                alert("Please select between 1 and 8 members.");
                membersInput.focus();
                return;
            }

            const bookingData = {
                name: name,
                phone: phone,
                booking_date: dateString,
                time_slot: selectedSlot.textContent.trim(),
                members: Number(members),
                band: bandInput ? bandInput.value.trim() : ""
            };

            let orderCreated = null;
            let checkoutCompleted = false;

            bookingInProgress = true;
            confirmButton.disabled = true;

            try {
                // Recheck availability before creating the order.
                confirmButton.textContent = "Checking availability...";

                const availabilityResponse = await fetch(
                    `${API_URL}/availability?booking_date=${encodeURIComponent(dateString)}`
                );

                const latestAvailability =
                    await availabilityResponse.json();

                if (!availabilityResponse.ok) {
                    throw new Error(
                        latestAvailability.detail ||
                        "Could not verify availability."
                    );
                }

                const latestSlot = Array.isArray(
                    latestAvailability.slots
                )
                    ? latestAvailability.slots.find(slot => {
                        return (
                            normalizeSlotLabel(slot.label) ===
                            normalizeSlotLabel(bookingData.time_slot)
                        );
                    })
                    : null;

                if (
                    latestAvailability.closed ||
                    !latestSlot ||
                    latestSlot.available !== true
                ) {
                    await loadAvailability(dateString);

                    throw new Error(
                        "This slot is no longer available. Please choose another."
                    );
                }

                // Create Razorpay order and temporary booking hold.
                confirmButton.textContent = "Preparing checkout...";

                const orderResponse = await fetch(
                    `${API_URL}/payments/create-order`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify(bookingData)
                    }
                );

                const orderResult = await orderResponse.json();

                if (!orderResponse.ok) {
                    throw new Error(
                        orderResult.detail ||
                        "Could not create the payment order."
                    );
                }

                orderCreated = orderResult;

                if (typeof window.Razorpay !== "function") {
                    throw new Error(
                        "Razorpay Checkout did not load. Please refresh the page."
                    );
                }

                // Configure Razorpay Checkout.
                const checkoutOptions = {
                    key: orderResult.key_id,
                    amount: orderResult.amount,
                    currency: orderResult.currency,
                    name: "Zote Jam Room",
                    description: "One-hour jam room booking",
                    order_id: orderResult.order_id,

                    prefill: {
                        name: orderResult.name || name,
                        contact: orderResult.phone || phone
                    },

                    notes: {
                        booking_id: String(orderResult.booking_id),
                        booking_date: dateString,
                        time_slot: bookingData.time_slot
                    },

                    theme: {
                        color: "#c5a46d"
                    },

                    handler: async function (paymentResponse) {
                        checkoutCompleted = true;

                        try {
                            const verifyResponse = await fetch(
                                `${API_URL}/payments/verify`,
                                {
                                    method: "POST",
                                    headers: {
                                        "Content-Type": "application/json"
                                    },
                                    body: JSON.stringify({
                                        booking_id: orderResult.booking_id,
                                        razorpay_order_id:
                                            paymentResponse.razorpay_order_id,
                                        razorpay_payment_id:
                                            paymentResponse.razorpay_payment_id,
                                        razorpay_signature:
                                            paymentResponse.razorpay_signature
                                    })
                                }
                            );

                            const verifyResult =
                                await verifyResponse.json();

                            if (!verifyResponse.ok) {
                                throw new Error(
                                    verifyResult.detail ||
                                    "Payment verification failed."
                                );
                            }

                            alert(
                                "Payment successful and booking confirmed!\n\n" +
                                `Booking ID: ${orderResult.booking_id}\n` +
                                `Date: ${formatDate(dateString)}\n` +
                                `Time: ${bookingData.time_slot}\n` +
                                `Total paid: ₹${orderResult.total_amount}`
                            );

                            await loadAvailability(dateString);

                        } catch (error) {
                            console.error(
                                "Payment verification error:",
                                error
                            );

                            alert(
                                "Checkout returned a payment response, " +
                                "but your booking could not be confirmed yet.\n\n" +
                                "Do not pay again. Contact the studio with " +
                                `Booking ID ${orderResult.booking_id}.\n\n` +
                                error.message
                            );
                        }
                    },

                    // Called when the customer closes Checkout.
                    modal: {
                        ondismiss: async function () {
                            console.log(
                                "RAZORPAY CHECKOUT DISMISSED"
                            );

                            console.log(
                                "checkoutCompleted:",
                                checkoutCompleted
                            );

                            console.log(
                                "orderCreated:",
                                orderCreated
                            );

                            if (checkoutCompleted || !orderCreated) {
                                console.log(
                                    "Cancellation skipped by the if condition."
                                );
                                return;
                            }

                            try {
                                console.log(
                                    "Sending cancellation request..."
                                );

                                const cancelResponse = await fetch(
                                    `${API_URL}/payments/cancel`,
                                    {
                                        method: "POST",
                                        headers: {
                                            "Content-Type": "application/json"
                                        },
                                        body: JSON.stringify({
                                            booking_id:
                                                orderCreated.booking_id,
                                            razorpay_order_id:
                                                orderCreated.order_id
                                        })
                                    }
                                );

                                const cancelResult =
                                    await cancelResponse.json();

                                console.log(
                                    "Cancellation HTTP status:",
                                    cancelResponse.status
                                );

                                console.log(
                                    "Cancellation response:",
                                    cancelResult
                                );

                                if (!cancelResponse.ok) {
                                    throw new Error(
                                        cancelResult.detail ||
                                        "The server could not cancel this booking hold."
                                    );
                                }

                                await loadAvailability(dateString);

                            } catch (error) {
                                console.error(
                                    "Could not cancel checkout:",
                                    error
                                );

                                alert(
                                    "We could not confirm cancellation of " +
                                    "the temporary booking hold. Please " +
                                    "refresh availability and check the " +
                                    "booking status before trying again."
                                );
                            }
                        }
                    }
                };

                const checkout = new window.Razorpay(checkoutOptions);

                checkout.on("payment.failed", function (response) {
                    console.error(
                        "Razorpay payment failed:",
                        response.error
                    );

                    alert(
                        "Payment was not completed. If money appears " +
                        "to have been deducted, contact the studio " +
                        "before trying again."
                    );
                });

                checkout.open();

            } catch (error) {
                console.error("Booking/payment error:", error);

                alert(
                    error.message ||
                    "Could not start checkout. Please try again."
                );

                // If an order was created but Checkout could not open,
                // attempt to release the unpaid booking hold.
                if (orderCreated && !checkoutCompleted) {
                    try {
                        const cancelResponse = await fetch(
                            `${API_URL}/payments/cancel`,
                            {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json"
                                },
                                body: JSON.stringify({
                                    booking_id: orderCreated.booking_id,
                                    razorpay_order_id: orderCreated.order_id
                                })
                            }
                        );

                        if (!cancelResponse.ok) {
                            console.error(
                                "The server did not confirm cancellation."
                            );
                        }

                        await loadAvailability(dateString);

                    } catch (cancelError) {
                        console.error(
                            "Checkout cancellation error:",
                            cancelError
                        );
                    }
                }

            } finally {
                bookingInProgress = false;
                confirmButton.disabled = false;
                confirmButton.textContent = "Confirm Booking →";
            }
        });
    }

    // ----------------------------------------
    // INITIAL PAGE STATE
    // ----------------------------------------

    if (summaryDate && bookingDate.value) {
        summaryDate.textContent = formatDate(bookingDate.value);
    }

    if (bookingDate.value) {
        loadAvailability(bookingDate.value);
    } else {
        resetSlots("Please select a date to see available slots.");
    }
}
