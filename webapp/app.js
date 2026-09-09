const tg = window.Telegram?.WebApp;

const ICONS = {
  home:  '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  list:  '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1.5"/><circle cx="3.5" cy="12" r="1.5"/><circle cx="3.5" cy="18" r="1.5"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 5.5a3.5 3.5 0 0 1 0 7M17.5 20a6.4 6.4 0 0 0-2-4.6"/>',
  user:  '<circle cx="12" cy="8" r="3.75"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/>',
  bell:  '<path d="M6 9a6 6 0 1 1 12 0c0 4 1.5 5.5 1.5 5.5h-15S6 13 6 9z"/><path d="M10 18a2 2 0 0 0 4 0"/>',
  inbox: '<path d="M4 13h4l1.5 3h5L16 13h4"/><path d="M4 13 6 5h12l2 8v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5.2l3.2 2"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  alert: '<path d="M12 4.5 21 19.5H3z"/><path d="M12 10v4M12 16.6v.1"/>',
};

let ME = null;
let inviteRole = "employee";

function drawIcons(root = document) {
  root.querySelectorAll("[data-ico]").forEach((el) => {
    const path = ICONS[el.dataset.ico];
    if (!path || el.dataset.drawn) return;
    el.dataset.drawn = "1";
    el.innerHTML =
      `<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
  });
}

function show(id) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
  window.scrollTo(0, 0);
}

function toast(text) {
  const el = document.getElementById("toast");
  el.textContent = text;
  el.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add("hidden"), 2600);
}

function initials(name) {
  return (name || "?").split(/\s+/).slice(0, 2).map((w) => w[0] || "").join("").toUpperCase();
}

function avatarHtml(person, cls = "avatar") {
  return person.photo
    ? `<img class="${cls}" src="${person.photo}" alt="">`
    : `<div class="${cls}">${initials(person.name)}</div>`;
}

async function call(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Init-Data": tg?.initData || "",
      ...(options.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || "xato"), { data });
  return data;
}

/* ---------- Asosiy ekran ---------- */

function fillMain(me) {
  ME = me;
  document.getElementById("head-company").textContent = me.company;
  document.getElementById("head-sub").textContent = me.department || "Yordamchi AI";
  document.getElementById("me-name").textContent = me.name;
  document.getElementById("me-role").textContent = me.role_name;
  document.getElementById("pr-name").textContent = me.name;
  document.getElementById("pr-sub").textContent =
    (me.username ? "@" + me.username + " · " : "") + me.role_name;

  const s = me.stats;
  document.getElementById("st-new").textContent = s.new;
  document.getElementById("st-doing").textContent = s.doing;
  document.getElementById("st-done").textContent = s.done;
  document.getElementById("st-late").textContent = s.late;
  document.getElementById("me-today").textContent = s.new + s.doing;

  document.getElementById("me-avatar").outerHTML = avatarHtml(me, "avatar").replace(
    "class=\"avatar\"", "class=\"avatar\" id=\"me-avatar\"");
  document.getElementById("pr-avatar").outerHTML = avatarHtml(me, "avatar").replace(
    "class=\"avatar\"", "class=\"avatar\" id=\"pr-avatar\"");

  const active = me.tasks.filter((t) => t.status !== "done").slice(0, 6);
  document.getElementById("task-list").innerHTML = active.length
    ? active.map(taskHtml).join("")
    : `<div class="empty">Hozircha vazifa yo'q.<br>Guruhda topshiriq berilganda shu yerda paydo bo'ladi.</div>`;

  show("screen-main");
  drawIcons();
}

/* ---------- Vazifalar ---------- */

const CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>';

function taskHtml(t) {
  const cls = t.late ? "late" : t.status;
  const meta = [];
  if (!t.mine && t.assignee.name) meta.push(t.assignee.name);
  if (t.due_h) meta.push(t.late ? `<span class="late-word">${t.due_h} — kechikdi</span>` : t.due_h);
  if (t.author && t.mine) meta.push(t.author);

  return `
    <div class="task ${cls}" data-id="${t.id}">
      <button class="task-check" data-action="cycle" data-id="${t.id}" data-status="${t.status}">${CHECK}</button>
      <div class="task-body">
        <div class="task-text">${escapeHtml(t.text)}</div>
        ${meta.length ? `<div class="task-meta">${meta.join(" · ")}</div>` : ""}
      </div>
      ${t.status === "doing" ? '<span class="tag doing">Jarayonda</span>' : ""}
    </div>`;
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

let taskFilter = "active";
let taskScope = "mine";

async function loadTasks() {
  const box = document.getElementById("tasks-full");
  box.innerHTML = `<div class="empty">Yuklanmoqda…</div>`;

  let data;
  try {
    data = await call(`/api/tasks?scope=${taskScope}`);
  } catch (e) {
    box.innerHTML = `<div class="empty">Ma'lumot yuklanmadi.</div>`;
    return;
  }

  document.getElementById("scope-filters").classList.toggle("hidden", !data.boss);

  const list = data.tasks.filter((t) =>
    taskFilter === "all" ? true : taskFilter === "done" ? t.status === "done" : t.status !== "done");

  box.innerHTML = list.length
    ? list.map(taskHtml).join("")
    : `<div class="empty">Bu bo'limda vazifa yo'q.</div>`;
}

async function cycleStatus(id, current) {
  const next = { new: "doing", doing: "done", done: "new" }[current] || "doing";
  try {
    await call(`/api/task/${id}/status`, { method: "POST", body: JSON.stringify({ status: next }) });
    tg?.HapticFeedback?.impactOccurred?.("light");
  } catch (e) {
    return toast("O'zgartirilmadi");
  }
  toast({ doing: "Boshlandi", done: "Bajarildi ✅", new: "Qaytarildi" }[next]);
  ME = await call("/api/me");
  fillMain(ME);
  if (!document.getElementById("tab-tasks").classList.contains("hidden")) loadTasks();
}

/* ---------- Jamoa ---------- */

async function loadTeam() {
  const box = document.getElementById("invite-box");
  const list = document.getElementById("team-list");
  list.innerHTML = `<div class="empty">Yuklanmoqda…</div>`;

  let data;
  try {
    data = await call("/api/team");
  } catch (e) {
    list.innerHTML = `<div class="empty">Ma'lumot yuklanmadi.</div>`;
    return;
  }

  box.innerHTML = data.can_invite
    ? `<div class="chips">
         <button class="chip on" data-role="employee">Xodim</button>
         <button class="chip" data-role="head">Bo'lim boshlig'i</button>
       </div>
       <button class="btn btn-primary" data-action="make-invite">Taklif havolasi yaratish</button>
       <div id="invite-result"></div>`
    : "";

  box.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      box.querySelectorAll(".chip").forEach((c) => c.classList.remove("on"));
      chip.classList.add("on");
      inviteRole = chip.dataset.role;
    });
  });

  list.innerHTML =
    `<div class="section-title">Xodimlar · ${data.team.length}</div>` +
    data.team.map((p) => `
      <div class="row">
        ${avatarHtml(p)}
        <div class="who">
          <div class="who-name">${p.name}</div>
          <div class="who-sub">${p.username ? "@" + p.username : (p.department || "—")}</div>
        </div>
        <span class="tag ${p.role}">${roleName(p.role)}</span>
      </div>`).join("");
}

function roleName(role) {
  return { owner: "Rahbar", head: "Bo'lim boshlig'i", employee: "Xodim" }[role] || "Xodim";
}

async function makeInvite() {
  try {
    const inv = await call("/api/invite", {
      method: "POST",
      body: JSON.stringify({ role: inviteRole }),
    });
    document.getElementById("invite-result").innerHTML = `
      <div class="invite-card">
        <div class="invite-note">${roleName(inv.role)} uchun taklif kodi</div>
        <div class="invite-code">${inv.code}</div>
        <div class="invite-note">Havolani xodimga yuboring — u bosishi bilan jamoaga qo'shiladi.</div>
        <button class="btn btn-primary" data-action="share-invite" data-link="${inv.link}">Havolani yuborish</button>
      </div>`;
  } catch (e) {
    toast("Havola yaratilmadi");
  }
}

/* ---------- Tugmalar ---------- */

document.addEventListener("click", async (ev) => {
  const el = ev.target.closest("[data-action]");
  if (!el) return;
  const action = el.dataset.action;

  if (action === "go-create") show("screen-create");
  if (action === "go-join") show("screen-join");
  if (action === "back-start") show("screen-start");

  if (action === "create-company") {
    const name = document.getElementById("inp-company").value.trim();
    if (name.length < 2) return toast("Nomni kiriting");
    el.disabled = true;
    try {
      fillMain(await call("/api/company", { method: "POST", body: JSON.stringify({ name }) }));
    } catch (e) {
      toast("Yaratilmadi, qaytadan urining");
    }
    el.disabled = false;
  }

  if (action === "join") {
    const code = document.getElementById("inp-code").value.trim().toUpperCase();
    if (code.length !== 6) return toast("6 belgili kodni kiriting");
    el.disabled = true;
    try {
      fillMain(await call("/api/join", { method: "POST", body: JSON.stringify({ code }) }));
    } catch (e) {
      toast("Kod topilmadi yoki ishlatilgan");
    }
    el.disabled = false;
  }

  if (action === "make-invite") makeInvite();

  if (action === "cycle") cycleStatus(el.dataset.id, el.dataset.status);

  if (action === "share-invite") {
    const link = el.dataset.link;
    const text = `${ME.company} jamoasiga qo'shiling:`;
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(
        `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`);
    } else {
      navigator.clipboard?.writeText(link);
      toast("Havola nusxalandi");
    }
  }
});

function setupTabs() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".tab-body").forEach((t) => t.classList.add("hidden"));
      document.getElementById("tab-" + btn.dataset.tab).classList.remove("hidden");
      window.scrollTo(0, 0);
      if (btn.dataset.tab === "team") loadTeam();
      if (btn.dataset.tab === "tasks") loadTasks();
    });
  });

  const pick = (wrap, chip) => {
    wrap.querySelectorAll(".chip").forEach((c) => c.classList.remove("on"));
    chip.classList.add("on");
  };

  document.getElementById("task-filters").addEventListener("click", (ev) => {
    const chip = ev.target.closest(".chip");
    if (!chip) return;
    pick(ev.currentTarget, chip);
    taskFilter = chip.dataset.filter;
    loadTasks();
  });

  document.getElementById("scope-filters").addEventListener("click", (ev) => {
    const chip = ev.target.closest(".chip");
    if (!chip) return;
    pick(ev.currentTarget, chip);
    taskScope = chip.dataset.scope;
    loadTasks();
  });
}

function fail(text) {
  const el = document.getElementById("load-msg");
  el.textContent = text;
  el.classList.remove("hidden");
}

async function boot() {
  drawIcons();
  setupTabs();

  if (tg) {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#2B31E0");
    tg.setBackgroundColor("#F1F3F8");
  }

  let me;
  try {
    me = await call("/api/me");
  } catch (e) {
    fail("Ilovani Telegram orqali oching.");
    return;
  }

  if (me.member) fillMain(me);
  else show("screen-start");
  drawIcons();
}

boot();
