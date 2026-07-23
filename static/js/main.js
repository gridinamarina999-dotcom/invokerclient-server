(() => {
  document.addEventListener("DOMContentLoaded", () => {
    initReveal();
    initPasswordToggles();
  });

  function initReveal() {
    const items = document.querySelectorAll(
      ".feature-block, .price-card, .support-card, .reveal, .cta-band"
    );
    if (!items.length) return;

    // Сразу показываем — без тяжёлых анимаций
    items.forEach((el) => el.classList.add("is-visible"));
  }

  function initPasswordToggles() {
    document.querySelectorAll("[data-password-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.getAttribute("data-password-toggle");
        const input = document.getElementById(targetId);
        if (!input) return;

        const show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.textContent = show ? "Скрыть" : "Показать";
        btn.setAttribute("aria-label", show ? "Скрыть пароль" : "Показать пароль");
      });
    });
  }
})();
