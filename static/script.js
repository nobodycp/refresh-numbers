const form = document.getElementById("refresh-form");
const phoneInput = document.getElementById("phone");
const submitBtn = document.getElementById("submit-btn");
const messageEl = document.getElementById("message");

function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
}

function isValidNumber(value) {
    return /^05\d{8}$/.test(value);
}

phoneInput.addEventListener("input", () => {
    phoneInput.value = phoneInput.value.replace(/\D/g, "").slice(0, 10);
});

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const number = phoneInput.value.trim();

    if (!isValidNumber(number)) {
        showMessage("Number must be 10 digits and start with 05", "error");
        return;
    }

    submitBtn.disabled = true;
    showMessage("Processing request...", "info");

    try {
        const res = await fetch("/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone_number: number }),
        });

        const data = await res.json();

        switch (data.code) {
            case 1:
                showMessage(data.message || "Number refreshed successfully", "success");
                break;
            case 2:
                showMessage(data.message || "Please wait before trying again", "warn");
                break;
            case 0:
                showMessage(data.message || "Number not found in the system", "error");
                break;
            default:
                showMessage(data.message || "An unexpected error occurred", "error");
        }
    } catch (err) {
        showMessage("Failed to connect to the server", "error");
    } finally {
        submitBtn.disabled = false;
    }
});
