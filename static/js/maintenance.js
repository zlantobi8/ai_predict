(async function () {
    PM.showOverlay("Loading…");
    const user = await PM.requireAuth();
    if (!user) { PM.hideOverlay(); return; }

    const body = document.getElementById("maintenanceTableBody");
    const upcomingList = document.getElementById("upcomingList");
    const modalEl = document.getElementById("addMaintenanceModal");
    const form = document.getElementById("maintenanceForm");
    const modalTitle = modalEl.querySelector(".modal-title");
    const saveButton = modalEl.querySelector(".modal-footer .btn-primary");
    const field = id => document.getElementById(id);

    const BADGE = {
        "Scheduled": "status-scheduled",
        "Due Soon": "status-due",
        "Overdue": "status-overdue",
        "Completed": "status-completed",
    };
    const badge = status => `<span class="status-badge ${BADGE[status] || "status-scheduled"}">${PM.esc(status)}</span>`;

    let logs = [];
    let editingId = null;

    /* ---------- loading ---------- */
    async function loadEquipment() {
        const list = await PM.api("/equipment");
        field("mEquipment").innerHTML = '<option value="">Select Equipment</option>' +
            list.map(e => `<option value="${e.id}">${PM.esc(e.name)}</option>`).join("");
    }

    async function load() {
        body.innerHTML = PM.loadingRow(7, "Loading maintenance records…");
        try {
            logs = await PM.api("/maintenance");
        } catch (e) {
            body.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Could not load maintenance records.</td></tr>';
            throw e;
        }
        renderTable();
        renderSummary();
        renderUpcoming();
    }

    /* ---------- rendering ---------- */
    function renderSummary() {
        const count = status => logs.filter(l => l.display_status === status).length;
        field("scheduledCount").textContent = count("Scheduled");
        field("dueCount").textContent = count("Due Soon");
        field("overdueCount").textContent = count("Overdue");
        field("completedCount").textContent = count("Completed");
    }

    function renderTable() {
        const text = field("maintenanceSearch").value.toLowerCase().trim();
        const type = field("maintenanceTypeFilter").value.toLowerCase();
        const status = field("maintenanceStatusFilter").value;

        const rows = logs.filter(l =>
            (!text || [l.equipment_name, l.technician, l.maintenance_type].some(v => (v || "").toLowerCase().includes(text))) &&
            (!type || (l.maintenance_type || "").toLowerCase().includes(type)) &&
            (!status || l.display_status === status));

        if (!rows.length) {
            body.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">${
                logs.length ? "No records match your filters." : "No maintenance scheduled yet. Click “Add Maintenance” to schedule one."}</td></tr>`;
            return;
        }
        body.innerHTML = rows.map(l => `
            <tr>
                <td>${PM.pad("MT", l.id)}</td>
                <td><strong>${PM.esc(l.equipment_name)}</strong><small>${PM.esc(l.equipment_location || "")}</small></td>
                <td>${PM.esc(l.maintenance_type)}</td>
                <td>${PM.fmtDate(l.scheduled_date)}</td>
                <td>${PM.esc(l.technician || "—")}</td>
                <td>${badge(l.display_status)}</td>
                <td>
                    <button type="button" class="action-btn view-btn" title="View" onclick="viewMaintenance(${l.id})"><i class="bi bi-eye"></i></button>
                    <button type="button" class="action-btn edit-btn" title="Edit" onclick="editMaintenance(${l.id})"><i class="bi bi-pencil"></i></button>
                    <button type="button" class="action-btn delete-btn" title="Delete" onclick="deleteMaintenance(${l.id}, this)"><i class="bi bi-trash"></i></button>
                </td>
            </tr>`).join("");
    }

    function renderUpcoming() {
        // The next few jobs that are not finished yet, soonest first (overdue jobs come first).
        const next = logs.filter(l => l.display_status !== "Completed")
            .sort((a, b) => a.scheduled_date.localeCompare(b.scheduled_date) || a.id - b.id)
            .slice(0, 5);
        if (!next.length) {
            upcomingList.innerHTML = '<p class="text-muted text-center py-3 mb-0">Nothing is waiting to be done.</p>';
            return;
        }
        upcomingList.innerHTML = next.map(l => {
            const d = PM.dayAndMonth(l.scheduled_date);
            return `
            <div class="upcoming-item">
                <div class="date-box"><strong>${d.day}</strong><span>${d.month}</span></div>
                <div class="upcoming-details">
                    <h6>${PM.esc(l.equipment_name)}</h6>
                    <p>${PM.esc(l.maintenance_type)} • ${PM.esc(l.equipment_location || l.category || "")}</p>
                </div>
                ${badge(l.display_status)}
            </div>`;
        }).join("");
    }

    ["maintenanceSearch"].forEach(id => field(id).addEventListener("input", renderTable));
    ["maintenanceTypeFilter", "maintenanceStatusFilter"].forEach(id => field(id).addEventListener("change", renderTable));

    /* ---------- add / edit ---------- */
    modalEl.addEventListener("hidden.bs.modal", () => {
        editingId = null;
        form.reset();
        modalTitle.innerHTML = '<i class="bi bi-wrench-adjustable-circle"></i> Schedule Maintenance';
        saveButton.innerHTML = '<i class="bi bi-check-lg"></i> Schedule Maintenance';
    });

    window.saveMaintenance = async function () {
        if (!form.checkValidity()) { form.reportValidity(); return; }

        const payload = {
            equipment_id: Number(field("mEquipment").value),
            maintenance_type: field("mType").value,
            scheduled_date: field("mDate").value,
            technician: field("mStaff").value.trim(),
            description: field("mDescription").value.trim(),
            status: field("mStatus").value,
        };

        PM.setBtnLoading(saveButton, true, editingId === null ? "Scheduling…" : "Updating…");
        try {
            if (editingId === null) await PM.api("/maintenance", { method: "POST", body: payload });
            else await PM.api("/maintenance/" + editingId, { method: "PUT", body: payload });
            bootstrap.Modal.getInstance(modalEl).hide();
            await load();
        } catch (e) {
            PM.showError(e);
        } finally {
            PM.setBtnLoading(saveButton, false);
        }
    };

    window.editMaintenance = function (id) {
        const l = logs.find(x => x.id === id);
        if (!l) return;
        editingId = id;
        field("mEquipment").value = l.equipment_id;
        field("mType").value = l.maintenance_type;
        field("mDate").value = (l.scheduled_date || "").slice(0, 10);
        field("mStaff").value = l.technician || "";
        field("mDescription").value = l.description || "";
        field("mStatus").value = l.status === "completed" ? "completed" : "scheduled";
        modalTitle.innerHTML = '<i class="bi bi-pencil-square"></i> Edit Maintenance';
        saveButton.innerHTML = '<i class="bi bi-check-lg"></i> Update Maintenance';
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    };

    window.deleteMaintenance = async function (id, button) {
        const l = logs.find(x => x.id === id);
        if (!l || !confirm("Are you sure you want to delete the maintenance record for " + l.equipment_name + "?")) return;
        PM.setBtnLoading(button, true);
        try {
            await PM.api("/maintenance/" + id, { method: "DELETE" });
            await load(); // table re-renders, so no need to restore the (now gone) button
        } catch (e) {
            PM.setBtnLoading(button, false);
            PM.showError(e);
        }
    };

    window.viewMaintenance = function (id) {
        const l = logs.find(x => x.id === id);
        if (!l) return;
        alert(
            "Maintenance Details\n\n" +
            "Equipment: " + l.equipment_name + "\n" +
            "Type: " + l.maintenance_type + "\n" +
            "Scheduled Date: " + PM.fmtDate(l.scheduled_date) + "\n" +
            (l.completed_date ? "Completed: " + PM.fmtDate(l.completed_date) + "\n" : "") +
            "Assigned Staff: " + (l.technician || "—") + "\n" +
            "Status: " + l.display_status + "\n" +
            "Notes: " + (l.description || "—"));
    };

    try {
        await Promise.all([loadEquipment(), load()]);
    } catch (e) { PM.showError(e); } finally { PM.hideOverlay(); }
})();
