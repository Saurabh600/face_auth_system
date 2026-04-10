/**
 * main.js — Global JavaScript utilities for FaceAuth
 *
 * This file is loaded on every page and handles:
 *   - Navbar scroll effect (glass blur increases)
 *   - Flash message auto-dismiss
 *   - Simple entrance animations
 *   - Utility functions used across pages
 */

// ── Navbar: add shadow when page is scrolled ──────────
window.addEventListener("scroll", () => {
    const nav = document.querySelector(".glass-nav");
    if (!nav) return;
    if (window.scrollY > 50) {
        nav.style.boxShadow = "0 4px 30px rgba(0,0,0,0.5)";
    } else {
        nav.style.boxShadow = "none";
    }
});

// ── Auto-dismiss flash alerts after 5 seconds ─────────
document.addEventListener("DOMContentLoaded", () => {
    const alerts = document.querySelectorAll(".alert");
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });
});

// ── Entrance animation for sections ───────────────────
// Adds 'visible' class to elements as they enter viewport
const observeEntrance = () => {
    const targets = document.querySelectorAll(
        ".feature-card, .step-card, .tech-badge, .stat-card, .dash-card"
    );
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity    = "1";
                entry.target.style.transform  = "translateY(0)";
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    targets.forEach((el, i) => {
        el.style.opacity   = "0";
        el.style.transform = "translateY(20px)";
        el.style.transition = `opacity 0.5s ease ${i * 0.05}s, transform 0.5s ease ${i * 0.05}s`;
        observer.observe(el);
    });
};

document.addEventListener("DOMContentLoaded", observeEntrance);
