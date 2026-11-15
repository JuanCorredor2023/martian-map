// Reproducible checks of the 3D map, run in the browser with ?check=<name>.
// They print a JSON result on the page; the numbers go into paper/notes/P1_3d_map.md.
import * as THREE from 'three';
import { SOL_IN_SECONDS, sunPosition } from './mars_sun.js';

function correlation(x, y) {
  const n = x.length;
  let mx = 0, my = 0;
  for (let i = 0; i < n; i++) { mx += x[i]; my += y[i]; }
  mx /= n; my /= n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) {
    sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) ** 2; syy += (y[i] - my) ** 2;
  }
  return Number((sxy / Math.sqrt(sxx * syy)).toFixed(3));
}

// ?check=shading : is the terrain lit from the right side?
//
// Renders the terrain without the photo, seen from straight above, four times: lit
// from the north, south, east and west. The north-minus-south image must follow the
// north-facing slope of the surface being shaded, low + k * detail (same for east
// minus west). If the normal map were mirrored or inverted, the correlation with the
// "detail flipped" surface would be the high one instead.
export function shadingCheck({terrain, scene, renderer, sun, sunDirection}) {
  const N = 250, block = terrain.n / N, k = terrain.k;
  const target = new THREE.WebGLRenderTarget(N, N);
  const camera = new THREE.OrthographicCamera(-terrain.half, terrain.half, terrain.half, -terrain.half, 1, 20000);
  camera.position.set(0, 8000, 0);
  camera.up.set(0, 0, -1);                                 // north at the top of the image
  camera.lookAt(0, 0, 0);

  const hemi = scene.children.find(o => o.isHemisphereLight);
  const saved = {fog: scene.fog, sun: sun.intensity, hemi: hemi.intensity, pos: sun.position.clone(),
                 maps: terrain.materials.map(m => m.map)};
  // Only the terrain is measured: hide the route, the markers and the rotation ring.
  const hidden = scene.children.filter(o => o !== terrain.group && !o.isLight && o.visible);
  hidden.forEach(o => { o.visible = false; });
  scene.fog = null;
  sun.intensity = 1.2;                                     // dim enough not to clip at 255
  hemi.intensity = 0.3;
  terrain.materials.forEach(m => { m.map = null; m.needsUpdate = true; });

  const shot = azimuth => {
    sun.position.copy(sunDirection(azimuth, 35)).multiplyScalar(5000);
    renderer.setRenderTarget(target);
    renderer.render(scene, camera);
    renderer.setRenderTarget(null);
    const rgba = new Uint8Array(N * N * 4);
    renderer.readRenderTargetPixels(target, 0, 0, N, N, rgba);     // rows from the south
    return Float32Array.from({length: N * N}, (_, i) => rgba[i * 4 + 1]);
  };
  const [north, south, east, west] = [0, 180, 90, 270].map(shot);

  const {n, step, low, detail} = terrain;
  const slope = (a, i, j) => {                             // [d/dEast, d/dNorth]
    const jm = Math.max(0, j - 1), jp = Math.min(n - 1, j + 1);
    const im = Math.max(0, i - 1), ip = Math.min(n - 1, i + 1);
    return [(a[i * n + jp] - a[i * n + jm]) / ((jp - jm) * step),
            (a[im * n + j] - a[ip * n + j]) / ((ip - im) * step)];
  };
  const c = {ns: [], ew: [], okN: [], flipN: [], lowN: [], okE: [], flipE: [], lowE: []};
  for (let py = 2; py < N - 2; py++) {
    for (let px = 2; px < N - 2; px++) {
      let le = 0, ln = 0, de = 0, dn = 0;
      for (let a = 0; a < block; a++) {
        for (let b = 0; b < block; b++) {
          const i = (N - 1 - py) * block + a, j = px * block + b;
          const gl = slope(low, i, j), gd = slope(detail, i, j);
          le += gl[0]; ln += gl[1]; de += gd[0]; dn += gd[1];
        }
      }
      const m = block * block, p = py * N + px;
      le /= m; ln /= m; de /= m; dn /= m;
      c.ns.push(north[p] - south[p]); c.ew.push(east[p] - west[p]);
      c.okN.push(-(ln + k * dn)); c.flipN.push(-(ln - k * dn)); c.lowN.push(-ln);
      c.okE.push(-(le + k * de)); c.flipE.push(-(le - k * de)); c.lowE.push(-le);
    }
  }

  scene.fog = saved.fog; sun.intensity = saved.sun; hemi.intensity = saved.hemi;
  sun.position.copy(saved.pos);
  hidden.forEach(o => { o.visible = true; });
  terrain.materials.forEach((m, i) => { m.map = saved.maps[i]; m.needsUpdate = true; });
  target.dispose();

  const mean = a => Number((a.reduce((s, v) => s + v, 0) / a.length).toFixed(2));
  return {
    check: 'shading', quality: terrain.quality, mesh_step_m: step, exaggeration: k,
    north_minus_south: {correct: correlation(c.ns, c.okN), detail_flipped: correlation(c.ns, c.flipN),
                        hillside_only: correlation(c.ns, c.lowN)},
    east_minus_west: {correct: correlation(c.ew, c.okE), detail_flipped: correlation(c.ew, c.flipE),
                      hillside_only: correlation(c.ew, c.lowE)},
    mean_brightness: {north: mean(north), south: mean(south), east: mean(east), west: mean(west)},
  };
}

// ?check=route : is the route on the ground, as long as the plan says, and are the
// markers where the plan puts them?
//
// For k = 1, 3 and 5 it measures the height of the drawn route above the drawn terrain
// at every vertex of the drawn line and at three points inside every segment (a straight
// segment would dip under a convex crease of the mesh if the line were not cut at the
// triangle edges). The terrain height used is terrain.surfaceAt(); to show that it is
// the mesh that is really drawn, vertical rays are cast against the triangles at about
// 20 vertices spread along each leg and compared with it.
export function routeCheck({terrain, overlays, markers, plan, setRelief}) {
  const round = (v, d = 3) => Number(v.toFixed(d));
  const out = {check: 'route', quality: terrain.quality, mesh_step_m: terrain.step, lift_m: overlays.lift,
               source: plan && plan.source, legs: overlays.legs.map(l => ({name: l.name, route_vertices: l.x.length, drawn_vertices: l.ground.length / 2}))};
  if (!overlays.legs.length) return {...out, error: 'no route drawn'};
  const startK = terrain.k, raycaster = new THREE.Raycaster(), down = new THREE.Vector3(0, -1, 0);
  out.clearance_m = [1, 3, 5].map(k => {
    setRelief(k);
    let atVertex = Infinity, inside = Infinity, rayError = 0, rays = 0;
    for (const {positions: p} of overlays.legs) {
      const n = p.length / 3, every = Math.max(1, Math.floor(n / 20));
      for (let i = 0; i < n; i++) {
        const X = p[i * 3], Y = p[i * 3 + 1], Z = p[i * 3 + 2];
        atVertex = Math.min(atVertex, Y - terrain.surfaceAt(X, Z));
        if (i % every === 0) {
          raycaster.set(new THREE.Vector3(X, 10000, Z), down);
          const hit = raycaster.intersectObjects(terrain.group.children, false)[0];
          if (hit) { rayError = Math.max(rayError, Math.abs(hit.point.y - terrain.surfaceAt(X, Z))); rays++; }
        }
        if (i === n - 1) continue;
        for (const f of [0.25, 0.5, 0.75]) {
          const x = X + (p[i * 3 + 3] - X) * f, y = Y + (p[i * 3 + 4] - Y) * f, z = Z + (p[i * 3 + 5] - Z) * f;
          inside = Math.min(inside, y - terrain.surfaceAt(x, z));
        }
      }
    }
    return {k: terrain.k, min_at_vertices: round(atVertex), min_inside_segments: round(inside),
            rays, max_ray_vs_surfaceAt: round(rayError, 6)};
  });
  setRelief(startK);

  // 2D length of what is drawn (both legs, the return one with its sideways shift)
  // against the length the plan declares.
  let drawn = 0;
  for (const {positions: p} of overlays.legs) {
    for (let i = 3; i < p.length; i += 3) drawn += Math.hypot(p[i] - p[i - 3], p[i + 2] - p[i - 1]);
  }
  const route = plan && plan.model && plan.model.routes.find(r => r.kind === 'route');
  const declared = route ? route.totals.length_m : null;
  out.length_m = {drawn: round(drawn, 1), declared, vertices_2d: route ? round(route.lengthM, 1) : null,
                  drawn_vs_declared_pct: declared ? round(100 * (drawn - declared) / declared, 2) : null};

  // Markers: scene position back to Mars metres against the marker's own coordinates,
  // and height above the ground (the habitat label stands on its dome).
  let offset = 0, above = 0;
  for (const item of markers.items) {
    const [x, y] = terrain.toMars(item.position[0], item.position[2]);
    offset = Math.max(offset, Math.hypot(x - item.marker.x, y - item.marker.y));
    if (!item.dome) above = Math.max(above, Math.abs(item.sprite.position.y - terrain.surfaceAt(item.position[0], item.position[2])));
  }
  out.markers = {count: markers.items.length, kinds: markers.items.map(i => i.marker.kind).join(' '),
                 max_position_error_m: round(offset, 6), max_height_off_ground_m: round(above, 6)};
  return out;
}

// ?check=rehearse : does the rehearsal camera walk the route as it should, and does
// leaving the rehearsal put everything back?
//
// Enters the rehearsal and walks the whole route on the real terrain in steps of 0.1 s
// of plan time (under 0.1 m), in first person: height of the eye above the drawn ground
// under it, largest move of the camera in one step, fastest turn of the heading per
// metre walked (the turn on the spot at a stop is reported apart), and distance of the
// camera from the true route (against every segment of it). Then the chase view every
// second; then real playback at x60 through update(), to see it pause at each stop
// with its card; then exit, twice, comparing camera, relief and scene with before.
// Nothing is asked from the server (the walkback lines on pause are switched off).
export function rehearseCheck({terrain, scene, camera, controls, rehearsal, plan}) {
  const round = (v, d = 3) => Number(v.toFixed(d));
  const model = rehearsal.model, route = plan && plan.model && plan.model.routes.find(r => r.kind === 'route');
  const out = {check: 'rehearse', quality: terrain.quality, mesh_step_m: terrain.step, source: plan && plan.source};
  if (!model || !route) return {...out, error: 'no route to rehearse'};
  const snapshot = () => ({
    position: camera.position.toArray(), quaternion: camera.quaternion.toArray(), fov: camera.fov, near: camera.near,
    k: terrain.k, yaw: controls.yaw, pitch: controls.pitch, enabled: controls.enabled,
    children: scene.children.map(o => o.name || o.type).join(' '),
    label: document.getElementById('relief-label').textContent, slider: document.getElementById('relief').disabled,
    player: document.getElementById('player').hidden, card: document.getElementById('card').hidden});
  const before = snapshot(), walkbackOnPause = rehearsal.walkbackOnPause, DEG = Math.PI / 180;
  const turnOf = (a, b) => { let d = Math.abs(a - b) % (2 * Math.PI); return (d > Math.PI ? 2 * Math.PI - d : d) / DEG; };
  rehearsal.walkbackOnPause = false;
  rehearsal.enter();
  out.route = {vertices: route.coords.length, length_m: round(model.length, 1), duration_s: round(model.duration, 1),
               time_base: model.assumedSpeed === null ? 'profile t_s' : `assumed ${model.assumedSpeed} m/s`,
               stops: model.stops.map(s => ({vertex: s.index, station: s.station && s.station.id,
                                             arrive_s: round(s.arrive, 1), wait_s: round(s.waitS, 1)}))};
  out.while_rehearsing = {relief_k: terrain.k, relief_label: document.getElementById('relief-label').textContent,
                          slider_disabled: document.getElementById('relief').disabled, near_m: camera.near,
                          fov_deg: camera.fov, controls_enabled: controls.enabled};

  // First person, every 0.1 s of plan time.
  const first = {steps: 0, eye_min_m: Infinity, eye_max_m: 0, max_move_m: 0, max_turn_deg_per_m: 0,
                 max_turn_on_the_spot_deg: 0, max_off_route_m: 0};
  const c = route.coords;
  let prev = null;
  for (let time = model.start; ; time = Math.min(model.end, time + 0.1)) {
    rehearsal.seek(time);
    const s = rehearsal.state, p = camera.position, eye = p.y - terrain.surfaceAt(p.x, p.z);
    first.eye_min_m = Math.min(first.eye_min_m, eye); first.eye_max_m = Math.max(first.eye_max_m, eye);
    const [x, y] = terrain.toMars(p.x, p.z);
    let off = Infinity;
    for (let i = 1; i < c.length; i++) {
      const ax = c[i - 1][0], ay = c[i - 1][1], dx = c[i][0] - ax, dy = c[i][1] - ay, len2 = dx * dx + dy * dy;
      const f = len2 > 0 ? Math.min(1, Math.max(0, ((x - ax) * dx + (y - ay) * dy) / len2)) : 0;
      off = Math.min(off, Math.hypot(x - ax - dx * f, y - ay - dy * f));
    }
    first.max_off_route_m = Math.max(first.max_off_route_m, off);
    if (prev) {
      const walked = s.distance - prev.distance, turn = turnOf(rehearsal.pose.yaw, prev.yaw);
      first.max_move_m = Math.max(first.max_move_m, p.distanceTo(prev.p));
      const atStop = s.standing || prev.standing ||
        model.stops.some(stop => [stop.arrive, stop.leave].some(t => t > prev.time - 1e-9 && t < s.time + 1e-9));
      if (atStop || walked < 1e-9) first.max_turn_on_the_spot_deg = Math.max(first.max_turn_on_the_spot_deg, turn);
      else first.max_turn_deg_per_m = Math.max(first.max_turn_deg_per_m, turn / walked);
    }
    prev = {p: p.clone(), yaw: rehearsal.pose.yaw, distance: s.distance, standing: s.standing, time: s.time};
    first.steps++;
    if (time >= model.end) break;
  }
  out.first_person = Object.fromEntries(Object.entries(first).map(([key, v]) => [key, round(v)]));

  // Chase view, every second.
  rehearsal.setChase(true);
  const chase = {steps: 0, camera_min_above_ground_m: Infinity, to_walker_min_m: Infinity, to_walker_max_m: 0, walker_shown: true};
  for (let time = model.start; time <= model.end; time += 1) {
    rehearsal.seek(time);
    const p = camera.position, w = rehearsal.walker.position;
    chase.camera_min_above_ground_m = Math.min(chase.camera_min_above_ground_m, p.y - terrain.surfaceAt(p.x, p.z));
    chase.to_walker_min_m = Math.min(chase.to_walker_min_m, p.distanceTo(w));
    chase.to_walker_max_m = Math.max(chase.to_walker_max_m, p.distanceTo(w));
    chase.walker_shown = chase.walker_shown && rehearsal.walker.visible && scene.children.includes(rehearsal.walker);
    chase.steps++;
  }
  out.chase = Object.fromEntries(Object.entries(chase).map(([key, v]) => [key, typeof v === 'number' ? round(v) : v]));
  rehearsal.setChase(false);

  // Real playback: x60, 60 updates per second of screen time, pressing play again at each stop.
  rehearsal.seek(model.start);
  rehearsal.speed = 60;
  const playback = {updates: 0, pauses: [], needs_render_while_paused: 0};
  rehearsal.update(0);
  playback.needs_render_while_paused += rehearsal.update(1 / 60) ? 1 : 0;      // paused, nothing touched: no frame
  rehearsal.play();
  while (playback.updates < 1e5) {
    rehearsal.update(1 / 60);
    playback.updates++;
    if (rehearsal.playing) continue;
    const s = rehearsal.state, card = document.querySelector('#card .card-title');
    playback.pauses.push({time_s: round(s.time, 1), vertex: round(s.at, 2), distance_m: round(s.distance, 1),
                          card: document.getElementById('card').hidden ? null : card && card.textContent,
                          text: document.getElementById('rh-progress').textContent});
    if (s.time >= model.end) break;
    rehearsal.play();
  }
  out.playback_x60 = playback;

  // Leave, and do it all once more: nothing may be left behind.
  rehearsal.exit();
  const after1 = snapshot();
  rehearsal.enter(); rehearsal.setChase(true); rehearsal.seek((model.start + model.end) / 2); rehearsal.exit();
  const after2 = snapshot();
  rehearsal.walkbackOnPause = walkbackOnPause;
  const same = after => ({
    camera_moved_m: round(Math.hypot(...after.position.map((v, i) => v - before.position[i])), 9),
    camera_turned: round(Math.max(...after.quaternion.map((v, i) => Math.abs(v - before.quaternion[i]))), 9),
    rest_equal: ['fov', 'near', 'k', 'yaw', 'pitch', 'enabled', 'children', 'label', 'slider', 'player', 'card']
      .every(key => after[key] === before[key])});
  out.after_exit = {once: same(after1), twice: same(after2), relief_k: after2.k, fov_deg: after2.fov, near_m: after2.near,
                    scene: after2.children, listeners_left: rehearsal._listeners.length};
  return out;
}

// ?check=sun : is the scene lit by the Sun of Mars of the chosen sol and time?
//
// For 07:00, 12:00, 15:00, 17:00 and 21:00 local true solar time of the page's sol: the
// Sun's azimuth and elevation computed here again with mars_sun.js from the instant
// the page says, the direction of the light in the scene against the unit vector of
// that azimuth and elevation, the light levels and what the panel says. Then, with
// "Relief only" on, the terrain is rendered from straight above with the page's own
// lights at 07:00 and at 17:00: slopes facing east must be the bright ones in the
// morning and the dark ones in the afternoon. Then the photo is put back and compared
// with before, and the rehearsal is entered to see the Sun advance with the EVA clock
// and return to the start on exit. Everything is left as it was found.
export function sunCheck({terrain, scene, renderer, sun, sunView, rehearsal}) {
  const round = (v, d = 3) => Number(v.toFixed(d)), text = id => document.getElementById(id).textContent;
  const out = {check: 'sun', quality: terrain.quality, exaggeration: terrain.k};
  if (!sunView.state) return {...out, error: 'the light is fixed by ?light=: the Sun is not used'};
  const hemi = scene.children.find(o => o.isHemisphereLight);
  const before = {start: {...sunView.start}, reliefOnly: sunView.reliefOnly};
  const site = sunView.site, sol = before.start.sol;
  out.site = {lon_east_deg: round(site.lonEastDeg, 4), lat_planetocentric_deg: round(site.latCentricDeg, 4),
              lat_planetographic_deg: round(site.latDeg, 4)};
  out.sol = sol;

  // Light direction, levels and panel at five times of the sol.
  out.times = [7, 12, 15, 17, 21].map(hours => {
    sunView.set({hours});
    const s = sunView.state, p = sunPosition(s.utcMs, site);
    const az = THREE.MathUtils.degToRad(p.azimuth), el = THREE.MathUtils.degToRad(p.elevation);
    const want = new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el));
    const light = sun.position.clone().sub(sun.target.position).normalize();
    return {local_true_solar_time: text('sun-time-text'), utc: new Date(s.utcMs).toISOString(), ls_deg: round(p.ls, 2),
            ltst_h: round(p.ltst, 5), azimuth_deg: round(p.azimuth, 2), elevation_deg: round(p.elevation, 2),
            light_off_the_sun_deg: round(THREE.MathUtils.radToDeg(light.angleTo(want)), 6),
            light_from: light.x > 0.1 ? 'east' : light.x < -0.1 ? 'west' : 'meridian',
            sun_light: round(sun.intensity), sky_light: round(hemi.intensity),
            sky_colour: `#${scene.background.getHexString()}`, panel: text('sun-readout')};
  });

  // Relief only, from above, with the page's own lights: 07:00 against 17:00.
  const maps = terrain.materials.map(m => m.map), colours = terrain.materials.map(m => m.color.getHex());
  sunView.setReliefOnly(true);
  const N = 250, block = terrain.n / N, k = terrain.k;
  const target = new THREE.WebGLRenderTarget(N, N);
  const camera = new THREE.OrthographicCamera(-terrain.half, terrain.half, terrain.half, -terrain.half, 1, 20000);
  camera.position.set(0, 8000, 0);
  camera.up.set(0, 0, -1);                                 // north at the top of the image
  camera.lookAt(0, 0, 0);
  const hidden = scene.children.filter(o => o !== terrain.group && !o.isLight && o.visible);
  hidden.forEach(o => { o.visible = false; });
  const fog = scene.fog;
  scene.fog = null;
  const shot = hours => {
    sunView.set({hours});
    renderer.setRenderTarget(target);
    renderer.render(scene, camera);
    renderer.setRenderTarget(null);
    const rgba = new Uint8Array(N * N * 4);
    renderer.readRenderTargetPixels(target, 0, 0, N, N, rgba);     // rows from the south
    return Float32Array.from({length: N * N}, (_, i) => rgba[i * 4 + 1]);
  };
  const morning = shot(7), afternoon = shot(17);
  scene.fog = fog;
  hidden.forEach(o => { o.visible = true; });
  target.dispose();

  // East-facing slope of the shaded surface (low + k * detail), mean of each block.
  const {n, step, low, detail} = terrain;
  const eastward = (a, i, j) => {
    const jm = Math.max(0, j - 1), jp = Math.min(n - 1, j + 1);
    return -(a[i * n + jp] - a[i * n + jm]) / ((jp - jm) * step);
  };
  const diff = [], facing = [], side = {east: [0, 0, 0], west: [0, 0, 0]};
  let clipped = 0;
  for (let py = 2; py < N - 2; py++) {
    for (let px = 2; px < N - 2; px++) {
      let e = 0;
      for (let a = 0; a < block; a++) {
        for (let b = 0; b < block; b++) {
          const i = (N - 1 - py) * block + a, j = px * block + b;
          e += eastward(low, i, j) + k * eastward(detail, i, j);
        }
      }
      e /= block * block;
      const q = py * N + px;
      diff.push(morning[q] - afternoon[q]);
      facing.push(e);
      if (morning[q] >= 255 || afternoon[q] >= 255) clipped++;
      const bin = e > 0.1 ? side.east : e < -0.1 ? side.west : null;       // steeper than 1 in 10
      if (bin) { bin[0] += morning[q]; bin[1] += afternoon[q]; bin[2]++; }
    }
  }
  const means = b => ({pixels: b[2], at_07: round(b[0] / b[2], 1), at_17: round(b[1] / b[2], 1)});
  out.relief_only_from_above = {
    morning_minus_afternoon_vs_east_facing_slope: correlation(diff, facing),
    mean_brightness_east_facing: means(side.east), mean_brightness_west_facing: means(side.west),
    clipped_pixels: clipped, photo_hidden: terrain.materials.every(m => m.map === null)};

  sunView.setReliefOnly(false);
  out.photo_back = {tiles: maps.length, same_textures: terrain.materials.every((m, i) => m.map === maps[i]),
                    same_colours: terrain.materials.every((m, i) => m.color.getHex() === colours[i])};

  // Rehearsal: the Sun follows the EVA clock from 15:00 and goes back on exit.
  sunView.set({hours: 15});
  const start = {...sunView.state}, model = rehearsal.model;
  if (model) {
    const walkbackOnPause = rehearsal.walkbackOnPause;
    rehearsal.walkbackOnPause = false;
    rehearsal.enter();
    const moved = elapsed => {
      rehearsal.seek(model.start + elapsed);
      const s = sunView.state;
      return {eva_s: round(elapsed, 1), sun_advanced_s: round((s.utcMs - start.utcMs) / 1000, 3),
              local_time_advanced_min: round((s.ltst - start.ltst) * 60, 3),
              expected_min: round(elapsed / SOL_IN_SECONDS * 1440, 3), panel_time: text('sun-time-text'),
              elevation_deg: round(s.elevation, 2), azimuth_deg: round(s.azimuth, 2),
              controls_disabled: document.getElementById('sun-time').disabled && document.getElementById('sun-sol').disabled,
              note: text('sun-note')};
    };
    out.rehearsal = {duration_s: round(model.duration, 1), at: [0, 600, model.duration].map(moved)};
    rehearsal.exit();
    rehearsal.walkbackOnPause = walkbackOnPause;
    const s = sunView.state;
    out.rehearsal.after_exit = {sun_back_at_start: s.utcMs === start.utcMs && s.elevation === start.elevation,
                                panel_time: text('sun-time-text'), elevation_deg: round(s.elevation, 2),
                                controls_disabled: document.getElementById('sun-time').disabled};
  } else {
    out.rehearsal = {error: 'no route to rehearse'};
  }

  sunView.set(before.start);
  sunView.setReliefOnly(before.reliefOnly);
  return out;
}

export const CHECKS = {shading: shadingCheck, route: routeCheck, rehearse: rehearseCheck, sun: sunCheck};
