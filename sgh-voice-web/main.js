const navbar = document.getElementById("navbar");
const langButton = document.getElementById("langBtn");
const langDropdown = document.getElementById("langDropdown");
const mobileToggle = document.getElementById("mobileToggle");
const navLinks = document.getElementById("navLinks");
const riskAcknowledgement = document.getElementById("riskAck");
const apkDownloadButton = document.getElementById("apkDownloadButton");
const macDownloadButton = document.getElementById("macDownloadButton");
const copyHashButton = document.getElementById("copyHashButton");
const apkHash = document.getElementById("apkHash");
const downloadRegistrationForm = document.getElementById("downloadRegistrationForm");
const downloadName = document.getElementById("downloadName");
const downloadEmail = document.getElementById("downloadEmail");
const downloadPrivacyConsent = document.getElementById("downloadPrivacyConsent");
const downloadRegistrationStatus = document.getElementById("downloadRegistrationStatus");
const downloadButtons = [apkDownloadButton, macDownloadButton].filter(Boolean);
let downloadIsPending = false;

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
        target.scrollIntoView({ behavior: "smooth", block: "start" });
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
    button.tabIndex = enabled ? 0 : -1;
    const labelElement = button.querySelector("span");
    if (labelElement) labelElement.textContent = label;
}

function syncDownloadState() {
    const registered = registrationIsValid();
    const androidEnabled = registered && riskAcknowledgement?.checked && !downloadIsPending;
    const macEnabled = registered && !downloadIsPending;

    setDownloadButtonState(
        apkDownloadButton,
        androidEnabled,
        androidEnabled
            ? translate("download.android.ctaReady", "登記並下載 APK")
            : translate("download.android.cta", "填寫資料並確認風險後下載 APK")
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
    const link = document.createElement("a");
    link.href = button.dataset.downloadHref;
    link.download = button.dataset.filename || "";
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
}

async function handleDownload(event) {
    event.preventDefault();
    const button = event.currentTarget;

    if (!registrationIsValid()) {
        downloadRegistrationForm?.reportValidity();
        setRegistrationStatus(
            translate("download.registration.invalid", "請填妥姓名／暱稱、有效 Email，並勾選隱私權同意。"),
            "error"
        );
        return;
    }

    if (button.dataset.platform === "android" && !riskAcknowledgement?.checked) {
        riskAcknowledgement?.focus();
        setRegistrationStatus(
            translate("download.registration.riskRequired", "下載 Android APK 前，請先勾選測試版風險確認。"),
            "error"
        );
        return;
    }

    downloadIsPending = true;
    syncDownloadState();
    setRegistrationStatus(
        translate("download.registration.saving", "正在登記下載資料…"),
        "pending"
    );

    try {
        const firestore = await window.SGH_FIRESTORE_READY;
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
        console.error("Unable to register download:", error);
        setRegistrationStatus(
            translate("download.registration.error", "登記失敗，尚未開始下載。請稍後再試。"),
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

if (copyHashButton && apkHash) {
    copyHashButton.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(apkHash.textContent.trim());
            copyHashButton.textContent = translate("download.hash.copied", "已複製");
            window.setTimeout(() => {
                copyHashButton.textContent = translate("download.hash.copy", "複製");
            }, 1600);
        } catch {
            const range = document.createRange();
            range.selectNodeContents(apkHash);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
        }
    });
}

window.addEventListener("sgh:languagechange", () => {
    syncDownloadState();
    if (downloadRegistrationStatus?.dataset.state === "idle") {
        setRegistrationStatus(
            translate("download.registration.status", "填妥資料後，請選擇下方要下載的平台。")
        );
    }
});
