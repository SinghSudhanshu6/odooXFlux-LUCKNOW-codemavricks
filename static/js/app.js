(function () {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduce) {
    document.querySelectorAll(".tilt").forEach((card) => {
      card.addEventListener("pointermove", (e) => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = `perspective(900px) rotateY(${x * 12}deg) rotateX(${-y * 12}deg) translateY(-3px)`;
      });
      card.addEventListener("pointerleave", () => { card.style.transform = ""; });
    });
    const deck = document.querySelector(".deck");
    if (deck) addEventListener("pointermove", (e) => {
      const x = e.clientX / innerWidth - 0.5, y = e.clientY / innerHeight - 0.5;
      deck.style.transform = `rotateY(${-18 + x * 24}deg) rotateX(${8 - y * 18}deg)`;
    });
  }
  document.querySelectorAll("[data-count]").forEach((el) => {
    const end = parseFloat(el.dataset.count), prefix = el.dataset.prefix || "", dec = el.dataset.dec ? 2 : 0;
    const fmt = (n) => prefix + n.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec });
    if (reduce || isNaN(end)) { el.textContent = fmt(end || 0); return; }
    const t0 = performance.now(), dur = 900;
    (function tick(now) {
      const p = Math.min((now - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(end * e);
      if (p < 1) requestAnimationFrame(tick);
    })(t0);
  });
  const btn = document.getElementById("menu-btn"), side = document.getElementById("side");
  if (btn && side) btn.addEventListener("click", () => side.classList.toggle("open"));
  document.querySelectorAll("[data-confirm]").forEach((f) =>
    f.addEventListener("submit", (e) => { if (!confirm(f.dataset.confirm)) e.preventDefault(); }));
  setTimeout(() => document.querySelectorAll(".toast").forEach((t) => { t.style.transition = "opacity .5s"; t.style.opacity = 0; }), 6000);
})();
