(async function () {
    PM.showOverlay("Loading…");
    const user = await PM.requireAuth();
    if (!user) { PM.hideOverlay(); return; }

    const field = id => document.getElementById(id);
    const RISK = {
        low: { label: "Low", cls: "status-healthy" },
        moderate: { label: "Medium", cls: "status-warning" },
        high: { label: "High", cls: "status-danger" },
        critical: { label: "Critical", cls: "status-danger" },
    };
    const ACTION = {
        "Healthy": "Continue routine monitoring",
        "Needs Monitoring": "Keep monitoring and re-check the readings soon",
        "Needs Maintenance": "Schedule maintenance inspection",
        "Critical": "Carry out immediate inspection",
    };

    let data = null;

    /* ---------- load + render ---------- */
    async function load() {
        const from = field("fromDate").value;
        const to = field("toDate").value;
        const query = new URLSearchParams();
        if (from) query.set("from", from);
        if (to) query.set("to", to);
        data = await PM.api("/reports/overview" + (query.toString() ? "?" + query : ""));
        render();
        field("reportRange").textContent =
            "Showing " + (from || to
                ? (from ? "from " + PM.fmtDate(from) : "") + (from && to ? " " : "") + (to ? "up to " + PM.fmtDate(to) : "")
                : "all dates") +
            " · equipment status is always the current state.";
    }

    function render() {
        const s = data.summary;
        field("rpEquipment").textContent = s.total_equipment;
        field("rpMaintenance").textContent = s.maintenance_records;
        field("rpPredictions").textContent = s.predictions_made;
        field("rpAtRisk").textContent = s.at_risk_faulty;

        const e = data.equipment_status;
        const total = e.healthy + e.at_risk + e.faulty || 1;
        [["Healthy", e.healthy], ["AtRisk", e.at_risk], ["Faulty", e.faulty]].forEach(([key, n]) => {
            field("bar" + key).style.width = Math.round(n / total * 100) + "%";
            field("cnt" + key).textContent = n;
        });

        const m = data.maintenance_activity;
        field("actScheduled").textContent = m.scheduled;
        field("actDue").textContent = m.due_soon;
        field("actOverdue").textContent = m.overdue;
        field("actCompleted").textContent = m.completed;

        field("predictionSummaryBody").innerHTML = data.prediction_summary.map(r => {
            const risk = RISK[r.risk_level] || RISK.moderate;
            return `
            <tr>
                <td><strong>${PM.esc(r.predicted_condition)}</strong></td>
                <td><span class="status-badge ${risk.cls}">${risk.label}</span></td>
                <td>${r.equipment_count}</td>
                <td>${PM.esc(ACTION[r.predicted_condition] || "")}</td>
            </tr>`;
        }).join("");
    }

    /* ---------- filter (Apply button) ---------- */
    window.filterReport = async function (button) {
        const from = field("fromDate").value;
        const to = field("toDate").value;
        if (from && to && from > to) {
            alert("Invalid date range.\n\nThe From Date cannot be later than the To Date.");
            return;
        }

        const type = field("reportType").value;
        const show = (el, visible) => { el.style.display = visible ? "" : "none"; };
        show(document.querySelector(".status-report").closest(".col-lg-6"), type === "all" || type === "equipment");
        show(document.querySelector(".maintenance-summary").closest(".col-lg-6"), type === "all" || type === "maintenance");
        show(document.querySelector(".prediction-report-card"), type === "all" || type === "prediction");

        PM.setBtnLoading(button, true, "Applying…");
        try { await load(); } catch (e) { PM.showError(e); } finally { PM.setBtnLoading(button, false); }
    };

    window.printReport = () => window.print();

    /* ---------- Generate Report: download what is on screen as a CSV ---------- */
    window.generateReport = function () {
        if (!data) return;
        const type = field("reportType").value;
        const rows = [["AI Predictive Maintenance — Report"], ["Generated", new Date().toLocaleString()],
            ["Report type", field("reportType").selectedOptions[0].text.trim()],
            ["From", field("fromDate").value || "all dates"], ["To", field("toDate").value || "all dates"], []];

        rows.push(["Summary"], ["Total equipment", data.summary.total_equipment],
            ["Maintenance records", data.summary.maintenance_records],
            ["Predictions made", data.summary.predictions_made],
            ["At risk / faulty equipment", data.summary.at_risk_faulty], []);

        if (type === "all" || type === "equipment") {
            rows.push(["Equipment status (current)"], ["Healthy", data.equipment_status.healthy],
                ["At risk", data.equipment_status.at_risk], ["Faulty", data.equipment_status.faulty], []);
        }
        if (type === "all" || type === "maintenance") {
            rows.push(["Maintenance activity"], ["Scheduled", data.maintenance_activity.scheduled],
                ["Due soon", data.maintenance_activity.due_soon], ["Overdue", data.maintenance_activity.overdue],
                ["Completed", data.maintenance_activity.completed], []);
        }
        if (type === "all" || type === "prediction") {
            rows.push(["Prediction summary"], ["Prediction", "Risk level", "Number of equipment", "Recommended action"]);
            data.prediction_summary.forEach(r => rows.push([r.predicted_condition, (RISK[r.risk_level] || RISK.moderate).label,
                r.equipment_count, ACTION[r.predicted_condition] || ""]));
        }

        const csvCell = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
        const csv = rows.map(r => r.map(csvCell).join(",")).join("\r\n");
        const link = document.createElement("a");
        link.href = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }));
        link.download = "predictive-maintenance-report-" + PM.todayISO() + ".csv";
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(link.href);
    };

    try { await load(); } catch (e) { PM.showError(e); } finally { PM.hideOverlay(); }
})();
