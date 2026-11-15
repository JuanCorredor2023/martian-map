// Landing page (web/home/, issue #126). Run from the repo root:  node --test tests/web/
// Static checks only: every link and image on the two pages resolves to a file the app
// serves from web/, the pages stay offline (no external scripts, styles or images), and
// nothing from the design mock is left (mock.js, the hero switch, the mock footer).
import assert from 'node:assert/strict';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { test } from 'node:test';

const WEB = new URL('../../web/', import.meta.url);
const HOME = new URL('home/', WEB);
const PAGES = ['index.html', 'demo.html'];
const read = name => readFileSync(new URL(name, HOME), 'utf8');

// Every URL a page loads or links to: href, src and each srcset candidate.
function urls(html) {
  const out = [];
  for (const m of html.matchAll(/\s(href|src)="([^"]*)"/g)) out.push({ attr: m[1], url: m[2] });
  for (const m of html.matchAll(/\ssrcset="([^"]*)"/g))
    for (const part of m[1].split(',')) out.push({ attr: 'srcset', url: part.trim().split(/\s+/)[0] });
  return out;
}

// The file the app's StaticFiles(web/, html=True) serves for a same-origin URL.
function servedFile(url, base) {
  const path = url.split('#')[0].split('?')[0];
  if (path === '') return null;                       // same-page anchor
  const target = new URL(path, path.startsWith('/') ? WEB : base);
  if (path.startsWith('/')) target.pathname = WEB.pathname + path.slice(1);
  if (target.pathname.endsWith('/')) target.pathname += 'index.html';
  return target;
}

for (const page of PAGES) {
  test(`${page}: every local link and image exists in web/`, () => {
    const html = read(page);
    const missing = [];
    for (const { attr, url } of urls(html)) {
      if (/^(https?:|mailto:)/.test(url) || url === '#') continue;
      const file = servedFile(url, HOME);
      if (file && !(existsSync(file) && statSync(file).isFile())) missing.push(`${attr}=${url}`);
    }
    assert.deepEqual(missing, []);
  });

  test(`${page}: same-page anchors point at ids on the page`, () => {
    const html = read(page);
    const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map(m => m[1]));
    const bad = urls(html).map(u => u.url).filter(u => u.startsWith('#') && u !== '#' && !ids.has(u.slice(1)));
    assert.deepEqual(bad, []);
  });

  test(`${page}: offline, no external scripts, styles or images`, () => {
    const html = read(page);
    assert.doesNotMatch(html, /<script[^>]+src="https?:/);
    assert.doesNotMatch(html, /<link[^>]+href="https?:/);
    assert.doesNotMatch(html, /\s(src|srcset)="https?:/);
  });

  test(`${page}: one h1, lang and a title`, () => {
    const html = read(page);
    assert.equal(html.match(/<h1[\s>]/g)?.length, 1);
    assert.match(html, /<html lang="en">/);
    assert.match(html, /<title>[^<]+Mars EVA Planner<\/title>|<title>Mars EVA Planner<\/title>/);
  });

  test(`${page}: no leftovers from the design mock`, () => {
    const html = read(page);
    assert.doesNotMatch(html, /mock\.js|data-app-link|data-hero|hero__bg|Design mock/i);
  });

  test(`${page}: the video slot is there, hidden until the YouTube link exists`, () => {
    const html = read(page);
    const a = html.match(/<a[^>]*data-youtube-link[^>]*>/)?.[0];
    assert.ok(a, 'data-youtube-link anchor');
    if (/href="#"/.test(a)) assert.match(a, /\shidden[\s>]/, 'a placeholder link must stay hidden');
  });
}

test('the landing page opens the three app views and the demo page', () => {
  const hrefs = urls(read('index.html')).map(u => u.url);
  for (const want of ['/', '/3d/', '/guide.html', 'demo.html']) assert.ok(hrefs.includes(want), want);
});

test('every image in assets/ is used by a page (no dead weight)', async () => {
  const { readdirSync } = await import('node:fs');
  const used = new Set(PAGES.flatMap(p => urls(read(p)).map(u => u.url)).filter(u => u.startsWith('assets/')));
  const unused = readdirSync(new URL('assets/', HOME)).map(f => `assets/${f}`).filter(f => !used.has(f));
  assert.deepEqual(unused, []);
});

test('styles.css has no mock-only rules', () => {
  const css = readFileSync(new URL('styles.css', HOME), 'utf8');
  assert.doesNotMatch(css, /mock|data-hero|toast/i);
});

test('"Try it" opens the planner on 1 Terrain, in the header and the hero (#173)', () => {
  for (const page of PAGES) {
    const html = read(page);
    const tryIt = html.match(/<a[^>]*class="btn btn-primary[^"]*"[^>]*>Try it<\/a>/g) ?? [];
    assert.ok(tryIt.length >= 1, `${page}: a Try it button`);
    for (const a of tryIt) assert.match(a, /href="\/\?tab=terrain"/, a);
    assert.doesNotMatch(html, /class="btn[^"]*"[^>]*>Plan \(2D\)</, `${page}: no Plan (2D) button left`);
  }
  assert.match(read('index.html'), /<section class="hero"[\s\S]*?>Try it<\/a>[\s\S]*?<\/section>/);
});

test('the paper has its own section, its link hidden until the paper is public (#196)', () => {
  const html = read('index.html');
  const section = html.match(/<section[^>]*id="paper"[\s\S]*?<\/section>/)?.[0];
  assert.ok(section, 'section#paper');
  assert.match(section, /<h2 id="paper-title">/);
  const a = section.match(/<a[^>]*data-paper-link[^>]*>/)?.[0];
  assert.ok(a, 'data-paper-link anchor');
  if (/href="#"/.test(a)) {
    assert.match(a, /\shidden[\s>]/, 'a placeholder link must stay hidden');
    assert.match(section, /class="paper__soon"/, 'say the paper is coming while there is no link');
  }
});

test('the colour bands still alternate after the paper section', () => {
  const html = read('index.html');
  const bands = [...html.matchAll(/<section class="section( band-alt)?"[^>]*id="([^"]+)"/g)].map(m => [m[2], !!m[1]]);
  for (let i = 1; i < bands.length; i++) assert.notEqual(bands[i][1], bands[i - 1][1], `${bands[i - 1][0]} → ${bands[i][0]}`);
});
