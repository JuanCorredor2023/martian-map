// Mock-only helpers for the #126 design mock. Delete this file when the page moves
// into the app; the pages work without it (hero A, plain links).
//
// 1. A small "Hero A / B" switch (bottom left) to compare the two hero directions.
//    ?hero=b opens B; ?clean hides the switch (used for the screenshots).
// 2. When the page is not served by the app (the mock server, a file, the Artifact),
//    links to the app explain where they go instead of opening a page that does not exist.
(() => {
  const root = document.documentElement;
  const params = new URLSearchParams(location.search);

  // 1. Hero switch
  const hasHero = !!document.querySelector('.hero');
  let hero = 'a';
  try { hero = localStorage.getItem('mock-hero') === 'b' ? 'b' : 'a'; } catch { /* storage blocked */ }
  if (params.has('hero')) hero = params.get('hero') === 'b' ? 'b' : 'a';

  function setHero(value) {
    hero = value;
    root.dataset.hero = value;
    document.querySelectorAll('[data-hero-btn]').forEach(b =>
      b.setAttribute('aria-pressed', String(b.dataset.heroBtn === value)));
    try { localStorage.setItem('mock-hero', value); } catch { /* storage blocked */ }
  }

  if (hasHero) {
    if (!params.has('clean')) {
      const bar = document.createElement('div');
      bar.className = 'mock-bar';
      bar.setAttribute('role', 'group');
      bar.setAttribute('aria-label', 'Mock: choose the hero version');
      bar.innerHTML = '<span>Mock</span>' +
        '<button type="button" data-hero-btn="a">Hero A</button>' +
        '<button type="button" data-hero-btn="b">Hero B</button>';
      bar.addEventListener('click', e => {
        const b = e.target.closest('[data-hero-btn]');
        if (b) setHero(b.dataset.heroBtn);
      });
      document.body.append(bar);
    }
    setHero(hero);
  }

  // 2. Links to the app: ask the app's /health on click; open the link only if it answers.
  let toast, timer;
  function say(text) {
    if (!toast) {
      toast = document.createElement('p');
      toast.className = 'mock-toast';
      toast.setAttribute('role', 'status');
      document.body.append(toast);
    }
    toast.hidden = false;
    toast.textContent = text;
    clearTimeout(timer);
    timer = setTimeout(() => { toast.hidden = true; }, 4500);
  }

  document.addEventListener('click', e => {
    const a = e.target.closest('a[data-app-link]');
    if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    fetch('/health', { cache: 'no-store' })
      .then(r => r.ok && (r.headers.get('content-type') || '').includes('json'))
      .catch(() => false)
      .then(inApp => {
        if (inApp) location.assign(a.href);
        else say(`In the app, this opens ${a.dataset.appLink} (${a.getAttribute('href')}). This mock runs outside the app.`);
      });
  });
})();
