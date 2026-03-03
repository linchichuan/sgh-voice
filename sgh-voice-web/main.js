// ===== SGH Voice Landing — main.js =====

// --- Navbar scroll effect ---
const navbar = document.getElementById("navbar");
window.addEventListener("scroll", () => {
    navbar.classList.toggle("scrolled", window.scrollY > 20);
}, { passive: true });

// --- Language dropdown toggle ---
const langBtn = document.getElementById("langBtn");
const langDropdown = document.getElementById("langDropdown");
langBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    langDropdown.classList.toggle("open");
});
document.addEventListener("click", () => langDropdown.classList.remove("open"));

// --- Mobile menu toggle ---
const mobileToggle = document.getElementById("mobileToggle");
const navLinks = document.querySelector(".nav-links");
if (mobileToggle) {
    mobileToggle.addEventListener("click", () => {
        navLinks.classList.toggle("mobile-open");
        mobileToggle.classList.toggle("active");
    });
}

// --- Smooth scroll for anchor links ---
document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener("click", (e) => {
        const target = document.querySelector(link.getAttribute("href"));
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: "smooth" });
            if (navLinks.classList.contains("mobile-open")) {
                navLinks.classList.remove("mobile-open");
                mobileToggle.classList.remove("active");
            }
        }
    });
});

// --- Wait for Firebase to be ready ---
function waitForFirestore(callback, retries = 20) {
    if (window._firestore) { callback(window._firestore); return; }
    if (retries <= 0) { console.warn("Firestore not loaded"); return; }
    setTimeout(() => waitForFirestore(callback, retries - 1), 200);
}

// --- Subscribe form → Firestore ---
document.getElementById("subscribeForm").addEventListener("submit", function (e) {
    e.preventDefault();
    const email = document.getElementById("emailInput").value.trim();
    if (!email) return;

    const submitBtn = this.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.style.opacity = "0.6";

    waitForFirestore(async ({ db, collection, addDoc, serverTimestamp }) => {
        try {
            await addDoc(collection(db, "sgh-voice-subscribers"), {
                email: email,
                createdAt: serverTimestamp(),
                source: "landing-page",
                lang: document.documentElement.lang || "ja"
            });
            document.querySelector("#subscribeForm .input-group").style.display = "none";
            document.querySelector("#subscribeForm .subscribe-note").style.display = "none";
            document.getElementById("subscribeSuccess").style.display = "flex";
        } catch (err) {
            console.error("Subscribe error:", err);
            submitBtn.disabled = false;
            submitBtn.style.opacity = "1";
            alert("エラーが発生しました。もう一度お試しください。");
        }
    });
});

// --- Contact form → Firestore ---
document.getElementById("contactForm").addEventListener("submit", function (e) {
    e.preventDefault();
    const name = document.getElementById("contactName").value.trim();
    const email = document.getElementById("contactEmail").value.trim();
    const subject = document.getElementById("contactSubject").value.trim();
    const message = document.getElementById("contactMessage").value.trim();
    if (!name || !email || !message) return;

    const submitBtn = this.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.style.opacity = "0.6";

    document.getElementById("contactError").style.display = "none";

    waitForFirestore(async ({ db, collection, addDoc, serverTimestamp }) => {
        try {
            await addDoc(collection(db, "sgh-voice-contacts"), {
                name: name,
                email: email,
                subject: subject,
                message: message,
                createdAt: serverTimestamp(),
                lang: document.documentElement.lang || "ja",
                status: "new"
            });
            // Hide form, show success
            this.querySelectorAll(".form-row, .form-group, .contact-submit-btn").forEach(el => el.style.display = "none");
            document.getElementById("contactSuccess").style.display = "flex";
        } catch (err) {
            console.error("Contact error:", err);
            submitBtn.disabled = false;
            submitBtn.style.opacity = "1";
            document.getElementById("contactError").style.display = "block";
        }
    });
});

// --- Intersection Observer for scroll animations ---
const observerOptions = { threshold: 0.1, rootMargin: "0px 0px -40px 0px" };
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

document.querySelectorAll(".feature-card, .step-card, .pricing-card, .download-card, .contact-card").forEach(el => {
    el.style.opacity = "0";
    el.style.transform = "translateY(24px)";
    el.style.transition = "opacity 0.6s ease, transform 0.6s ease";
    observer.observe(el);
});

// Add visible class styles
const style = document.createElement("style");
style.textContent = `.visible { opacity: 1 !important; transform: translateY(0) !important; }`;
document.head.appendChild(style);

// --- Stagger animation delay ---
document.querySelectorAll(".features-grid .feature-card").forEach((el, i) => {
    el.style.transitionDelay = `${i * 80}ms`;
});
document.querySelectorAll(".steps-grid .step-card").forEach((el, i) => {
    el.style.transitionDelay = `${i * 120}ms`;
});
