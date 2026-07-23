document.addEventListener("DOMContentLoaded", () => {
  const items = document.querySelectorAll(".feature-block, .price-card, .support-card");
  if (!items.length) return;

  const show = (el) => el.classList.add("is-visible");

  // Если observer не сработает — всё равно покажем блоки
  const fallback = window.setTimeout(() => items.forEach(show), 1000);

  if (!("IntersectionObserver" in window)) {
    items.forEach(show);
    window.clearTimeout(fallback);
    return;
  }

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          show(entry.target);
          io.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.05, rootMargin: "40px" }
  );

  items.forEach((el) => io.observe(el));
});
