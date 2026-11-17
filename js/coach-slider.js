/* ============================================================
   IriSkating — слайдер фотографий тренера (hero1..4)
   Тот же паттерн, что slideshow.js: fade, точки, стрелки, автоплей
   ============================================================ */

(function () {
  "use strict";

  const DELAY = 5000; // ms на фото

  let index = 0;
  let timer = null;
  let slides = [];
  let dotsBox = null;

  function applyActive() {
    slides.forEach((slide, i) => slide.classList.toggle("active", i === index));
    [...dotsBox.children].forEach((dot, i) => dot.classList.toggle("active", i === index));
  }

  function goTo(i) {
    index = (i + slides.length) % slides.length;
    applyActive();
    schedule();
  }

  function next() { goTo(index + 1); }
  function prev() { goTo(index - 1); }

  function schedule() {
    clearTimeout(timer);
    // при prefers-reduced-motion не крутим автоплей — только точки/стрелки
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    timer = setTimeout(next, DELAY);
  }

  function init() {
    const box = document.getElementById("coachSlider");
    if (!box) return;

    slides = [...box.querySelectorAll(".coach-slide")];
    if (slides.length === 0) return;
    dotsBox = box.querySelector(".coach-dots");

    slides.forEach((_, i) => {
      const dot = document.createElement("button");
      dot.className = "hs-dot";
      dot.setAttribute("aria-label", `Photo ${i + 1}`);
      dot.addEventListener("click", () => goTo(i));
      dotsBox.appendChild(dot);
    });

    box.querySelector(".hs-prev").addEventListener("click", prev);
    box.querySelector(".hs-next").addEventListener("click", next);

    // на десктопе пауза при наведении — как в hero-слайдере
    box.addEventListener("mouseenter", () => clearTimeout(timer));
    box.addEventListener("mouseleave", schedule);

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        clearTimeout(timer);
      } else {
        schedule();
      }
    });

    index = 0;
    applyActive();
    schedule();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
