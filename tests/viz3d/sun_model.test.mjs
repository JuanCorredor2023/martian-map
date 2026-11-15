// The Sun of the 3D map (web/3d/sun_model.js). Run from the repo root:  node --test tests/viz3d/
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { SOL_IN_SECONDS, sunPosition } from '../../web/3d/mars_sun.js';
import * as M from '../../web/3d/sun_model.js';

const close = (a, b, tol = 1e-9, what = '') => assert.ok(Math.abs(a - b) <= tol, `${what} ${a} vs ${b}`);
// Centre of the study box (AGENTS.md, contract table).
const SITE = M.siteFromCrs((8142537.492786024 + 8144537.492786024) / 2, (-285463.075189438 - 283463.075189438) / 2);

test('site of the box centre from CRS metres', () => {
  close(SITE.lonEastDeg, 137.3864, 1e-4);
  close(SITE.latCentricDeg, -4.7991, 1e-4);
  close(SITE.latDeg, -4.8558, 1e-4);                     // planetographic
});

test('URL values: sol and local time', () => {
  assert.equal(M.parseSol('4711'), 4711);
  assert.equal(M.parseSol('0'), 0);
  for (const bad of ['', null, undefined, '-3', '47.5', 'abc', '10000']) assert.equal(M.parseSol(bad), null);
  assert.equal(M.parseClock('15:00'), 15);
  assert.equal(M.parseClock('7:30'), 7.5);
  assert.equal(M.parseClock('07'), 7);
  for (const bad of ['', null, '24:00', '12:60', '15h', '1500', '-1:00']) assert.equal(M.parseClock(bad), null);
  assert.equal(M.clockText(15), '15:00');
  assert.equal(M.clockText(7.0833), '07:05');
  assert.equal(M.clockText(23.9999), '00:00');
  assert.equal(M.clockText(24.5), '00:30');
});

test('compass words and the light vector in scene axes (X east, Y up, Z south)', () => {
  assert.deepEqual([0, 44, 90, 135, 180, 225, 270, 315, 350, -10].map(M.compassWord),
                   ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west', 'north', 'north']);
  const same = (a, b) => a.forEach((v, i) => close(v, b[i], 1e-12));
  same(M.sunVector(0, 0), [0, 0, -1]);                   // from the north: -Z
  same(M.sunVector(90, 0), [1, 0, 0]);                   // from the east
  same(M.sunVector(270, 0), [-1, 0, 0]);
  same(M.sunVector(123, 90), [0, 1, 0]);
  const v = M.sunVector(282, 44);
  close(Math.hypot(...v), 1, 1e-12);
});

test('light levels: full by day, no sun light at the horizon, a dim sky at night, no jumps', () => {
  const day = M.lightLevels(44), horizon = M.lightLevels(0), night = M.lightLevels(-30);
  assert.deepEqual([day.sun, day.sky, day.night], [M.SUN_FULL, M.SKY_DAY, false]);     // as before this block
  assert.equal(horizon.sun, 0);
  assert.equal(night.sun, 0);
  assert.equal(night.sky, M.SKY_NIGHT);
  assert.ok(night.night && M.SKY_NIGHT > 0.2);                                         // never black
  assert.ok(horizon.sky > M.SKY_NIGHT && horizon.sky < M.SKY_DAY);
  let prev = M.lightLevels(-20);
  for (let el = -19.9; el <= 30; el += 0.1) {
    const now = M.lightLevels(el);
    assert.ok(now.sun >= prev.sun && now.sky >= prev.sky && now.day >= prev.day, `monotonic at ${el}`);
    assert.ok(now.sun - prev.sun < 0.04 && now.sky - prev.sky < 0.02, `smooth at ${el}`);
    prev = now;
  }
});

test('default afternoon: sol 4711 at 15:00 is lit from the west at full level', () => {
  const s = M.sunState({sol: M.DEFAULT_SOL, hours: M.DEFAULT_HOURS}, SITE);
  assert.equal(new Date(s.utcMs).toISOString().slice(0, 16), '2025-11-06T16:52');
  close(s.ltst, 15, 1e-6);
  close(s.elevation, 43.9, 0.1);
  close(s.azimuth, 282.3, 0.1);
  close(s.ls, 167.4, 0.1);
  assert.equal(s.sun, M.SUN_FULL);
  assert.equal(s.sky, M.SKY_DAY);
  assert.ok(s.direction[0] < 0 && s.direction[1] > 0 && s.direction[2] < 0);           // west, up, a little north
  assert.equal(M.readoutText(s), 'Sun 44° above the horizon · light from the west (azimuth 282°) · Ls 167°');
  assert.equal(M.utcText(s.utcMs), '2025-11-06 16:52 UTC');
});

test('morning from the east, afternoon from the west, noon on the meridian, night says so', () => {
  const at = hours => M.sunState({sol: 4711, hours}, SITE);
  assert.ok(at(7).direction[0] > 0.9 && at(17).direction[0] < -0.9);                   // opposite sides
  close(at(7).elevation, at(17).elevation, 0.05);
  close(at(12).direction[0], 0, 1e-6);
  assert.ok(at(12).elevation > at(11).elevation && at(12).elevation > at(13).elevation);
  const night = at(21);
  assert.ok(night.night && night.sun === 0 && night.sky === M.SKY_NIGHT);
  assert.match(M.readoutText(night), /^Night: the Sun is below the horizon \(45° under it\) · Ls 16[78]°$/);
  assert.match(M.readoutText(at(18)), /^Night: the Sun is below the horizon \(1° under it\)/);
});

test('rehearsal: the Sun advances with the elapsed EVA time from the chosen start', () => {
  const start = M.sunState({sol: 4711, hours: 15}, SITE);
  const later = M.sunState({sol: 4711, hours: 15, elapsedS: 2402.5}, SITE);            // the E4 plan: 40 min
  assert.equal(later.startUtcMs, start.utcMs);
  close(later.utcMs - start.utcMs, 2402500, 1e-6);
  close(later.ltst - 15, M.solarHours(2402.5), 1e-4);                                  // 39 min of Mars clock
  close(M.solarHours(SOL_IN_SECONDS), 24, 1e-12);
  assert.equal(M.clockText(later.ltst), '15:39');
  close(later.hourAngle - start.hourAngle, 360 * 2402.5 / SOL_IN_SECONDS, 1e-3);       // 9.7 degrees
  assert.ok(later.elevation < start.elevation);
  // The state is the Sun of mars_sun.js at that instant, nothing else.
  const p = sunPosition(later.utcMs, SITE);
  assert.deepEqual([later.elevation, later.azimuth, later.ls], [p.elevation, p.azimuth, p.ls]);
});
