(async function () {
    PM.showOverlay("Loading…");
    const user = await PM.requireAuth();
    if (!user) { PM.hideOverlay(); return; }

    const body = document.getElementById("historyTableBody");
    const field = id => document.getElementById(id);

    const ACTIVITY = {
        prediction: { label: "Prediction", cls: "prediction-badge", icon: "bi-robot", prefix: "PR" },
        maintenance: { label: "Maintenance", cls: "maintenance-badge", icon: "bi-wrench", prefix: "MT" },
        user: { label: "User", cls: "user-badge", icon: "bi-person", prefix: "USR" },
    };
    const RESULT_CLASS = {
        "Healthy": "status-success", "Completed": "status-success",
        "Needs Monitoring": "status-warning", "Needs Maintenance": "status-warning", "Due Soon": "status-warning",
        "Critical": "status-danger", "Overdue": "status-danger", "Inactive": "status-danger",
        "Scheduled": "status-active", "Active": "status-active",
    };

    let records = [];

    body.innerHTML = PM.loadingRow(7, "Loading history…");
    try {
        const data = await PM.api("/history");
        records = data.records;
        field("predictionHistoryCount").textContent = data.counts.predictions;
        field("maintenanceHistoryCount").textContent = data.counts.maintenance;
        field("userHistoryCount").textContent = data.counts.users;
        field("totalHistoryCount").textContent = data.counts.total;
        render();
    } catch (e) {
        body.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Could not load history.</td></tr>';
        PM.showError(e);
    } finally {
        PM.hideOverlay();
    }

    function render() {
        const text = field("historySearch").value.toLowerCase().trim();
        const type = field("historyTypeFilter").value;
        const status = field("historyStatusFilter").value;

        const rows = records.map((r, i) => ({ r, i })).filter(({ r }) =>
            (type === "all" || r.activity === type) &&
            (status === "all" || (r.result || "").toLowerCase() === status) &&
            (!text || [PM.pad(ACTIVITY[r.activity].prefix, r.record_id), ACTIVITY[r.activity].label,
                r.equipment_name, r.actor, r.result].some(v => (v || "").toLowerCase().includes(text))));

        if (!rows.length) {
            body.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">${
                records.length ? "No history matches your filters." : "Nothing has been recorded yet."}</td></tr>`;
            return;
        }
        body.innerHTML = rows.map(({ r, i }) => {
            const a = ACTIVITY[r.activity];
            return `
            <tr>
                <td>${PM.pad(a.prefix, r.record_id)}</td>
                <td>${PM.fmtDate(r.occurred_at)}<small>${PM.fmtTime(r.occurred_at)}</small></td>
                <td><span class="activity-badge ${a.cls}"><i class="bi ${a.icon}"></i> ${a.label}</span></td>
                <td>${r.equipment_name
                    ? `<strong>${PM.esc(r.equipment_name)}</strong><small>${PM.esc(r.equipment_location || "")}</small>`
                    : "—"}</td>
                <td>${PM.esc(r.actor || "—")}</td>
                <td><span class="status-badge ${RESULT_CLASS[r.result] || "status-active"}">${PM.esc(r.result)}</span></td>
                <td><button type="button" class="action-btn view-btn" title="View" onclick="viewHistory(${i})"><i class="bi bi-eye"></i></button></td>
            </tr>`;
        }).join("");
    }

    field("historySearch").addEventListener("input", render);
    field("historyTypeFilter").addEventListener("change", render);
    field("historyStatusFilter").addEventListener("change", render);

    window.viewHistory = function (index) {
        const r = records[index];
        if (!r) return;
        const a = ACTIVITY[r.activity];
        let detail = "";
        if (r.activity === "prediction") detail = "Risk level: " + r.risk_level + "\nConfidence: " + Math.round(r.confidence * 100) + "%";
        if (r.activity === "maintenance") detail = "Maintenance type: " + r.maintenance_type + "\nScheduled for: " + PM.fmtDate(r.scheduled_date);
        if (r.activity === "user") detail = "Account created with role: " + PM.roleLabel(r.role);
        alert(
            "History Details\n\n" +
            "ID: " + PM.pad(a.prefix, r.record_id) + "\n" +
            "Date & Time: " + PM.fmtDate(r.occurred_at) + " " + PM.fmtTime(r.occurred_at) + "\n" +
            "Activity: " + a.label + "\n" +
            "Equipment: " + (r.equipment_name || "—") + "\n" +
            "User: " + (r.actor || "—") + "\n" +
            "Result / Status: " + r.result + "\n" + detail);
    };
})();
