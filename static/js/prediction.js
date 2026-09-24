(async function () {
    PM.showOverlay("Loading…");
    const user = await PM.requireAuth();
    if (!user) { PM.hideOverlay(); return; }

    const form = document.getElementById("predictionForm");
    const equipmentSelect = document.getElementById("equipmentSelect");
    const hoursInput = document.getElementById("operatingHours");
    const submitButton = form.querySelector('button[type="submit"]');
    const resultArea = document.querySelector(".prediction-result-placeholder");
    const historyBody = document.getElementById("predictionHistoryBody");

    const RISK = {
        low: { label: "Low", cls: "status-healthy" },
        moderate: { label: "Medium", cls: "status-warning" },
        high: { label: "High", cls: "status-danger" },
        critical: { label: "Critical", cls: "status-danger" },
    };
    const riskOf = level => RISK[level] || RISK.moderate;

    let history = [];

    /* ---------- equipment dropdown ---------- */
    async function loadEquipment() {
        equipmentSelect.innerHTML = '<option value="">Loading equipment…</option>';
        const list = await PM.api("/equipment");
        if (!list.length) {
            equipmentSelect.innerHTML = '<option value="">No equipment registered yet</option>';
            submitButton.disabled = true;
            return;
        }
        equipmentSelect.innerHTML = '<option value="">Select equipment</option>' + list.map(e =>
            `<option value="${e.id}" data-hours="${PM.esc(e.operating_hours)}">${PM.esc(e.name)}${e.location ? " — " + PM.esc(e.location) : ""}</option>`).join("");
    }

    // Operating hours are already known for the equipment, so pre-fill them (still editable).
    equipmentSelect.addEventListener("change", () => {
        const option = equipmentSelect.selectedOptions[0];
        if (option && option.dataset.hours !== undefined && option.value) hoursInput.value = option.dataset.hours;
    });

    /* ---------- run a prediction ---------- */
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!form.checkValidity()) { form.reportValidity(); return; }

        PM.setBtnLoading(submitButton, true, "Predicting…");
        try {
            const result = await PM.api("/predictions", {
                method: "POST",
                body: {
                    equipment_id: Number(equipmentSelect.value),
                    temperature: Number(document.getElementById("temperature").value),
                    vibration: Number(document.getElementById("vibration").value),
                    voltage: Number(document.getElementById("voltage").value),
                    operating_hours: Number(hoursInput.value),
                    maintenance_history: document.getElementById("maintenanceHistory").value,
                },
            });
            showResult(result);
            equipmentSelect.selectedOptions[0].dataset.hours = hoursInput.value;
            loadHistory().catch(() => {}); // errors are already shown in the history table
        } catch (e) {
            PM.showError(e);
        } finally {
            PM.setBtnLoading(submitButton, false);
        }
    });

    function showResult(r) {
        const risk = riskOf(r.risk_level);
        resultArea.innerHTML = `
            <div class="result-icon"><i class="bi bi-robot"></i></div>
            <h5>${PM.esc(r.predicted_condition)}</h5>
            <span class="status-badge ${risk.cls}">${risk.label} Risk</span>
            <p class="mt-3">${PM.esc(r.recommendation)}</p>
            <small>
                ${PM.esc(r.equipment_name)} · model confidence ${Math.round(r.confidence * 100)}%
                ${r.alert_created ? "<br>An alert has been raised for this equipment." : ""}
            </small>`;
    }

    /* ---------- history ---------- */
    async function loadHistory() {
        historyBody.innerHTML = PM.loadingRow(6, "Loading prediction history…");
        try {
            history = await PM.api("/predictions?limit=20");
        } catch (e) {
            historyBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">Could not load prediction history.</td></tr>';
            throw e;
        }
        if (!history.length) {
            historyBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No predictions yet.</td></tr>';
            return;
        }
        historyBody.innerHTML = history.map(p => {
            const risk = riskOf(p.risk_level);
            return `
            <tr>
                <td>${PM.pad("PR", p.id)}</td>
                <td><strong>${PM.esc(p.equipment_name)}</strong><small>${PM.esc(p.equipment_location || "")}</small></td>
                <td>${PM.esc(p.predicted_condition)}</td>
                <td><span class="status-badge ${risk.cls}">${risk.label}</span></td>
                <td>${PM.fmtDate(p.created_at)}</td>
                <td><button type="button" class="action-btn view-btn" title="View" data-id="${p.id}"><i class="bi bi-eye"></i></button></td>
            </tr>`;
        }).join("");
    }

    historyBody.addEventListener("click", event => {
        const button = event.target.closest("button[data-id]");
        const p = button && history.find(x => x.id === Number(button.dataset.id));
        if (!p) return;
        alert(
            "Prediction Details\n\n" +
            "ID: " + PM.pad("PR", p.id) + "\n" +
            "Equipment: " + p.equipment_name + "\n" +
            "Date: " + PM.fmtDate(p.created_at) + " " + PM.fmtTime(p.created_at) + "\n" +
            "Prediction: " + p.predicted_condition + " (" + riskOf(p.risk_level).label + " risk, " + Math.round(p.confidence * 100) + "% confidence)\n\n" +
            "Temperature: " + p.temperature + " °C\n" +
            "Vibration: " + p.vibration + " mm/s\n" +
            "Voltage: " + p.voltage + " V\n" +
            "Operating hours: " + PM.number(p.operating_hours) + "\n" +
            "Maintenance history: " + p.maintenance_history + "\n" +
            "Run by: " + (p.created_by || "—"));
    });

    try {
        await Promise.all([loadEquipment(), loadHistory()]);
    } catch (e) { PM.showError(e); } finally { PM.hideOverlay(); }
})();
