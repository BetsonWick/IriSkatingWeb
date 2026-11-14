/* ============================================================
   IriSkating — admin page logic: login + bookings dashboard
   ============================================================ */

(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  const PROGRAMS = {
    individual: "Индивидуальный онлайн-урок",
    group: "Групповой онлайн-класс",
    video: "Видеоанализ и обратная связь",
    fitness: "SkateFit — программа снижения веса",
  };

  const TIMES = {
    morning: "Утро",
    afternoon: "День",
    evening: "Вечер",
    any: "Любое время",
  };

  const METHODS = {
    telegram: "Telegram",
    instagram: "Instagram",
    whatsapp: "WhatsApp",
    email: "Email",
  };

  const STATUS_LABELS = {
    new: "новая",
    confirmed: "подтверждена",
    cancelled: "отменена",
  };

  let toastTimer = null;

  function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
  }

  function showView(name) {
    $("#loginView").hidden = name !== "login";
    $("#dashView").hidden = name !== "dash";
    $("#logoutBtn").hidden = name !== "dash";
  }

  async function api(path, options) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (response.status === 401) {
      showView("login");
      throw new Error("unauthorized");
    }
    if (!response.ok) {
      let detail = String(response.status);
      try {
        const body = await response.json();
        if (body && body.detail) detail = String(body.detail);
      } catch (err) {
        /* not json */
      }
      throw new Error(detail);
    }
    return response.json();
  }

  /* ---------- login ---------- */

  $("#loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = $("#loginError");
    error.hidden = true;
    try {
      await api("/api/login", {
        method: "POST",
        body: JSON.stringify({
          username: $("#loginUser").value.trim(),
          password: $("#loginPass").value,
        }),
      });
      $("#loginPass").value = "";
      await enterDashboard();
    } catch (err) {
      error.textContent =
        err.message === "unauthorized"
          ? "Неверный логин или пароль."
          : `Ошибка: ${err.message}`;
      error.hidden = false;
    }
  });

  $("#logoutBtn").addEventListener("click", async () => {
    try {
      await api("/api/logout", { method: "POST" });
    } catch (err) {
      /* session already gone */
    }
    showView("login");
  });

  /* ---------- dashboard ---------- */

  function statusChip(status) {
    const chip = document.createElement("span");
    chip.className = `status-chip status-${status}`;
    chip.textContent = STATUS_LABELS[status] || status;
    return chip;
  }

  function actionButtons(booking) {
    const wrap = document.createElement("div");
    wrap.className = "row-actions";

    if (booking.status !== "confirmed") {
      const confirm = document.createElement("button");
      confirm.className = "icon-btn confirm";
      confirm.title = "Подтвердить";
      confirm.innerHTML = '<svg class="icon"><use href="#i-check"/></svg>';
      confirm.addEventListener("click", () => setStatus(booking.id, "confirmed"));
      wrap.appendChild(confirm);
    }
    if (booking.status !== "cancelled") {
      const cancel = document.createElement("button");
      cancel.className = "icon-btn cancel";
      cancel.title = "Отменить";
      cancel.innerHTML = '<svg class="icon"><use href="#i-close"/></svg>';
      cancel.addEventListener("click", () => setStatus(booking.id, "cancelled"));
      wrap.appendChild(cancel);
    }
    if (booking.status !== "new") {
      const reopen = document.createElement("button");
      reopen.className = "icon-btn";
      reopen.title = "Вернуть в новые";
      reopen.innerHTML = '<svg class="icon"><use href="#i-refresh"/></svg>';
      reopen.addEventListener("click", () => setStatus(booking.id, "new"));
      wrap.appendChild(reopen);
    }
    return wrap;
  }

  async function setStatus(id, status) {
    try {
      await api(`/api/bookings/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await loadBookings();
      showToast(STATUS_LABELS[status] ? `Статус: ${STATUS_LABELS[status]}` : "Обновлено");
    } catch (err) {
      if (err.message !== "unauthorized") showToast(`Ошибка: ${err.message}`);
    }
  }

  async function loadBookings() {
    const body = $("#bookingsBody");
    body.innerHTML = '<tr><td colspan="10" class="empty-row">Загрузка…</td></tr>';
    try {
      const bookings = await api("/api/bookings");
      if (bookings.length === 0) {
        body.innerHTML =
          '<tr><td colspan="10" class="empty-row">Пока заявок нет — они появятся здесь после отправки формы на сайте.</td></tr>';
        return;
      }
      body.innerHTML = "";
      bookings.forEach((b) => {
        const row = document.createElement("tr");
        const cells = [
          String(b.id),
          b.created_at,
          b.name,
          b.contact,
          METHODS[b.contact_method] || b.contact_method || "—",
          PROGRAMS[b.program] || b.program,
          b.preferred_date,
          TIMES[b.preferred_time] || b.preferred_time,
          b.comment || "—",
        ];
        cells.forEach((text, i) => {
          const td = document.createElement("td");
          if (i === 1) td.className = "b-date";
          if (i === 7) td.className = "b-comment";
          td.textContent = text;
          row.appendChild(td);
        });
        const statusTd = document.createElement("td");
        statusTd.appendChild(statusChip(b.status));
        row.appendChild(statusTd);
        const actionsTd = document.createElement("td");
        actionsTd.appendChild(actionButtons(b));
        row.appendChild(actionsTd);
        body.appendChild(row);
      });
    } catch (err) {
      if (err.message !== "unauthorized") {
        body.innerHTML = `<tr><td colspan="10" class="empty-row">Ошибка загрузки: ${err.message}</td></tr>`;
      }
    }
  }

  /* ---------- stats (visits / bookings by country) ---------- */

  const statsState = { data: null, window: "24h" };

  function statsRow(text, colspan = 4) {
    return `<tr><td colspan="${colspan}" class="empty-row">${text}</td></tr>`;
  }

  function renderStats() {
    const body = $("#statsBody");
    const foot = $("#statsFoot");
    const note = $("#statsNote");
    const data = statsState.data;
    if (!data) return;

    const baseNote =
      "Источник — Prometheus (те же данные, что в Grafana). «XX» — страна посетителя не определена (заход не через Cloudflare).";

    if (!data.prometheus_ok) {
      body.innerHTML = statsRow("Prometheus недоступен — статистика появится, когда он ответит.");
      foot.hidden = true;
      note.textContent = baseNote;
      return;
    }

    const window_ = data.windows.find((w) => w.key === statsState.window);
    if (!window_ || window_.countries.length === 0) {
      body.innerHTML = statsRow(`Пока нет визитов за ${window_ ? window_.label : statsState.window}.`);
      foot.hidden = true;
      note.textContent = baseNote;
      return;
    }

    body.innerHTML = "";
    window_.countries.forEach((row) => {
      const conversion =
        row.visits > 0 ? ((row.bookings / row.visits) * 100).toFixed(1) + "%" : "—";
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${row.country}</td>` +
        `<td class="num">${Math.round(row.visits)}</td>` +
        `<td class="num">${Math.round(row.bookings)}</td>` +
        `<td class="num">${conversion}</td>`;
      body.appendChild(tr);
    });

    const totalConversion =
      window_.visits > 0 ? ((window_.bookings / window_.visits) * 100).toFixed(1) + "%" : "—";
    foot.hidden = false;
    foot.innerHTML =
      `<tr><td>Итого</td>` +
      `<td class="num">${Math.round(window_.visits)}</td>` +
      `<td class="num">${Math.round(window_.bookings)}</td>` +
      `<td class="num">${totalConversion}</td></tr>`;

    const at = data.generated_at ? new Date(data.generated_at).toLocaleString("ru-RU") : "";
    note.textContent = baseNote + (at ? ` Данные на ${at}.` : "");
  }

  async function loadStats() {
    const body = $("#statsBody");
    body.innerHTML = statsRow("Загрузка…");
    try {
      statsState.data = await api("/api/stats");
      renderStats();
    } catch (err) {
      if (err.message !== "unauthorized") {
        body.innerHTML = statsRow(`Ошибка загрузки статистики: ${err.message}`);
      }
    }
  }

  $("#statsToggle").addEventListener("click", (event) => {
    const btn = event.target.closest(".chip-btn");
    if (!btn) return;
    statsState.window = btn.dataset.window;
    document
      .querySelectorAll("#statsToggle .chip-btn")
      .forEach((b) => b.classList.toggle("active", b === btn));
    renderStats();
  });

  async function enterDashboard() {
    showView("dash");
    await loadBookings();
    loadStats();
  }

  $("#refreshBtn").addEventListener("click", async () => {
    await loadBookings();
    loadStats();
  });

  /* ---------- boot ---------- */

  (async () => {
    try {
      const me = await api("/api/me");
      if (me && me.username) {
        await enterDashboard();
        return;
      }
    } catch (err) {
      /* not logged in */
    }
    showView("login");
  })();
})();
