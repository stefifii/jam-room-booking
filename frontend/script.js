// ==========================================
// ZOTE JAM ROOM - BOOKING SYSTEM
// ==========================================


// ---------- ELEMENTS ----------

// Date
const bookingDate = document.getElementById("booking-date");
const summaryDate = document.getElementById("summary-date");

// Time slots
const timeSlots = document.querySelectorAll(".time-slot");
const summaryTime = document.getElementById("summary-time");

// Customer details
const nameInput = document.getElementById("name");
const phoneInput = document.getElementById("phone");
const membersInput = document.getElementById("members");

// Continue button
const confirmButton = document.querySelector(".confirm-button");


// ---------- DATE SETUP ----------

// Get today's date
const today = new Date();

// Format today's date as YYYY-MM-DD
const todayFormatted = today.toISOString().split("T")[0];

// Prevent selecting dates in the past
bookingDate.min = todayFormatted;


// ---------- DATE SELECTION ----------

bookingDate.addEventListener("change", function () {

    // Make sure a date was selected
    if (!bookingDate.value) {
        return;
    }

    const selectedDate = new Date(bookingDate.value);

    // 0 = Sunday
    // 1 = Monday
    // 2 = Tuesday
    // ...
    // 6 = Saturday
    const day = selectedDate.getDay();


    // Check if Sunday
    if (day === 0) {

        alert(
            "Zote Jam Room is closed on Sundays. Please select another date."
        );

        bookingDate.value = "";
        summaryDate.textContent = "Select a date";

        return;
    }


    // Format date nicely
    const formattedDate = selectedDate.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "long",
        year: "numeric"
    });


    // Update booking summary
    summaryDate.textContent = formattedDate;

});


// ---------- TIME SLOT SELECTION ----------

timeSlots.forEach(function (slot) {

    slot.addEventListener("click", function () {

        // Remove selected state from every slot
        timeSlots.forEach(function (otherSlot) {
            otherSlot.classList.remove("selected");
        });


        // Select the clicked slot
        slot.classList.add("selected");


        // Update booking summary
        summaryTime.textContent = slot.textContent.trim();


        // For debugging
        console.log(
            "Selected time:",
            slot.textContent.trim()
        );

    });

});


// ---------- FORM VALIDATION ----------

confirmButton.addEventListener("click", function () {

    // Check date
    if (!bookingDate.value) {

        alert("Please select a date.");

        bookingDate.focus();

        return;
    }


    // Check Sunday again
    const selectedDate = new Date(bookingDate.value);

    if (selectedDate.getDay() === 0) {

        alert(
            "Zote Jam Room is closed on Sundays. Please select another date."
        );

        return;
    }


    // Check time
    const selectedTime = document.querySelector(".time-slot.selected");

    if (!selectedTime) {

        alert("Please select a time slot.");

        return;
    }


    // Check name
    const name = nameInput.value.trim();

    if (!name) {

        alert("Please enter your full name.");

        nameInput.focus();

        return;
    }


    // Check phone
    const phone = phoneInput.value.trim();

    if (!phone) {

        alert("Please enter your phone number.");

        phoneInput.focus();

        return;
    }


    // Check if phone contains exactly 10 digits
    const phonePattern = /^[6-9]\d{9}$/;

    if (!phonePattern.test(phone)) {

        alert(
            "Please enter a valid 10-digit Indian phone number."
        );

        phoneInput.focus();

        return;
    }


    // Check number of people
    if (!membersInput.value) {

        alert("Please select the number of people.");

        membersInput.focus();

        return;
    }


    // Everything is valid
    alert("Your booking details are complete! 🎸");

});