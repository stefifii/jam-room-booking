
const API_URL = "http://127.0.0.1:8000";

const loginSection = document.getElementById("login-section");
const dashboardSection = document.getElementById("dashboard-section");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const logoutButton = document.getElementById("logout-button");
const refreshButton = document.getElementById("refresh-button");
const tableBody = document.getElementById("booking-table-body");
const searchInput = document.getElementById("search-input");
const statusFilter = document.getElementById("status-filter");
const dashboardMessage = document.getElementById("dashboard-message");
const emptyState = document.getElementById("empty-state");

let adminCredentials = sessionStorage.getItem("zoteAdminCredentials") || "";
let bookings = [];
let isLoading = false;

function makeAuthHeader() {
  return `Basic ${adminCredentials}`;
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Authorization": makeAuthHeader(),
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });

  if (response.status === 401) {
    logout();
    throw new Error("Your session is no longer authorized. Please sign in again.");
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "The request could not be completed.");
  }

  return data;
}

function showDashboard() {
  loginSection.classList.add("hidden");
  dashboardSection.classList.remove("hidden");
  logoutButton.classList.remove("hidden");
}

function showLogin() {
  loginSection.classList.remove("hidden");
  dashboardSection.classList.add("hidden");
  logoutButton.classList.add("hidden");
}

function logout() {
  adminCredentials = "";
  sessionStorage.removeItem("zoteAdminCredentials");
  bookings = [];
  showLogin();
  loginError.textContent = "";
  dashboardMessage.textContent = "";
  loginForm.reset();
}

function setMessage(message, type = "") {
  dashboardMessage.textContent = message;
  dashboardMessage.className = `message ${type}`.trim();
}

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]);
}

function formatDate(dateString) {
  if (!dateString) return "—";

  // Use midday to avoid timezone shifting the calendar date.
  const date = new Date(`${dateString}T12:00:00`);

  if (Number.isNaN(date.getTime())) return dateString;

  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  });
}

function formatMoney(amount) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0
  }).format(Number(amount || 0));
}

async function loadStats() {
  const stats = await apiRequest("/admin/stats");

  document.getElementById("total-bookings").textContent =
    stats.total_bookings;
  document.getElementById("pending-bookings").textContent =
    stats.pending_bookings;
  document.getElementById("confirmed-bookings").textContent =
    stats.confirmed_bookings;
  document.getElementById("upcoming-bookings").textContent =
    stats.upcoming_bookings;
}

async function loadBookings() {
  const result = await apiRequest("/admin/bookings");
  bookings = result.bookings || [];
  renderBookings();
}

function renderBookings() {
  const searchTerm = searchInput.value.trim().toLowerCase();
  const selectedStatus = statusFilter.value;

  const filteredBookings = bookings.filter(booking => {
    const matchesSearch = [
      booking.booking_id,
      booking.customer_name,
      booking.phone,
      booking.booking_date,
      booking.time_slot
    ].some(value => String(value ?? "").toLowerCase().includes(searchTerm));

    const matchesStatus =
      selectedStatus === "all" ||
      String(booking.status).toLowerCase() === selectedStatus;

    return matchesSearch && matchesStatus;
  });

  document.getElementById("booking-count").textContent =
    `${filteredBookings.length} booking${filteredBookings.length === 1 ? "" : "s"}`;

  emptyState.classList.toggle("hidden", filteredBookings.length !== 0);
  tableBody.innerHTML = "";

  for (const booking of filteredBookings) {
    const status = String(booking.status || "pending").toLowerCase();

    const actionButtons = status === "pending"
      ? `
        <button class="button button-primary" data-action="confirmed"
          data-id="${Number(booking.booking_id)}">Confirm</button>
        <button class="button button-danger" data-action="cancelled"
          data-id="${Number(booking.booking_id)}">Cancel</button>
      `
      : status === "confirmed"
      ? `
        <button class="button button-danger" data-action="cancelled"
          data-id="${Number(booking.booking_id)}">Cancel</button>
      `
      : `<span class="muted">No actions</span>`;

    const row = document.createElement("tr");

    row.innerHTML = `
      <td>
        <span class="booking-id">#${Number(booking.booking_id)}</span>
      </td>
      <td>
        <div class="customer-name">${escapeHTML(booking.customer_name)}</div>
        <div class="customer-phone">${escapeHTML(booking.phone)}</div>
      </td>
      <td>
        <div class="date-text">${escapeHTML(formatDate(booking.booking_date))}</div>
        <div class="time-text">${escapeHTML(booking.time_slot)}</div>
      </td>
      <td>${Number(booking.members)}</td>
      <td>${escapeHTML(formatMoney(booking.total_amount))}</td>
      <td>
        <span class="status status-${escapeHTML(status)}">
          ${escapeHTML(status)}
        </span>
      </td>
      <td><div class="actions">${actionButtons}</div></td>
    `;

    tableBody.appendChild(row);
  }
}

async function refreshDashboard() {
  if (isLoading) return;

  isLoading = true;
  refreshButton.disabled = true;
  refreshButton.textContent = "Loading...";
  setMessage("Refreshing dashboard...");

  try {
    await Promise.all([loadStats(), loadBookings()]);
    setMessage("Dashboard is up to date.", "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    isLoading = false;
    refreshButton.disabled = false;
    refreshButton.textContent = "↻ Refresh";
  }
}

loginForm.addEventListener("submit", async event => {
  event.preventDefault();
  loginError.textContent = "";

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  if (!username || !password) {
    loginError.textContent = "Enter your username and password.";
    return;
  }

  // Encode credentials for HTTP Basic authentication.
  adminCredentials = btoa(`${username}:${password}`);

  try {
    // Test credentials against a protected endpoint first.
    const stats = await apiRequest("/admin/stats");

    sessionStorage.setItem(
      "zoteAdminCredentials",
      adminCredentials
    );

    document.getElementById("total-bookings").textContent =
      stats.total_bookings;
    document.getElementById("pending-bookings").textContent =
      stats.pending_bookings;
    document.getElementById("confirmed-bookings").textContent =
      stats.confirmed_bookings;
    document.getElementById("upcoming-bookings").textContent =
      stats.upcoming_bookings;

    showDashboard();
    await loadBookings();
    setMessage("Signed in successfully.", "success");
  } catch (error) {
    adminCredentials = "";
    sessionStorage.removeItem("zoteAdminCredentials");
    showLogin();

    if (error.message.includes("no longer authorized")) {
      loginError.textContent = "Invalid username or password.";
    } else {
      loginError.textContent =
        "Could not connect to the server. Check that FastAPI is running.";
    }
  }
});

logoutButton.addEventListener("click", logout);
refreshButton.addEventListener("click", refreshDashboard);
searchInput.addEventListener("input", renderBookings);
statusFilter.addEventListener("change", renderBookings);

tableBody.addEventListener("click", async event => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;

  const bookingId = Number(button.dataset.id);
  const newStatus = button.dataset.action;

  if (!Number.isInteger(bookingId) || bookingId < 1) return;

  const actionText = newStatus === "confirmed" ? "confirm" : "cancel";

  if (!window.confirm(`Are you sure you want to ${actionText} booking #${bookingId}?`)) {
    return;
  }

  button.disabled = true;
  setMessage(`Updating booking #${bookingId}...`);

  try {
    await apiRequest(`/admin/bookings/${bookingId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus })
    });

    await Promise.all([loadStats(), loadBookings()]);
    setMessage(`Booking #${bookingId} is now ${newStatus}.`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    button.disabled = false;
  }
});

// Restore the dashboard for the current browser tab if still authorized.
async function restoreSession() {
  if (!adminCredentials) {
    showLogin();
    return;
  }

  try {
    await apiRequest("/admin/stats");
    showDashboard();
    await refreshDashboard();
  } catch {
    adminCredentials = "";
    sessionStorage.removeItem("zoteAdminCredentials");
    showLogin();
  }
}

restoreSession();
