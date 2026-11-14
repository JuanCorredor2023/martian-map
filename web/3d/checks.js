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

export const CHECKS = {shading: shadingCheck};
