"use strict";

const state = { jobs: [], stats: {}, kill: false };

// ── helpers ────────────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const scoreClass = (s) => (s == null ? "" : s >= 75 ? "hi" : s >= 50 ? "mid" : "lo");

async function api(path, method = "GET", body) {
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if (body) opt.body = JSON.stringify(body);
  const r = await fetch("/api" + path, opt);
  return r.json();
}

// ── rendering ───────────────────────────────────────────────────────────────
function renderStats() {
  const s = state.stats;
  const items = [
    ["Applied today", s.applied_today ?? 0],
    ["This week", s.applied_week ?? 0],
    ["To review", (s.by_status && s.by_status.scored) || 0],
    ["Avg score", s.avg_score != null ? s.avg_score : "—"],
    ["Total", s.total ?? 0],
    ["Mode", s.llm ? "AI" : "Free"],
  ];
  $("#stats").innerHTML = "";
  items.forEach(([l, n]) => {
    const d = el("div", "stat");
    d.append(el("div", "n", esc(String(n))), el("div", "l", esc(l)));
    $("#stats").append(d);
  });
}

function renderPending() {
  const box = $("#pendingCards");
  box.innerHTML = "";
  const pending = state.jobs.filter((j) => j.status === "scored")
    .sort((a, b) => (b.score || 0) - (a.score || 0));
  $("#pendingEmpty").style.display = pending.length ? "none" : "block";
  pending.forEach((j) => box.append(pendingCard(j)));
}

function pendingCard(j) {
  const card = el("div", "card");
  const head = el("div", "card-head");
  const left = el("div");
  left.append(el("h3", null, esc(j.title || "Untitled role")),
    el("div", "co", esc([j.company, j.location].filter(Boolean).join(" · "))));
  head.append(left, el("div", "score " + scoreClass(j.score), (j.score ?? "—") + ""));
  card.append(head);
  if (j.rationale) card.append(el("div", "rationale", esc(j.rationale)));

  const actions = el("div", "card-actions");
  const view = el("button", null, "View / copy");
  view.onclick = () => openDetail(j.id);
  const applied = el("button", "approve", "Mark applied");
  applied.onclick = () => act("/approve/" + j.id);
  const skip = el("button", "reject", "Skip");
  skip.onclick = () => act("/reject/" + j.id);
  actions.append(view, applied, skip);
  card.append(actions);
  return card;
}

function renderTable() {
  const filter = $("#statusFilter").value;
  const rows = state.jobs.filter((j) => !filter || j.status === filter);
  const tb = $("#jobsTable tbody");
  tb.innerHTML = "";
  rows.forEach((j) => {
    const tr = el("tr");
    tr.append(
      el("td", null, `<span class="score ${scoreClass(j.score)}">${j.score ?? "—"}</span>`),
      el("td", null, esc(j.title || "—")),
      el("td", null, esc(j.company || "—")),
      el("td", null, `<span class="badge ${j.status}">${j.status}</span>`),
    );
    const act = el("td");
    const btn = el("button", "linkbtn", "View");
    btn.onclick = () => openDetail(j.id);
    act.append(btn);
    tr.append(act);
    tb.append(tr);
  });
}

function renderAll() { renderStats(); renderPending(); renderTable(); }

// ── detail modal ────────────────────────────────────────────────────────────
function openDetail(id) {
  const j = state.jobs.find((x) => x.id === id);
  if (!j) return;
  const b = $("#modalBody");
  b.innerHTML = "";
  b.append(el("h3", null, esc(j.title || "Untitled role")));
  b.append(el("div", "co", esc([j.company, j.location].filter(Boolean).join(" · "))));
  if (j.url) b.append(el("p", null, `<a class="linkbtn" href="${esc(j.url)}" target="_blank" rel="noopener">Open posting ↗</a>`));
  b.append(el("p", null, `Score: <b class="${scoreClass(j.score)}">${j.score ?? "—"}</b> · Status: <span class="badge ${j.status}">${j.status}</span>`));
  if (j.rationale) b.append(el("p", "rationale", esc(j.rationale)));

  if (j.cover_letter) {
    b.append(copyBar("Cover letter", j.cover_letter));
    b.append(el("pre", null, esc(j.cover_letter)));
  }
  const answers = j.answers || {};
  const keys = Object.keys(answers);
  if (keys.length) {
    b.append(el("h4", null, "Screening answers"));
    keys.forEach((q) => {
      const qa = el("div", "qa");
      qa.append(el("div", "q", esc(q)), el("div", "a", esc(answers[q] || "—")));
      b.append(qa);
    });
  }

  const bar = el("div", "card-actions");
  const rescore = el("button", null, "Re-score");
  rescore.onclick = () => { act("/rescore/" + j.id); closeModal(); };
  const applied = el("button", "approve", "Mark applied");
  applied.onclick = () => { act("/approve/" + j.id); closeModal(); };
  const skip = el("button", "reject", "Skip");
  skip.onclick = () => { act("/reject/" + j.id); closeModal(); };
  bar.append(rescore, applied, skip);
  b.append(bar);

  $("#modal").classList.remove("hidden");
}
function copyBar(title, text) {
  const bar = el("div", "copybar");
  bar.append(el("h4", null, esc(title)));
  const btn = el("button", null, "Copy");
  btn.onclick = async () => {
    try { await navigator.clipboard.writeText(text); btn.textContent = "Copied"; }
    catch { btn.textContent = "Select & copy"; }
    setTimeout(() => (btn.textContent = "Copy"), 1500);
  };
  bar.append(btn);
  return bar;
}
function closeModal() { $("#modal").classList.add("hidden"); }

// ── actions ─────────────────────────────────────────────────────────────────
async function act(path) { await api(path, "POST"); await refresh(); }

async function refresh() {
  const [jobsRes, stats] = await Promise.all([api("/jobs"), api("/stats")]);
  state.jobs = jobsRes.jobs || [];
  state.stats = stats;
  state.kill = !!stats.kill_switch;
  updateKillBtn();
  renderAll();
}

function updateKillBtn() {
  const btn = $("#killBtn");
  if (state.kill) { btn.textContent = "RESUME"; btn.classList.add("paused"); }
  else { btn.textContent = "STOP"; btn.classList.remove("paused"); }
}

// ── profile editor ──────────────────────────────────────────────────────────
const PROFILE_FIELDS = [
  ["full_name", "Full name", "text"],
  ["current_title", "Current title", "text"],
  ["years_experience", "Years experience", "number"],
  ["keywords", "Keywords", "list"],
  ["target_titles", "Target titles", "list"],
  ["locations", "Locations", "list"],
  ["min_salary", "Minimum salary", "number"],
  ["seniority", "Seniority", "text"],
  ["work_authorization", "Work authorization", "text"],
  ["companies_exclude", "Exclude companies", "list"],
  ["match_threshold", "Match threshold (0-100)", "number"],
];
let PROFILE = {};
async function loadProfile() {
  PROFILE = await api("/profile");
  const form = $("#profileForm");
  form.innerHTML = "";
  PROFILE_FIELDS.forEach(([key, label, type]) => {
    const lab = el("label", null, esc(label));
    const inp = el("input");
    inp.id = "p-" + key;
    inp.type = type === "number" ? "number" : "text";
    const v = PROFILE[key];
    inp.value = Array.isArray(v) ? v.join(", ") : (v == null ? "" : v);
    inp.dataset.type = type;
    lab.append(inp);
    form.append(lab);
  });
}
async function saveProfile() {
  const patch = {};
  PROFILE_FIELDS.forEach(([key, , type]) => {
    const inp = $("#p-" + key);
    if (type === "list") patch[key] = inp.value.split(",").map((s) => s.trim()).filter(Boolean);
    else if (type === "number") patch[key] = inp.value === "" ? null : Number(inp.value);
    else patch[key] = inp.value;
  });
  await api("/profile", "PUT", { profile: patch });
  $("#saveProfileBtn").textContent = "Saved ✓";
  setTimeout(() => ($("#saveProfileBtn").textContent = "Save profile"), 1500);
}

// ── CV upload / onboarding ───────────────────────────────────────────────────
let cvUploaded = false;
async function loadCvStatus() {
  const r = await api("/resume");
  cvUploaded = r.source && r.source !== "none";
  const s = $("#cvStatus");
  if (s) {
    s.textContent = cvUploaded
      ? `CV parsed (${r.source}) — ${(r.skills || []).length} skills found. Profile auto-filled below.`
      : "No CV uploaded yet.";
  }
  $("#onboard").classList.toggle("hidden", cvUploaded);
}

async function uploadCv() {
  const input = $("#cvFile");
  const f = input.files[0];
  if (!f) return;
  const btn = $("#uploadBtn");
  btn.textContent = "Parsing…"; btn.disabled = true;
  try {
    const fd = new FormData();
    fd.append("file", f);
    const res = await fetch("/api/resume/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) {
      btn.textContent = data.detail || "Upload failed";
    } else {
      btn.textContent = `Parsed ✓ (${data.skills_found} skills)`;
      input.value = "";
      await loadProfile();
      await loadCvStatus();
      await refresh();
    }
  } catch (e) {
    btn.textContent = "Upload failed";
  }
  setTimeout(() => { btn.textContent = "Upload & parse CV"; btn.disabled = false; }, 2200);
}

// ── search links ────────────────────────────────────────────────────────────
async function loadLinks() {
  const dp = $("#datePosted").value;
  const remote = $("#remoteOnly").checked;
  const box = $("#searchLinks");
  box.innerHTML = "<p class='hint'>Building links…</p>";
  const res = await api(`/links?date_posted=${dp}&remote_only=${remote}`);
  box.innerHTML = "";
  const list = res.links || [];
  if (!list.length) {
    box.innerHTML = "<p class='empty'>Add target titles or keywords in Profile to generate searches.</p>";
    return;
  }
  list.forEach((l) => {
    const a = el("a", "searchlink");
    a.href = l.url;
    a.target = "_blank";
    a.rel = "noopener";
    a.innerHTML = `<span>${esc(l.label)}</span><span class="go">Search ↗</span>`;
    box.append(a);
  });
}

// ── websocket ───────────────────────────────────────────────────────────────
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  ws.onopen = () => $("#conn").classList.add("ok");
  ws.onclose = () => { $("#conn").classList.remove("ok"); setTimeout(connect, 2500); };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "snapshot") {
      state.jobs = msg.jobs || [];
      state.kill = !!msg.kill_switch;
      updateKillBtn(); refresh();
    } else {
      // Any mutation event: cheap full refresh keeps the UI simple & correct.
      refresh();
      if (msg.type === "resume_uploaded") loadCvStatus();
    }
  };
}

// ── wiring ──────────────────────────────────────────────────────────────────
document.querySelectorAll(".tabs button").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "profile") { loadProfile(); loadCvStatus(); }
    if (btn.dataset.tab === "search") loadLinks();
  };
});

function gotoProfile() {
  document.querySelector('.tabs button[data-tab="profile"]').click();
}
$("#onboardGo").onclick = gotoProfile;
$("#uploadBtn").onclick = uploadCv;

$("#statusFilter").onchange = renderTable;
$("#datePosted").onchange = loadLinks;
$("#remoteOnly").onchange = loadLinks;
$("#modalClose").onclick = closeModal;
$("#modal").onclick = (e) => { if (e.target.id === "modal") closeModal(); };
$("#saveProfileBtn").onclick = saveProfile;

$("#addBtn").onclick = async () => {
  const job = {
    title: $("#f-title").value, company: $("#f-company").value,
    location: $("#f-location").value, url: $("#f-url").value,
    description: $("#f-description").value,
  };
  if (!job.description.trim() && !job.title.trim()) return;
  await api("/jobs", "POST", job);
  ["title", "company", "location", "url", "description"].forEach((k) => ($("#f-" + k).value = ""));
  document.querySelector('.tabs button[data-tab="pending"]').click();
  await refresh();
};

// Kill switch with confirm
$("#killBtn").onclick = () => {
  if (state.kill) { act("/resume"); return; }  // resume needs no confirm
  $("#killModal").classList.remove("hidden");
};
$("#killCancel").onclick = () => $("#killModal").classList.add("hidden");
$("#killConfirm").onclick = () => { act("/kill"); $("#killModal").classList.add("hidden"); };

connect();
refresh();
loadCvStatus();
