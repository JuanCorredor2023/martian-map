// Controls of the 3D map (web/3d): the safety net of issue #124. Run from the repo root:
//   node --test tests/viz3d/
//
// Simplifying the interface must not drop a feature that works. For each of the 31
// features of the 3D view (the list of #124, in its order) this reads the files and checks
// that the feature's control or way in is still there and still wired: the element ids of
// web/3d/index.html (buttons stay buttons, inputs stay inputs), the handlers behind them,
// the URL parameters, the ?check= modes and the keys. Layout and colours are not checked,
// and wording only where something depends on it: the card button labels that
// ?check=stations compares ("Done, continue", "View the rover photo") and the words
// "EVA clock" of the Sun note. A feature moved on purpose (a new id, another key) is
// updated here in the same PR.
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { test } from 'node:test';

import * as L from '../../web/3d/map_layers_model.js';
import * as W from '../../web/3d/walk_model.js';

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8').replace(/\r\n/g, '\n');
// Without comments, so that a comment naming a control cannot pass for it. (No string of
// these files holds "/*", or "//" after a space.)
const code = path => read(path).replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/.*$/gm, '$1');
const PAGE = read('../../web/3d/index.html').replace(/<!--[\s\S]*?-->/g, '');
const JS = Object.fromEntries(readdirSync(new URL('../../web/3d/', import.meta.url)).filter(f => f.endsWith('.js'))
  .map(f => [f.slice(0, -3), code(`../../web/3d/${f}`)]));
const GUIDE = code('../../web/guide_core.js');
const literal = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// ---- the page ------------------------------------------------------------------------

// Start tags with their attributes; values in double quotes, single quotes or bare.
const TAG = /<([a-zA-Z][\w-]*)((?:\s+[\w:-]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*)\s*\/?>/g;
const ATTR = /([\w:-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
const tags = html => [...html.matchAll(TAG)].map(m => ({
  tag: m[1].toLowerCase(), end: m.index + m[0].length,
  attrs: Object.fromEntries([...m[2].matchAll(ATTR)].map(([, k, ...v]) => [k.toLowerCase(), v.find(x => x !== undefined) ?? ''])),
}));
const TAGS = tags(PAGE);
const PAGE_IDS = TAGS.filter(t => t.attrs.id !== undefined).map(t => t.attrs.id);
const ELEMENTS = new Map(TAGS.filter(t => t.attrs.id !== undefined).map(t => [t.attrs.id, t]));
// What is inside the element with this id, up to its own closing tag.
function inner(id) {
  const el = ELEMENTS.get(id);
  if (!el) return '';
  const re = new RegExp(`${TAG.source}|</(${el.tag})\\s*>`, 'gi');
  re.lastIndex = el.end;
  for (let depth = 1, m; (m = re.exec(PAGE));) {
    if (m[3]) depth--; else if (m[1].toLowerCase() === el.tag) depth++;
    if (!depth) return PAGE.slice(el.end, m.index);
  }
  return PAGE.slice(el.end);
}
// Elements that the code makes (they are not in index.html), by the module that makes them.
const BUILT = {'message-close': 'main', 'photo-overlay': 'photos', 'photo-bar': 'photos', 'photo-opacity': 'photos',
               'photo-prev': 'photos', 'photo-next': 'photos', 'photo-realign': 'photos', 'photo-exit': 'photos'};

// The element with this id; one of `kinds` when given.
function element(id, kinds = null) {
  const el = ELEMENTS.get(id);
  assert.ok(el, `web/3d/index.html has no element with id="${id}"`);
  if (kinds) assert.ok(kinds.includes(el.tag), `#${id} is a <${el.tag}>, no longer a <${kinds.join('> or <')}>`);
  return el;
}
const present = (...ids) => ids.forEach(id => element(id));
const buttons = (...ids) => ids.forEach(id => element(id, ['button']));
// Inputs stay usable from the keyboard: an input, a select or a button, never a plain box.
const inputs = (...ids) => ids.forEach(id => element(id, ['input', 'select', 'textarea', 'button']));

// ---- the code ------------------------------------------------------------------------

// The module web/3d/<file>.js has code that matches re.
function inCode(file, re, what) {
  assert.ok(file in JS, `web/3d/${file}.js is gone`);
  assert.match(JS[file], re, `web/3d/${file}.js: ${what}`);
}
// main.js reads ?name= (and compares it with `value` in the same statement, when given).
const param = (name, value) => inCode('main',
  new RegExp(`params\\.get\\(\\s*['"]${name}['"]\\s*\\)${value === undefined ? '' : `[^;]*['"]${value}['"]`}`),
  `?${name}=${value ?? ''} is no longer read`);
// Index just past the bracket that closes the one at src[open]; strings are skipped.
function closing(src, open) {
  const pairs = {'(': ')', '[': ']', '{': '}'}, wanted = [];
  for (let i = open; i < src.length; i++) {
    const c = src[i];
    if (c === '"' || c === "'" || c === '`') {
      while (++i < src.length && src[i] !== c && (c === '`' || src[i] !== '\n')) if (src[i] === '\\') i++;
    } else if (pairs[c]) {
      wanted.push(pairs[c]);
    } else if (c === wanted[wanted.length - 1]) {
      wanted.pop();
      if (!wanted.length) return i + 1;
    }
  }
  return src.length;
}
// Each `<target>.addEventListener(...)` of a module: the event type and the text of the call.
function listeners(file, target) {
  const src = JS[file];
  return [...src.matchAll(new RegExp(`${target}\\.addEventListener\\(`, 'g'))].map(m => {
    const text = src.slice(m.index + m[0].length - 1, closing(src, m.index + m[0].length - 1));
    return {file, type: /^\(\s*['"]([\w-]+)['"]/.exec(text)?.[1], text};
  });
}
// The text of a function or method of a module, by name ('' when it has none).
function bodyOf(file, name) {
  const src = JS[file];
  for (const m of src.matchAll(new RegExp(`(?:\\bfunction\\s+|^[ \\t]+(?:async\\s+)?)${literal(name)}\\s*\\(`, 'gm'))) {
    const after = closing(src, m.index + m[0].length - 1), brace = /^\s*\{/.exec(src.slice(after));
    if (brace) return src.slice(after + brace[0].length - 1, closing(src, after + brace[0].length - 1));
  }
  return '';
}
const KEYWORDS = new Set(['if', 'for', 'while', 'switch', 'catch', 'function', 'return', 'typeof', 'await', 'new']);
// Does this code of a module call fn (a pattern, as 'hideMessage' or 'this\\.enter'), or pass
// it as the handler, itself or in a function or method of the module that it calls?
function calls(file, text, fn) {
  const re = new RegExp(`(?<![\\w$])${fn}\\(|[(,]\\s*${fn}\\s*[,)]`);
  if (re.test(text)) return true;
  const names = new Set([...text.matchAll(/(?<![\w$])([\w$]+)\(/g)].map(m => m[1]).filter(n => !KEYWORDS.has(n)));
  return [...names].some(name => re.test(bodyOf(file, name)));
}
// The listeners of #id in the modules but the checks: looked up by id, or through a const.
function listenersOf(id) {
  const find = `\\b(?:el|ui|getElementById)\\(\\s*['"]${id}['"]\\s*\\)`;
  return Object.keys(JS).filter(file => file !== 'checks').flatMap(file => {
    // const pick = el('layer-pick');
    const held = new RegExp(`\\b(?:const|let)\\s+([\\w$]+)\\s*=\\s*${find}\\s*[;,]`).exec(JS[file]);
    return [...listeners(file, find), ...(held ? listeners(file, `\\b${literal(held[1])}`) : [])];
  });
}
// Something listens to `type` on #id; with fn, its handler calls fn (as calls() says).
function wired(id, type, fn = null) {
  const found = listenersOf(id).filter(l => l.type === type);
  assert.ok(found.length, `nothing listens to "${type}" on #${id} any more`);
  if (fn) {
    assert.ok(found.some(l => calls(l.file, l.text, fn)),
              `#${id}: its "${type}" handler no longer calls ${fn.replace(/\\/g, '')}()`);
  }
}
// A card button (card.js makes one for each {label, onClick}) whose onClick calls fn first.
const cardAction = (file, fn, what) => inCode(file, new RegExp(
  `\\blabel:\\s*(?:'[^']*'|"[^"]*")\\s*,\\s*onClick:\\s*(?:\\([^)]*\\)|[\\w$]+)\\s*=>\\s*\\{?\\s*${fn}\\(`), what);
// Every label that checks.js compares (?check=stations) is the label of a card button in a module.
function sameLabels() {
  const wanted = [...JS.checks.matchAll(/\.includes\(\s*'([^']+)'\s*\)|textContent === '([^']+)'/g)].map(m => m[1] ?? m[2]);
  assert.ok(wanted.length >= 2, 'web/3d/checks.js no longer compares the card labels');
  for (const label of wanted) {
    const button = new RegExp(`\\blabel:\\s*['"]${literal(label)}['"]\\s*,\\s*onClick:`);
    assert.ok(Object.entries(JS).some(([file, src]) => file !== 'checks' && button.test(src)),
              `?check=stations looks for "${label}", which no card button says any more`);
  }
}
// The module that makes this element still gives it its id.
const built = id => inCode(BUILT[id], new RegExp(`(?:\\.id\\s*=\\s*|\\bid:\\s*)['"]${id}['"]|\\bid=["']${id}["']`),
                           `#${id} is no longer made`);
// The methods of a module's classes (two-space indent, as in web/3d), as text.
const methods = file => JS[file].split(/\n(?= {2}(?:async )?[\w$]+\([^)]*\) \{[ \t]*\n)/);
const methodWith = (file, re) => methods(file).find(m => re.test(m)) ?? '';

test('the page: every id is read here, used once, and not made again by the code', () => {
  const raw = [...PAGE.matchAll(/\sid\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/g)].map(m => m[1] ?? m[2] ?? m[3]);
  assert.deepEqual(PAGE_IDS, raw, 'an element of web/3d/index.html was not read');
  const twice = PAGE_IDS.filter((id, i) => PAGE_IDS.indexOf(id) !== i);
  assert.deepEqual(twice, [], `ids used twice in web/3d/index.html: ${twice.join(' ')}`);
  for (const id of Object.keys(BUILT)) assert.ok(!ELEMENTS.has(id), `#${id} is in the page and made by ${BUILT[id]}.js too`);
});

test('1. free flight: drag, right-drag or Shift + drag, wheel and touch; ?drag=pan', () => {
  element('view', ['canvas']);
  inCode('main', /new TerrainControls\(\s*camera,\s*canvas\b/, 'the free-flight controls are no longer on the view');
  param('drag', 'pan');
  for (const type of ['pointerdown', 'pointermove', 'wheel']) {
    inCode('controls', new RegExp(`\\.addEventListener\\(\\s*'${type}'`), `nothing handles "${type}" any more`);
  }
  inCode('controls', /e\.button === 2/, 'the right button no longer moves the map');
  inCode('controls', /e\.shiftKey/, 'Shift + drag no longer moves the map');
  inCode('controls', /type:\s*'two'/, 'two fingers no longer move, pinch and twist');
});

test('2. compass (face north) and home (reset the view)', () => {
  present('compass', 'compass-needle');          // a <div> for now: #124 (c) makes it a button
  buttons('home');
  wired('compass', 'click', 'faceNorth');
  wired('home', 'click', 'controls\\.home');
});

test('3. readout of position, height and speed; ?fps=1', () => {
  present('readout');
  param('fps', '1');
});

test('4. relief x1 to x5: the slider and ?k=', () => {
  inputs('relief');
  present('relief-label');
  wired('relief', 'input');
  param('k');
});

test('5. quality and debugging: ?q=, ?light=, ?spin=1', () => {
  param('q');
  param('light');
  param('spin', '1');
  present('quality-label');
});

test('6. view link: ?view= and "Copy link to this view"', () => {
  param('view');
  buttons('copy-view');
  inputs('view-link');
  present('share-note');
  wired('copy-view', 'click');
});

test('7. Save image', () => {
  buttons('save-image');
  wired('save-image', 'click');
});

test('8. last plan, Reload plan and the default plan; ?plan=default', () => {
  buttons('plan-reload', 'plan-default');
  present('plan-default-box', 'plan-source');
  wired('plan-reload', 'click');
  wired('plan-default', 'click');
  param('plan', 'default');
  inCode('main', /\bloadLastPlan\(/, 'the last plan is no longer loaded');
  inCode('main', /\brequestDefaultPlan\(/, 'the default plan can no longer be asked for');
});

test('9. link back to the 2D planner', () => {
  assert.ok(TAGS.some(t => t.tag === 'a' && ['/', '../', '/index.html'].includes(t.attrs.href)),
            'web/3d/index.html has no link to the 2D planner (href "/", "../" or "/index.html")');
});

test('10. route on the relief', () => {
  inCode('main', /new RouteOverlay\(/, 'the route is no longer drawn');
  inCode('main', /\boverlays\.setPlan\(/, 'the plan no longer reaches the route');
});

test('11. pins, their card and "Fly here"', () => {
  element('card');
  // A click (pointerup) on the view picks the pin under it and selects it; the pin's card follows.
  const up = listeners('main', `\\b(?:canvas|ui\\(\\s*['"]view['"]\\s*\\))`).filter(l => l.type === 'pointerup');
  assert.ok(up.some(l => calls('main', l.text, 'markers\\.pick') && calls('main', l.text, 'markers\\.select')),
            'web/3d/main.js: a click on the view no longer picks and selects a pin');
  inCode('main', /\bmarkers\.onSelect\s*=/, 'a selected pin no longer shows its card');
  cardAction('main', 'flyToMarker', 'a pin card no longer flies there');
  // The parts of the card that the checks read, its buttons and its close cross.
  for (const cls of ['card-title', 'card-media']) inCode('card', new RegExp(`'${cls}'`), `the card has no .${cls}`);
  inCode('card', /'button',\s*'card-action'/, 'the card actions are no longer buttons');
  inCode('card', /'button',\s*'card-close'/, 'the card can no longer be closed');
});

test('12. Sun: sol, local solar time and sky; ?sol= and ?lt=', () => {
  inputs('sun-sol', 'sun-time');
  present('sun-time-text', 'sun-readout');
  wired('sun-sol', 'change');
  wired('sun-time', 'input');
  param('sol');
  param('lt');
});

test('13. the Sun follows the EVA clock while rehearsing', () => {
  present('sun-note');
  inCode('rehearse', /\bthis\.onTime\((?!\s*null\b)/, 'the rehearsal no longer gives its EVA clock');
  inCode('main', /\bonTime:[^;]*\bsunView\.follow\(/, 'the EVA clock no longer moves the Sun');
  // The note may move to the player and change its words (#124, block 2): any module but the checks.
  assert.ok(Object.entries(JS).some(([file, src]) => file !== 'checks' && /[`'"][^`'"]*EVA clock/.test(src)),
            'no module says "EVA clock" any more');
});

test('14. Relief only and Shadows; ?shadows=0', () => {
  inputs('relief-only', 'shadows');
  wired('relief-only', 'change');
  wired('shadows', 'change');
  param('shadows', '0');
});

test('15. map layer of the 2D planner (six), its opacity and legend', () => {
  inputs('layer-pick', 'layer-opacity');
  present('layer-legend', 'layer-note');
  assert.ok(tags(inner('layer-pick')).some(t => t.tag === 'option' && t.attrs.value === ''),
            '#layer-pick has no "off" option (value="")');
  wired('layer-pick', 'change');
  wired('layer-opacity', 'input');
  for (const id of ['radio', 'slope', 'steep', 'sand', 'cost', 'rocks']) {
    assert.ok((L.LAYERS ?? []).some(l => l.id === id), `web/3d/map_layers_model.js has no "${id}" layer`);
  }
  inCode('map_layers', /\bof LAYERS\b|\bLAYERS\.(?:forEach|map)\(/, 'the layers are no longer offered in #layer-pick');
  inCode('main', /import\(\s*'\.\/map_layers\.js'\s*\)/, 'the map layers are no longer loaded');
});

test('16. rover photo stops: pins and cards', () => {
  inputs('photos-show');
  present('photos-note');
  wired('photos-show', 'change');
  inCode('main', /import\(\s*'\.\/photos\.js'\s*\)/, 'the rover photos are no longer loaded');
  inCode('main', /\bphotoMarkers\.pickAll\(/, 'a click no longer picks a photo stop');
  inCode('main', /\bphotos\.openGroup\(/, 'a photo stop no longer opens its card');
  inCode('main', /\bphotos\.chooseStop\(/, 'stops on top of each other can no longer be chosen');
});

test('17. photo view: fade, Previous / Next, Realign, Exit and Esc', () => {
  cardAction('photos', 'this\\.enter', 'a photo stop card no longer opens the photo view');
  for (const id of ['photo-overlay', 'photo-bar', 'photo-opacity', 'photo-prev', 'photo-next', 'photo-realign',
                    'photo-exit']) built(id);
  inCode('photos', /\bmake\('button'/, 'the photo bar has no buttons any more');
  inCode('photos', /'keydown'/, 'the photo view no longer listens to the keys');
  assert.match(methodWith('photos', /'Escape'/), /\bthis\.exit\(\)/, 'web/3d/photos.js: Esc no longer leaves the photo view');
});

test('18. photo by link: ?photo= (the "Open in 3D" of the HUD)', () => {
  param('photo');
  inCode('main', /\bparsePhotoParam\(/, '?photo= is no longer read as a photo id');
  inCode('main', /\bphotos\.enter\(/, '?photo= no longer opens the photo view');
});

test('19. nearest rover photo on a station card', () => {
  inCode('main', /\bphotos\.stationPreview\(/, 'a station card no longer shows its nearest photo');
  inCode('rehearse', /\bthis\.stationMedia\(/, 'a stop card of the rehearsal no longer shows its nearest photo');
  assert.ok(calls('photos', bodyOf('photos', 'stationPreview'), 'this\\.enter'),
            'web/3d/photos.js: the nearest photo can no longer be opened from the card');
  sameLabels();
});

test('20. enter and leave the rehearsal', () => {
  buttons('rehearse', 'rh-exit');
  present('player', 'rehearse-note');
  wired('rehearse', 'click');
  wired('rh-exit', 'click');
});

test('21. player: play / pause (also Space), speed and position bar', () => {
  buttons('rh-play');
  inputs('rh-speed', 'rh-scrub');
  present('rh-progress');
  wired('rh-play', 'click');
  wired('rh-speed', 'change');
  wired('rh-scrub', 'input');
  // Space does what the Play button does, whatever that method is called.
  const play = listenersOf('rh-play').filter(l => l.type === 'click').map(l => /\bthis\.([\w$]+)\(/.exec(l.text)?.[1])
    .find(Boolean);
  inCode('rehearse', /'keydown'/, 'the rehearsal no longer listens to the keys');
  assert.ok(play && new RegExp(`\\bthis\\.${literal(play)}\\(`).test(methodWith('rehearse', /'Space'/)),
            'web/3d/rehearse.js: Space no longer does what Play does');
});

test('22. chase view, looking around and Recentre (also double-click)', () => {
  buttons('rh-chase', 'rh-recentre');
  wired('rh-chase', 'click');
  wired('rh-recentre', 'click');
  inCode('rehearse', /'pointermove'/, 'dragging no longer looks around');
  inCode('rehearse', /'dblclick'[^;]*\brecentre\(\)/, 'a double-click no longer looks forward again');
});

test('23. stops: card, tasks and "Done, continue"', () => {
  element('card');
  inCode('rehearse', /\bG\.stationCard\(/, 'a stop card no longer lists the tasks');
  sameLabels();
});

test('24. energy bar and walkback lines on pause', () => {
  present('rh-energy', 'rh-bar-used', 'rh-bar-rv', 'rh-bar-free', 'rh-energy-text');
  inCode('rehearse', /\brequestWalkback\(/, 'a pause no longer asks for the walkback lines');
});

test('25. guide: next maneuver, meters and radio', () => {
  // The banner and the values of the meters; ?check=guide reads all but the radio.
  present('rh-man', 'rh-man-arrow', 'rh-man-text', 'rh-man-dist', 'rh-meters', 'rh-v-energy', 'rh-v-back',
          'rh-eva-track', 'rh-v-eva', 'rh-v-radio');
});

test('26. voice on / off', () => {
  buttons('rh-voice');
  wired('rh-voice', 'click');
});

test('27. Return home, Detour and Solar storm', () => {
  buttons('rh-home', 'rh-detour', 'rh-storm');
  present('rh-alert', 'rh-note');
  for (const id of ['rh-home', 'rh-detour', 'rh-storm']) wired(id, 'click');
});

test('28. end summary card and the walk log (POST /walks)', () => {
  // The method that sums up the walk, whatever its name: something calls it, and it shows a card.
  const end = methodWith('rehearse', /\bG\.walkSummary\(/), name = /^ {2}(?:async )?([\w$]+)\(/.exec(end)?.[1];
  assert.ok(name && new RegExp(`\\bthis\\.${literal(name)}\\(`).test(JS.rehearse),
            'web/3d/rehearse.js: arriving no longer sums up the walk');
  assert.match(end, /\bshowCard\(/, 'web/3d/rehearse.js: the end summary is no longer a card');
  inCode('rehearse', /\bG\.postWalk\(/, 'the walk is no longer kept for the debrief');
  assert.match(GUIDE, /fetch\(\s*["']\/walks["']\s*,\s*\{\s*method:\s*["']POST["']/,
               'web/guide_core.js no longer posts the walk to /walks');
});

test('29. replay from the end', () => {
  // In play() or in a method of its own: back to the start, then playing.
  assert.ok(methods('rehearse').some(m => /\bthis\.seek\(this\.model\.start\)/.test(m) &&
                                          /\bthis\.play\(\)|\bthis\.playing\s*=\s*true\b/.test(m)),
            'web/3d/rehearse.js: nothing plays again from the start any more');
});

test('30. Walk freely: W A S D or arrows, Shift, F, C, Esc and the touch pad', () => {
  buttons('walk', 'wk-run', 'wk-fast', 'wk-chase', 'wk-exit');
  present('walk-bar', 'wk-keys', 'wk-hint');
  for (const id of ['walk', 'wk-run', 'wk-fast', 'wk-chase', 'wk-exit']) wired(id, 'click');
  // Keys by KeyboardEvent.code. A and D step sideways; the left and right arrows step
  // sideways too today and turn after block 3 of #124: either way they stay bound.
  const moves = {forward: ['KeyW', 'ArrowUp'], back: ['KeyS', 'ArrowDown'], left: ['KeyA'], right: ['KeyD']};
  for (const [way, codes] of Object.entries(moves)) {
    for (const c of codes) assert.ok(W.KEYS?.[way]?.includes(c), `web/3d/walk_model.js: ${c} no longer moves ${way}`);
  }
  for (const c of ['ArrowLeft', 'ArrowRight']) {
    assert.ok(Object.values(W.KEYS ?? {}).flat().includes(c), `web/3d/walk_model.js: ${c} does nothing any more`);
  }
  inCode('walk', /\bW\.KEYS\b/, 'the walk no longer moves with the keys of walk_model.js');
  inCode('walk', /'keydown'/, 'the walk no longer listens to the keys');
  inCode('walk', /\bshiftKey\b|'Shift(?:Left|Right)'/, 'Shift no longer runs');
  inCode('walk', /'KeyF'/, 'F no longer switches fast travel');
  inCode('walk', /'KeyC'/, 'C no longer switches the chase view');
  assert.match(methodWith('walk', /'Escape'/), /\bthis\.exit\(\)/, 'web/3d/walk.js: Esc no longer leaves the walk');
  // The arrow pad of touch screens (its buttons may sit in rows): walk.js wires them and
  // ?check=walk presses one.
  element('walk-pad');
  const pad = tags(inner('walk-pad'));
  for (const way of ['forward', 'back', 'left', 'right']) {
    assert.ok(pad.some(t => t.tag === 'button' && t.attrs['data-walk'] === way), `#walk-pad has no "${way}" button`);
  }
  inCode('walk', /#walk-pad \[data-walk\]/, 'the pad buttons are no longer wired');
});

test('31. messages and the ten ?check= modes', () => {
  present('message');
  built('message-close');
  wired('message-close', 'click', 'hideMessage');
  // Esc closes the message: a key handler that sees Escape and hides it, itself or through a function.
  const keys = listeners('main', '\\b(?:window|document)').filter(l => l.type === 'keydown' && /['"]Escape['"]/.test(l.text));
  assert.ok(keys.some(l => calls('main', l.text, 'hideMessage')), 'web/3d/main.js: Esc no longer closes the message');
  param('check');
  inCode('main', /import\(\s*'\.\/checks\.js'\s*\)/, 'the checks are no longer loaded');
  inCode('main', /\bCHECKS\[check\]/, 'the check named in the address is no longer run');
  const table = /export const CHECKS = \{([^}]*)\}/.exec(JS.checks);
  assert.ok(table, 'web/3d/checks.js has no CHECKS table');
  const modes = Object.fromEntries([...table[1].matchAll(/(\w+):\s*(\w+)/g)].map(([, name, fn]) => [name, fn]));
  for (const name of ['shading', 'route', 'rehearse', 'sun', 'shadows', 'guide', 'photos', 'stations', 'walk', 'layers']) {
    assert.ok(modes[name], `?check=${name} is gone`);
    inCode('checks', new RegExp(`\\bfunction ${modes[name]}\\(`), `?check=${name} runs ${modes[name]}(), which is gone`);
  }
});

test('every id that the 3D code looks up is in the page, or made by the code', () => {
  const lookups = /(?:(?<![\w.$])(?:el|ui|text|fill|show)|\bdocument\.getElementById)\(\s*['"]([\w-]+)['"]/g;
  const loops = /for \(const id of \[([^\]]*)\]\)\s*(?:el|ui)\(id\)/g;
  const selectors = /\b(?:querySelector(?:All)?|closest)\(\s*(['"])(.*?)\1/g;
  for (const [file, src] of Object.entries(JS)) {
    const wanted = new Set([...src.matchAll(lookups)].map(m => m[1]));
    for (const [, list] of src.matchAll(loops)) for (const [, id] of list.matchAll(/['"]([\w-]+)['"]/g)) wanted.add(id);
    for (const [, , sel] of src.matchAll(selectors)) for (const [, id] of sel.matchAll(/#([\w-]+)/g)) wanted.add(id);
    for (const id of wanted) {
      if (BUILT[id]) built(id);
      else assert.ok(ELEMENTS.has(id), `web/3d/${file}.js looks up #${id}, which web/3d/index.html no longer has`);
    }
  }
});
