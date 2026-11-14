// 3D map of the boxwork box (P1, issue #42): entry point.
//
// URL parameters (all optional):
//   q=low|high      quality preset (default: low on touch or small screens, else high)
//   k=1..5          local relief exaggeration
//   light=az,el     light direction in degrees: azimuth from north towards east, elevation
//   fps=1           render every frame and show frames per second
//   spin=1          slowly orbit the camera (to measure fps without touching anything)
//   check=shading   run a check from checks.js and show its result as JSON
import * as THREE from 'three';
import { MapControls } from 'three/addons/controls/MapControls.js';
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

function showMessage(html) {
  ui('message').innerHTML = html;
  ui('message').hidden = false;
}

async function main() {
  if (window.innerWidth < 700 || window.innerHeight < 500) ui('about').open = false;
  const quality = pickQuality();
  const canvas = ui('view');
  const renderer = new THREE.WebGLRenderer({canvas, antialias: quality === 'high',
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
    showMessage(`${err.message.replace(BUILD_HINT, '')}<code>${BUILD_HINT}</code>`);
    return;
  }
  scene.add(terrain.group);
  const k = terrain.setExaggeration(Number(params.get('k')) || 1);
  ui('relief-label').textContent = k === 1 ? 'Relief at true scale'
    : `Local relief ×${k} (exaggerated)`;
  ui('quality-label').textContent = `Quality: ${quality} · mesh every ${terrain.step} m · ` +
    `${(terrain.triangles / 1e6).toFixed(1)} M triangles`;

  // Light: one "sun" plus sky light, so slopes facing away are dim but not black.
  const [az, el] = (params.get('light') || '270,35').split(',').map(Number);
  const sun = new THREE.DirectionalLight(0xfff2e2, 2.6);
  sun.position.copy(sunDirection(az, el)).multiplyScalar(5000);
  scene.add(sun, sun.target);
  scene.add(new THREE.HemisphereLight(0xf0d6b8, 0x6b4a36, 1.1));

  // Camera: start south of the box looking north, like a tilted map.
  const controls = new MapControls(camera, canvas);
  controls.target.set(0, terrain.heightAt(0, 0), 0);
  camera.position.set(0, controls.target.y + 1500, 2000);
  Object.assign(controls, {enableDamping: true, dampingFactor: 0.12, zoomToCursor: true,
                           minDistance: 8, maxDistance: 7000, maxPolarAngle: THREE.MathUtils.degToRad(86)});
  controls.autoRotate = params.get('spin') === '1';
  controls.autoRotateSpeed = 2;
  controls.update();

  // Keep the point the camera orbits inside the box and on the ground.
  const edge = terrain.half;
  function settleTarget() {
    const t = controls.target;
    t.x = THREE.MathUtils.clamp(t.x, -edge, edge);
    t.z = THREE.MathUtils.clamp(t.z, -edge, edge);
    t.y = terrain.heightAt(t.x, t.z);
    // Never let the camera sink below the ground.
    const floor = terrain.heightAt(THREE.MathUtils.clamp(camera.position.x, -edge, edge),
                                   THREE.MathUtils.clamp(camera.position.z, -edge, edge)) + 3;
    if (camera.position.y < floor) camera.position.y = floor;
  }

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    dirty = true;
  }

  // Render only when something changed, unless fps/spin ask for every frame.
  const continuous = params.get('fps') === '1' || controls.autoRotate;
  let dirty = true, frames = 0, since = performance.now(), fps = 0;
  controls.addEventListener('change', () => { dirty = true; });
  window.addEventListener('resize', resize);
  resize();

  function readout() {
    const [x, y] = terrain.toMars(controls.target.x, controls.target.z);
    const text = `x ${x.toFixed(0)} m · y ${y.toFixed(0)} m · elevation ` +
      `${terrain.elevation(terrain.heightAt(controls.target.x, controls.target.z, 1)).toFixed(0)} m`;
    ui('readout').textContent = continuous ? `${text} · ${fps.toFixed(0)} fps` : text;
    // The needle shows where north is on screen (north is -Z).
    ui('compass-needle').setAttribute('transform',
      `rotate(${THREE.MathUtils.radToDeg(controls.getAzimuthalAngle())})`);
  }

  function frame(now) {
    requestAnimationFrame(frame);
    controls.update();                                   // applies damping and auto-rotate
    if (!dirty && !continuous) return;
    settleTarget();
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
  window.viz3d = {terrain, scene, camera, controls, renderer, sun, sunDirection,
                  get fps() { return fps; }, redraw() { dirty = true; }};

  // ?check=<name>: run a reproducible check (checks.js) and show its JSON result.
  const check = params.get('check');
  if (check) {
    const {CHECKS} = await import('./checks.js');
    const result = CHECKS[check] ? CHECKS[check](window.viz3d) : {error: `unknown check: ${check}`};
    window.viz3d.checkResult = result;
    console.log(JSON.stringify(result));
    showMessage(`<code style="text-align:left;white-space:pre-wrap">${JSON.stringify(result, null, 1)}</code>`);
    dirty = true;
  }
}

main().catch(err => {
  console.error(err);
  showMessage(`Error: ${err.message}`);
});
