/* =====================================================================
   Phone Refresh Portal — i18n + theme + form logic
   ===================================================================== */

const TRANSLATIONS = {
    ar: {
        "page.title": "تحديث الهاتف - Pro Sim",
        "brand.title": "Pro Sim",
        "brand.tag": "بوابة تحديث الأرقام",
        "app.title": "تحديث رقم الهاتف",
        "app.subtitle": "أدخل الرقم وسنتولّى التحديث لك خلال ثوانٍ.",
        "form.label": "رقم الهاتف",
        "form.hint": "10 أرقام تبدأ بـ 05",
        "form.submit": "تحديث الآن",
        "form.submitting": "جارِ التنفيذ",
        "footer.text": "© بوابة تحديث الأرقام",
        "validation.length": "الرقم يجب أن يكون 10 أرقام",
        "validation.prefix": "الرقم يجب أن يبدأ بـ 05",
        "validation.digits": "الرقم يجب أن يحتوي على أرقام فقط",
        "validation.ok": "الرقم جاهز للإرسال",
        "msg.success": "تم تحديث الرقم بنجاح",
        "msg.wait": "الرقم محدَّث مؤخراً، حاول بعد قليل",
        "msg.notfound": "الرقم غير موجود في النظام",
        "msg.error": "حدث خطأ غير متوقع",
        "msg.network": "تعذّر الاتصال بالخادم",
        "msg.sending": "جاري الإرسال...",
        "aria.lang": "تغيير اللغة",
        "aria.theme": "تبديل الوضع"
    },
    en: {
        "page.title": "Phone Refresh - Pro Sim",
        "brand.title": "Pro Sim",
        "brand.tag": "Phone Refresh Portal",
        "app.title": "Refresh a phone number",
        "app.subtitle": "Enter the number and we'll handle the refresh in seconds.",
        "form.label": "Phone Number",
        "form.hint": "10 digits starting with 05",
        "form.submit": "Refresh now",
        "form.submitting": "Processing",
        "footer.text": "© Phone Refresh Portal",
        "validation.length": "Number must be 10 digits",
        "validation.prefix": "Number must start with 05",
        "validation.digits": "Numbers only",
        "validation.ok": "Looks good",
        "msg.success": "Number refreshed successfully",
        "msg.wait": "Recently refreshed — please wait a bit",
        "msg.notfound": "Number not found in the system",
        "msg.error": "An unexpected error occurred",
        "msg.network": "Failed to connect to the server",
        "msg.sending": "Sending request...",
        "aria.lang": "Change language",
        "aria.theme": "Toggle theme"
    }
};

const STORAGE = { LANG: "rn_lang", THEME: "rn_theme" };

const $ = (sel) => document.querySelector(sel);

const html = document.documentElement;
const langToggle = $("#lang-toggle");
const langLabel = langToggle.querySelector("[data-lang-label]");
const themeToggle = $("#theme-toggle");
const form = $("#refresh-form");
const inputWrap = $(".input-wrap");
const phoneInput = $("#phone");
const fieldHint = $("#field-hint");
const submitBtn = $("#submit-btn");
const submitLabel = submitBtn.querySelector(".cta-label");
const alertBox = $("#alert");
const alertIcon = alertBox.querySelector(".alert-icon");
const alertText = alertBox.querySelector(".alert-text");

const systemPrefersDark = window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;

let currentLang = localStorage.getItem(STORAGE.LANG) || "ar";
let currentTheme = localStorage.getItem(STORAGE.THEME) || (systemPrefersDark ? "dark" : "light");

function t(key) {
    return (TRANSLATIONS[currentLang] && TRANSLATIONS[currentLang][key]) || key;
}

/* ---------- i18n ---------- */

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
    langLabel.textContent = lang === "ar" ? "EN" : "عربي";
    langToggle.setAttribute("aria-label", t("aria.lang"));
    themeToggle.setAttribute("aria-label", t("aria.theme"));

    validatePhone(phoneInput.value, false);
}

/* ---------- Theme ---------- */

function applyTheme(theme) {
    currentTheme = theme;
    localStorage.setItem(STORAGE.THEME, theme);
    html.setAttribute("data-theme", theme);
}

/* ---------- Validation ---------- */

function validatePhone(value, markInvalid = true) {
    inputWrap.classList.remove("invalid", "valid");
    fieldHint.classList.remove("error", "ok");

    if (!value) {
        fieldHint.textContent = t("form.hint");
        return { ok: false, silent: true };
    }

    if (!/^\d+$/.test(value)) {
        fieldHint.textContent = t("validation.digits");
        fieldHint.classList.add("error");
        if (markInvalid) inputWrap.classList.add("invalid");
        return { ok: false };
    }

    if (!value.startsWith("05")) {
        fieldHint.textContent = t("validation.prefix");
        fieldHint.classList.add("error");
        if (markInvalid) inputWrap.classList.add("invalid");
        return { ok: false };
    }

    if (value.length !== 10) {
        fieldHint.textContent = t("validation.length");
        if (markInvalid) inputWrap.classList.add("invalid");
        return { ok: false };
    }

    fieldHint.textContent = t("validation.ok");
    fieldHint.classList.add("ok");
    inputWrap.classList.add("valid");
    return { ok: true };
}

/* ---------- Alert ---------- */

const ALERT_GLYPH = {
    success: "✓",
    error: "!",
    warn: "!",
    info: "…"
};

function showAlert(text, type) {
    alertText.textContent = text;
    alertIcon.textContent = ALERT_GLYPH[type] || "•";
    alertBox.className = "alert";
    void alertBox.offsetWidth;
    alertBox.classList.add("visible", type);
}

function hideAlert() {
    alertBox.className = "alert";
    alertText.textContent = "";
    alertIcon.textContent = "";
}

/* ---------- Loading ---------- */

function setLoading(loading) {
    submitBtn.disabled = loading;
    submitBtn.classList.toggle("loading", loading);
    submitLabel.textContent = loading ? t("form.submitting") : t("form.submit");
}

/* ---------- Submit ---------- */

const CODE_TO_TYPE = { 1: "success", 2: "warn", 0: "error", 4: "error" };
const CODE_TO_KEY = {
    1: "msg.success",
    2: "msg.wait",
    0: "msg.notfound",
    4: "msg.error"
};

async function submitRefresh(number) {
    setLoading(true);
    showAlert(t("msg.sending"), "info");

    try {
        const res = await fetch("/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone_number: number })
        });

        let data = {};
        try { data = await res.json(); } catch (_) {}

        const code = typeof data.code === "number" ? data.code : 4;
        const type = CODE_TO_TYPE[code] || "error";
        showAlert(t(CODE_TO_KEY[code] || "msg.error"), type);
    } catch (_) {
        showAlert(t("msg.network"), "error");
    } finally {
        setLoading(false);
    }
}

/* ---------- Events ---------- */

phoneInput.addEventListener("input", () => {
    phoneInput.value = phoneInput.value.replace(/\D/g, "").slice(0, 10);
    validatePhone(phoneInput.value);
});

phoneInput.addEventListener("focus", hideAlert);

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

/* ---------- Init ---------- */

applyTheme(currentTheme);
applyLanguage(currentLang);
