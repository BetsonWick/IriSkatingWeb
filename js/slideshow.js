/* ============================================================
   IriSkating — hero slideshow: photos & videos from training
   ============================================================ */

(function () {
  "use strict";

  /* ---------- EDIT ME: your training media ----------
     1) Drop your files into assets/media/
     2) Add slides below. type: "image" or "video".
        Video: use mp4 (H.264). It plays muted automatically
        while its slide is active; the poster is shown until
        the video loads (and if the file is missing).
        `tag` is the little label on the slide, per language. */
  const HERO_MEDIA = [
    { type: "video", src: "assets/media/training-7.mp4" },   // IMG_9780 — позиция 1
    { type: "video", src: "assets/media/training-1.mp4" },
    { type: "video", src: "assets/media/training-8.mp4" },   // IMG_9781 — позиция 3
    { type: "video", src: "assets/media/training-4.mp4" },
    { type: "video", src: "assets/media/training-9.mp4" },   // IMG_9782 — позиция 5
    { type: "video", src: "assets/media/training-5.mp4" },
    { type: "video", src: "assets/media/training-10.mp4" },  // IMG_9783 — позиция 7
    { type: "video", src: "assets/media/training-2.mp4" },
    { type: "video", src: "assets/media/training-3.mp4" },
    { type: "video", src: "assets/media/training-6.mp4" },
  ];

  const IMAGE_DELAY = 5000; // ms per photo

  let index = 0;
  let timer = null;
  let hovered = false;
  let container, dotsBox;
  const slides = []; // { el, tag, video, working }

  function lang() {
    return (document.documentElement.getAttribute("lang") || "en").slice(0, 2);
  }

  /* ---------- build ---------- */

  function buildSlide(item) {
    const el = document.createElement("div");
    el.className = "hs-slide";

    if (item.type === "video") {
      if (item.poster) {
        const poster = document.createElement("img");
        poster.className = "hs-media";
        poster.src = item.poster;
        poster.alt = "";
        el.appendChild(poster);
      }

      let video = null;
      if (item.src) {
        video = document.createElement("video");
        video.className = "hs-media hs-video";
        video.src = item.src;
        if (item.poster) video.poster = item.poster;
        video.muted = true;
        video.playsInline = true;
        video.preload = "metadata";
        video.setAttribute("muted", "");
        video.setAttribute("playsinline", "");
        video.addEventListener("error", () => {
          video.style.display = "none"; // fall back to poster
        }, { once: true });
        el.appendChild(video);
      }

      const scrim = document.createElement("div");
      scrim.className = "hs-scrim";
      el.appendChild(scrim);

      slides.push({ el, video, playing: false });
      return el;
    }

    const img = document.createElement("img");
    img.className = "hs-media";
    img.src = item.src || "";
    img.alt = "";
    el.appendChild(img);

    const scrim = document.createElement("div");
    scrim.className = "hs-scrim";
    el.appendChild(scrim);

    slides.push({ el, video: null, playing: false });
    return el;
  }

  function buildDots() {
    HERO_MEDIA.forEach((_, i) => {
      const dot = document.createElement("button");
      dot.className = "hs-dot";
      dot.setAttribute("aria-label", `Slide ${i + 1}`);
      dot.addEventListener("click", () => goTo(i, true));
      dotsBox.appendChild(dot);
    });
  }

  /* ---------- playback ---------- */

  function stopVideo(slide) {
    if (slide.video && slide.playing) {
      slide.video.pause();
      try { slide.video.currentTime = 0; } catch (err) { /* noop */ }
      slide.playing = false;
    }
  }

  function playVideo(slide) {
    if (!slide.video || slide.video.style.display === "none") return false;
    const p = slide.video.play();
    if (p && typeof p.catch === "function") {
      p.catch(() => { /* autoplay blocked — timer keeps going */ });
    }
    slide.playing = true;
    return true;
  }

  function applyActive() {
    slides.forEach((s, i) => {
      const active = i === index;
      s.el.classList.toggle("active", active);
      if (!active) stopVideo(s);
    });
    [...dotsBox.children].forEach((d, i) => d.classList.toggle("active", i === index));
  }

  function goTo(i) {
    if (i === index) { applyActive(); schedule(); return; }
    index = (i + slides.length) % slides.length;
    applyActive();
    schedule();
  }

  function next() { goTo((index + 1) % slides.length); }
  function prev() { goTo((index - 1 + slides.length) % slides.length); }

  function schedule() {
    clearTimeout(timer);
    const current = slides[index];
    if (current && playVideo(current)) {
      // advance when the video ends (fallback: 3 min in case 'ended' never fires)
      current.video.addEventListener("ended", next, { once: true });
      timer = setTimeout(next, 180000);
      return;
    }
    timer = setTimeout(next, IMAGE_DELAY);
  }

  function restartCurrent() {
    const current = slides[index];
    if (current && current.video && current.playing) {
      stopVideo(current);
    }
    applyActive();
    schedule();
  }

  /* ---------- events ---------- */

  function init() {
    container = document.getElementById("heroMedia");
    if (!container) return;

    HERO_MEDIA.forEach((item) => container.appendChild(buildSlide(item)));

    const art = container.closest(".hero-art");
    dotsBox = document.createElement("div");
    dotsBox.className = "hs-dots";
    art.appendChild(dotsBox);
    buildDots();

    const prevBtn = art.querySelector(".hs-prev");
    const nextBtn = art.querySelector(".hs-next");
    if (prevBtn) prevBtn.addEventListener("click", prev);
    if (nextBtn) nextBtn.addEventListener("click", next);

    art.addEventListener("mouseenter", () => {
      hovered = true;
      clearTimeout(timer);
    });
    art.addEventListener("mouseleave", () => {
      hovered = false;
      schedule();
    });

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
