/* Shared helpers used by every page: login state, calling the API, formatting.
   Loaded before each page's own script (see templates/). */
const PM = (() => {
    const TOKEN_KEY = "pm_token";
    const USER_KEY = "pm_user";
    const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const ROLE_LABELS = {
        admin: "Administrator",
        maintenance_staff: "Maintenance Staff",
        technical_staff: "Technical Staff",
    };

    /* ---------- session ---------- */
    const getToken = () => localStorage.getItem(TOKEN_KEY);
    const getUser = () => {
        try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch (e) { return null; }
    };
    function saveSession(token, user) {
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
    function clearSession() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
    }
    function toLogin(reason) {
        clearSession();
        window.location.replace("/" + (reason ? "?reason=" + encodeURIComponent(reason) : ""));
    }
    const logout = () => toLogin();

    /* ---------- API ---------- */
    class ApiError extends Error {
        constructor(message, status) { super(message); this.status = status; }
    }

    /* ---------- global top loading bar ----------
       Shown automatically for every PM.api() call in flight, on every page,
       so any fetch (login, loading a table, saving, deleting…) gets visible feedback
       even if the calling code doesn't add its own spinner. */
    let activeRequests = 0;
    let barEl = null;

    function ensureBar() {
        if (barEl) return barEl;
        if (!document.getElementById("pm-loading-styles")) {
            const style = document.createElement("style");
            style.id = "pm-loading-styles";
            style.textContent = `
                #pm-progress-bar {
                    position: fixed; top: 0; left: 0; width: 100%; height: 3px;
                    z-index: 3000; pointer-events: none; opacity: 0; transition: opacity .2s ease;
                }
                #pm-progress-bar.pm-active { opacity: 1; }
                #pm-progress-bar .pm-progress-bar-inner {
                    position: absolute; top: 0; left: -40%; height: 100%; width: 40%;
                    background: linear-gradient(90deg, #0d6efd, #6ea8fe);
                    border-radius: 0 2px 2px 0;
                }
                #pm-progress-bar.pm-active .pm-progress-bar-inner { animation: pm-bar-slide 1.1s ease-in-out infinite; }
                @keyframes pm-bar-slide { 0% { left: -40%; } 100% { left: 100%; } }
                .pm-btn-spinner {
                    display: inline-block; width: 0.9em; height: 0.9em; margin-right: .4em;
                    border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%;
                    vertical-align: -0.15em; animation: pm-spin .75s linear infinite;
                }
                @keyframes pm-spin { to { transform: rotate(360deg); } }
                #pm-overlay {
                    position: fixed; inset: 0; background: rgba(234, 242, 254, 0.72);
                    backdrop-filter: blur(1px); -webkit-backdrop-filter: blur(1px);
                    display: flex; flex-direction: column; align-items: center; justify-content: center;
                    z-index: 4000; opacity: 0; pointer-events: none; transition: opacity .15s ease;
                }
                #pm-overlay.pm-active { opacity: 1; pointer-events: all; }
                .pm-overlay-spinner {
                    width: 64px; height: 64px; border-radius: 50%;
                    border: 6px solid #d6cdfb; border-top-color: #7c4dff; border-right-color: #7c4dff;
                    animation: pm-spin .8s linear infinite;
                }
                .pm-overlay-text { margin-top: 18px; font-size: 1.15rem; color: #384153; }
            `;
            document.head.appendChild(style);
        }
        barEl = document.createElement("div");
        barEl.id = "pm-progress-bar";
        barEl.innerHTML = '<div class="pm-progress-bar-inner"></div>';
        (document.body || document.documentElement).appendChild(barEl);
        return barEl;
    }
    function startLoading() { activeRequests++; ensureBar().classList.add("pm-active"); }
    function stopLoading() {
        activeRequests = Math.max(0, activeRequests - 1);
        if (activeRequests === 0) ensureBar().classList.remove("pm-active");
    }

    /* Full-page "Loading…" overlay (light blue background, purple ring spinner).
       Use for a hard page-level wait, e.g. the very first load of a page.
       Don't combine with table loadingRow()s underneath — the overlay covers them. */
    let overlayEl = null;
    function ensureOverlay() {
        ensureBar(); // makes sure the shared <style> block (incl. overlay CSS) exists
        if (overlayEl) return overlayEl;
        overlayEl = document.createElement("div");
        overlayEl.id = "pm-overlay";
        overlayEl.innerHTML = '<div class="pm-overlay-spinner" role="status" aria-label="Loading"></div><div class="pm-overlay-text"></div>';
        (document.body || document.documentElement).appendChild(overlayEl);
        return overlayEl;
    }
    function showOverlay(label) {
        const el = ensureOverlay();
        el.querySelector(".pm-overlay-text").textContent = label || "Loading…";
        el.classList.add("pm-active");
    }
    function hideOverlay() {
        if (overlayEl) overlayEl.classList.remove("pm-active");
    }

    async function api(path, { method = "GET", body, auth = true } = {}) {
        const headers = {};
        if (body !== undefined) headers["Content-Type"] = "application/json";
        if (auth && getToken()) headers["Authorization"] = "Bearer " + getToken();

        startLoading();
        try {
            let response;
            try {
                response = await fetch("/api" + path, {
                    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
                });
            } catch (e) {
                throw new ApiError("Cannot reach the server. Is the application running?", 0);
            }

            let data = null;
            try { data = await response.json(); } catch (e) { /* empty or non-JSON body */ }

            if (response.status === 401 && auth) {
                toLogin((data && data.error) || "Please log in again");
                throw new ApiError("Session ended", 401);
            }
            if (!response.ok) {
                throw new ApiError((data && data.error) || "Request failed (" + response.status + ")", response.status);
            }
            return data;
        } finally {
            stopLoading();
        }
    }

    /* ---------- reusable loading UI ---------- */
    /* Put a button into (or out of) a "working" state: disables it, remembers its
       original contents, and shows a small inline spinner + optional label. */
    function setBtnLoading(btn, loading, label) {
        if (!btn) return;
        ensureBar(); // make sure the spinner keyframes/styles exist even if no fetch has run yet
        if (loading) {
            if (btn.dataset.pmOriginal === undefined) btn.dataset.pmOriginal = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="pm-btn-spinner" aria-hidden="true"></span>' + (label ? esc(label) : "");
        } else {
            if (btn.dataset.pmOriginal !== undefined) {
                btn.innerHTML = btn.dataset.pmOriginal;
                delete btn.dataset.pmOriginal;
            }
            btn.disabled = false;
        }
    }

    /* A placeholder row to show inside a <tbody> while its first fetch is in flight.
       (esc/loadingRow are called later, after this whole IIFE has finished running,
       so `esc` below is already initialized by then.) */
    function loadingRow(colspan, label) {
        return '<tr><td colspan="' + colspan + '" class="text-center text-muted py-4">' +
            '<span class="pm-btn-spinner" aria-hidden="true"></span>' + esc(label || "Loading…") + '</td></tr>';
    }

    /* ---------- page guard ---------- */
    /* Call at the top of every protected page. Returns the current user, or null
       (after redirecting to the login page). */
    async function requireAuth() {
        if (!getToken()) { toLogin(); return null; }
        let user;
        try {
            user = await api("/auth/me");
        } catch (e) {
            if (e.status === 401) return null;       // already redirected
            alert(e.message);
            return null;
        }
        localStorage.setItem(USER_KEY, JSON.stringify(user));

        document.querySelectorAll("[data-logout]").forEach(el =>
            el.addEventListener("click", ev => { ev.preventDefault(); logout(); }));
        document.querySelectorAll("[data-user-name]").forEach(el => { el.textContent = user.full_name; });
        document.querySelectorAll("[data-user-role]").forEach(el => { el.textContent = roleLabel(user.role); });
        if (user.role !== "admin") {
            document.querySelectorAll('a[href="/users"]').forEach(el => { el.style.display = "none"; });
        }
        return user;
    }

    /* ---------- formatting ---------- */
    const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));

    /* '2026-09-18' or '2026-09-18T14:30:00' -> parts, without timezone surprises */
    function parts(iso) {
        const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(iso || "");
        if (!m) return null;
        return { y: +m[1], mo: +m[2], d: +m[3], h: m[4] !== undefined ? +m[4] : null, mi: m[5] !== undefined ? +m[5] : null };
    }
    function fmtDate(iso) {
        const p = parts(iso);
        return p ? String(p.d).padStart(2, "0") + " " + MONTHS[p.mo - 1] + " " + p.y : "—";
    }
    function fmtTime(iso) {
        const p = parts(iso);
        if (!p || p.h === null) return "";
        const h12 = p.h % 12 === 0 ? 12 : p.h % 12;
        return String(h12).padStart(2, "0") + ":" + String(p.mi).padStart(2, "0") + " " + (p.h < 12 ? "AM" : "PM");
    }
    function dayAndMonth(iso) {
        const p = parts(iso);
        return p ? { day: String(p.d).padStart(2, "0"), month: MONTHS[p.mo - 1].toUpperCase() } : { day: "—", month: "" };
    }
    function todayISO() {
        const t = new Date();
        return t.getFullYear() + "-" + String(t.getMonth() + 1).padStart(2, "0") + "-" + String(t.getDate()).padStart(2, "0");
    }
    const roleLabel = role => ROLE_LABELS[role] || role || "";
    const pad = (prefix, id) => prefix + String(id).padStart(3, "0");
    const number = value => Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 1 });
    const showError = err => alert(err && err.message ? err.message : String(err));

    return {
        getToken, getUser, saveSession, clearSession, logout, api, ApiError, requireAuth,
        esc, fmtDate, fmtTime, dayAndMonth, todayISO, roleLabel, pad, number, showError,
        setBtnLoading, loadingRow, showOverlay, hideOverlay,
    };
})();
 
