const navbar = document.getElementById("navbar");
const langButton = document.getElementById("langBtn");
const langDropdown = document.getElementById("langDropdown");
const mobileToggle = document.getElementById("mobileToggle");
const navLinks = document.getElementById("navLinks");
const riskAcknowledgement = document.getElementById("riskAck");
const apkDownloadButton = document.getElementById("apkDownloadButton");
const macDownloadButton = document.getElementById("macDownloadButton");
const downloadRegistrationForm = document.getElementById("downloadRegistrationForm");
const downloadName = document.getElementById("downloadName");
const downloadEmail = document.getElementById("downloadEmail");
const downloadPrivacyConsent = document.getElementById("downloadPrivacyConsent");
const downloadRegistrationStatus = document.getElementById("downloadRegistrationStatus");
const downloadButtons = [apkDownloadButton, macDownloadButton].filter(Boolean);
let downloadIsPending = false;
let androidApplicationSubmitted = false;

function updateNavbar() {
    if (navbar) {
        navbar.classList.toggle("scrolled", window.scrollY > 12);
    }
}

updateNavbar();
window.addEventListener("scroll", updateNavbar, { passive: true });

function closeLanguageMenu() {
    if (!langButton || !langDropdown) return;
    langDropdown.classList.remove("open");
    langButton.setAttribute("aria-expanded", "false");
}

if (langButton && langDropdown) {
    langButton.addEventListener("click", (event) => {
        event.stopPropagation();
        const isOpen = langDropdown.classList.toggle("open");
        langButton.setAttribute("aria-expanded", String(isOpen));
    });

    langDropdown.addEventListener("click", closeLanguageMenu);
    document.addEventListener("click", closeLanguageMenu);
}

function closeMobileMenu() {
    if (!mobileToggle || !navLinks) return;
    navLinks.classList.remove("mobile-open");
    mobileToggle.classList.remove("active");
    mobileToggle.setAttribute("aria-expanded", "false");
    document.body.classList.remove("menu-open");
}

if (mobileToggle && navLinks) {
    mobileToggle.addEventListener("click", () => {
        const isOpen = navLinks.classList.toggle("mobile-open");
        mobileToggle.classList.toggle("active", isOpen);
        mobileToggle.setAttribute("aria-expanded", String(isOpen));
        document.body.classList.toggle("menu-open", isOpen);
    });
}

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        closeLanguageMenu();
        closeMobileMenu();
    }
});

document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", (event) => {
        const selector = link.getAttribute("href");
        if (!selector || selector === "#") return;
        const target = document.querySelector(selector);
        if (!target) return;

        event.preventDefault();
        // A navigation link may target progressive-disclosure content.
        let disclosure = target.closest("details");
        while (disclosure) {
            disclosure.open = true;
            disclosure = disclosure.parentElement?.closest("details");
        }
        target.scrollIntoView({
            behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
            block: "start",
        });
        closeMobileMenu();
    });
});

document.querySelectorAll(".faq-list details").forEach((details) => {
    details.addEventListener("toggle", () => {
        if (!details.open) return;
        document.querySelectorAll(".faq-list details").forEach((other) => {
            if (other !== details) other.open = false;
        });
    });
});

function translate(key, fallback) {
    return (window.SGH_I18N && window.SGH_I18N[key]) || fallback;
}

function registrationIsValid() {
    return Boolean(
        downloadRegistrationForm
        && downloadName
        && downloadEmail
        && downloadPrivacyConsent
        && downloadName.value.trim()
        && downloadName.validity.valid
        && downloadEmail.validity.valid
        && downloadPrivacyConsent.checked
    );
}

function setDownloadButtonState(button, enabled, label) {
    if (!button) return;

    button.classList.toggle("disabled", !enabled);
    button.setAttribute("aria-disabled", String(!enabled));
    if (button.tagName === "BUTTON") button.disabled = !enabled;
    button.tabIndex = enabled ? 0 : -1;
    const labelElement = button.querySelector("span");
    if (labelElement) labelElement.textContent = label;
}

function syncDownloadState() {
    const registered = registrationIsValid();
    const androidEnabled = registered && riskAcknowledgement?.checked && !downloadIsPending && !androidApplicationSubmitted;
    const macEnabled = registered && !downloadIsPending;

    setDownloadButtonState(
        apkDownloadButton,
        androidEnabled,
        androidApplicationSubmitted
            ? translate("download.android.submitted", "已收到申請，等待邀請")
            : translate("download.android.cta", "申請 Android 封閉測試")
    );
    setDownloadButtonState(
        macDownloadButton,
        macEnabled,
        macEnabled
            ? translate("download.mac.ctaReady", "登記並下載 macOS v2.6.0")
            : translate("download.mac.cta", "填寫資料後下載 macOS v2.6.0")
    );
}

function setRegistrationStatus(message, state = "idle") {
    if (!downloadRegistrationStatus) return;
    downloadRegistrationStatus.textContent = message;
    downloadRegistrationStatus.dataset.state = state;
}

function startFileDownload(button) {
    // Only macOS uses direct downloads. Android applications never navigate.
    if (button.dataset.platform !== "macos") return;
    window.location.assign(button.dataset.downloadHref);
}

async function handleDownload(event) {
    event.preventDefault();
    const button = event.currentTarget;
    const isAndroid = button.dataset.platform === "android";
    if (downloadIsPending || (isAndroid && androidApplicationSubmitted)) return;
    if (!isAndroid && button.dataset.platform !== "macos") return;

    if (!registrationIsValid()) {
        downloadRegistrationForm?.reportValidity();
        setRegistrationStatus(
            translate("download.registration.invalid", "請填妥姓名／暱稱、有效 Email，並勾選隱私權同意。"),
            "error"
        );
        return;
    }

    if (isAndroid && !riskAcknowledgement?.checked) {
        riskAcknowledgement?.focus();
        setRegistrationStatus(
            translate("download.registration.riskRequired", "請確認願意使用 Android 手機參加至少 14 天的封閉測試。"),
            "error"
        );
        return;
    }

    downloadIsPending = true;
    syncDownloadState();
    setRegistrationStatus(
        translate("download.registration.saving", "正在儲存資料…"),
        "pending"
    );

    try {
        const firestore = await window.SGH_FIRESTORE_READY;
        if (isAndroid) {
            await firestore.addDoc(firestore.collection(firestore.db, "sgh-voice-alpha-applications"), {
                name: downloadName.value.trim(),
                email: downloadEmail.value.trim().toLowerCase(),
                platform: "android",
                track: "alpha",
                status: "pending",
                locale: window.SGH_LANG || "zh",
                consentVersion: 1,
                privacyConsent: true,
                testingCommitment: true,
                createdAt: firestore.serverTimestamp()
            });
            androidApplicationSubmitted = true;
            setRegistrationStatus(
                translate("download.android.success", "已收到申請，等待安排邀請。這不代表已取得 Google Play 測試資格；目前尚未寄出郵件，也不會自動下載。"),
                "success"
            );
            return;
        }
        await firestore.addDoc(firestore.collection(firestore.db, "sgh-voice-downloads"), {
            name: downloadName.value.trim(),
            email: downloadEmail.value.trim().toLowerCase(),
            platform: button.dataset.platform,
            version: button.dataset.version,
            fileName: button.dataset.filename,
            locale: window.SGH_LANG || document.documentElement.lang || "unknown",
            consentVersion: 2,
            riskAcknowledged: button.dataset.platform === "android"
                ? Boolean(riskAcknowledgement?.checked)
                : false,
            createdAt: firestore.serverTimestamp()
        });

        setRegistrationStatus(
            translate("download.registration.success", "登記完成，下載即將開始。"),
            "success"
        );
        startFileDownload(button);
    } catch (error) {
        console.error("Unable to save registration:", error?.code || "unknown");
        setRegistrationStatus(
            translate("download.registration.error", "資料尚未儲存，未送出申請或開始下載。請稍後再試。"),
            "error"
        );
    } finally {
        downloadIsPending = false;
        syncDownloadState();
    }
}

if (downloadRegistrationForm) {
    downloadRegistrationForm.addEventListener("submit", (event) => event.preventDefault());
    downloadRegistrationForm.addEventListener("input", syncDownloadState);
    downloadRegistrationForm.addEventListener("change", syncDownloadState);
}

if (riskAcknowledgement) {
    riskAcknowledgement.addEventListener("change", syncDownloadState);
}

if (downloadButtons.length) {
    downloadButtons.forEach((button) => button.addEventListener("click", handleDownload));
    syncDownloadState();
}

window.addEventListener("sgh:languagechange", () => {
    syncDownloadState();
    if (androidApplicationSubmitted) {
        setRegistrationStatus(translate("download.android.success", "已收到申請，等待邀請。"), "success");
        return;
    }
    if (downloadRegistrationStatus?.dataset.state === "idle") {
        setRegistrationStatus(
            translate("download.registration.status", "填妥資料後，請選擇下方要下載的平台。")
        );
    }
});
