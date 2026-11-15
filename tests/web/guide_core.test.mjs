// Shared guide logic (web/guide_core.js). Run from the repo root:  node --test tests/web/
// Uses the real /plan answers kept by the 3D map's tests (tests/viz3d/fixtures/, read only).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import * as G from '../../web/guide_core.js';

const fixture = name => JSON.parse(readFileSync(new URL(`../viz3d/fixtures/${name}.json`, import.meta.url), 'utf8'));
const saved = (name, maxMin = 120) => ({request: {max_duration_min: maxMin}, plan: fixture(name)});

test('E4 round trip: one goal, the habitat at the end, maneuvers in order', () => {
  const r = G.routeFromPlan(saved('plan_e4'));
  assert.equal(r.kind, 'plan');
  assert.equal(r.d.length, r.coords.length);
  const goals = r.events.filter(e => e.goal), ends = r.events.filter(e => e.end);
  assert.equal(goals.length, 1);
  assert.equal(ends.length, 1);
  assert.equal(ends[0].i, r.coords.length - 1);
  for (let k = 1; k < r.events.length; k++) assert.ok(r.events[k].dist >= r.events[k - 1].dist);
  // no "sharp turn" announced at the goal's turnaround (it is an arrival)
  const g = goals[0];
  assert.ok(!r.events.some(e => !e.goal && !e.end && Math.abs(e.dist - g.dist) < 25));
});

test('E5 tour: one arrival per visited station, in the visiting order', () => {
  const r = G.routeFromPlan(saved('plan_tour_e5'));
  const p = fixture('plan_tour_e5').features.find(f => f.properties.kind === 'route').properties;
  const arrivals = r.events.filter(e => e.goal).map(e => e.text);
  assert.deepEqual(arrivals, p.visit_order.map(id => `Arrive at station ${id}`));
});

test('announcements: "in 80 m" then the maneuver, each once', () => {
  const r = G.routeFromPlan(saved('plan_e4'));
  const ev = r.events[0], spoken = new Set(), said = [];
  for (let i = 0; i <= ev.i; i++) said.push(...G.announcements(r, i, spoken));
  for (let i = 0; i <= ev.i; i++) assert.deepEqual(G.announcements(r, i, spoken), []);   // never twice
  assert.ok(said.includes(ev.text));
  assert.ok(said.some(t => /^In \d+ meters, /.test(t)) || ev.dist < 80);
});

test('meters: energy left after returning, return time, EVA time left', () => {
  const s = saved('plan_e4', 120), r = G.routeFromPlan(s), limit = G.evaLimitS(s);
  assert.equal(limit, 7200);
  const start = G.meters(r, 0, limit), end = G.meters(r, r.coords.length - 1, limit);
  assert.ok(Math.abs(start.energy.leftWh - (r.usable - r.used[0] - r.rv[0])) < 1e-9);
  assert.ok(start.back.s <= 1 && end.back.s <= 1);                 // at the habitat
  assert.ok(start.eva.leftS === 7200 && start.eva.good);
  assert.ok(end.eva.leftS === 7200 - r.t[r.t.length - 1]);
  assert.equal(end.eva.overrun, r.t[r.t.length - 1] > 7200);
  assert.equal(G.meters(r, 0, null).eva, null);                    // no limit, no meter
  assert.equal(G.evaLimitS({request: {max_duration_min: null}}), null);
});

test('arrivals: each planned station once; skipped stations never', () => {
  const s = saved('plan_tour_e5'), r = G.routeFromPlan(s);
  const st = s.plan.features.filter(f => f.properties.kind === 'station');
  const visited = new Set(), got = [];
  for (let i = 0; i < r.coords.length; i++) got.push(...G.arrivals(r, i, st, visited).map(p => p.id));
  assert.equal(new Set(got).size, got.length);
  for (const id of got) assert.notEqual(st.find(f => f.properties.id === id).properties.visited, false);
});

test('station card, detour point and the walking clock', () => {
  const card = G.stationCard({id: 'R0', type: 'ridge', service_time_min: 10},
                             {ridge: {label: 'Ridge', why: 'clays'}});
  assert.equal(card.title, 'Station R0 · Ridge · 10 min');
  assert.deepEqual(card.tasks, G.TASKS.ridge);
  const r = G.routeFromPlan(saved('plan_e4'));
  const off = G.detourPoint(r, 50);
  assert.ok(G.nearestOnRoute(r, off).dist > G.OFF_ROUTE_M);        // the demo detour is off route
  const k = G.advance(r, 0, 60);
  assert.ok(r.t[k] >= 60 || k === r.t.length - 1);
  assert.ok(k === 0 || r.t[k - 1] < 60);
});

test('voice: on by default, toggles, silent when off', () => {
  const calls = [];
  const synth = {cancel: () => calls.push('cancel'), speak: u => calls.push(u.text)};
  globalThis.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
  const v = G.createVoice({synth});
  assert.equal(v.on, true);
  assert.equal(v.say('hello'), true);
  assert.equal(v.toggle(), false);
  assert.equal(v.say('quiet'), false);
  assert.ok(calls.includes('hello') && !calls.includes('quiet'));
  delete globalThis.SpeechSynthesisUtterance;
});

test('solar storm: dose on the way home from the RAD scenarios', () => {
  const home = {t: [600, 900, 1500]};                                // 15 min home, clock absolute
  const s = G.stormMessage(home, {scenarios: [{id: 'real', rate_ugy_h: 20}, {id: 'x50', rate_ugy_h: 500}]});
  assert.ok(Math.abs(s.minutes - 15) < 1e-9);
  assert.ok(Math.abs(s.realUgy - 5) < 1e-9 && Math.abs(s.x50Ugy - 125) < 1e-9);
  assert.equal(G.stormMessage(home, null).realUgy, null);
});

test('return home: the energy meter still counts what returning needs', async () => {
  const r = G.routeFromPlan(saved('plan_e4')), i = 400;
  const answer = {features: [{geometry: {coordinates: [r.coords[i], [0, 0], [1, 1]]},
                              properties: {t_s: [0, 300, 600], used_wh: [0, 20, 40], time_s: 600,
                                           energy_wh: 40, length_m: 450}}]};
  globalThis.fetch = async () => ({ok: true, json: async () => answer});
  const home = await G.returnHome(r, i, {plan: {properties: {habitat: [0, 0]}}});
  delete globalThis.fetch;
  assert.equal(home.route.kind, 'home');
  assert.deepEqual(home.route.rv, [40, 20, 0]);
  assert.equal(home.route.t[0], r.t[i]);                      // the EVA clock keeps running
  const m = G.meters(home.route, 0, 7200);
  assert.ok(Math.abs(m.energy.leftWh - (r.usable - r.used[i] - 40)) < 1e-9);
  assert.equal(m.back.s, 600);
});

test('rejoin search looks ahead only: a round trip never snaps onto the way back', () => {
  // Out along y = 0 to x = 100, back along y = 2 (parallel legs 2 m apart).
  const coords = [];
  for (let x = 0; x <= 100; x++) coords.push([x, 0]);
  for (let x = 100; x >= 0; x--) coords.push([x, 2]);
  const r = G.prepareRoute({coords, t: coords.map((_, k) => k), used: coords.map((_, k) => k / 10),
                            rv: null, rvTime: null, usable: 100, turnIndex: 100, goalName: 'Goal', kind: 'plan'});
  const back = 101 + 70;                                 // vertex (30, 2) on the way back
  const off = [30, 2 + 25];                              // 25 m beside both legs, nearer the way back
  assert.ok(G.nearestOnRoute(r, off, 20).k <= 100);     // walking out: rejoin the way out
  assert.ok(G.nearestOnRoute(r, off, 150).k > 100);     // walking back: rejoin the way back
  assert.ok(G.nearestOnRoute(r, off, 0).k <= 100 && back > 100);
  assert.ok(Math.abs(G.nearestOnRoute(r, off, 20).dist - 25) < 1e-9);
});

test('rejoin: within 15 m of the route nothing is asked', async () => {
  const r = G.routeFromPlan(saved('plan_e4'));
  let asked = false;
  globalThis.fetch = async () => { asked = true; return {ok: true, json: async () => ({})}; };
  const out = await G.rejoin(r, 100, [r.coords[100][0] + 5, r.coords[100][1]], saved('plan_e4'));
  delete globalThis.fetch;
  assert.equal(out, null);
  assert.equal(asked, false);
});

test('return home while standing at a stop keeps the real clock and energy', async () => {
  const r = G.routeFromPlan(saved('plan_e4')), i = 400;
  const answer = {features: [{geometry: {coordinates: [r.coords[i], [0, 0]]},
                              properties: {t_s: [0, 600], used_wh: [0, 40], time_s: 600, energy_wh: 40, length_m: 450}}]};
  globalThis.fetch = async () => ({ok: true, json: async () => answer});
  const now = {t: r.t[i] - 120, used: r.used[i] - 3};    // mid-wait: before the vertex's departure time
  const home = await G.returnHome(r, i, {plan: {properties: {habitat: [0, 0]}}}, r.coords[i], now);
  delete globalThis.fetch;
  assert.equal(home.route.t[0], now.t);
  assert.equal(home.route.used[0], now.used);
});

test('storm alert text is shared by both views', () => {
  const html = G.stormHtml({minutes: 11, realUgy: 2.2, x50Ugy: 54, rule: 'r'});
  assert.ok(html.includes('11.0 min') && html.includes('2.2 µGy') && html.includes('54 µGy'));
  assert.ok(G.stormFailedHtml('no path').includes('no path'));
});

test('radio (E11): meter states, debounced loss/back events and spoken warnings', () => {
  const coords = Array.from({length: 301}, (_, k) => [k, 0]);
  const r = G.prepareRoute({coords, t: coords.map((_, k) => 2 * k), used: coords.map(() => 0), rv: null,
                            rvTime: null, usable: 100, turnIndex: null, goalName: '', kind: 'plan'});
  // radio until 100 m, silent to 200 m with a 3 m flicker at 150, back after 200
  r.radio = coords.map((_, k) => k < 100 || (k >= 150 && k < 153) || k >= 200);
  r.pair = coords.map((_, k) => (r.radio[k] ? 'direct' : k < 180 ? 'relay' : 'none'));
  r.radioEvents = G.radioEvents(r);
  assert.deepEqual(r.radioEvents.map(e => [e.kind, e.i]), [['loss', 100], ['back', 200]]);   // flicker gone
  assert.equal(r.radioEvents[0].silentS, 200);                 // 100 m at 2 s/m
  assert.equal(r.radioEvents[0].relay, false);                 // the partner loses it too after 180 m
  assert.equal(G.radioState(r, 50).state, 'direct');
  assert.equal(G.radioState(r, 120).state, 'relay');
  assert.equal(G.radioState(r, 190).state, 'none');
  const spoken = new Set(), said = [];
  for (let i = 0; i <= 210; i++) said.push(...G.radioAnnouncements(r, i, spoken));
  assert.equal(said.length, 2);
  assert.match(said[0], /^In 80 meters you lose direct radio for about 3 minutes/);
  assert.equal(said[1], 'Direct radio back.');
  assert.equal(G.radioState({radio: undefined}, 0), null);     // no radio data: no meter
});
