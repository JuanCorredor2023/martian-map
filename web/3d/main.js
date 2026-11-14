// 3D map of the boxwork box (P1, issue #42): entry point.
//
// URL parameters (all optional):
//   q=low|high      quality preset (default: low on touch or small screens, else high)
//   k=1..5          local relief exaggeration at the start (default 2; the panel has a slider)
//   plan=default    ask the server for a plan with the default settings on load, as the
//                   "Plan with default settings" button does (see api.js)
//   light=az,el     light direction in degrees: azimuth from north towards east, elevation
//   fps=1           render every frame and show frames per second
//   spin=1          slowly orbit the camera (to measure fps without touching anything)
//   check=shading   run a check from checks.js (shading, route) and show its result as JSON
//   drag=pan        map-style mouse: drag moves, right-drag rotates (default: drag rotates)
import * as THREE from 'three';
import { loadLastPlan, requestDefaultPlan } from './api.js';
import { TerrainControls } from './controls.js';
import { MarkerLayer } from './markers.js';
import { RouteOverlay } from './overlays.js';
import { mainRoute, parsePlan, planMarkers } from './plan_model.js';
import { Terrain, BUILD_HINT } from './terrain.js';

const ui = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const SKY = 0xd8b690;                       // dusty butterscotch sky (a look, not a model)

function pickQuality() {
  const q = params.get('q');
  if (q === 'low' || q === 'high') return q;
  const small = Math.min(screen.width, screen.height) < 900;
  return navigator.maxTouchPoints > 0 || small || (navigator.deviceMemory || 8) <= 4 ? 'low' : 'high';
}

// Unit vector towards the light. Azimuth from north, clockwise; scene Z is south.
function sunDirection(azDeg, elDeg) {
  const az = THREE.MathUtils.degToRad(azDeg), el = THREE.MathUtils.degToRad(elDeg);
  return new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el));
}

// Centred message box. It can always be closed: the cross, the Escape key or a
// click outside it.
function showMessage(html) {
  const box = ui('message');
  box.innerHTML = `<button id="message-close" title="Close (Esc)" aria-label="Close">×</button>${html}`;
  box.hidden = false;
  ui('message-close').addEventListener('click', hideMessage);
}

function hideMessage() { ui('message').hidden = true; }

window.addEventListener('keydown', e => { if (e.key === 'Escape') hideMessage(); });
window.addEventListener('pointerdown', e => {
  if (!ui('message').hidden && !ui('message').contains(e.target)) hideMessage();
});

async function main() {
  if (window.innerWidth < 700 || window.innerHeight < 500) ui('about').open = ui('plan-box').open = false;
  const quality = pickQuality();
  const canvas = ui('view');
  // The stencil buffer is used by the route's see-through pass (overlays.js).
  const renderer = new THREE.WebGLRenderer({canvas, antialias: quality === 'high', stencil: true,
                                            powerPreference: 'high-performance'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, quality === 'high' ? 2 : 1.5));

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(SKY);
  scene.fog = new THREE.Fog(SKY, 4000, 12000);

  const camera = new THREE.PerspectiveCamera(50, 1, 2, 30000);

  ui('readout').textContent = 'Loading terrain…';
  let terrain;
  try {
    terrain = await Terrain.load(quality, {
      maxAnisotropy: renderer.capabilities.getMaxAnisotropy(),
      onProgress: step => { ui('readout').textContent = `Loading ${step}…`; },
    });
  } catch (err) {
    console.error(err);
    ui('readout').textContent = 'Terrain not loaded';
    ui('plan-source').textContent = 'No terrain to draw the plan on.';
    showMessage(`${err.message.replace(BUILD_HINT, '')}<code>${BUILD_HINT}</code>`);
    return;
  }
  scene.add(terrain.group);
  ui('quality-label').textContent = `Quality: ${quality} · mesh every ${terrain.step} m · ` +
    `${(terrain.triangles / 1e6).toFixed(1)} M triangles`;

  // Light: one "sun" plus sky light, so slopes facing away are dim but not black.
  const [az, el] = (params.get('light') || '270,35').split(',').map(Number);
  const sun = new THREE.DirectionalLight(0xfff2e2, 2.6);
  sun.position.copy(sunDirection(az, el)).multiplyScalar(5000);
  scene.add(sun, sun.target);
  scene.add(new THREE.HemisphereLight(0xf0d6b8, 0x6b4a36, 1.1));

  // Camera: an arcball on the terrain (controls.js). Start south of the box looking
  // north, like a tilted map.
  const controls = new TerrainControls(camera, canvas, terrain, scene,
                                       {leftDrag: params.get('drag') === 'pan' ? 'pan' : 'rotate'});
  controls.autoRotate = params.get('spin') === '1';
  controls.home();
  ui('compass').addEventListener('click', () => controls.faceNorth());
  ui('home').addEventListener('click', () => controls.home());

  // What is drawn on the ground: the route of the plan and the markers.
  const overlays = new RouteOverlay(terrain, scene);
  const markers = new MarkerLayer(terrain, scene, camera);

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    overlays.setResolution(w, h);
    markers.setResolution(w, h);
    dirty = true;
  }

  // Render only when something changed, unless fps/spin ask for every frame.
  const continuous = params.get('fps') === '1' || controls.autoRotate;
  let dirty = true, frames = 0, since = performance.now(), fps = 0, last = performance.now();
  window.addEventListener('resize', resize);
  resize();

  function readout() {
    const centre = controls.centreGround();             // what is at the middle of the screen
    let text = 'Looking at the sky';
    if (centre && Math.abs(centre[0]) <= terrain.half && Math.abs(centre[2]) <= terrain.half) {
      const [x, y] = terrain.toMars(centre[0], centre[2]);
      text = `x ${x.toFixed(0)} m · y ${y.toFixed(0)} m · elevation ` +
        `${terrain.elevation(terrain.heightAt(centre[0], centre[2], 1)).toFixed(0)} m`;
    } else if (centre) {
      text = 'Outside the study box';
    }
    ui('readout').textContent = continuous ? `${text} · ${fps.toFixed(0)} fps` : text;
    // The needle shows where north is on screen: it turns against the heading.
    ui('compass-needle').setAttribute('transform', `rotate(${-THREE.MathUtils.radToDeg(controls.yaw)})`);
  }

  // Relief slider. The shown height is DEM + (k - 1) * local relief, so everything
  // that stands on the ground is placed again: route, markers and the camera's floor.
  function setRelief(value) {
    const k = terrain.setExaggeration(Number(value) || 1);
    overlays.refresh();
    markers.refresh();
    controls.refresh();
    ui('relief').value = k;
    ui('relief-label').textContent = k === 1 ? 'Relief at true scale' : `Local relief ×${k} (exaggerated)`;
    dirty = true;
    return k;
  }
  let pendingRelief = null;                    // dragging the slider: at most one update per frame
  ui('relief').max = terrain.maxExaggeration;
  ui('relief').disabled = false;
  ui('relief').addEventListener('input', e => { pendingRelief = e.target.value; });
  setRelief(params.get('k') || 2);

  // A click (not a drag) on a marker selects it. Nothing is shown yet: later blocks
  // set markers.onSelect.
  let press = null;
  canvas.addEventListener('pointerdown', e => { press = {x: e.clientX, y: e.clientY, id: e.pointerId}; });
  canvas.addEventListener('pointerup', e => {
    if (!press || press.id !== e.pointerId || Math.hypot(e.clientX - press.x, e.clientY - press.y) > 4) return;
    const r = canvas.getBoundingClientRect();
    const hit = markers.pick([(e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height * 2 - 1)]);
    if (hit) markers.select(hit);
  });

  // ---- plan ---------------------------------------------------------------------
  const line = (parent, cls, text) => {
    const div = document.createElement('div');
    div.className = cls;
    div.textContent = text;                    // text from the server: never as HTML
    parent.append(div);
  };

  // Draw a plan: {fc, source, error, missing, stationTypes} as api.js returns it. The
  // page draws what the answer contains; a plan with no route still shows its points.
  function showPlan(got) {
    const model = got.fc ? parsePlan(got.fc) : null;
    overlays.setPlan(model);
    markers.set(model ? planMarkers(model, got.stationTypes || {}) : []);
    window.viz3d.plan = {...got, model};

    const route = model && mainRoute(model), facts = [], warnings = ui('plan-warnings');
    const origin = model && model.properties.source ? ` (${model.properties.source})` : '';
    ui('plan-source').textContent =
      got.source === 'last' ? `Last plan from the planner${origin}`
      : got.source === 'default' ? "Default request: saved stations, the planner's default limits, start at the box centre"
      : got.fc ? 'Plan given to the page'
      : got.missing ? 'No plan yet: plan an EVA in the 2D planner, then press Reload plan'
      : 'No plan to show: the terrain works without it.';
    ui('plan-default-box').hidden = Boolean(got.fc);
    if (route) {
      const t = route.totals;
      facts.push(`${(t.length_m ?? route.lengthM).toFixed(0)} m`);
      if (t.time_s !== null) facts.push(`${(t.time_s / 60).toFixed(0)} min`);
      if (t.energy_wh !== null) {
        facts.push(`${t.energy_wh.toFixed(0)} Wh${t.usable_wh !== null ? ` of ${t.usable_wh.toFixed(0)} usable` : ''}`);
      }
    }
    ui('plan-facts').textContent = facts.join(' · ');
    const key = ui('plan-key');
    key.replaceChildren();
    for (const leg of overlays.legs.slice(0, 2)) {
      const item = document.createElement('span'), swatch = document.createElement('i');
      item.className = 'key';
      swatch.style.background = `rgb(${leg.color.join(',')})`;
      item.append(swatch, overlays.legs.length > 1 ? leg.name : 'route');
      key.append(item);
    }
    warnings.replaceChildren();
    if (got.error) line(warnings, 'warn', got.error);
    if (model && !route) line(warnings, 'warn', 'The plan has no route.');
    if (route && route.totals.feasible === false) line(warnings, 'warn', '⚠ Not feasible within the limits');
    for (const w of (model ? model.warnings : [])) line(warnings, 'warn', `⚠ ${w}`);
    for (const n of (model ? model.notes : [])) line(warnings, 'warn', `Ignored: ${n}`);
    dirty = true;
  }

  // The page only reads the saved plan. It never asks for a new one by itself: the
  // server saves every plan it makes, and the guide screen loads the saved one.
  async function fetchPlan(text, ask) {
    ui('plan-reload').disabled = ui('plan-default').disabled = true;
    ui('plan-source').textContent = text;
    try {
      showPlan(await ask());
    } finally {
      ui('plan-reload').disabled = ui('plan-default').disabled = false;
    }
  }
  const reloadPlan = () => fetchPlan('Loading the saved plan…', () => loadLastPlan());
  const planDefault = () => fetchPlan('Planning with the default settings… (about 10 s the first time)',
                                      () => requestDefaultPlan({start: terrain.toMars(0, 0)}));
  ui('plan-reload').addEventListener('click', reloadPlan);
  ui('plan-default').addEventListener('click', planDefault);

  function frame(now) {
    requestAnimationFrame(frame);
    if (pendingRelief !== null) { setRelief(pendingRelief); pendingRelief = null; }
    if (controls.update((now - last) / 1000)) dirty = true;    // wheel easing, auto-rotate, drags
    last = now;
    if (!dirty && !continuous) return;
    renderer.render(scene, camera);
    dirty = false;
    frames++;
    if (now - since >= 1000) {
      fps = frames * 1000 / (now - since);
      frames = 0; since = now;
    }
    readout();
  }
  requestAnimationFrame(frame);

  // Handle for the manual checks listed in the PR and for later blocks.
  // `plan` is {fc, source, error, missing, stationTypes, model} once a plan was asked for.
  window.viz3d = {terrain, scene, camera, controls, renderer, sun, sunDirection, overlays, markers,
                  plan: null, showPlan, reloadPlan, planDefault, setRelief,
                  get fps() { return fps; }, redraw() { dirty = true; }};
  // The terrain is usable while the plan loads. ?plan=default is the user asking.
  const planReady = params.get('plan') === 'default' ? planDefault() : reloadPlan();

  // ?check=<name>: run a reproducible check (checks.js) and show its JSON result.
  const check = params.get('check');
  if (check) {
    const {CHECKS} = await import('./checks.js');
    await planReady;
    const result = CHECKS[check] ? CHECKS[check](window.viz3d) : {error: `unknown check: ${check}`};
    window.viz3d.checkResult = result;
    console.log(JSON.stringify(result));
    const plain = new URLSearchParams(params);
    plain.delete('check');
    showMessage(`<div class="muted">Result of the "${check}" check, shown because the address has
      <b>?check=${check}</b>. <a href="?${plain}">Open the map without it</a>.</div>
      <code style="text-align:left;white-space:pre-wrap">${JSON.stringify(result, null, 1)}</code>`);
    dirty = true;
  }
}

main().catch(err => {
  console.error(err);
  showMessage(`Error: ${err.message}`);
});
