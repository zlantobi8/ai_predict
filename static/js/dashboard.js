(async function () {
    PM.showOverlay("Loading…");

    const user = await PM.requireAuth();
    if (!user) { PM.hideOverlay(); return; }

    const set = (id, value) => { document.getElementById(id).textContent = value; };

    const recentBody = document.getElementById("recentMaintenance");
    recentBody.innerHTML = PM.loadingRow(4, "Loading recent maintenance…");

    try {
        const s = await PM.api("/dashboard/summary");

        set("totalEquipment", s.total_equipment);
        set("healthyEquipment", s.healthy_equipment);
        set("atRiskEquipment", s.at_risk_equipment + s.faulty_equipment);
        set("maintenanceDue", s.maintenance_due);

        set("summaryHealthy", s.healthy_equipment);
        set("summaryAtRisk", s.at_risk_equipment + s.faulty_equipment);
        set("summaryDue", s.maintenance_due);
        set("summaryAlerts", s.open_alerts);

        if (!s.recent_maintenance.length) {
            recentBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">No maintenance records yet.</td></tr>';
            return;
        }
        recentBody.innerHTML = s.recent_maintenance.map(m => `
            <tr>
                <td>${PM.esc(m.equipment_name)}</td>
                <td>${PM.esc(m.maintenance_type)}</td>
                <td>${PM.fmtDate(m.completed_date || m.scheduled_date)}</td>
                <td><span class="status ${m.display_status === "Completed" ? "completed" : "pending"}">${PM.esc(m.display_status)}</span></td>
            </tr>`).join("");
    } catch (e) {
        recentBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">Could not load recent maintenance.</td></tr>';
        PM.showError(e);
    } finally {
        PM.hideOverlay();
    }
})();
