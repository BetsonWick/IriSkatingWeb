/* ============================================================
   IriSkating — benefits text slider (above the Special offer card)
   ============================================================ */

(function () {
  "use strict";

  const DELAY = 6000; // ms per slide

  let index = 0;
  let timer = null;
  let box, dotsBox;
  const slides = []; // .ts-slide elements

  function applyActive() {
    slides.forEach((el, i) => el.classList.toggle("active", i === index));
    [...dotsBox.children].forEach((d, i) => d.classList.toggle("active", i === index));
  }

  function goTo(i) {
    index = (i + slides.length) % slides.length;
    applyActive();
    schedule();
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(() => goTo(index + 1), DELAY);
  }

  function init() {
    box = document.getElementById("benefitSlider");
    if (!box) return;

    slides.push(...box.querySelectorAll(".ts-slide"));
    if (slides.length === 0) return;

    dotsBox = box.querySelector(".ts-dots");
    slides.forEach((_, i) => {
      const dot = document.createElement("button");
      dot.className = "ts-dot";
      dot.setAttribute("aria-label", `Slide ${i + 1}`);
      dot.addEventListener("click", () => goTo(i));
      dotsBox.appendChild(dot);
    });

    const prevBtn = box.querySelector(".ts-prev");
    const nextBtn = box.querySelector(".ts-next");
    if (prevBtn) prevBtn.addEventListener("click", () => goTo(index - 1));
    if (nextBtn) nextBtn.addEventListener("click", () => goTo(index + 1));

    // pause autoplay while the reader looks at the block
    box.addEventListener("mouseenter", () => clearTimeout(timer));
    box.addEventListener("mouseleave", schedule);

    // no autoplay in background tabs
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) clearTimeout(timer);
      else schedule();
    });

    applyActive();
    schedule();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
