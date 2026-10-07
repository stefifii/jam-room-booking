// Get all the time-slot buttons
const timeSlots = document.querySelectorAll(".time-slot");

// Add a click event to every time slot
timeSlots.forEach(function(slot) {

    slot.addEventListener("click", function() {

        // Remove "selected" from all slots
        timeSlots.forEach(function(otherSlot) {
            otherSlot.classList.remove("selected");
        });

        // Add "selected" to the slot we clicked
        slot.classList.add("selected");

        // Show the selected time in the console
        console.log("Selected time:", slot.textContent);
    });

});

// Get the booking summary time element
const summaryTime = document.getElementById("summary-time");

// Update summary when a time slot is selected
timeSlots.forEach(function(slot) {

    slot.addEventListener("click", function() {

        summaryTime.textContent = slot.textContent;

    });

});

// Get the date input and summary date element
const bookingDate = document.getElementById("booking-date");
const summaryDate = document.getElementById("summary-date");

// Update summary when a date is selected
// Get today's date
const today = new Date();

// Format today's date as YYYY-MM-DD
const todayFormatted = today.toISOString().split("T")[0];

// Prevent selecting dates in the past
bookingDate.min = todayFormatted;


// Check the selected date
bookingDate.addEventListener("change", function() {

    if (!bookingDate.value) {
        return;
    }

    const selectedDate = new Date(bookingDate.value);

    // Get the day of the week
    // 0 = Sunday, 1 = Monday, ..., 6 = Saturday
    const day = selectedDate.getDay();


    // Check if selected date is Sunday
    if (day === 0) {

        alert("Zote Jam Room is closed on Sundays. Please select another date.");

        bookingDate.value = "";
        summaryDate.textContent = "Select a date";

        return;
    }


    // Format the date nicely
    const formattedDate = selectedDate.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "long",
        year: "numeric"
    });


    // Show the date in the booking summary
    summaryDate.textContent = formattedDate;

});