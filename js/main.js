/* ============================================================
   IriSkating — page logic
   Language switching, header, booking modal (prototype), toast
   ============================================================ */

(function () {
  "use strict";

  const { I18N, LANGS, t } = window.IRI_I18N;
  const STORAGE_KEY = "iriskating_lang";
  const BOOKINGS_KEY = "iriskating_bookings";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  /* ============================================================
     i18n
     ============================================================ */

  function applyLang(lang) {
    const dict = I18N[lang] ? lang : "en";

    $$("[data-i18n]").forEach((el) => {
      const value = t(dict, el.getAttribute("data-i18n"));
      if (value !== undefined) el.textContent = value;
    });

    $$("[data-i18n-ph]").forEach((el) => {
      const value = t(dict, el.getAttribute("data-i18n-ph"));
      if (value !== undefined) el.setAttribute("placeholder", value);
    });

    $$("[data-i18n-aria]").forEach((el) => {
      const value = t(dict, el.getAttribute("data-i18n-aria"));
      if (value !== undefined) el.setAttribute("aria-label", value);
    });

    document.documentElement.setAttribute("lang", dict === "zh" ? "zh-CN" : dict);

    const meta = LANGS.find((l) => l.code === dict);
    $("#langCurrent").textContent = meta ? meta.short : "EN";

    $$("#langMenu li").forEach((li) => {
      li.setAttribute("aria-selected", String(li.getAttribute("data-lang") === dict));
    });

    try {
      localStorage.setItem(STORAGE_KEY, dict);
    } catch (err) {
      /* storage unavailable — fine for a prototype */
    }

    // let dynamic components (hero slideshow) re-render localized bits
    document.dispatchEvent(new CustomEvent("irilang", { detail: { lang: dict } }));
  }

  function initLang() {
    let saved = null;
    try {
      saved = localStorage.getItem(STORAGE_KEY);
    } catch (err) {
      /* ignore */
    }
    // English is the default; only an explicit saved choice overrides it
    applyLang(saved || "en");

    const select = $("#langSelect");
    const btn = $("#langBtn");
    const menu = $("#langMenu");

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = select.classList.toggle("open");
      btn.setAttribute("aria-expanded", String(open));
    });

    menu.addEventListener("click", (e) => {
      const li = e.target.closest("li[data-lang]");
      if (!li) return;
      applyLang(li.getAttribute("data-lang"));
      select.classList.remove("open");
      btn.setAttribute("aria-expanded", "false");
    });

    document.addEventListener("click", () => {
      select.classList.remove("open");
      btn.setAttribute("aria-expanded", "false");
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        select.classList.remove("open");
        btn.setAttribute("aria-expanded", "false");
      }
    });
  }

  /* ============================================================
     Header: scroll state, burger, active nav link
     ============================================================ */

  function initHeader() {
    const header = $("#siteHeader");
    const onScroll = () => header.classList.toggle("scrolled", window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    const burger = $("#burger");
    burger.addEventListener("click", () => {
      const open = document.body.classList.toggle("nav-open");
      burger.setAttribute("aria-expanded", String(open));
    });

    // close mobile nav after clicking a link
    $$(".main-nav .nav-link").forEach((link) => {
      link.addEventListener("click", () => {
        document.body.classList.remove("nav-open");
        burger.setAttribute("aria-expanded", "false");
      });
    });

    // highlight active section
    const links = $$(".main-nav .nav-link");
    const sections = links
      .map((link) => $(link.getAttribute("href")))
      .filter(Boolean);

    const spy = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          links.forEach((link) =>
            link.classList.toggle("active", link.getAttribute("href") === `#${entry.target.id}`)
          );
        });
      },
      { rootMargin: "-35% 0px -55% 0px" }
    );
    sections.forEach((sec) => spy.observe(sec));
  }

  /* ============================================================
     Toast
     ============================================================ */

  let toastTimer = null;

  function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
  }

  function initProtoButtons() {
    $$("[data-proto]").forEach((el) => {
      el.addEventListener("click", (e) => {
        if (el.tagName === "A") e.preventDefault();
        const kind = el.getAttribute("data-proto");
        showToast(kind === "video" ? t(currentLang(), "toast.video") : t(currentLang(), "toast.proto"));
      });
    });
  }

  function currentLang() {
    return document.documentElement.getAttribute("lang").slice(0, 2) || "en";
  }

  /* ============================================================
     Booking modal (prototype)
     ============================================================ */

  const modal = () => $("#bookModal");

  function openModal(lessonType) {
    const overlay = modal();
    resetModalView();
    if (lessonType) $("#bkType").value = lessonType;
    overlay.classList.add("open");
    overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    setTimeout(() => $("#bkName").focus(), 120);
  }

  function closeModal() {
    const overlay = modal();
    overlay.classList.remove("open");
    overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function resetModalView() {
    $("#bookFormView").hidden = false;
    $("#bookSuccessView").hidden = true;
    $("#bookError").hidden = true;
    $$("#bookForm .invalid").forEach((el) => el.classList.remove("invalid"));
  }

  function typeLabel(value) {
    return t(currentLang(), `modal.${value}`) || value;
  }

  function timeLabel(value) {
    return t(currentLang(), `modal.${value}`) || value;
  }

  function saveBooking(data) {
    try {
      const list = JSON.parse(localStorage.getItem(BOOKINGS_KEY) || "[]");
      list.push(Object.assign({ ts: new Date().toISOString() }, data));
      localStorage.setItem(BOOKINGS_KEY, JSON.stringify(list));
    } catch (err) {
      /* prototype: storage may be unavailable */
    }
  }

  function initModal() {
    $$("[data-book]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const type = btn.getAttribute("data-book");
        openModal(I18N[currentLang()] && $("#bkType").querySelector(`option[value="${type}"]`) ? type : null);
      });
    });

    $("#bookClose").addEventListener("click", closeModal);
    $("#bookDone").addEventListener("click", closeModal);
    $("#bookAgain").addEventListener("click", () => {
      resetModalView();
      $("#bookForm").reset();
    });

    modal().addEventListener("click", (e) => {
      if (e.target === modal()) closeModal();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal().classList.contains("open")) closeModal();
    });

    // min date = today
    const dateInput = $("#bkDate");
    dateInput.min = new Date().toISOString().split("T")[0];

    $("#bookForm").addEventListener("submit", (e) => {
      e.preventDefault();

      const name = $("#bkName");
      const contact = $("#bkContact");
      const date = $("#bkDate");
      let valid = true;

      [name, contact, date].forEach((field) => {
        const ok = field.value.trim().length > 0;
        field.classList.toggle("invalid", !ok);
        if (!ok) valid = false;
      });

      if (!valid) {
        const err = $("#bookError");
        err.textContent =
          currentLang() === "ru"
            ? "Заполните имя, контакт и дату."
            : currentLang() === "fr"
              ? "Veuillez renseigner le nom, le contact et la date."
              : currentLang() === "zh"
                ? "请填写姓名、联系方式和日期。"
                : "Please fill in name, contact and date.";
        err.hidden = false;
        return;
      }

      const data = {
        name: name.value.trim(),
        contact: contact.value.trim(),
        type: $("#bkType").value,
        date: date.value,
        time: $("#bkTime").value,
        comment: $("#bkComment").value.trim(),
      };
      saveBooking(data);

      $("#bookSummary").innerHTML = "";
      [typeLabel(data.type), data.date, timeLabel(data.time)].forEach((txt) => {
        const chip = document.createElement("span");
        chip.textContent = txt;
        $("#bookSummary").appendChild(chip);
      });

      $("#bookFormView").hidden = true;
      $("#bookSuccessView").hidden = false;
    });
  }

  /* ============================================================
     Reveal-on-scroll
     ============================================================ */

  function initReveal() {
    const targets = $$(".offer-card, .tile, .event-card, .news-card, .lesson-card, .contact-row, .coach-photo, .coach-info, .hero-copy, .hero-art");
    targets.forEach((el) => el.classList.add("reveal"));

    // Reveal whatever is inside the viewport. IntersectionObserver is not
    // reliable in inactive/background tabs, so we check rects directly.
    function revealVisible() {
      const vh = window.innerHeight || document.documentElement.clientHeight;
      $$(".reveal:not(.in)").forEach((el) => {
        const r = el.getBoundingClientRect();
        if (r.top < vh * 0.92 && r.bottom > 0) el.classList.add("in");
      });
    }

    window.addEventListener("scroll", revealVisible, { passive: true });
    window.addEventListener("resize", revealVisible, { passive: true });
    revealVisible();

    // Safety net for environments where scroll events are suspended
    // (background tabs, some embedders). Self-cancels once everything is shown.
    let ticks = 0;
    const timer = setInterval(() => {
      ticks += 1;
      revealVisible();
      if (ticks > 200 || document.querySelectorAll(".reveal:not(.in)").length === 0) {
        clearInterval(timer);
      }
    }, 250);
  }

  /* ============================================================
     Boot
     ============================================================ */

  document.addEventListener("DOMContentLoaded", () => {
    initLang();
    initHeader();
    initProtoButtons();
    initModal();
    initReveal();
  });
})();
