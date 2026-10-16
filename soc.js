const button = document.querySelector('[data-motion]');
const state = document.getElementById('motion-state');
const controls = document.querySelector('.motion-tools');

if (button && state && controls && window.matchMedia) {
  const root = document.documentElement;
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  let paused = false;
  const update = () => {
    const running = !paused && !preference.matches && !document.hidden;
    root.classList.toggle('motion-active', running);
    button.setAttribute('aria-pressed', String(running));
    button.setAttribute('aria-disabled', String(preference.matches));
    state.textContent = preference.matches ? button.dataset.reducedLabel : paused ? button.dataset.resumeLabel : button.dataset.pauseLabel;
  };
  button.addEventListener('click', () => {
    if (preference.matches) return;
    paused = !paused;
    update();
  });
  preference.addEventListener('change', update);
  document.addEventListener('visibilitychange', update);
  controls.hidden = false;
  update();

  // Content starts visible; a failed or unavailable observer only skips decoration.
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        if (root.classList.contains('motion-active')) entry.target.classList.add('is-seen');
        observer.unobserve(entry.target);
      }
    }, { threshold: 0.12 });
    document.querySelectorAll('[data-reveal]').forEach(element => observer.observe(element));
  }
}
