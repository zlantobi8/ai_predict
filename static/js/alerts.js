(async function () {
    PM.showOverlay("Loading…");
    const user = await PM.requireAuth();
    if (!user) { PM.hideOverlay(); return; }

    const body = document.getElementById("alertsTableBody");
    const field = id => document.getElementById(id);

    const SEVERITY = { low: "status-active", medium: "status-warning", high: "status-warning", critical: "status-danger" };
    const STATUS = { open: "status-danger", acknowledged: "status-warning", resolved: "status-success" };

    let alerts = [];

    async function load() {
        body.innerHTML = PM.loadingRow(7, "Loading alerts…");
        try {
            alerts = await PM.api("/alerts");
        } catch (e) {
            body.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Could not load alerts.</td></tr>';
            PM.showError(e);
            return;
        }
        field("openAlertCount").textContent = alerts.filter(a => a.status === "open").length;
        field("ackAlertCount").textContent = alerts.filter(a => a.status === "acknowledged").length;
        field("resolvedAlertCount").textContent = alerts.filter(a => a.status === "resolved").length;
        field("totalAlertCount").textContent = alerts.length;
        render();
    }

    function render() {
        const text = field("alertSearch").value.toLowerCase().trim();
        const status = field("alertStatusFilter").value;
        const rows = alerts.filter(a =>
            (status === "all" || a.status === status) &&
            (!text || [a.equipment_name, a.message, a.severity].some(v => (v || "").toLowerCase().includes(text))));

        if (!rows.length) {
            body.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">${
                alerts.length ? "No alerts match your filters."
                    : "No alerts. One is raised automatically when a prediction shows high or critical risk."}</td></tr>`;
            return;
        }
        body.innerHTML = rows.map(a => `
            <tr>
                <td>${PM.pad("AL", a.id)}</td>
                <td><strong>${PM.esc(a.equipment_name)}</strong><small>${PM.esc(a.equipment_location || "")}</small></td>
                <td>${PM.esc(a.message)}</td>
                <td><span class="status-badge ${SEVERITY[a.severity] || "status-warning"}">${PM.esc(a.severity)}</span></td>
                <td><span class="status-badge ${STATUS[a.status] || "status-active"}">${PM.esc(a.status)}</span></td>
                <td>${PM.fmtDate(a.created_at)}<small>${PM.fmtTime(a.created_at)}</small></td>
                <td>
                    ${a.status === "open" ? `<button class="btn btn-sm btn-outline-warning" onclick="setAlert(${a.id}, 'acknowledged', this)">Acknowledge</button>` : ""}
                    ${a.status !== "resolved" ? `<button class="btn btn-sm btn-outline-success" onclick="setAlert(${a.id}, 'resolved', this)">Resolve</button>`
                        : `<button class="btn btn-sm btn-outline-secondary" onclick="setAlert(${a.id}, 'open', this)">Re-open</button>`}
                </td>
            </tr>`).join("");
    }

    window.setAlert = async function (id, status, button) {
        PM.setBtnLoading(button, true);
        try {
            await PM.api("/alerts/" + id, { method: "PUT", body: { status } });
            await load(); // table re-renders, so no need to restore the (now gone) button
        } catch (e) {
            PM.setBtnLoading(button, false);
            PM.showError(e);
        }
    };

    field("alertSearch").addEventListener("input", render);
    field("alertStatusFilter").addEventListener("change", render);

    load().finally(() => PM.hideOverlay());
})();
