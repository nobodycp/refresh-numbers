const TRANSLATIONS = {
    ar: {
        "page.title": "تحديث الأرقام",
        "app.title": "نظام تحديث الأرقام",
        "app.subtitle": "أدخل رقم الهاتف لتحديثه",
        "form.label": "رقم الهاتف",
        "form.hint": "يجب أن يكون الرقم 10 أرقام ويبدأ بـ 05",
        "form.submit": "تحديث",
        "form.submitting": "جارِ التنفيذ...",
        "footer.text": "© نظام تحديث الأرقام",
        "validation.length": "الرقم يجب أن يكون 10 أرقام",
        "validation.prefix": "الرقم يجب أن يبدأ بـ 05",
        "validation.digits": "الرقم يجب أن يحتوي على أرقام فقط",
        "validation.ok": "الرقم صالح",
        "msg.success": "تم تحديث الرقم بنجاح",
        "msg.wait": "يجب الانتظار قبل المحاولة مرة أخرى",
        "msg.notfound": "الرقم غير موجود في النظام",
        "msg.error": "حدث خطأ غير متوقع",
        "msg.network": "تعذر الاتصال بالخادم",
        "aria.lang": "تغيير اللغة",
        "aria.theme": "تبديل الوضع"
    },
    en: {
        "page.title": "Refresh Numbers",
        "app.title": "Phone Number Refresh",
        "app.subtitle": "Enter a phone number to refresh it",
        "form.label": "Phone Number",
        "form.hint": "Number must be 10 digits and start with 05",
        "form.submit": "Refresh",
        "form.submitting": "Processing...",
        "footer.text": "© Phone Number Refresh",
        "validation.length": "Number must be 10 digits",
        "validation.prefix": "Number must start with 05",
        "validation.digits": "Number must contain only digits",
        "validation.ok": "Looks good",
        "msg.success": "Number refreshed successfully",
        "msg.wait": "Please wait before trying again",
        "msg.notfound": "Number not found in the system",
        "msg.error": "An unexpected error occurred",
        "msg.network": "Failed to connect to the server",
        "aria.lang": "Change language",
        "aria.theme": "Toggle theme"
    }
};

const STORAGE = {
    LANG: "rn_lang",
    THEME: "rn_theme"
};

const html = document.documentElement;
const themeToggle = document.getElementById("theme-toggle");
const langToggle = document.getElementById("lang-toggle");
const langLabel = langToggle.querySelector("[data-lang-label]");
const form = document.getElementById("refresh-form");
const phoneInput = document.getElementById("phone");
const submitBtn = document.getElementById("submit-btn");
const submitLabel = submitBtn.querySelector(".btn-label");
const fieldHint = document.getElementById("field-hint");
const alertBox = document.getElementById("alert");

let currentLang = localStorage.getItem(STORAGE.LANG) || "ar";
let currentTheme = localStorage.getItem(STORAGE.THEME) || "light";

function t(key) {
    return (TRANSLATIONS[currentLang] && TRANSLATIONS[currentLang][key]) || key;
}

function applyLanguage(lang) {
    currentLang = lang;
    localStorage.setItem(STORAGE.LANG, lang);

    html.setAttribute("lang", lang);
    html.setAttribute("dir", lang === "ar" ? "rtl" : "ltr");

    document.querySelectorAll("[data-i18n]").forEach((el) => {
        const key = el.getAttribute("data-i18n");
        el.textContent = t(key);
    });

    document.title = t("page.title");
    langLabel.textContent = lang === "ar" ? "EN" : "ع";
    langToggle.setAttribute("aria-label", t("aria.lang"));
    themeToggle.setAttribute("aria-label", t("aria.theme"));

    validatePhone(phoneInput.value, false);
}

function applyTheme(theme) {
    currentTheme = theme;
    localStorage.setItem(STORAGE.THEME, theme);
    html.setAttribute("data-theme", theme);
}

function validatePhone(value, markInvalid = true) {
    const input = phoneInput;
    input.classList.remove("invalid", "valid");
    fieldHint.classList.remove("error");

    if (!value) {
        fieldHint.textContent = t("form.hint");
        return { ok: false, silent: true };
    }

    if (!/^\d+$/.test(value)) {
        fieldHint.textContent = t("validation.digits");
        fieldHint.classList.add("error");
        if (markInvalid) input.classList.add("invalid");
        return { ok: false };
    }

    if (!value.startsWith("05")) {
        fieldHint.textContent = t("validation.prefix");
        fieldHint.classList.add("error");
        if (markInvalid) input.classList.add("invalid");
        return { ok: false };
    }

    if (value.length !== 10) {
        fieldHint.textContent = t("validation.length");
        if (markInvalid) input.classList.add("invalid");
        return { ok: false };
    }

    fieldHint.textContent = t("validation.ok");
    input.classList.add("valid");
    return { ok: true };
}

function showAlert(text, type) {
    alertBox.textContent = text;
    alertBox.className = "alert";
    void alertBox.offsetWidth;
    alertBox.classList.add("visible", type);
}

function hideAlert() {
    alertBox.className = "alert";
    alertBox.textContent = "";
}

function setLoading(loading) {
    submitBtn.disabled = loading;
    submitBtn.classList.toggle("loading", loading);
    submitLabel.textContent = loading ? t("form.submitting") : t("form.submit");
}

const CODE_TO_TYPE = { 1: "success", 2: "warn", 0: "error", 4: "error" };
const CODE_TO_KEY = {
    1: "msg.success",
    2: "msg.wait",
    0: "msg.notfound",
    4: "msg.error"
};

async function submitRefresh(number) {
    setLoading(true);
    showAlert(t("form.submitting"), "info");

    try {
        const res = await fetch("/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone_number: number })
        });

        let data = {};
        try {
            data = await res.json();
        } catch (_) {}

        const code = typeof data.code === "number" ? data.code : 4;
        const type = CODE_TO_TYPE[code] || "error";
        const localized = t(CODE_TO_KEY[code] || "msg.error");
        showAlert(localized, type);
    } catch (_) {
        showAlert(t("msg.network"), "error");
    } finally {
        setLoading(false);
    }
}

phoneInput.addEventListener("input", () => {
    phoneInput.value = phoneInput.value.replace(/\D/g, "").slice(0, 10);
    validatePhone(phoneInput.value);
});

phoneInput.addEventListener("focus", () => hideAlert());

form.addEventListener("submit", (e) => {
    e.preventDefault();
    const number = phoneInput.value.trim();
    const result = validatePhone(number);
    if (!result.ok) {
        showAlert(fieldHint.textContent, "error");
        phoneInput.focus();
        return;
    }
    submitRefresh(number);
});

themeToggle.addEventListener("click", () => {
    applyTheme(currentTheme === "light" ? "dark" : "light");
});

langToggle.addEventListener("click", () => {
    applyLanguage(currentLang === "ar" ? "en" : "ar");
});

applyTheme(currentTheme);
applyLanguage(currentLang);
