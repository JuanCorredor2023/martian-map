// Reproducible checks of the 3D map, run in the browser with ?check=<name>.
// They print a JSON result on the page; the numbers go into paper/notes/P1_3d_map.md.
import * as THREE from 'three';

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

export const CHECKS = {shading: shadingCheck, route: routeCheck};
