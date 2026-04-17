/* =====================================================================
   Pro Sim — i18n, theme, validation, animated background
   ===================================================================== */

const TRANSLATIONS = {
    ar: {
        "page.title": "تحديث الهاتف - Pro Sim",
        "app.title": "مرحبا بك",
        "app.subtitle": "الرجاء ادخال رقم الهاتف لتحديث الرقم",
        "form.label": "رقم الهاتف",
        "form.submit": "تحديث",
        "form.submitting": "جارِ التنفيذ",
        "validation.length": "الرقم يجب أن يكون 10 أرقام",
        "validation.prefix": "الرقم يجب أن يبدأ بـ 05",
        "validation.digits": "أرقام فقط",
        "validation.ok": "جاهز للإرسال",
        "msg.success": "تم تحديث الرقم بنجاح",
        "msg.wait": "الرقم محدَّث مؤخراً، حاول بعد قليل",
        "msg.notfound": "الرقم الخاص بك غير تابع لوكالة Pro Sim",
        "msg.error": "حدث خطأ غير متوقع",
        "msg.network": "تعذّر الاتصال بالخادم",
        "msg.sending": "جاري الإرسال..."
    },
    en: {
        "page.title": "Phone Refresh - Pro Sim",
        "app.title": "Welcome",
        "app.subtitle": "Please enter the phone number to refresh it",
        "form.label": "Phone Number",
        "form.submit": "Refresh",
        "form.submitting": "Processing",
        "validation.length": "Number must be 10 digits",
        "validation.prefix": "Number must start with 05",
        "validation.digits": "Numbers only",
        "validation.ok": "Ready",
        "msg.success": "Number refreshed successfully",
        "msg.wait": "Recently refreshed, try again shortly",
        "msg.notfound": "Your number is not registered with Pro Sim agency",
        "msg.error": "An unexpected error occurred",
        "msg.network": "Failed to connect to the server",
        "msg.sending": "Sending request..."
    }
};

const STORAGE = { LANG: "rn_lang", THEME: "rn_theme" };

const $ = (s) => document.querySelector(s);

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
const alertText = alertBox.querySelector(".alert-text");
const footerText = $("#footer-text");

let currentLang = localStorage.getItem(STORAGE.LANG) || "ar";
let currentTheme = localStorage.getItem(STORAGE.THEME) || "dark";

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
        el.textContent = t(el.getAttribute("data-i18n"));
    });

    document.title = t("page.title");
    langLabel.textContent = lang === "ar" ? "EN" : "عربي";
    footerText.textContent = `pro sim ${new Date().getFullYear()}`;

    validatePhone(phoneInput.value, false);
}

/* ---------- Theme ---------- */

function applyTheme(theme) {
    currentTheme = theme;
    localStorage.setItem(STORAGE.THEME, theme);
    html.setAttribute("data-theme", theme);
    if (typeof refreshBgColor === "function") refreshBgColor();
}

/* ---------- Validation ---------- */

function validatePhone(value, markInvalid = true) {
    inputWrap.classList.remove("invalid", "valid");
    fieldHint.classList.remove("error", "ok");

    if (!value) {
        fieldHint.textContent = "";
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

function showAlert(text, type) {
    alertText.textContent = text;
    alertBox.className = "alert";
    void alertBox.offsetWidth;
    alertBox.classList.add("visible", type);
}

function hideAlert() {
    alertBox.className = "alert";
    alertText.textContent = "";
}

/* ---------- Loading ---------- */

function setLoading(loading) {
    submitBtn.disabled = loading;
    submitBtn.classList.toggle("loading", loading);
    submitLabel.textContent = loading ? t("form.submitting") : t("form.submit");
}

/* ---------- Submit ---------- */

const CODE_TO_TYPE = { 1: "success", 2: "warn", 0: "error", 4: "error" };
const CODE_TO_KEY  = { 1: "msg.success", 2: "msg.wait", 0: "msg.notfound", 4: "msg.error" };

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
        showAlert(fieldHint.textContent || t("validation.length"), "error");
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

/* =====================================================================
   Animated background (gentle drifting dots with connecting threads)
   ===================================================================== */

const canvas = document.getElementById("bg-canvas");
const ctx = canvas.getContext("2d");
let W = 0, H = 0, DPR = Math.min(window.devicePixelRatio || 1, 2);
let dots = [];
let dotColor = "rgba(15,23,42,0.22)";
let raf;

function refreshBgColor() {
    const c = getComputedStyle(document.documentElement).getPropertyValue("--dot").trim();
    if (c) dotColor = c;
}

function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W * DPR;
    canvas.height = H * DPR;
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    seedDots();
}

function seedDots() {
    const target = Math.max(36, Math.min(90, Math.floor((W * H) / 22000)));
    dots = new Array(target).fill(0).map(() => ({
        x: Math.random() * W,
        y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.25,
        vy: (Math.random() - 0.5) * 0.25,
        r: Math.random() * 1.4 + 0.4
    }));
}

function tick() {
    ctx.clearRect(0, 0, W, H);
    const linkDist = 130;
    const linkDist2 = linkDist * linkDist;

    for (let i = 0; i < dots.length; i++) {
        const d = dots[i];
        d.x += d.vx;
        d.y += d.vy;
        if (d.x < -20) d.x = W + 20;
        if (d.x > W + 20) d.x = -20;
        if (d.y < -20) d.y = H + 20;
        if (d.y > H + 20) d.y = -20;

        ctx.beginPath();
        ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
        ctx.fillStyle = dotColor;
        ctx.fill();
    }

    ctx.lineWidth = 1;
    for (let i = 0; i < dots.length; i++) {
        for (let j = i + 1; j < dots.length; j++) {
            const a = dots[i], b = dots[j];
            const dx = a.x - b.x, dy = a.y - b.y;
            const d2 = dx * dx + dy * dy;
            if (d2 < linkDist2) {
                const alpha = 1 - d2 / linkDist2;
                ctx.strokeStyle = dotColor.replace(/[\d.]+\)$/, (alpha * 0.5).toFixed(3) + ")");
                ctx.beginPath();
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
                ctx.stroke();
            }
        }
    }

    raf = requestAnimationFrame(tick);
}

window.addEventListener("resize", () => {
    cancelAnimationFrame(raf);
    resize();
    tick();
});

/* ---------- Init ---------- */

applyTheme(currentTheme);
applyLanguage(currentLang);
refreshBgColor();
resize();
tick();
