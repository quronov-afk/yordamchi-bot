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

function drawIcons(root = document) {
  root.querySelectorAll("[data-ico]").forEach((el) => {
    const path = ICONS[el.dataset.ico];
    if (!path) return;
    el.innerHTML =
      `<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
  });
}

function initials(name) {
  return (name || "?")
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0] || "")
    .join("")
    .toUpperCase();
}

function fillMe(me) {
  document.getElementById("me-name").textContent = me.name;
  document.getElementById("me-role").textContent = me.role;
  document.getElementById("pr-name").textContent = me.name;
  document.getElementById("pr-sub").textContent = me.username ? "@" + me.username : me.role;

  const s = me.stats;
  document.getElementById("st-new").textContent = s.new;
  document.getElementById("st-doing").textContent = s.doing;
  document.getElementById("st-done").textContent = s.done;
  document.getElementById("st-late").textContent = s.late;
  document.getElementById("me-today").textContent = s.new + s.doing;

  for (const id of ["me-avatar", "pr-avatar"]) {
    const box = document.getElementById(id);
    if (me.photo) {
      box.outerHTML = `<img class="avatar" id="${id}" src="${me.photo}" alt="">`;
    } else {
      box.textContent = initials(me.name);
    }
  }

  const list = document.getElementById("task-list");
  list.innerHTML = me.tasks.length
    ? ""
    : `<div class="empty">Hozircha vazifa yo'q.<br>Guruhda topshiriq berilganda shu yerda paydo bo'ladi.</div>`;
}

function setupTabs() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".tab-body").forEach((t) => t.classList.add("hidden"));
      document.getElementById("tab-" + btn.dataset.tab).classList.remove("hidden");
      window.scrollTo(0, 0);
    });
  });
}

function fail(text) {
  document.getElementById("load-msg").textContent = text;
  document.getElementById("load-msg").classList.remove("hidden");
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

  try {
    const res = await fetch("/api/me", {
      headers: { "X-Init-Data": tg?.initData || "" },
    });
    if (!res.ok) {
      fail("Ilovani Telegram orqali oching.");
      return;
    }
    fillMe(await res.json());
  } catch (e) {
    fail("Ulanishda xatolik. Qaytadan urinib ko'ring.");
    return;
  }

  document.getElementById("screen-loading").classList.add("hidden");
  document.getElementById("screen-main").classList.remove("hidden");
}

boot();
