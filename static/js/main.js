(() => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.addEventListener("DOMContentLoaded", () => {
    initReveal();
    if (!reduceMotion) {
      initParticles();
      initCursorGlow();
      initParallaxFog();
      initMagneticButtons();
    } else {
      document.querySelectorAll(".reveal, .feature-block, .price-card, .support-card")
        .forEach((el) => el.classList.add("is-visible"));
    }
  });

  function initReveal() {
    const items = document.querySelectorAll(
      ".feature-block, .price-card, .support-card, .reveal, .cta-band"
    );
    if (!items.length) return;

    const show = (el, i = 0) => {
      window.setTimeout(() => el.classList.add("is-visible"), i * 70);
    };

    const fallback = window.setTimeout(() => items.forEach((el) => show(el)), 1200);

    if (!("IntersectionObserver" in window)) {
      items.forEach((el, i) => show(el, i));
      window.clearTimeout(fallback);
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const siblings = [...entry.target.parentElement?.children || []];
          const idx = Math.max(0, siblings.indexOf(entry.target));
          show(entry.target, idx % 4);
          io.unobserve(entry.target);
        });
      },
      { threshold: 0.08, rootMargin: "50px" }
    );

    items.forEach((el) => io.observe(el));
  }

  function initParticles() {
    const canvas = document.getElementById("fx-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let w = 0;
    let h = 0;
    let raf = 0;
    const particles = [];
    const COUNT = Math.min(70, Math.floor(window.innerWidth / 18));

    function resize() {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    }

    function spawn() {
      particles.length = 0;
      for (let i = 0; i < COUNT; i += 1) {
        particles.push({
          x: Math.random() * w,
          y: Math.random() * h,
          r: Math.random() * 2 + 0.4,
          vx: (Math.random() - 0.5) * 0.35,
          vy: -0.15 - Math.random() * 0.45,
          a: 0.15 + Math.random() * 0.45,
        });
      }
    }

    function tick() {
      ctx.clearRect(0, 0, w, h);
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.y < -10) {
          p.y = h + 10;
          p.x = Math.random() * w;
        }
        if (p.x < -10) p.x = w + 10;
        if (p.x > w + 10) p.x = -10;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(167, 139, 250, ${p.a})`;
        ctx.fill();
      }

      // soft links between nearby particles
      for (let i = 0; i < particles.length; i += 1) {
        for (let j = i + 1; j < particles.length; j += 1) {
          const a = particles[i];
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy);
          if (dist < 110) {
            ctx.strokeStyle = `rgba(139, 92, 246, ${0.12 * (1 - dist / 110)})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      raf = requestAnimationFrame(tick);
    }

    resize();
    spawn();
    tick();
    window.addEventListener("resize", () => {
      resize();
      spawn();
    });
    window.addEventListener("beforeunload", () => cancelAnimationFrame(raf));
  }

  function initCursorGlow() {
    const glow = document.querySelector(".cursor-glow");
    if (!glow || window.matchMedia("(pointer: coarse)").matches) {
      glow?.remove();
      return;
    }

    let x = window.innerWidth / 2;
    let y = window.innerHeight / 2;
    let tx = x;
    let ty = y;

    window.addEventListener("pointermove", (e) => {
      tx = e.clientX;
      ty = e.clientY;
      glow.classList.add("is-on");
    });

    function loop() {
      x += (tx - x) * 0.12;
      y += (ty - y) * 0.12;
      glow.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
      requestAnimationFrame(loop);
    }
    loop();
  }

  function initParallaxFog() {
    const fogs = document.querySelectorAll(".fog");
    if (!fogs.length) return;

    window.addEventListener("pointermove", (e) => {
      const px = (e.clientX / window.innerWidth - 0.5) * 24;
      const py = (e.clientY / window.innerHeight - 0.5) * 18;
      fogs.forEach((fog, i) => {
        const k = (i + 1) * 0.45;
        fog.style.translate = `${px * k}px ${py * k}px`;
      });
    });
  }

  function initMagneticButtons() {
    const buttons = document.querySelectorAll(".btn-primary");
    buttons.forEach((btn) => {
      btn.addEventListener("pointermove", (e) => {
        const rect = btn.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        btn.style.transform = `translate(${x * 0.12}px, ${y * 0.18}px)`;
      });
      btn.addEventListener("pointerleave", () => {
        btn.style.transform = "";
      });
    });
  }
})();
