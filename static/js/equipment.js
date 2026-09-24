(async function () {
    PM.showOverlay("Loading…");
    const user = await PM.requireAuth();
    if (!user) { PM.hideOverlay(); return; }

    const body = document.getElementById("equipmentBody");
    const form = document.getElementById("equipmentForm");
    const modalEl = document.getElementById("addEquipmentModal");
    const modalTitle = document.getElementById("equipmentModalTitle");
    const saveButton = document.getElementById("saveEquipmentBtn");
    const readingFields = document.getElementById("readingFields");
    const field = id => document.getElementById(id);

    const HEALTH_CLASS = { "Healthy": "healthy", "At Risk": "risk", "Faulty": "faulty" };
    const TYPE_LABEL = { "lathe": "Lathe machine", "drilling": "Drilling machine", "ac": "Air conditioner (AC)", "water-pump": "Water pump" };

    let all = [];
    let editingId = null;

    /* ---------- table ---------- */
    async function load() {
        body.innerHTML = PM.loadingRow(8, "Loading equipment…");
        try {
            all = await PM.api("/equipment");
            render();
        } catch (e) {
            body.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">Could not load equipment.</td></tr>';
            PM.showError(e);
        }
    }

    function render() {
        const text = field("searchEquipment").value.toLowerCase().trim();
        const category = field("categoryFilter").value.toLowerCase();
        const health = field("statusFilter").value;

        const rows = all.filter(e =>
            (!text || [e.name, e.location, e.category].some(v => (v || "").toLowerCase().includes(text))) &&
            (!category || (e.category || "").toLowerCase().includes(category)) &&
            (!health || e.health === health));

        if (!rows.length) {
            body.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">${
                all.length ? "No equipment matches your filters." : "No equipment registered yet. Click “+ Add Equipment” to add one."}</td></tr>`;
            return;
        }
        body.innerHTML = rows.map(e => `
            <tr>
                <td>${PM.pad("EQ", e.id)}</td>
                <td><strong>${PM.esc(e.name)}</strong></td>
                <td>${PM.esc(e.category)}</td>
                <td>${PM.esc(e.location || "—")}</td>
                <td>${PM.number(e.operating_hours)}</td>
                <td>${PM.esc(e.condition)}</td>
                <td><span class="status ${HEALTH_CLASS[e.health] || "healthy"}">${PM.esc(e.health)}</span></td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" data-action="view" data-id="${e.id}">View</button>
                    <button class="btn btn-sm btn-outline-warning" data-action="edit" data-id="${e.id}">Edit</button>
                    <button class="btn btn-sm btn-outline-danger" data-action="delete" data-id="${e.id}">Delete</button>
                </td>
            </tr>`).join("");
    }

    body.addEventListener("click", event => {
        const button = event.target.closest("button[data-action]");
        if (!button) return;
        const item = all.find(e => e.id === Number(button.dataset.id));
        if (!item) return;
        if (button.dataset.action === "delete") { deleteItem(item, button); return; }
        ({ view: viewItem, edit: editItem })[button.dataset.action](item);
    });

    ["searchEquipment"].forEach(id => field(id).addEventListener("input", render));
    ["categoryFilter", "statusFilter"].forEach(id => field(id).addEventListener("change", render));

    /* ---------- view / delete ---------- */
    function viewItem(e) {
        alert(
            "Equipment Details\n\n" +
            "ID: " + PM.pad("EQ", e.id) + "\n" +
            "Name: " + e.name + "\n" +
            "Type: " + (TYPE_LABEL[e.equipment_type] || e.equipment_type) + "\n" +
            "Category: " + e.category + "\n" +
            "Location: " + (e.location || "—") + "\n" +
            "Operating hours: " + PM.number(e.operating_hours) + "\n" +
            "Status: " + e.health + "\n" +
            "Last prediction: " + (e.last_prediction_at
                ? e.condition + " (" + Math.round(e.last_confidence * 100) + "% confidence) on " + PM.fmtDate(e.last_prediction_at)
                : "none yet") + "\n" +
            "Last maintenance: " + PM.fmtDate(e.last_maintenance_date));
    }

    async function deleteItem(e, button) {
        if (!confirm("Delete " + e.name + "?\n\nIts predictions, maintenance records and alerts will be deleted too.")) return;
        PM.setBtnLoading(button, true);
        try {
            await PM.api("/equipment/" + e.id, { method: "DELETE" });
            await load(); // table re-renders, so no need to restore the (now gone) button
        } catch (err) {
            PM.setBtnLoading(button, false);
            PM.showError(err);
        }
    }

    /* ---------- add / edit modal ---------- */
    function editItem(e) {
        editingId = e.id;
        field("eqName").value = e.name;
        field("eqType").value = e.equipment_type;
        field("eqCategory").value = e.category;
        field("eqLocation").value = e.location || "";
        field("eqHours").value = e.operating_hours;
        field("eqCondition").value = e.status;
        readingFields.classList.add("d-none");
        modalTitle.textContent = "Edit Equipment";
        saveButton.textContent = "Update Equipment";
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }

    // Whenever the modal closes, go back to "add" mode with an empty form.
    modalEl.addEventListener("hidden.bs.modal", () => {
        editingId = null;
        form.reset();
        readingFields.classList.remove("d-none");
        modalTitle.textContent = "Add New Equipment";
        saveButton.textContent = "Save Equipment";
    });

    saveButton.addEventListener("click", async () => {
        if (!form.checkValidity()) { form.reportValidity(); return; }

        const payload = {
            name: field("eqName").value.trim(),
            equipment_type: field("eqType").value,
            category: field("eqCategory").value,
            location: field("eqLocation").value.trim(),
            status: field("eqCondition").value,
        };
        if (field("eqHours").value !== "") payload.operating_hours = Number(field("eqHours").value);

        if (editingId === null) {
            const readings = ["eqTemp", "eqVib", "eqVolt"].map(id => field(id).value);
            const filled = readings.filter(v => v !== "").length;
            if (filled && filled < 3) {
                alert("Enter all three sensor readings (temperature, vibration, voltage) or leave them all blank.");
                return;
            }
            if (filled === 3) {
                payload.temperature = Number(readings[0]);
                payload.vibration = Number(readings[1]);
                payload.voltage = Number(readings[2]);
            }
        }

        PM.setBtnLoading(saveButton, true, editingId === null ? "Saving…" : "Updating…");
        try {
            if (editingId === null) await PM.api("/equipment", { method: "POST", body: payload });
            else await PM.api("/equipment/" + editingId, { method: "PUT", body: payload });
            bootstrap.Modal.getInstance(modalEl).hide();
            await load();
        } catch (err) {
            PM.showError(err);
        } finally {
            PM.setBtnLoading(saveButton, false);
        }
    });

    load().finally(() => PM.hideOverlay());
})();
