// Guide logic shared by the two views of a walk: the arm-tablet guide (web/guide.html,
// 2D map) and the 3D rehearsal (web/3d/). No drawing here: maneuvers, voice, the
// "can I make it back?" meters, and the server calls for the way home, rejoining the
// route and the solar storm. Pure functions take a `route` object:
//
//   {coords: [[x, y], ...]   Mars CRS metres, one per vertex
//    t: [s], used: [Wh]      EVA clock and energy used at each vertex (absolute)
//    rv: [Wh] | null         energy needed to return from each vertex (E4's R(v))
//    rvTime: [s] | null      time to return from each vertex
//    usable: Wh              usable energy (budget minus margin)
//    turnIndex, goalName     single-goal round trip (E4)
//    stops: [{i, name}]      multi-station tour (E5): vertex index and station id
//    kind: "plan" | "home"}  "home" after Return home (drawn red, no station cards)
//
// prepareRoute(route) adds `d` (cumulative distance) and `events` (maneuvers).

export const OFF_ROUTE_M = 15;          // farther than this from the route: off route
export const REJOIN_AHEAD_M = 30;       // rejoin this far ahead of the nearest point
export const EMERGENCY_RETURN_S = 1800; // the red line: 30 min of emergency oxygen
export const STATION_RADIUS_M = 12;     // closer than this to a station: arrived

export const TASKS = {
  ridge: ["Photograph the ridge wall and its central fracture", "Sample the ridge cement (clays + Fe oxides)"],
  hollow: ["Image the hollow floor", "Sample bedrock under the sand (siderite)", "Watch your footing: loose sand"],
  contact: ["Photograph both sides of the contact", "Sample each unit near the contact"],
  curiosity: ["Find and photograph Curiosity's drill hole", "Compare the rock with the rover's data"],
};

// --- voice -----------------------------------------------------------------
export function createVoice({lang = "en-US", rate = 1.0, synth = globalThis.speechSynthesis} = {}) {
  let on = true;
  return {
    get on() { return on; },
    set(value) { on = Boolean(value); if (!on && synth) synth.cancel(); return on; },
    toggle() { return this.set(!on); },
    say(text) {
      if (!on || !synth || typeof SpeechSynthesisUtterance === "undefined") return false;
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text); u.lang = lang; u.rate = rate;
      synth.speak(u);
      return true;
    },
  };
}

// --- maneuvers from the route geometry -------------------------------------
export function cumulativeDistance(c) {
  const d = [0];
  for (let i = 1; i < c.length; i++) d.push(d[i - 1] + Math.hypot(c[i][0] - c[i - 1][0], c[i][1] - c[i - 1][1]));
  return d;
}

export function headingAt(c, d, i, span) {
  // Heading (rad, east = 0, counter-clockwise) over +-span metres, robust to 1 m staircases.
  let a = i, b = i;
  while (a > 0 && d[i] - d[a] < span) a--;
  while (b < c.length - 1 && d[b] - d[i] < span) b++;
  return Math.atan2(c[b][1] - c[a][1], c[b][0] - c[a][0]);
}

export function buildEvents(c, d, turnIndex, goalName, endText, stops) {
  // stops: [{i, name}] for a multi-station tour (E5); otherwise the single goal at turnIndex.
  const stopIdx = (stops || []).map(s => s.i).concat(turnIndex != null ? [turnIndex] : []);
  const ev = [];
  let last = -1e9;
  for (let i = 0; i < c.length; i++) {
    if (d[i] - last < 25 || d[i] < 10 || d[d.length - 1] - d[i] < 10) continue;
    // turnarounds at stations are announced as arrivals, not as sharp turns
    if (stopIdx.some(k => Math.abs(d[i] - d[k]) < 25)) continue;
    let ahead = i; while (ahead < c.length - 1 && d[ahead] - d[i] < 15) ahead++;
    let behind = i; while (behind > 0 && d[i] - d[behind] < 15) behind--;
    const hin = headingAt(c, d, behind, 8), hout = headingAt(c, d, ahead, 8);
    let delta = (hout - hin) * 180 / Math.PI;
    delta = ((delta + 540) % 360) - 180;                     // -180..180, + = left
    if (Math.abs(delta) < 40) continue;
    const side = delta > 0 ? "left" : "right";
    const kind = Math.abs(delta) > 135 ? "Sharp " + side : Math.abs(delta) > 70 ? "Turn " + side : "Bear " + side;
    const arrow = Math.abs(delta) > 135 ? (delta > 0 ? "↶" : "↷") : delta > 0 ? (Math.abs(delta) > 70 ? "←" : "↖") : (Math.abs(delta) > 70 ? "→" : "↗");
    ev.push({i, dist: d[i], text: kind, arrow}); last = d[i];
  }
  if (stops && stops.length) {
    for (const s of stops) ev.push({i: s.i, dist: d[s.i], text: `Arrive at station ${s.name}`, arrow: "⚑", goal: true});
  } else if (turnIndex != null && turnIndex > 0 && turnIndex < c.length - 1) {
    ev.push({i: turnIndex, dist: d[turnIndex], text: goalName, arrow: "⚑", goal: true});
  }
  ev.push({i: c.length - 1, dist: d[c.length - 1], text: endText, arrow: "⌂", end: true});
  return ev.sort((a, b) => a.dist - b.dist);
}

export function prepareRoute(r) {
  r.d = cumulativeDistance(r.coords);
  r.events = buildEvents(r.coords, r.d, r.turnIndex, r.goalName, "Arrive at the habitat", r.stops);
  return r;
}

// The route of the plan saved by the HUD (GET /plan/last), ready to walk.
export function routeFromPlan(saved) {
  const feats = saved.plan.features;
  const f = feats.find(x => x.properties.kind === "route");
  const goalSt = feats.find(x => x.properties.kind === "goal");
  const goalName = goalSt && goalSt.properties.station ? `Arrive at station ${goalSt.properties.station}` : "Arrive at the goal";
  const p = f.properties;
  const stops = (p.stop_index || []).map((i, k) => ({i, name: p.visit_order[k]}));
  return prepareRoute({coords: f.geometry.coordinates, t: p.t_s, used: p.used_wh, rv: p.rv_wh, rvTime: p.rv_time_s,
                       usable: p.usable_wh, turnIndex: p.turn_index, goalName, kind: "plan", stops});
}

// Maximum EVA duration of the saved plan (s), or null when the plan had none.
export function evaLimitS(saved) {
  const m = saved && saved.request && saved.request.max_duration_min;
  return Number.isFinite(m) && m > 0 ? m * 60 : null;
}

// Next maneuver from vertex i: the event, the metres to it and the banner text.
export function nextManeuver(r, i) {
  const next = r.events.find(e => e.dist > r.d[i] + 1) || r.events[r.events.length - 1];
  const togo = Math.max(0, next.dist - r.d[i]);
  return {event: next, togo, distText: togo < 5 ? "now" : `in ${Math.round(togo / 10) * 10} m`};
}

// What to say at vertex i ("In 80 meters, turn left", then "Turn left"), each once.
export function announcements(r, i, spoken) {
  const {event: next, togo} = nextManeuver(r, i);
  const out = [];
  for (const th of [80, 20]) {
    const key = `${r.kind}-${next.i}-${th}`;
    if (togo <= th && togo > (th === 80 ? 20 : 0) && !spoken.has(key)) {
      spoken.add(key);
      out.push(th === 80 ? `In ${Math.round(togo / 10) * 10} meters, ${next.text.toLowerCase()}` : next.text);
    }
  }
  return out;
}

// "Can I make it back?" at vertex i, and how much of the EVA's time is left.
//   energy: left after returning (Wh) out of usable; good while above 25 %.
//   back:   time to the habitat against the 30 min line; good up to 25 min.
//   eva:    elapsed EVA time against max_duration (null when there is no limit).
export function meters(r, i, limitS = null) {
  const used = r.used[i], need = r.rv ? r.rv[i] : 0, left = r.usable - used - need;
  const back = r.rvTime ? r.rvTime[i] : r.t[r.t.length - 1] - r.t[i];
  const out = {
    energy: {leftWh: left, usableWh: r.usable, frac: left / r.usable, good: left > 0.25 * r.usable,
             text: `${left.toFixed(0)} of ${r.usable.toFixed(0)} Wh`},
    back: {s: back, frac: 1 - back / EMERGENCY_RETURN_S, good: back <= 1500, text: `${(back / 60).toFixed(1)} min`},
    eva: null,
  };
  if (limitS) {
    const elapsed = r.t[i], leftS = limitS - elapsed, endS = elapsed + back;   // back home if you turn now
    out.eva = {elapsedS: elapsed, limitS, leftS, frac: leftS / limitS,
               good: endS <= limitS && leftS > 0.1 * limitS, overrun: r.t[r.t.length - 1] > limitS,
               text: `${Math.max(0, leftS / 60).toFixed(0)} of ${(limitS / 60).toFixed(0)} min left`};
  }
  return out;
}

// Stations the walker reaches at vertex i (planned ones only, each once).
export function arrivals(r, i, stationFeatures, visited) {
  if (r.kind !== "plan") return [];
  const here = r.coords[i], out = [];
  for (const f of stationFeatures) {
    const id = f.properties.id, [sx, sy] = f.geometry.coordinates;
    if (f.properties.visited === false) continue;              // not in the E5 tour
    if (!visited.has(id) && Math.hypot(sx - here[0], sy - here[1]) < STATION_RADIUS_M) {
      visited.add(id); out.push(f.properties);
    }
  }
  return out;
}

// Card of a station: title, why it matters (rubric) and the tasks of its type.
export function stationCard(p, rubric) {
  const type = (rubric || {})[p.type];
  return {title: `Station ${p.id}${type ? " · " + type.label : ""} · ${p.service_time_min ?? 10} min`,
          why: type ? type.why : "", tasks: TASKS[p.type] || ["Document the site"],
          speech: `Arrived at station ${p.id}. ${type ? type.label : ""}.`};
}

// Vertex index reached after `seconds` of EVA clock from vertex i.
export function advance(r, i, seconds) {
  const target = r.t[i] + seconds;
  let k = i; while (k < r.t.length - 1 && r.t[k] < target) k++;
  return k;
}

// --- server calls ----------------------------------------------------------
const post = async (url, body) => {
  const res = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const out = await res.json();
  if (!res.ok) throw new Error(typeof out.detail === "string" ? out.detail : `HTTP ${res.status}`);
  return out;
};

const planLimits = saved => ({habitat: saved.plan.properties.habitat,
                              max_cell_slope_deg: saved.plan.properties.max_cell_slope_deg,
                              human_cost: saved.plan.properties.human_cost !== false});

// Fastest way home from vertex i (POST /guide/return_home), as a route of kind "home".
// The EVA clock and the energy keep counting from where the walker was.
export async function returnHome(r, i, saved, here = r.coords[i]) {
  const out = await post("/guide/return_home", {position: here, ...planLimits(saved)});
  const f = out.features[0], p = f.properties, t0 = r.t[i], u0 = r.used[i];
  // On the way home, what returning still needs is what is left of this path.
  const route = prepareRoute({coords: f.geometry.coordinates, t: p.t_s.map(v => v + t0),
                              used: p.used_wh.map(v => v + u0), rv: p.used_wh.map(v => p.energy_wh - v),
                              rvTime: p.t_s.map(v => p.time_s - v),
                              usable: r.usable, turnIndex: null, goalName: "", kind: "home"});
  return {route, summary: p,
          text: `Way home: ${(p.time_s / 60).toFixed(1)} min, ${p.length_m.toFixed(0)} m, ${p.energy_wh.toFixed(0)} Wh.`,
          speech: `Returning home. ${Math.round(p.time_s / 60)} minutes.`};
}

export function nearestOnRoute(r, pt) {
  let best = 0, bestD = Infinity;
  for (let k = 0; k < r.coords.length; k++) {
    const dd = Math.hypot(r.coords[k][0] - pt[0], r.coords[k][1] - pt[1]);
    if (dd < bestD) { bestD = dd; best = k; }
  }
  return {k: best, dist: bestD};
}

// Demo: a point 25 m to the left of the walking direction at vertex i.
export function detourPoint(r, i) {
  const c = r.coords, a = Math.min(i, c.length - 2), b = Math.min(c.length - 1, a + 10);
  const hx = c[b][0] - c[a][0], hy = c[b][1] - c[a][1], n = Math.hypot(hx, hy) || 1;
  return [c[a][0] - 25 * hy / n, c[a][1] + 25 * hx / n];
}

// Off route at pt while at vertex i: null if within OFF_ROUTE_M, else the new route
// (least-energy path back to the route a little ahead, then the rest of the plan with
// its clock and energy shifted), from POST /guide/rejoin.
export async function rejoin(r, i, pt, saved) {
  const near = nearestOnRoute(r, pt);
  if (near.dist <= OFF_ROUTE_M) return null;
  let j = Math.max(near.k, i);
  while (j < r.coords.length - 1 && r.d[j] - r.d[Math.max(near.k, i)] < REJOIN_AHEAD_M) j++;
  const out = await post("/guide/rejoin", {position: pt, target: r.coords[j], ...planLimits(saved)});
  const p = out.features[0].properties, rc = out.features[0].geometry.coordinates;
  const t0 = r.t[i], u0 = r.used[i];
  const dt = t0 + p.time_s - r.t[j], du = u0 + p.energy_wh - r.used[j];
  const tail = k => k > j;
  const route = prepareRoute({...r,
    coords: rc.concat(r.coords.filter((_, k) => tail(k))),
    t: p.t_s.map(v => v + t0).concat(r.t.filter((_, k) => tail(k)).map(v => v + dt)),
    used: p.used_wh.map(v => v + u0).concat(r.used.filter((_, k) => tail(k)).map(v => v + du)),
    rv: r.rv ? p.rv_wh.concat(r.rv.filter((_, k) => tail(k))) : null,
    rvTime: r.rvTime ? p.rv_time_s.concat(r.rvTime.filter((_, k) => tail(k))) : null,
    turnIndex: r.turnIndex != null && r.turnIndex > j ? r.turnIndex - (j + 1) + rc.length : null,
    stops: (r.stops || []).filter(s => s.i > j).map(s => ({...s, i: s.i - (j + 1) + rc.length}))});
  return {route, offM: near.dist, text: `Back on track: ${p.time_s.toFixed(0)} s to rejoin the route.`};
}

// Solar storm (E12): the dose on the way home for the real event and a 50x storm.
export function stormMessage(homeRoute, radInfo) {
  const tH = (homeRoute.t[homeRoute.t.length - 1] - homeRoute.t[0]) / 3600;
  const sc = radInfo ? radInfo.scenarios : [];
  const real = sc.find(s => s.id === "real"), x50 = sc.find(s => s.id === "x50");
  return {minutes: tH * 60,
          realUgy: real ? tH * real.rate_ugy_h : null, x50Ugy: x50 ? tH * x50.rate_ugy_h : null,
          rule: "RAD rate above 1.5× its 3-day median, 2 readings in a row"};
}
