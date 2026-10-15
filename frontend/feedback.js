
const API_URL = "http://127.0.0.1:8000";

const feedbackForm = document.getElementById("feedback-form");
const ratingInput = document.getElementById("rating");
const ratingLabel = document.getElementById("rating-label");
const starButtons = document.querySelectorAll(".star");
const message = document.getElementById("feedback-message");
const submitButton = document.getElementById("submit-button");

const ratingDescriptions = {
  1: "Poor",
  2: "Could be better",
  3: "Good",
  4: "Really good",
  5: "Amazing!"
};

let selectedRating = 0;

function selectRating(rating) {
  selectedRating = rating;
  ratingInput.value = String(rating);
  ratingLabel.textContent = ratingDescriptions[rating];

  starButtons.forEach(button => {
    const buttonRating = Number(button.dataset.rating);
    const isSelected = buttonRating <= rating;

    button.classList.toggle("active", isSelected);
    button.setAttribute("aria-pressed", String(buttonRating === rating));
  });
}

starButtons.forEach(button => {
  button.addEventListener("click", () => {
    selectRating(Number(button.dataset.rating));
  });
});

feedbackForm.addEventListener("submit", async event => {
  event.preventDefault();

  message.textContent = "";
  message.className = "";

  const bookingId = Number(
    document.getElementById("booking-id").value
  );

  const comment = document.getElementById("comment").value.trim();

  if (!Number.isInteger(bookingId) || bookingId < 1) {
    message.textContent = "Please enter a valid booking ID.";
    message.className = "error";
    return;
  }

  if (selectedRating < 1 || selectedRating > 5) {
    message.textContent = "Please select a star rating.";
    message.className = "error";
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = "Submitting...";

  try {
    const response = await fetch(`${API_URL}/feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        booking_id: bookingId,
        rating: selectedRating,
        comment
      })
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(
        data.detail || "Could not submit feedback. Please try again."
      );
    }

    message.textContent = data.message || "Thank you for your feedback!";
    message.className = "success";

    feedbackForm.reset();
    selectedRating = 0;
    ratingInput.value = "";
    ratingLabel.textContent = "Select a rating";

    starButtons.forEach(button => {
      button.classList.remove("active");
      button.setAttribute("aria-pressed", "false");
    });
  } catch (error) {
    message.textContent =
      error.message || "Could not connect to the server.";
    message.className = "error";
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Submit feedback →";
  }
});
