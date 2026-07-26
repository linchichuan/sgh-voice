const navbar = document.getElementById("navbar");
const langButton = document.getElementById("langBtn");
const langDropdown = document.getElementById("langDropdown");
const mobileToggle = document.getElementById("mobileToggle");
const navLinks = document.getElementById("navLinks");
const riskAcknowledgement = document.getElementById("riskAck");
const apkDownloadButton = document.getElementById("apkDownloadButton");
const copyHashButton = document.getElementById("copyHashButton");
const apkHash = document.getElementById("apkHash");

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

function syncDownloadState() {
    if (!riskAcknowledgement || !apkDownloadButton) return;

    const accepted = riskAcknowledgement.checked;
    const label = apkDownloadButton.querySelector("span");
    apkDownloadButton.classList.toggle("disabled", !accepted);
    apkDownloadButton.setAttribute("aria-disabled", String(!accepted));
    apkDownloadButton.tabIndex = accepted ? 0 : -1;

    if (accepted) {
        apkDownloadButton.href = apkDownloadButton.dataset.downloadHref;
        apkDownloadButton.setAttribute("download", "SGHVoice-Android-v2.4.0.apk");
        label.textContent = translate("download.android.ctaReady", "我了解，下載 APK");
    } else {
        apkDownloadButton.removeAttribute("href");
        apkDownloadButton.removeAttribute("download");
        label.textContent = translate("download.android.cta", "勾選上方確認後下載 APK");
    }
}

if (riskAcknowledgement && apkDownloadButton) {
    riskAcknowledgement.addEventListener("change", syncDownloadState);
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

window.addEventListener("sgh:languagechange", syncDownloadState);
