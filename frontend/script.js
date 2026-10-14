
const API_URL = "http://127.0.0.1:8000";

const bookingDate = document.getElementById("booking-date");

// This script is also linked on the homepage.
// Stop here if the booking form is not present.
if (bookingDate) {
    const summaryDate = document.getElementById("summary-date");
    const summaryTime = document.getElementById("summary-time");
    const timeSlots = [...document.querySelectorAll(".time-slot")];

    const nameInput = document.getElementById("name");
    const phoneInput = document.getElementById("phone");
    const bandInput = document.getElementById("band");
    const membersInput = document.getElementById("members");
    const confirmButton = document.querySelector(".confirm-button");
    const availabilityMessage =
        document.querySelector(".availability-message");

    let availabilityLoadedFor = null;
    let requestNumber = 0;
    let isLoadingAvailability = false;

    function getLocalDateString() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");

        return `${year}-${month}-${day}`;
    }

    function formatDate(dateString) {
        const [year, month, day] = dateString.split("-").map(Number);

        return new Date(year, month - 1, day).toLocaleDateString(
            "en-IN",
            {
                day: "numeric",
                month: "long",
                year: "numeric"
            }
        );
    }

    function isSunday(dateString) {
        const [year, month, day] = dateString.split("-").map(Number);
        return new Date(year, month - 1, day).getDay() === 0;
    }

    function resetSlots(message = "Select a date to check availability.") {
        timeSlots.forEach(slot => {
            slot.disabled = true;
            slot.classList.remove("selected");
            slot.dataset.available = "false";
            slot.setAttribute("aria-pressed", "false");
        });

        summaryTime.textContent = "Select a time";
        availabilityMessage.textContent = message;
        availabilityLoadedFor = null;
    }

    bookingDate.min = getLocalDateString();
    resetSlots();

    async function loadAvailability(dateString) {
        const currentRequest = ++requestNumber;

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

            // Ignore outdated responses if the date changed.
            if (currentRequest !== requestNumber) {
                return false;
            }

            if (result.closed) {
                availabilityMessage.textContent =
                    "The studio is closed on Sundays. Choose another date.";

                bookingDate.value = "";
                summaryDate.textContent = "Select a date";
                return false;
            }

            const availableSlots = new Map(
                result.slots.map(slot => [
                    slot.label.trim(),
                    slot.available === true
                ])
            );

            timeSlots.forEach(slot => {
                const available =
                    availableSlots.get(slot.textContent.trim()) === true;

                slot.disabled = !available;
                slot.dataset.available = String(available);
                slot.classList.remove("selected");
                slot.setAttribute("aria-pressed", "false");

                slot.title = available
                    ? "Select this time"
                    : "This time slot is unavailable";
            });

            availabilityLoadedFor = dateString;
            summaryDate.textContent = formatDate(dateString);

            const count = [...availableSlots.values()]
                .filter(Boolean).length;

            availabilityMessage.textContent = count
                ? `${count} time slot(s) available. Choose your preferred time.`
                : "Sorry, no time slots are available for this date.";

            return true;

        } catch (error) {
            if (currentRequest !== requestNumber) {
                return false;
            }

            console.error("Availability error:", error);

            resetSlots(
                "Could not load availability. Check that your FastAPI server is running."
            );

            return false;

        } finally {
            if (currentRequest === requestNumber) {
                isLoadingAvailability = false;
            }
        }
    }

    // DATE SELECTION
    bookingDate.addEventListener("change", async () => {
        const dateString = bookingDate.value;

        if (!dateString) {
            requestNumber++;
            isLoadingAvailability = false;
            summaryDate.textContent = "Select a date";
            resetSlots();
            return;
        }

        if (dateString < getLocalDateString()) {
            requestNumber++;
            bookingDate.value = "";
            summaryDate.textContent = "Select a date";
            resetSlots("Please select today or a future date.");
            alert("You cannot book a date in the past.");
            return;
        }

        if (isSunday(dateString)) {
            requestNumber++;
            bookingDate.value = "";
            summaryDate.textContent = "Select a date";
            resetSlots("The studio is closed on Sundays.");
            alert("Zote Jam Room is closed on Sundays.");
            return;
        }

        await loadAvailability(dateString);
    });

    // TIME SLOT SELECTION
    timeSlots.forEach(slot => {
        slot.setAttribute("aria-pressed", "false");

        slot.addEventListener("click", () => {
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

    // CONFIRM BOOKING
    confirmButton.addEventListener("click", async () => {
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

        const selectedSlot = document.querySelector(".time-slot.selected");

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

        const name = nameInput.value.trim();
        const phone = phoneInput.value.trim();
        const members = membersInput.value;

        if (!name) {
            alert("Please enter your full name.");
            nameInput.focus();
            return;
        }

        if (!/^[6-9]\d{9}$/.test(phone)) {
            alert("Please enter a valid 10-digit Indian mobile number.");
            phoneInput.focus();
            return;
        }

        if (!members) {
            alert("Please select the number of people.");
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

        try {
            confirmButton.disabled = true;
            confirmButton.textContent = "Checking availability...";

            // Check again in case another customer booked this slot.
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
                    "This slot is no longer available. Please select another."
                );
            }

            confirmButton.textContent = "Saving booking...";

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
                "Booking saved successfully!\n\n" +
                `Booking ID: ${result.booking_id}\n` +
                `Date: ${formatDate(dateString)}\n` +
                `Time: ${bookingData.time_slot}\n` +
                `Total: ₹${result.total_amount ?? 400}\n\n` +
                "Payment has not been processed."
            );

            // Refresh the available slots after booking.
            await loadAvailability(dateString);

        } catch (error) {
            console.error("Booking error:", error);
            alert(error.message || "Could not submit your booking.");

        } finally {
            confirmButton.disabled = false;
            confirmButton.textContent = "Confirm Booking →";
        }
    });
}
