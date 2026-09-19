// Same origin when served by the backend; fall back to the local backend when opened as a file
const API_BASE =
  location.protocol === "file:" ? "http://127.0.0.1:8000/api" : `${location.origin}/api`;

const state = { user: null, studentsPage: 1, gradeStudentId: null, logsPage: 1 };
const $ = (id) => document.getElementById(id);

// ---------- Helpers ----------
function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

let toastTimer;
function toast(msg, type = "success") {
  const el = $("toast");
  el.textContent = msg;
  el.className = `toast ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 2500);
}

async function api(path, { method = "GET", body, form, raw = false } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      credentials: "include", // session lives in an HttpOnly cookie
      body: form ? form : body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Cannot reach the backend. Is the server running?");
  }

  if (res.status === 401 && state.user) {
    resetSession();
    throw new Error("Session expired, please sign in again");
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      if (typeof err.detail === "string") msg = err.detail;
      else if (Array.isArray(err.detail)) msg = err.detail.map((d) => `${d.loc.slice(-1)[0]}: ${d.msg}`).join("; ");
    } catch {}
    throw new Error(msg);
  }
  if (raw) return res;
  if (res.status === 204) return null;
  return res.json();
}

// Wrap an async action: toast on error, disable the triggering button while running
async function run(fn, btn) {
  if (btn) btn.disabled = true;
  try {
    return await fn();
  } catch (e) {
    toast(e.message, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ---------- Modal form ----------
let modalSubmit = null;
function openModal(title, fields, values, onSubmit) {
  $("modal-title").textContent = title;
  $("modal-fields").innerHTML = fields
    .map((f) => {
      const v = values?.[f.name];
      let input;
      if (f.type === "select") {
        input = `<select name="${f.name}" ${f.required ? "required" : ""}>${f.options
          .map((o) => `<option value="${esc(o.value)}" ${String(v ?? "") === String(o.value) ? "selected" : ""}>${esc(o.label)}</option>`)
          .join("")}</select>`;
      } else {
        const attrs = Object.entries(f.attrs || {}).map(([k, val]) => `${k}="${esc(val)}"`).join(" ");
        input = `<input name="${f.name}" type="${f.type || "text"}" value="${esc(v)}" ${f.required ? "required" : ""} ${f.disabled ? "disabled" : ""} ${attrs} />`;
      }
      return `<div class="form-row"><label>${esc(f.label)}</label>${input}</div>`;
    })
    .join("");
  modalSubmit = onSubmit;
  $("modal").classList.remove("hidden");
  $("modal-fields").querySelector("input:not([disabled]),select")?.focus();
}
function closeModal() {
  $("modal").classList.add("hidden");
  modalSubmit = null;
}
$("modal-cancel").addEventListener("click", closeModal);
$("modal").addEventListener("click", (e) => { if (e.target === $("modal")) closeModal(); });
$("modal-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = {};
  for (const el of $("modal-fields").querySelectorAll("input,select")) {
    if (el.disabled) continue;
    data[el.name] = el.type === "number" ? (el.value === "" ? null : Number(el.value)) : el.value;
  }
  const btn = e.submitter;
  await run(async () => {
    await modalSubmit(data);
    closeModal();
  }, btn);
});

// ---------- Auth / routing ----------
const isAdmin = () => state.user?.role === "admin";

function applyRole() {
  document.querySelectorAll(".admin-only").forEach((el) => el.classList.toggle("hidden", !isAdmin()));
}

function resetSession() {
  state.user = null;
  closeModal();
  $("nav").classList.add("hidden");
  $("user-box").classList.add("hidden");
  showView("login");
}

async function logout() {
  try { await api("/auth/logout", { method: "POST" }); } catch {}
  resetSession();
}

function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  $(`view-${name}`).classList.remove("hidden");
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${name}`));
}

const loaders = {
  students: loadStudents,
  classes: loadClasses,
  courses: loadCourses,
  grades: initGrades,
  stats: loadStats,
  users: loadUsers,
  logs: loadLogs,
};

function route() {
  if (!state.user) return showView("login");
  let name = location.hash.replace("#", "") || "students";
  if (!loaders[name] || ((name === "users" || name === "logs") && !isAdmin())) name = "students";
  showView(name);
  run(loaders[name]);
}
window.addEventListener("hashchange", route);

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  await run(async () => {
    await api("/auth/login", {
      method: "POST",
      body: { username: $("login-username").value.trim(), password: $("login-password").value },
    });
    await afterLogin();
    $("login-password").value = "";
  }, e.submitter);
});
$("logout-btn").addEventListener("click", logout);

$("change-password-btn").addEventListener("click", () =>
  openModal(
    "Change password",
    [
      { name: "old_password", label: "Current password", type: "password", required: true, attrs: { maxlength: 72, autocomplete: "current-password" } },
      { name: "new_password", label: "New password", type: "password", required: true, attrs: { minlength: 6, maxlength: 72, autocomplete: "new-password" } },
      { name: "confirm", label: "Confirm new password", type: "password", required: true, attrs: { minlength: 6, maxlength: 72, autocomplete: "new-password" } },
    ],
    {},
    async (data) => {
      if (data.new_password !== data.confirm) throw new Error("The new passwords do not match");
      await api("/auth/change-password", { method: "POST", body: { old_password: data.old_password, new_password: data.new_password } });
      toast("Password changed");
    }
  )
);

async function afterLogin() {
  state.user = await api("/auth/me");
  $("user-name").textContent = `${state.user.username} (${state.user.role === "admin" ? "admin" : "viewer"})`;
  $("nav").classList.remove("hidden");
  $("user-box").classList.remove("hidden");
  applyRole();
  route();
}

// ---------- Students ----------
const GENDER_LABELS = { male: "Male", female: "Female" };
const GENDER_OPTIONS = [{ value: "", label: "Select" }, ...Object.entries(GENDER_LABELS).map(([value, label]) => ({ value, label }))];

async function classOptions(includeEmptyLabel = "Unassigned") {
  const classes = await api("/classes");
  return [{ value: "", label: includeEmptyLabel }, ...classes.map((c) => ({ value: c.id, label: c.name }))];
}

function studentFields(classOpts, editing) {
  return [
    { name: "student_no", label: "Student No", required: true, disabled: editing, attrs: { maxlength: 20 } },
    { name: "name", label: "Name", required: true, attrs: { maxlength: 50 } },
    { name: "age", label: "Age", type: "number", required: true, attrs: { min: 1, max: 150 } },
    { name: "gender", label: "Gender", type: "select", required: true, options: GENDER_OPTIONS },
    { name: "major", label: "Major", attrs: { maxlength: 100 } },
    { name: "class_id", label: "Class", type: "select", options: classOpts },
  ];
}

function normalizeStudent(data) {
  return { ...data, major: data.major?.trim() || null, class_id: data.class_id ? Number(data.class_id) : null };
}

async function loadStudents() {
  const classes = await api("/classes");
  const filter = $("student-class-filter");
  const current = filter.value;
  filter.innerHTML = `<option value="">All classes</option>` + classes.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  filter.value = current;

  const params = new URLSearchParams({ page: state.studentsPage, size: 10 });
  const kw = $("student-keyword").value.trim();
  if (kw) params.set("keyword", kw);
  if (filter.value) params.set("class_id", filter.value);

  const page = await api(`/students?${params}`);
  const tbody = $("students-tbody");
  tbody.innerHTML = page.items.length
    ? page.items
        .map(
          (s) => `<tr>
          <td>${s.id}</td><td>${esc(s.student_no)}</td><td>${esc(s.name)}</td><td>${s.age}</td>
          <td>${esc(GENDER_LABELS[s.gender] ?? s.gender)}</td><td>${esc(s.major)}</td><td>${esc(s.class_name)}</td>
          <td class="admin-only">
            <button class="btn small" data-edit="${s.id}">Edit</button>
            <button class="btn small danger" data-del="${s.id}">Delete</button>
          </td></tr>`
        )
        .join("")
    : `<tr><td colspan="8" class="empty">No data</td></tr>`;
  applyRole();
  renderPager(page);
}

function renderPager(page) {
  const pages = Math.max(1, Math.ceil(page.total / page.size));
  $("students-pager").innerHTML = `
    <span class="muted">${page.total} total</span>
    <button class="btn small secondary" data-page="${page.page - 1}" ${page.page <= 1 ? "disabled" : ""}>Prev</button>
    <span>${page.page} / ${pages}</span>
    <button class="btn small secondary" data-page="${page.page + 1}" ${page.page >= pages ? "disabled" : ""}>Next</button>`;
}

$("students-pager").addEventListener("click", (e) => {
  const p = e.target.dataset.page;
  if (p) { state.studentsPage = Number(p); run(loadStudents); }
});
$("student-search-btn").addEventListener("click", () => { state.studentsPage = 1; run(loadStudents); });
$("student-keyword").addEventListener("keydown", (e) => { if (e.key === "Enter") { state.studentsPage = 1; run(loadStudents); } });
$("student-class-filter").addEventListener("change", () => { state.studentsPage = 1; run(loadStudents); });

$("student-add-btn").addEventListener("click", () =>
  run(async () => {
    openModal("Add student", studentFields(await classOptions(), false), {}, async (data) => {
      await api("/students", { method: "POST", body: normalizeStudent(data) });
      toast("Created");
      await loadStudents();
    });
  })
);

$("students-tbody").addEventListener("click", (e) => {
  const { edit, del } = e.target.dataset;
  if (edit) {
    run(async () => {
      const s = await api(`/students/${edit}`);
      openModal("Edit student", studentFields(await classOptions(), true), s, async (data) => {
        await api(`/students/${edit}`, { method: "PUT", body: normalizeStudent(data) });
        toast("Saved");
        await loadStudents();
      });
    });
  } else if (del && confirm("Delete this student? Their enrollments and grades will be deleted too.")) {
    run(async () => {
      await api(`/students/${del}`, { method: "DELETE" });
      toast("Deleted");
      await loadStudents();
    }, e.target);
  }
});

$("student-export-btn").addEventListener("click", (e) =>
  run(async () => {
    const res = await api("/students/export", { raw: true });
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: "students.xlsx" });
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, e.target)
);

$("student-import-btn").addEventListener("click", () => $("student-import-file").click());
$("student-import-file").addEventListener("change", (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  run(async () => {
    const form = new FormData();
    form.append("file", file);
    const r = await api("/students/import", { method: "POST", form });
    const msg = `Import finished: ${r.created} created, ${r.skipped} skipped${r.errors.length ? `, ${r.errors.length} failed` : ""}`;
    toast(msg, r.errors.length ? "warn" : "success");
    if (r.errors.length) alert(msg + "\n\n" + r.errors.join("\n"));
    state.studentsPage = 1;
    await loadStudents();
  }, $("student-import-btn"));
});

// ---------- Classes ----------
const CLASS_FIELDS = [
  { name: "name", label: "Class name", required: true, attrs: { maxlength: 50 } },
  { name: "major", label: "Major", attrs: { maxlength: 100 } },
];
const normalizeClass = (d) => ({ ...d, major: d.major?.trim() || null });

async function loadClasses() {
  const classes = await api("/classes");
  $("classes-tbody").innerHTML = classes.length
    ? classes
        .map(
          (c) => `<tr><td>${c.id}</td><td>${esc(c.name)}</td><td>${esc(c.major)}</td><td>${c.student_count}</td>
          <td class="admin-only">
            <button class="btn small" data-edit="${c.id}">Edit</button>
            <button class="btn small danger" data-del="${c.id}">Delete</button>
          </td></tr>`
        )
        .join("")
    : `<tr><td colspan="5" class="empty">No data</td></tr>`;
  applyRole();
}

$("class-add-btn").addEventListener("click", () =>
  openModal("Add class", CLASS_FIELDS, {}, async (data) => {
    await api("/classes", { method: "POST", body: normalizeClass(data) });
    toast("Created");
    await loadClasses();
  })
);

$("classes-tbody").addEventListener("click", (e) => {
  const { edit, del } = e.target.dataset;
  if (edit) {
    run(async () => {
      const c = await api(`/classes/${edit}`);
      openModal("Edit class", CLASS_FIELDS, c, async (data) => {
        await api(`/classes/${edit}`, { method: "PUT", body: normalizeClass(data) });
        toast("Saved");
        await loadClasses();
      });
    });
  } else if (del && confirm("Delete this class? Its students will become unassigned.")) {
    run(async () => {
      await api(`/classes/${del}`, { method: "DELETE" });
      toast("Deleted");
      await loadClasses();
    }, e.target);
  }
});

// ---------- Courses ----------
const COURSE_FIELDS = [
  { name: "code", label: "Course code", required: true, attrs: { maxlength: 20 } },
  { name: "name", label: "Course name", required: true, attrs: { maxlength: 100 } },
  { name: "credit", label: "Credits", type: "number", required: true, attrs: { min: 0, max: 20, step: 0.5 } },
];

async function loadCourses() {
  const courses = await api("/courses");
  $("courses-tbody").innerHTML = courses.length
    ? courses
        .map(
          (c) => `<tr><td>${c.id}</td><td>${esc(c.code)}</td><td>${esc(c.name)}</td><td>${c.credit}</td>
          <td class="admin-only">
            <button class="btn small" data-edit="${c.id}">Edit</button>
            <button class="btn small danger" data-del="${c.id}">Delete</button>
          </td></tr>`
        )
        .join("")
    : `<tr><td colspan="5" class="empty">No data</td></tr>`;
  applyRole();
}

$("course-add-btn").addEventListener("click", () =>
  openModal("Add course", COURSE_FIELDS, { credit: 2 }, async (data) => {
    await api("/courses", { method: "POST", body: data });
    toast("Created");
    await loadCourses();
  })
);

$("courses-tbody").addEventListener("click", (e) => {
  const { edit, del } = e.target.dataset;
  if (edit) {
    run(async () => {
      const c = await api(`/courses/${edit}`);
      openModal("Edit course", COURSE_FIELDS, c, async (data) => {
        await api(`/courses/${edit}`, { method: "PUT", body: data });
        toast("Saved");
        await loadCourses();
      });
    });
  } else if (del && confirm("Delete this course? All enrollments and grades for it will be deleted too.")) {
    run(async () => {
      await api(`/courses/${del}`, { method: "DELETE" });
      toast("Deleted");
      await loadCourses();
    }, e.target);
  }
});

// ---------- Grades ----------
async function initGrades() {
  await loadGradeStudentOptions();
  const courses = await api("/courses");
  $("grade-course-select").innerHTML =
    `<option value="">Select a course</option>` + courses.map((c) => `<option value="${c.id}">${esc(c.code)} ${esc(c.name)}</option>`).join("");
  await loadGrades();
}

async function loadGradeStudentOptions() {
  const params = new URLSearchParams({ page: 1, size: 100 });
  const kw = $("grade-student-keyword").value.trim();
  if (kw) params.set("keyword", kw);
  const page = await api(`/students?${params}`);
  $("grade-student-hint").classList.toggle("hidden", page.total <= 100);
  const sel = $("grade-student-select");
  sel.innerHTML =
    `<option value="">Select a student</option>` +
    page.items.map((s) => `<option value="${s.id}">${esc(s.student_no)} ${esc(s.name)}</option>`).join("");
  if (state.gradeStudentId && page.items.some((s) => s.id === state.gradeStudentId)) {
    sel.value = state.gradeStudentId;
  } else {
    state.gradeStudentId = null;
  }
}

async function loadGrades() {
  const tbody = $("grades-tbody");
  const summary = $("grades-summary");
  if (!state.gradeStudentId) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty">Select a student first</td></tr>`;
    summary.textContent = "";
    return;
  }
  const list = await api(`/enrollments?student_id=${state.gradeStudentId}`);
  tbody.innerHTML = list.length
    ? list
        .map(
          (e) => `<tr>
          <td>${esc(e.course_code)}</td><td>${esc(e.course_name)}</td><td>${e.credit}</td>
          <td>${isAdmin()
            ? `<input type="number" class="score-input" min="0" max="100" step="0.5" value="${e.score ?? ""}" data-score="${e.id}" placeholder="Not graded" />`
            : e.score ?? "Not graded"}</td>
          <td class="admin-only">
            <button class="btn small" data-save="${e.id}">Save</button>
            <button class="btn small danger" data-del="${e.id}">Drop</button>
          </td></tr>`
        )
        .join("")
    : `<tr><td colspan="5" class="empty">No enrollments for this student</td></tr>`;
  applyRole();

  const graded = list.filter((e) => e.score != null);
  const credits = list.reduce((a, e) => a + e.credit, 0);
  const avg = graded.length ? (graded.reduce((a, e) => a + e.score, 0) / graded.length).toFixed(1) : "-";
  summary.textContent = list.length ? `${list.length} course(s), ${credits} credits, ${graded.length} graded, average ${avg}` : "";
}

let gradeSearchTimer;
$("grade-student-keyword").addEventListener("input", () => {
  clearTimeout(gradeSearchTimer);
  gradeSearchTimer = setTimeout(() => run(async () => { await loadGradeStudentOptions(); await loadGrades(); }), 300);
});
$("grade-student-select").addEventListener("change", (e) => {
  state.gradeStudentId = e.target.value ? Number(e.target.value) : null;
  run(loadGrades);
});

$("enroll-btn").addEventListener("click", (e) =>
  run(async () => {
    const course_id = Number($("grade-course-select").value);
    if (!state.gradeStudentId) throw new Error("Select a student first");
    if (!course_id) throw new Error("Select a course");
    await api("/enrollments", { method: "POST", body: { student_id: state.gradeStudentId, course_id } });
    toast("Enrolled");
    await loadGrades();
  }, e.target)
);

$("grades-tbody").addEventListener("click", (e) => {
  const { save, del } = e.target.dataset;
  if (save) {
    run(async () => {
      const raw = document.querySelector(`[data-score="${save}"]`).value;
      await api(`/enrollments/${save}`, { method: "PUT", body: { score: raw === "" ? null : Number(raw) } });
      toast("Score saved");
      await loadGrades();
    }, e.target);
  } else if (del && confirm("Drop this course for the student?")) {
    run(async () => {
      await api(`/enrollments/${del}`, { method: "DELETE" });
      toast("Dropped");
      await loadGrades();
    }, e.target);
  }
});

// ---------- Statistics ----------
function renderBars(tbodyId, items) {
  const max = Math.max(1, ...items.map((i) => i.count));
  $(tbodyId).innerHTML = items.length
    ? items
        .map(
          (i) => `<tr><td class="bar-label">${esc(i.label)}</td>
          <td class="bar-cell"><div class="bar" style="width:${(i.count / max) * 100}%"></div></td>
          <td class="bar-num">${i.count}</td></tr>`
        )
        .join("")
    : `<tr><td class="empty">No data</td></tr>`;
}

async function loadStats() {
  const s = await api("/stats");
  $("stats-tiles").innerHTML = [
    ["Students", s.total_students],
    ["Classes", s.total_classes],
    ["Courses", s.total_courses],
  ]
    .map(([label, n]) => `<div class="tile"><div class="tile-num">${n}</div><div class="tile-label">${label}</div></div>`)
    .join("");
  renderBars("stats-major", s.by_major);
  renderBars("stats-gender", s.by_gender);
  renderBars("stats-class", s.by_class);
}

// ---------- Users ----------
async function loadUsers() {
  const users = await api("/auth/users");
  $("users-tbody").innerHTML = users
    .map(
      (u) => `<tr><td>${u.id}</td><td>${esc(u.username)}</td><td>${u.role === "admin" ? "Admin" : "Viewer"}</td>
      <td>
        <button class="btn small" data-reset="${u.id}" data-name="${esc(u.username)}">Reset password</button>
        ${u.id === state.user.id ? "" : `<button class="btn small danger" data-del="${u.id}">Delete</button>`}
      </td></tr>`
    )
    .join("");
}

$("user-add-btn").addEventListener("click", () =>
  openModal(
    "Add user",
    [
      { name: "username", label: "Username", required: true, attrs: { minlength: 2, maxlength: 50 } },
      { name: "password", label: "Password", type: "password", required: true, attrs: { minlength: 6, maxlength: 128 } },
      { name: "role", label: "Role", type: "select", options: [{ value: "user", label: "Viewer" }, { value: "admin", label: "Admin" }] },
    ],
    { role: "user" },
    async (data) => {
      await api("/auth/users", { method: "POST", body: data });
      toast("Created");
      await loadUsers();
    }
  )
);

$("users-tbody").addEventListener("click", (e) => {
  const { del, reset, name } = e.target.dataset;
  if (reset) {
    openModal(
      `Reset password: ${name}`,
      [{ name: "new_password", label: "New password", type: "password", required: true, attrs: { minlength: 6, maxlength: 72, autocomplete: "new-password" } }],
      {},
      async (data) => {
        await api(`/auth/users/${reset}/password`, { method: "PUT", body: data });
        toast("Password reset");
      }
    );
  } else if (del && confirm("Delete this user?")) {
    run(async () => {
      await api(`/auth/users/${del}`, { method: "DELETE" });
      toast("Deleted");
      await loadUsers();
    }, e.target);
  }
});

// ---------- Audit log ----------
function describeLog(l) {
  const p = l.path.replace(/^\/api/, "");
  const verbs = { POST: "Create", PUT: "Update", DELETE: "Delete" };
  let m;
  if (p === "/auth/login") return l.status === 200 ? "Login succeeded" : l.status === 429 ? "Login rate-limited" : "Login failed";
  if (p === "/auth/logout") return "Signed out";
  if (p === "/auth/change-password") return "Changed password";
  if ((m = p.match(/^\/auth\/users\/(\d+)\/password$/))) return `Reset password of user #${m[1]}`;
  if ((m = p.match(/^\/auth\/users(?:\/(\d+))?$/))) return `${verbs[l.method]} user${m[1] ? ` #${m[1]}` : ""}`;
  if (p === "/students/import") return "Imported students";
  const names = { students: "student", classes: "class", courses: "course", enrollments: "enrollment" };
  if ((m = p.match(/^\/([a-z]+)(?:\/(\d+))?$/)) && names[m[1]]) {
    return `${verbs[l.method] || l.method} ${names[m[1]]}${m[2] ? ` #${m[2]}` : ""}`;
  }
  return `${l.method} ${l.path}`;
}

async function loadLogs() {
  const params = new URLSearchParams({ page: state.logsPage, size: 20 });
  const u = $("log-username").value.trim();
  if (u) params.set("username", u);
  const page = await api(`/audit-logs?${params}`);
  $("logs-tbody").innerHTML = page.items.length
    ? page.items
        .map(
          (l) => `<tr>
          <td>${esc(new Date(l.created_at + "Z").toLocaleString())}</td>
          <td>${esc(l.username ?? "-")}</td><td>${esc(l.ip ?? "-")}</td>
          <td>${esc(describeLog(l))}</td>
          <td class="${l.status < 400 ? "ok" : "fail"}">${l.status}</td>
          <td class="log-detail" title="${esc(l.detail ?? "")}">${esc(l.detail ?? "")}</td></tr>`
        )
        .join("")
    : `<tr><td colspan="6" class="empty">No log entries</td></tr>`;

  const pages = Math.max(1, Math.ceil(page.total / page.size));
  $("logs-pager").innerHTML = `
    <span class="muted">${page.total} total</span>
    <button class="btn small secondary" data-page="${page.page - 1}" ${page.page <= 1 ? "disabled" : ""}>Prev</button>
    <span>${page.page} / ${pages}</span>
    <button class="btn small secondary" data-page="${page.page + 1}" ${page.page >= pages ? "disabled" : ""}>Next</button>`;
}

$("logs-pager").addEventListener("click", (e) => {
  const p = e.target.dataset.page;
  if (p) { state.logsPage = Number(p); run(loadLogs); }
});
$("log-search-btn").addEventListener("click", () => { state.logsPage = 1; run(loadLogs); });
$("log-username").addEventListener("keydown", (e) => { if (e.key === "Enter") { state.logsPage = 1; run(loadLogs); } });

// ---------- Startup ----------
(async () => {
  try {
    await afterLogin(); // a valid session cookie takes us straight in
  } catch {
    showView("login");
  }
})();
