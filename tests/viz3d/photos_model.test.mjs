// Rover photos of the 3D map (web/3d/photos_model.js). Run from the repo root:  node --test tests/viz3d/
//
// Fixture: fixtures/photos_catalog.json, three stops (7 Navcam photos, one from the left
// camera) of the real block 1 catalogue, generation 9d2e6fb0bc52df508447d619, trimmed as
// its "provenance" says: stop_0000 has one view and three sectors missing, stop_0018 two
// views and two sectors missing, stop_0079 four views and none missing.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { mslClock } from '../../web/3d/mars_sun.js';
import { siteFromCrs, sunState } from '../../web/3d/sun_model.js';
import * as P from '../../web/3d/photos_model.js';

const RAW = JSON.parse(readFileSync(new URL('./fixtures/photos_catalog.json', import.meta.url), 'utf8'));
const MODEL = P.parseCatalog(structuredClone(RAW));
const close = (a, b, tol, what = '') => assert.ok(Math.abs(a - b) <= tol, `${what} ${a} vs ${b} (tolerance ${tol})`);
const DEG = Math.PI / 180;
// The catalogue changed by `change` (a function that edits a copy), parsed.
const parsedWith = change => { const c = structuredClone(RAW); change(c); return P.parseCatalog(c); };
const LEFT_ID = 'NLB_811807254EDR_F1190000NCAM00290M_';
// Which sector a compass bearing (degrees) falls in, by its words: from north to east first.
const sectorWords = deg => ['N to E', 'E to S', 'S to W', 'W to N'][Math.floor((((deg % 360) + 360) % 360) / 90)];

test('the real catalogue parses whole: every stop, every photo, numbers as given', () => {
  assert.deepEqual(MODEL.problems, []);
  assert.equal(MODEL.generation, '9d2e6fb0bc52df508447d619');
  assert.deepEqual(MODEL.groups.map(g => g.id), ['stop_0000', 'stop_0018', 'stop_0079']);
  assert.equal(MODEL.photos.length, 7);
  assert.ok(MODEL.byId instanceof Map && MODEL.byId.size === 7);
  for (const raw of RAW.photos) {
    const p = MODEL.byId.get(raw.id);
    assert.equal(p.groupId, raw.group_id);
    assert.equal(p.sol, raw.sol);
    assert.equal(p.utcMs, Date.parse(raw.date_taken));
    assert.equal(p.lmst, raw.lmst);
    assert.equal(p.camera, raw.id === LEFT_ID ? 'Navcam left' : 'Navcam right');
    assert.equal(p.credit, 'NASA/JPL-Caltech');
    assert.equal(p.sourceUrl, raw.https_url);
    assert.equal(p.distanceM, raw.distance_to_representative_m);
    for (const key of ['x', 'y', 'z', 'heading', 'pitch', 'fov']) assert.equal(p[key], raw.pose[key], key);
    // The three images, as addresses under the photo folder of the page.
    assert.equal(p.available, true);
    assert.deepEqual(p.images, {thumb: P.PHOTO_ROOT + raw.assets.thumbnail, card: P.PHOTO_ROOT + raw.assets.unwarped,
                                compare: P.PHOTO_ROOT + raw.assets.rectified});
    for (const url of Object.values(p.images)) assert.match(url, /^\/tiles\/3d\/photos\/generations\/[0-9a-f]+\/assets\/[\w.-]+$/);
  }
  for (const raw of RAW.groups) {
    const g = MODEL.groups.find(x => x.id === raw.id);
    assert.deepEqual([g.x, g.y, g.z], [...raw.representative.xy, raw.representative.z]);
    assert.deepEqual(g.photoIds, raw.photo_ids);
  }
});

test('missing sectors are named in words, and no view of the stop looks into one', () => {
  const missing = Object.fromEntries(MODEL.groups.map(g => [g.id, g.missingSectors]));
  assert.deepEqual(missing, {stop_0000: ['N to E', 'E to S', 'W to N'], stop_0018: ['N to E', 'W to N'], stop_0079: []});
  for (const g of MODEL.groups) {
    const seen = new Set(g.photoIds.map(id => sectorWords(MODEL.byId.get(id).heading / DEG)));
    for (const words of g.missingSectors) assert.ok(!seen.has(words), `${g.id} has a view ${words}`);
    assert.equal(seen.size + g.missingSectors.length, 4, `${g.id}: every sector is either seen or missing`);
  }
});

test('not a catalogue, or another schema version: an error, said in words', () => {
  for (const bad of [null, 'catalog', 42, [], {}, {...RAW, schema_version: 2}, {...RAW, schema_version: '1'},
                     {schema_version: 1, groups: {}, photos: []}, {schema_version: 1, groups: []}]) {
    assert.throws(() => P.parseCatalog(bad), /not a photo catalogue|schema_version/);
  }
  const empty = P.parseCatalog({schema_version: 1, groups: [], photos: []});
  assert.deepEqual([empty.groups, empty.photos, empty.problems, empty.byId.size], [[], [], [], 0]);
});

test('a malformed photo is skipped and named in problems; the rest of its stop stays', () => {
  const victim = RAW.photos[1];                         // stop_0018's first view
  const cases = [
    [c => { delete c.photos[1].pose; }, /missing pose/],
    [c => { c.photos[1].pose = 'here'; }, /missing pose/],
    [c => { c.photos[1].pose.heading = null; }, /pose\.heading is not a finite number/],
    [c => { c.photos[1].pose.z = '-3700.1'; }, /pose\.z is not a finite number/],
    [c => { c.photos[1].pose.pitch = JSON.parse('1e999'); }, /pose\.pitch is not a finite number/],
    [c => { delete c.photos[1].pose.x; }, /pose\.x is not a finite number/],
    [c => { c.photos[1].group_id = 'stop_9999'; }, /unknown group/],
    [c => { c.photos[1].group_id = 'stop_0000'; }, /stop_0000 does not list it/],
    [c => { c.photos[1].date_taken = 'last Tuesday'; }, /date_taken/],
    [c => { c.photos[1].sol = 4489.5; }, /sol/],
    [c => { c.photos[1].instrument = 'MAST_LEFT'; }, /not a Navcam/],
  ];
  for (const [change, reason] of cases) {
    const m = parsedWith(change);
    assert.equal(m.problems.length, 1, JSON.stringify(m.problems));
    assert.equal(m.problems[0].id, victim.id);
    assert.match(m.problems[0].reason, reason);
    assert.equal(m.photos.length, 6);
    assert.ok(!m.byId.has(victim.id));
    for (const g of m.groups) assert.ok(!g.photoIds.includes(victim.id));
    assert.deepEqual(m.groups.find(g => g.id === 'stop_0018').photoIds, [RAW.photos[2].id]);
  }
});

test('bad photo ids, duplicates and things that are not photos are skipped and named', () => {
  for (const id of ['../x', '<b>', '', 'a'.repeat(81), 'NRB 1', 42, null]) {
    const m = parsedWith(c => { c.photos[1].id = id; });
    assert.equal(m.photos.length, 6);
    assert.ok(m.problems.some(p => /bad id/.test(p.reason)), `id ${JSON.stringify(id)}`);
    // The stop still lists the old id, which is no longer in the catalogue: said too.
    assert.ok(m.problems.some(p => p.id === RAW.photos[1].id && /not in the catalogue/.test(p.reason)));
    assert.ok(![...m.byId.keys()].includes(id));
  }
  const dup = parsedWith(c => { c.photos.push({...structuredClone(c.photos[3]), sol: 1}); });
  assert.deepEqual(dup.problems, [{id: RAW.photos[3].id, reason: 'photo skipped: duplicate id'}]);
  assert.equal(dup.byId.get(RAW.photos[3].id).sol, RAW.photos[3].sol);   // the first one is kept
  const junk = parsedWith(c => { c.photos.push('photo', null, [1, 2]); });
  assert.deepEqual(junk.problems.map(p => p.id), ['photos[7]', 'photos[8]', 'photos[9]']);
  assert.equal(junk.photos.length, 7);
});

test('a malformed stop is skipped with its photos, and every one is named', () => {
  const cases = [
    [c => { delete c.groups[1].representative; }, /no position/],
    [c => { c.groups[1].representative.xy = [8143795.688, null]; }, /no position/],
    [c => { c.groups[1].representative.z = 'low'; }, /no position/],
    [c => { c.groups[1].photo_ids = 'all'; }, /photo_ids is not a list/],
    [c => { c.groups[1].id = '<script>'; }, /bad id/],
  ];
  for (const [change, reason] of cases) {
    const m = parsedWith(change);
    assert.deepEqual(m.groups.map(g => g.id), ['stop_0000', 'stop_0079']);
    assert.match(m.problems[0].reason, reason);
    const orphans = m.problems.slice(1);
    assert.deepEqual(orphans.map(p => p.id), [RAW.photos[1].id, RAW.photos[2].id]);
    for (const p of orphans) assert.match(p.reason, /unknown group "stop_0018"/);
    assert.equal(m.photos.length, 5);
    assert.equal(P.photoMarkers(m).length, 2);
  }
  const twice = parsedWith(c => { c.groups.push(structuredClone(c.groups[0])); });
  assert.deepEqual(twice.problems, [{id: 'stop_0000', reason: 'stop skipped: duplicate id'}]);
  assert.equal(twice.groups.length, 3);
  const listsGhost = parsedWith(c => { c.groups[0].photo_ids.push('NRB_000000000EDR_F0000000NCAM00000M_'); });
  assert.deepEqual(listsGhost.groups[0].photoIds, [RAW.photos[0].id]);
  assert.match(listsGhost.problems[0].reason, /stop_0000 lists a photo that is not in the catalogue/);
});

test('images only when the assets are available, and only under the photo folder', () => {
  for (const status of ['missing_source', 'processing_failed', undefined]) {
    const m = parsedWith(c => { c.photos[0].assets.status = status; });
    const p = m.byId.get(RAW.photos[0].id);
    assert.deepEqual(m.problems, []);                    // still a photo: the card says the image is not there
    assert.equal(p.available, false);
    assert.deepEqual(p.images, {thumb: null, card: null, compare: null});
  }
  const noAssets = parsedWith(c => { delete c.photos[0].assets; }).byId.get(RAW.photos[0].id);
  assert.equal(noAssets.available, false);
  for (const path of ['../../../base/dem_1m.tif', '/etc/x.png', 'https://example.org/x.png', 'a\\b.png',
                      'x.png?raw=1', 'generations/./x.png', '', 42]) {
    const m = parsedWith(c => { c.photos[0].assets.rectified = path; });
    const p = m.byId.get(RAW.photos[0].id);
    assert.equal(p.available, false, `path ${JSON.stringify(path)}`);
    assert.deepEqual(p.images, {thumb: null, card: null, compare: null});
    assert.equal(m.problems.length, 1);
    assert.match(m.problems[0].reason, /image path is missing or unsafe/);
  }
});

test('catalogue text stays plain text: kept as written, never turned into markup or a script link', () => {
  const evil = '<img src=x onerror=alert(1)> & co';
  const m = parsedWith(c => {
    c.photos[0].image_credit = evil;
    c.photos[0].https_url = 'javascript:alert(1)';
    c.photos[1].https_url = 'http://mars.nasa.gov/x.JPG';
    c.photos[2].lmst = '<b>noon</b>';
  });
  const p = m.byId.get(RAW.photos[0].id);
  assert.equal(p.credit, evil);                          // for textContent: neither escaped nor interpreted
  assert.deepEqual(P.photoFacts(p).find(r => r[0] === 'Credit'), ['Credit', evil]);
  assert.equal(p.sourceUrl, null);
  assert.equal(m.byId.get(RAW.photos[1].id).sourceUrl, null);
  assert.deepEqual(P.photoFacts(m.byId.get(RAW.photos[2].id)).find(r => r[0] === 'Local time'), ['Local time', 'not given']);
  // What the module writes itself has no markup or entities in it.
  for (const photo of MODEL.photos) {
    for (const [label, value] of P.photoFacts(photo)) {
      assert.equal(typeof value, 'string');
      assert.doesNotMatch(label + value, /[<>&]/);
    }
  }
  for (const marker of P.photoMarkers(MODEL)) assert.doesNotMatch(marker.label, /[<>&]/);
});

test('one pin per stop with photos, labelled with a camera, all in one colour', () => {
  const markers = P.photoMarkers(MODEL);
  assert.deepEqual(markers.map(m => [m.id, m.kind, m.label]),
                   [['photo:stop_0000', 'photo', '📷'], ['photo:stop_0018', 'photo', '📷'], ['photo:stop_0079', 'photo', '📷']]);
  for (const [i, m] of markers.entries()) {
    assert.deepEqual([m.x, m.y], RAW.groups[i].representative.xy);
    assert.deepEqual(m.data, {kind: 'photo', groupId: RAW.groups[i].id});
    assert.deepEqual(m.color, markers[0].color);
    assert.ok(m.color.length === 3 && m.color.every(v => Number.isInteger(v) && v >= 0 && v <= 255));
  }
  // A stop whose only photo did not parse keeps its place in the model but has no pin;
  // a stop that lost one view keeps the views it has.
  const m = parsedWith(c => { delete c.photos[0].pose; delete c.photos[3].pose; });
  assert.deepEqual(m.groups.find(g => g.id === 'stop_0000').photoIds, []);
  assert.deepEqual(P.photoMarkers(m).map(x => x.id), ['photo:stop_0018', 'photo:stop_0079']);
  assert.equal(m.groups.find(g => g.id === 'stop_0079').photoIds.length, 3);
});

test('views of a stop: from north clockwise, with the compass word of each heading', () => {
  const views = P.viewsOf(MODEL, 'stop_0079');
  assert.deepEqual(views.map(v => [Math.round(v.heading / DEG), v.direction, v.camera]),
                   [[50, 'north-east', 'Navcam right'], [110, 'east', 'Navcam right'],
                    [235, 'south-west', 'Navcam left'], [350, 'north', 'Navcam right']]);
  assert.deepEqual(P.viewsOf(MODEL, 'stop_0018').map(v => v.direction), ['south', 'south-west']);
  // The order is made here, not taken from the catalogue: reversed lists give the same views.
  const reversed = parsedWith(c => { c.photos.reverse(); for (const g of c.groups) g.photo_ids.reverse(); });
  assert.deepEqual(P.viewsOf(reversed, 'stop_0079').map(v => v.id), views.map(v => v.id));
  // A heading written past a full turn or below zero sorts where it points.
  const wrapped = parsedWith(c => { c.photos[3].pose.heading -= 2 * Math.PI; c.photos[5].pose.heading = -0.1; });
  assert.deepEqual(P.viewsOf(wrapped, 'stop_0079').map(v => [v.id, v.direction]),
                   [[RAW.photos[3].id, 'north-east'], [RAW.photos[4].id, 'east'], [RAW.photos[6].id, 'north'], [LEFT_ID, 'north']]);
  assert.ok(views.every(v => MODEL.byId.get(v.id).direction === undefined));     // copies: the model is unchanged
  assert.deepEqual(P.viewsOf(MODEL, 'stop_9999'), []);
});

test("photo view pose: 1.9 m above the ground is right; under it, too high or off the map is reported, never fixed", () => {
  const photo = MODEL.photos[0];
  const same = pose => assert.deepEqual([pose.x, pose.y, pose.heading, pose.pitch, pose.fov],
                                        [photo.x, photo.y, photo.heading, photo.pitch, 40]);
  const good = P.photoPose(photo, photo.z - 1.9);
  same(good);
  close(good.eyeHeight, 1.9, 1e-9);
  assert.deepEqual([good.ok, good.reason], [true, null]);
  // The real stops: with the rover's own PLACES position as the ground, every camera is about 2 m up.
  for (const raw of RAW.photos) {
    const pose = P.photoPose(MODEL.byId.get(raw.id), raw.rover_position.z);
    assert.ok(pose.ok && pose.eyeHeight > 1.5 && pose.eyeHeight < 2.5, `${raw.id}: ${pose.eyeHeight} m`);
  }
  for (const eye of [0.5, 4]) assert.equal(P.photoPose(photo, photo.z - eye).ok, true, `${eye} m`);
  const bad = [[-0.4, /0\.40 m under the ground/], [0, /0\.00 m above/], [0.49, /0\.49 m above/],
               [4.01, /4\.01 m above/], [7, /7\.00 m above/]];
  for (const [eye, reason] of bad) {
    const pose = P.photoPose(photo, photo.z - eye);
    same(pose);
    close(pose.eyeHeight, eye, 1e-9, 'eye height as it is');
    assert.equal(pose.ok, false, `${eye} m`);
    assert.match(pose.reason, reason);
  }
  for (const ground of [null, undefined, NaN]) {
    const pose = P.photoPose(photo, ground);
    same(pose);
    assert.deepEqual([pose.ok, pose.eyeHeight], [false, null]);
    assert.match(pose.reason, /outside the map/);
  }
});

test('square view: on wide, tall and square canvases the square spans the field both across and up', () => {
  for (const [w, h] of [[1600, 900], [1280, 720], [900, 1600], [390, 844], [800, 800]]) {
    for (const fov of [40, 25]) {
      const v = P.squareView(w, h, fov);
      // Focal length in pixels of a camera with this vertical field on this canvas
      // (square pixels: the same across).
      const f = (h / 2) / Math.tan(v.fovY * DEG / 2);
      close(v.side / 2, f * Math.tan(fov * DEG / 2), 1e-9, `${w}x${h} at ${fov} deg: half side`);
      assert.equal(v.side, Math.min(w, h));               // as large as the canvas allows
      close(2 * v.left + v.side, w, 1e-9, 'centred across');
      close(2 * v.top + v.side, h, 1e-9, 'centred up');
      assert.ok(v.left >= 0 && v.top >= 0);
      // The camera sees at least the field on both axes, and exactly it on the short one.
      const across = 2 * Math.atan((w / 2) / f) / DEG;
      assert.ok(v.fovY >= fov - 1e-9 && across >= fov - 1e-9);
      close(Math.min(v.fovY, across), fov, 1e-9);
    }
  }
  assert.equal(P.squareView(1600, 900).fovY, 40);       // default field: the rectified images'
  for (const [w, h] of [[0, 0], [0, 900], [1600, 0], [-5, 10]]) {
    assert.deepEqual(P.squareView(w, h), {fovY: 40, side: 0, left: 0, top: 0});
  }
});

test("Sun of the photo: the mission clock reproduces each photo's LMST, and true solar time differs from it by under the equation of time", t => {
  const rows = [];
  for (const photo of MODEL.photos) {
    const [, sol, hh, mm, ss] = /^Sol-(\d{5})M(\d\d):(\d\d):(\d\d\.\d+)$/.exec(photo.lmst).map(Number);
    const lmstHours = hh + mm / 60 + ss / 3600;
    // The catalogue's own LMST is Curiosity's clock at its UTC instant, to within the
    // seconds of mars_sun.js (tests/viz3d/mars_sun.test.mjs: 2.4 to 3.4 s ahead).
    const clock = mslClock(photo.utcMs);
    assert.equal(clock.sol, sol);
    assert.equal(sol, photo.sol);
    close((clock.lmst - lmstHours) * 3600, 0, 4, `${photo.id}: seconds of mission clock`);
    // Local TRUE solar time where the rover was: away from the mission's mean time by the
    // equation of time (at most 51 min on Mars), on the same sol by day.
    const site = siteFromCrs(photo.x, photo.y);
    const sun = P.sunOf(photo, site.lonEastDeg);
    assert.deepEqual(P.sunOf(photo), sun);               // the photo's own longitude by default
    assert.equal(sun.sol, photo.sol);
    assert.ok(sun.hours >= 0 && sun.hours < 24);
    const minutes = (sun.hours - lmstHours) * 60;
    assert.ok(Math.abs(minutes) < 51, `${photo.id}: true minus mean solar time ${minutes.toFixed(1)} min`);
    // The page's Sun set to that sol and time (SunView.set -> sunState) is the photo's
    // own instant, with the Sun up: the scene is lit as the photo was.
    const state = sunState(sun, site);
    close(state.utcMs, photo.utcMs, 1, `${photo.id}: instant (ms)`);
    assert.ok(state.elevation > 0, `${photo.id}: Sun ${state.elevation.toFixed(1)} deg`);
    rows.push(`${photo.lmst.slice(10, 15)} LMST -> ${(minutes >= 0 ? '+' : '') + minutes.toFixed(1)} min true`);
  }
  t.diagnostic(rows.join('; '));
});

test('card facts: Earth date, sol, local time, camera, where it looks, credit', () => {
  assert.deepEqual(P.photoFacts(MODEL.photos[0]), [
    ['Date', '2025-02-11 11:54 UTC'],
    ['Sol', '4450'],
    ['Local time', '13:38 LMST'],
    ['Camera', 'Navcam right, black and white'],
    ['Looking', 'south-west (208°), 27° below the horizon'],
    ['Credit', 'NASA/JPL-Caltech'],
  ]);
  const left = Object.fromEntries(P.photoFacts(MODEL.byId.get(LEFT_ID)));
  assert.equal(left.Camera, 'Navcam left, black and white');
  assert.equal(left.Looking, 'south-west (235°), 10° above the horizon');          // pitch -10 degrees
  assert.equal(left['Local time'], '13:41 LMST');                                  // 13:41:14.956: not rounded up
  const level = Object.fromEntries(P.photoFacts({...MODEL.photos[0], heading: 2 * Math.PI - 0.001, pitch: 0.004}));
  assert.equal(level.Looking, 'north (0°), level with the horizon');
  assert.equal(Object.fromEntries(P.photoFacts({...MODEL.photos[0], credit: null})).Credit, 'not given');
});

test('?photo= parameter: real ids pass, anything else is null', () => {
  for (const p of MODEL.photos) assert.equal(P.parsePhotoParam(p.id), p.id);
  assert.equal(P.parsePhotoParam('a'.repeat(80)), 'a'.repeat(80));
  for (const bad of ['../x', '<b>', '', 'a'.repeat(81), ` ${LEFT_ID}`, 'NLB_1.JPG', 'a/b', 'x%2F', null, undefined, 42]) {
    assert.equal(P.parsePhotoParam(bad), null, JSON.stringify(bad));
  }
});
