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