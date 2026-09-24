(async function () {
    PM.showOverlay("Loading…");
    const me = await PM.requireAuth();
    if (!me) { PM.hideOverlay(); return; }

    const body = document.getElementById("userTableBody");
    const form = document.getElementById("userForm");
    const modalEl = document.getElementById("addUserModal");
    const modalTitle = modalEl.querySelector(".modal-title");
    const saveButton = modalEl.querySelector(".modal-footer .btn-primary");
    const addButton = document.querySelector(".add-user-btn");
    const field = id => document.getElementById(id);

    const ROLE_CLASS = { admin: "role-admin", maintenance_staff: "role-staff", technical_staff: "role-technical" };

    let users = [];
    let editingId = null;

    if (me.role !== "admin") {
        addButton.disabled = true;
        body.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Only administrators can manage users.</td></tr>';
        PM.hideOverlay();
        return;
    }

    async function load() {
        body.innerHTML = PM.loadingRow(6, "Loading users…");
        try {
            users = await PM.api("/users");
        } catch (e) {
            body.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Could not load users.</td></tr>';
            PM.showError(e);
            return;
        }
        render();
        renderSummary();
    }

    function initials(name) {
        return (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join("");
    }

    function render() {
        const text = field("userSearch").value.toLowerCase().trim();
        const role = field("roleFilter").value;
        const status = field("statusFilter").value;

        const rows = users.filter(u =>
            (role === "all" || PM.roleLabel(u.role).toLowerCase() === role) &&
            (status === "all" || u.status === status) &&
            (!text || [u.full_name, u.staff_id, u.email, PM.roleLabel(u.role)].some(v => (v || "").toLowerCase().includes(text))));

        if (!rows.length) {
            body.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No users match your filters.</td></tr>';
            return;
        }
        body.innerHTML = rows.map(u => `
            <tr>
                <td>${PM.pad("USR", u.id)}</td>
                <td>
                    <div class="user-info">
                        <div class="user-avatar">${PM.esc(initials(u.full_name))}</div>
                        <div><strong>${PM.esc(u.full_name)}</strong><small>ID: ${PM.esc(u.staff_id)}</small></div>
                    </div>
                </td>
                <td>${PM.esc(u.email || "—")}</td>
                <td><span class="role-badge ${ROLE_CLASS[u.role] || "role-staff"}">${PM.esc(PM.roleLabel(u.role))}</span></td>
                <td><span class="status-badge ${u.status === "active" ? "status-active" : "status-inactive"}">${u.status === "active" ? "Active" : "Inactive"}</span></td>
                <td>
                    <button type="button" class="action-btn view-btn" title="View" onclick="viewUser(${u.id})"><i class="bi bi-eye"></i></button>
                    <button type="button" class="action-btn edit-btn" title="Edit" onclick="editUser(${u.id})"><i class="bi bi-pencil"></i></button>
                    <button type="button" class="action-btn delete-btn" title="${u.id === me.id ? "You cannot delete your own account" : "Delete"}"
                        onclick="deleteUser(${u.id}, this)" ${u.id === me.id ? "disabled" : ""}><i class="bi bi-trash"></i></button>
                </td>
            </tr>`).join("");
    }

    function renderSummary() {
        field("totalUsers").textContent = users.length;
        field("adminCount").textContent = users.filter(u => u.role === "admin").length;
        field("staffCount").textContent = users.filter(u => u.role !== "admin").length;
        field("activeCount").textContent = users.filter(u => u.status === "active").length;
    }

    field("userSearch").addEventListener("input", render);
    field("roleFilter").addEventListener("change", render);
    field("statusFilter").addEventListener("change", render);

    /* ---------- add / edit ---------- */
    modalEl.addEventListener("hidden.bs.modal", () => {
        editingId = null;
        form.reset();
        field("staffId").readOnly = false;
        field("userPassword").required = true;
        field("passwordHint").textContent = "At least 6 characters.";
        modalTitle.innerHTML = '<i class="bi bi-person-plus"></i> Add User';
        saveButton.innerHTML = '<i class="bi bi-check-lg"></i> Save User';
    });

    window.saveUser = async function () {
        if (!form.checkValidity()) { form.reportValidity(); return; }

        const payload = {
            full_name: field("fullName").value.trim(),
            email: field("email").value.trim(),
            role: field("userRole").value,
            status: field("userStatus").value,
        };
        if (field("userPassword").value) payload.password = field("userPassword").value;

        PM.setBtnLoading(saveButton, true, editingId === null ? "Saving…" : "Updating…");
        try {
            if (editingId === null) {
                payload.staff_id = field("staffId").value.trim();
                await PM.api("/users", { method: "POST", body: payload });
            } else {
                await PM.api("/users/" + editingId, { method: "PUT", body: payload });
            }
            bootstrap.Modal.getInstance(modalEl).hide();
            await load();
        } catch (e) {
            PM.showError(e);
        } finally {
            PM.setBtnLoading(saveButton, false);
        }
    };

    window.editUser = function (id) {
        const u = users.find(x => x.id === id);
        if (!u) return;
        editingId = id;
        field("fullName").value = u.full_name;
        field("staffId").value = u.staff_id;
        field("staffId").readOnly = true;
        field("email").value = u.email || "";
        field("userRole").value = u.role;
        field("userStatus").value = u.status;
        field("userPassword").required = false;
        field("passwordHint").textContent = "Leave blank to keep the current password.";
        modalTitle.innerHTML = '<i class="bi bi-pencil-square"></i> Edit User';
        saveButton.innerHTML = '<i class="bi bi-check-lg"></i> Update User';
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    };

    window.deleteUser = async function (id, button) {
        const u = users.find(x => x.id === id);
        if (!u || !confirm("Are you sure you want to delete this user?\n\nUser ID: " + PM.pad("USR", u.id) + "\nName: " + u.full_name)) return;
        PM.setBtnLoading(button, true);
        try {
            await PM.api("/users/" + id, { method: "DELETE" });
            await load(); // table re-renders, so no need to restore the (now gone) button
        } catch (e) {
            PM.setBtnLoading(button, false);
            PM.showError(e);
        }
    };

    window.viewUser = function (id) {
        const u = users.find(x => x.id === id);
        if (!u) return;
        alert(
            "User Details\n\n" +
            "User ID: " + PM.pad("USR", u.id) + "\n" +
            "Staff ID (login): " + u.staff_id + "\n" +
            "Name: " + u.full_name + "\n" +
            "Email: " + (u.email || "—") + "\n" +
            "Role: " + PM.roleLabel(u.role) + "\n" +
            "Status: " + (u.status === "active" ? "Active" : "Inactive") + "\n" +
            "Created: " + PM.fmtDate(u.created_at));
    };

    load().finally(() => PM.hideOverlay());
})();
