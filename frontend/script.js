
 // ==========================================
// ZOTE JAM ROOM - BOOKING SYSTEM
// ==========================================

const API_URL = "http://127.0.0.1:8000";

// ---------- ELEMENTS ----------

const bookingDate = document.getElementById("booking-date");
const summaryDate = document.getElementById("summary-date");
const timeSlots = Array.from(document.querySelectorAll(".time-slot"));
const summaryTime = document.getElementById("summary-time");

const nameInput = document.getElementById("name");
const phoneInput = document.getElementById("phone");
const membersInput = document.getElementById("members");
const confirmButton = document.querySelector(".confirm-button");
const bandInput = document.getElementById("band");

// Message displayed above the time slots
const availabilityMessage = document.createElement("p");
availabilityMessage.className = "availability-message";
availabilityMessage.setAttribute("role", "status");
availabilityMessage.setAttribute("aria-live", "polite");

const slotsContainer = document.querySelector(".time-slots");

if (slotsContainer) {
    slotsContainer.parentNode.insertBefore(
        availabilityMessage,
        slotsContainer
    );
}

// ---------- DATE HELPERS ----------

// Use local calendar dates rather than UTC dates.
function getLocalDateString(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");

    return `${year}-${month}-${day}`;
}

function formatDate(dateString) {
    // Avoid timezone shifts when formatting a date-only value.
    const [year, month, day] = dateString.split("-").map(Number);

    return new Date(year, month - 1, day).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "long",
        year: "numeric"
    });
}

// ---------- STATE ----------

let availabilityLoadedFor = null;
let availabilityRequestNumber = 0;
let isLoadingAvailability = false;

// ---------- DATE SETUP ----------

bookingDate.min = getLocalDateString();

// Start with slots unavailable until a date is checked.
function resetSlots(message = "Select a date to check availability.") {
    timeSlots.forEach(slot => {
        slot.disabled = true;
        slot.classList.remove("selected");
        slot.removeAttribute("aria-pressed");
        slot.dataset.available = "false";
    });

    summaryTime.textContent = "Select a time";
    availabilityMessage.textContent = message;
    availabilityLoadedFor = null;
}

resetSlots();

// ---------- LOAD AVAILABILITY ----------

async function loadAvailability(dateString) {
    const requestNumber = ++availabilityRequestNumber;

    isLoadingAvailability = true;
    resetSlots("Checking available times...");

    try {
        const response = await fetch(
            `${API_URL}/availability?booking_date=${encodeURIComponent(dateString)}`
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.detail || "Could not check availability."
            );
        }

        // Ignore an old response if the user has picked another date.
        if (requestNumber !== availabilityRequestNumber) {
            return false;
        }

        if (result.closed) {
            availabilityMessage.textContent =
                "We're closed on Sundays. Please choose another date.";

            summaryDate.textContent = "Select a date";
            bookingDate.value = "";
            return false;
        }

        const availableByLabel = new Map(
            result.slots.map(slot => [
                slot.label.trim(),
                slot.available
            ])
        );

        timeSlots.forEach(slot => {
            const label = slot.textContent.trim();
            const available = availableByLabel.get(label) === true;

            slot.disabled = !available;
            slot.dataset.available = String(available);
            slot.classList.remove("selected");
            slot.setAttribute("aria-pressed", "false");

            if (!available) {
                slot.title = "This time slot is unavailable";
            } else {
                slot.title = "Select this time slot";
            }
        });

        availabilityLoadedFor = dateString;

        const availableCount = result.slots.filter(
            slot => slot.available
        ).length;

        if (availableCount === 0) {
            availabilityMessage.textContent =
                "Sorry, no time slots are available for this date.";
        } else {
            availabilityMessage.textContent =
                `${availableCount} time slot(s) available. Choose your preferred time.`;
        }

        summaryDate.textContent = formatDate(dateString);

        return true;

    } catch (error) {
        if (requestNumber !== availabilityRequestNumber) {
            return false;
        }

        console.error("Availability error:", error);

        resetSlots(
            "Couldn't load availability. Please check that the booking server is running and try again."
        );

        return false;

    } finally {
        if (requestNumber === availabilityRequestNumber) {
            isLoadingAvailability = false;
        }
    }
}

// ---------- DATE SELECTION ----------

bookingDate.addEventListener("change", async function () {
    const dateString = bookingDate.value;

    if (!dateString) {
        availabilityRequestNumber++;
        isLoadingAvailability = false;
        summaryDate.textContent = "Select a date";
        resetSlots();
        return;
    }

    // Parse as a local date to check the weekday correctly.
    const [year, month, day] = dateString.split("-").map(Number);
    const selectedDate = new Date(year, month - 1, day);

    if (selectedDate.getDay() === 0) {
        availabilityRequestNumber++;
        isLoadingAvailability = false;

        alert(
            "Zote Jam Room is closed on Sundays. Please select another date."
        );

        bookingDate.value = "";
        summaryDate.textContent = "Select a date";
        resetSlots("We're closed on Sundays.");
        return;
    }

    if (dateString < getLocalDateString()) {
        bookingDate.value = "";
        summaryDate.textContent = "Select a date";
        resetSlots("Please select today or a future date.");
        return;
    }

    await loadAvailability(dateString);
});

// ---------- TIME SLOT SELECTION ----------

timeSlots.forEach(slot => {
    slot.setAttribute("aria-pressed", "false");

    slot.addEventListener("click", function () {
        if (
            slot.disabled ||
            slot.dataset.available !== "true" ||
            availabilityLoadedFor !== bookingDate.value
        ) {
            return;
        }

        timeSlots.forEach(otherSlot => {
            otherSlot.classList.remove("selected");
            otherSlot.setAttribute("aria-pressed", "false");
        });

        slot.classList.add("selected");
        slot.setAttribute("aria-pressed", "true");

        summaryTime.textContent = slot.textContent.trim();
    });
});

// ---------- FORM SUBMISSION ----------

confirmButton.addEventListener("click", async function () {
    if (!bookingDate.value) {
        alert("Please select a date.");
        bookingDate.focus();
        return;
    }

    const dateString = bookingDate.value;

    const [year, month, day] = dateString.split("-").map(Number);
    const selectedDate = new Date(year, month - 1, day);

    if (selectedDate.getDay() === 0) {
        alert("Zote Jam Room is closed on Sundays.");
        return;
    }

    if (dateString < getLocalDateString()) {
        alert("You cannot book a date in the past.");
        return;
    }

    const selectedTime = document.querySelector(
        ".time-slot.selected"
    );

    if (!selectedTime) {
        alert("Please select an available time slot.");
        return;
    }

    if (
        selectedTime.disabled ||
        selectedTime.dataset.available !== "true" ||
        availabilityLoadedFor !== dateString ||
        isLoadingAvailability
    ) {
        alert("Please select a currently available time slot.");
        return;
    }

    const name = nameInput.value.trim();
    const phone = phoneInput.value.trim();

    if (!name) {
        alert("Please enter your full name.");
        nameInput.focus();
        return;
    }

    if (!/^[6-9]\d{9}$/.test(phone)) {
        alert("Please enter a valid 10-digit Indian phone number.");
        phoneInput.focus();
        return;
    }

    if (!membersInput.value) {
        alert("Please select the number of people.");
        membersInput.focus();
        return;
    }

    const bookingData = {
        name,
        phone,
        booking_date: dateString,
        time_slot: selectedTime.textContent.trim(),
        members: Number(membersInput.value),
        band: bandInput ? bandInput.value.trim() : ""
    };

    try {
        confirmButton.disabled = true;
        confirmButton.textContent = "Checking availability...";

        // Refresh availability before submitting.
        const availabilityResponse = await fetch(
            `${API_URL}/availability?booking_date=${encodeURIComponent(dateString)}`
        );

        const latestAvailability = await availabilityResponse.json();

        if (!availabilityResponse.ok) {
            throw new Error(
                latestAvailability.detail ||
                "Could not verify availability."
            );
        }

        if (latestAvailability.closed) {
            throw new Error("The studio is closed on this date.");
        }

        const latestSlot = latestAvailability.slots.find(
            slot => slot.label.trim() === bookingData.time_slot
        );

        if (!latestSlot || !latestSlot.available) {
            await loadAvailability(dateString);

            throw new Error(
                "Sorry, this time slot is no longer available. Please choose another."
            );
        }

        confirmButton.textContent = "Submitting booking...";

        const response = await fetch(`${API_URL}/bookings`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(bookingData)
        });

        const result = await response.json();

        if (!response.ok) {
            if (response.status === 409) {
                await loadAvailability(dateString);
            }

            throw new Error(
                typeof result.detail === "string"
                    ? result.detail
                    : "Could not submit your booking."
            );
        }

        alert(
            `Booking saved successfully!\n` +
            `Booking ID: ${result.booking_id}\n` +
            `Date: ${formatDate(dateString)}\n` +
            `Time: ${bookingData.time_slot}\n` +
            `Total: ₹${result.total_amount}\n\n` +
            `Your booking is pending. Payment has not been processed.`
        );

        // Refresh availability after a successful booking.
        await loadAvailability(dateString);

    } catch (error) {
        console.error("Booking error:", error);

        alert(error.message || "Could not submit your booking.");

    } finally {
        confirmButton.disabled = false;
        confirmButton.textContent = "Continue to Payment →";
    }
});
