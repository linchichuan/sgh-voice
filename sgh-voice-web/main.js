const navbar = document.getElementById("navbar");
const langButton = document.getElementById("langBtn");
const langDropdown = document.getElementById("langDropdown");
const mobileToggle = document.getElementById("mobileToggle");
const navLinks = document.getElementById("navLinks");

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
}

if (mobileToggle && navLinks) {
    mobileToggle.addEventListener("click", () => {
        const isOpen = navLinks.classList.toggle("mobile-open");
        mobileToggle.classList.toggle("active", isOpen);
        mobileToggle.setAttribute("aria-expanded", String(isOpen));
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
