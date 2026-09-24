(async function () {
    const form = document.getElementById("loginForm");
    const errorBox = document.getElementById("loginError");
    const button = document.getElementById("loginButton");

    function showError(message) {
        errorBox.textContent = message;
        errorBox.classList.remove("d-none");
    }

    const reason = new URLSearchParams(window.location.search).get("reason");
    if (reason) showError(reason);

    // Already logged in with a still-valid session? Skip the form.
    if (PM.getToken()) {
        try {
            await PM.api("/auth/me");
            window.location.replace("/dashboard");
            return;
        } catch (e) { /* a 401 clears the session and reloads this page; other errors just show the form */ }
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();
        errorBox.classList.add("d-none");
        PM.setBtnLoading(button, true, "Signing in…");
        try {
            const result = await PM.api("/auth/login", {
                method: "POST", auth: false,
                body: {
                    staff_id: document.getElementById("staffId").value.trim(),
                    password: document.getElementById("password").value,
                },
            });
            PM.saveSession(result.token, result.user);
            window.location.replace("/dashboard");
            // deliberately not restoring the button here — the page is navigating away
        } catch (e) {
            showError(e.message);
            PM.setBtnLoading(button, false);
        }
    });
})();
