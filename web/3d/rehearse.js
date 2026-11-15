// "Rehearse the route" mode of the 3D map (P1, issue #42, block 3).
//
// Walks the planned route at eye height before the EVA. The numbers (where the walker
// is, time, energy) come from rehearse_model.js; this file owns what the mode does to
// the page while it is on, and puts everything back when it is left:
//   - camera: first person, the eye EYE_HEIGHT above the shown ground, looking along the
//     path; dragging looks around (offsets from the direction of travel), double-click
//     or "Recentre" looks forward again. "Chase view" sees the walker from behind and
//     above. The free-flight controls are off and the near plane comes in to NEAR.
//   - relief: forced to true scale. At eye height an exaggerated knoll would be a wall
//     that is not there, and slopes are what the rehearsal is for.
//   - player bar: play / pause, speed, scrubber, and the 2D planner's energy bar.
//   - stops: arriving at one while playing pauses and shows its card; play again lets
//     the service time run with the walker standing.
//   - on pause: the walkback lines from that point (30 min return in red, energy-safe
//     boundary in cyan), as the 2D planner draws them; cleared on play and on exit.
//   - EVA clock: onTime(seconds since the start of the EVA) at every move, and
//     onTime(null) on exit; main.js moves the Sun with it (sun.js).
//   - guide: the same logic as the arm-tablet guide (web/guide_core.js, shared): next
//     maneuver, voice (on/off), energy left after returning, time back against the
//     30 min line, EVA time left against the plan's maximum duration, station tasks,
//     Return home, a demo detour that rejoins the route, and the solar storm alert. A
//     way home or a rejoin replaces the walked route (drawn on the ground) until exit.
// Nothing is rendered here: update(dt) says whether the view changed, and main.js draws.
import * as THREE from 'three';
import { requestWalkback, walkbackRequest } from './api.js';
import * as M from './camera_math.js';
import { hideCard, showCard, stationCard } from './card.js';
import { TYPE_COLORS, mainRoute } from './plan_model.js';
import { EYE_HEIGHT, buildRehearsal, clock, energyReadout, eyeAltitude, progressText } from './rehearse_model.js';
import * as G from '../guide_core.js';

const DEG = Math.PI / 180;
export const FOV = 60;             // degrees, vertical: wider than free flight, closer to what a walker sees
export const NEAR = 0.3;           // m: the ground is 1.7 m from the eye (free flight keeps 2 m)
const LOOK_DOWN = 3 * DEG;         // first person looks this far below the slope of the path
const PITCH_LIMIT = 70 * DEG;      // first person: how far up or down one can look
const CHASE_BACK = 15, CHASE_UP = 8;       // m behind the walker and above the ground it stands on
const CHASE_TARGET = 1.2;          // m above the ground: the camera looks at the walker's chest
const CHASE_TILT = Math.atan2(CHASE_UP - CHASE_TARGET, CHASE_BACK);
const CHASE_RANGE = Math.hypot(CHASE_UP - CHASE_TARGET, CHASE_BACK);
const CHASE_PITCH = [5 * DEG, 80 * DEG];   // the chase camera stays above the walker's horizon
const CHASE_FLOOR = 2;             // m: the chase camera stays this far above the ground
const VIEW_EASE = 6;               // 1/s: how fast the view follows a change of heading
const MAX_FRAME = 0.1;             // s: a frame never counts for more (tab in the background)
const WALKER_COLOR = 0xff40c8;     // the astronaut dot of the 2D planner
const RED_LINE = [255, 59, 48], SAFE_LINE = [54, 209, 255];       // the 2D planner's walkback colours
const HOME_LINE = [255, 69, 58], REJOIN_LINE = [255, 140, 58];     // guide: way home, rejoining path
const METER = {good: '#3ddc84', warn: '#ffcc00', bad: '#ff453a'};  // guide.html's meter colours
const RELIEF_REASON = 'Relief at true scale while rehearsing (eye height is real)';

const el = id => document.getElementById(id);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export class Rehearsal {
  // relief: {lock(reason), unlock(k)} from main.js; lines: a GroundLines layer for the
  // walkback boundaries; rubric(): the station rubric for the cards; onTime: see above.
  constructor({terrain, scene, camera, canvas, controls, relief, lines, rubric = () => ({}), onTime = () => {}}) {
    Object.assign(this, {terrain, scene, camera, canvas, controls, relief, lines, rubric, onTime});
    this.active = false;
    this.playing = false;
    this.plan = null;              // parsePlan() result
    this.model = null;             // buildRehearsal() result, or null when there is no route
    this.state = null;             // model.stateAt(time) of what is shown
    this.time = 0;
    this.speed = 60;
    this.chase = false;
    this.look = {yaw: 0, pitch: 0};        // what dragging adds to the direction of travel
    this.view = {heading: 0, pitch: 0};    // direction of travel as shown (eased while playing)
    this.viewYaw = 0;                      // heading of the camera itself, for the compass
    this.walkback = null;                  // properties of the last walkback answer shown
    this.walkbackOnPause = true;           // checks.js turns it off: it asks the server
    this._listeners = [];
    this._dirty = false;
    this._snap = true;
    this._drag = null;
    this._token = 0;
    this._stopCard = false;
    this.voice = G.createVoice();          // guide: spoken maneuvers and arrivals
    this.guide = null;                     // guide_core route of what is walked (null: no profile)
    this._extra = [];                      // lines of a way home or a rejoin, kept on play
    this._spoken = new Set();
    this._radInfo = undefined;

    // The player's own controls. They are hidden outside the rehearsal.
    el('rh-play').addEventListener('click', () => this.togglePlay());
    el('rh-speed').addEventListener('change', e => { this.speed = Number(e.target.value) || 60; });
    el('rh-scrub').addEventListener('input', e => { this.pause(false); this.seek(Number(e.target.value)); });
    el('rh-scrub').addEventListener('change', () => this._settle());
    el('rh-chase').addEventListener('click', () => this.setChase(!this.chase));
    el('rh-recentre').addEventListener('click', () => this.recentre());
    el('rh-exit').addEventListener('click', () => this.exit());
    el('rehearse').addEventListener('click', () => (this.active ? this.exit() : this.enter()));
    el('rh-voice').addEventListener('click', () => {
      const on = this.voice.toggle();
      el('rh-voice').textContent = on ? '🔊 Voice on' : '🔇 Voice off';
      el('rh-voice').setAttribute('aria-pressed', String(on));
    });
    el('rh-home').addEventListener('click', () => this.returnHome());
    el('rh-detour').addEventListener('click', () => this.detour());
    el('rh-storm').addEventListener('click', () => this.solarStorm());
  }

  // ---- public ------------------------------------------------------------------

  // plan: the result of parsePlan(), or null. Leaves the rehearsal if it was on.
  setPlan(plan) {
    this.exit();
    const route = plan ? mainRoute(plan) : null;
    this.plan = plan;
    this.model = route ? buildRehearsal(route, plan.points) : null;
    el('rehearse').disabled = !this.model;
    const m = this.model;
    el('rehearse-note').textContent =
      !plan ? 'No route to rehearse: there is no plan.'
      : !m ? 'No route to rehearse: the plan has no route.'
      : m.assumedSpeed !== null
        ? `Walk it at eye height. The plan has no times: ${clock(m.duration)} at an assumed ${m.assumedSpeed.toFixed(0)} m/s.`
        : `Walk it at eye height: ${clock(m.duration)} of EVA` +
          (m.stops.length ? `, ${m.stops.length} stop${m.stops.length > 1 ? 's' : ''}.` : '.');
  }

  enter() {
    if (this.active || !this.model) return false;
    const {controls, camera, model} = this;
    // Everything that exit() must put back.
    this._saved = {pose: controls.pose(), near: camera.near, relief: this.terrain.k};
    controls.cancel();
    controls.enabled = false;
    this.relief.lock(RELIEF_REASON);
    camera.near = NEAR;
    camera.fov = FOV;
    camera.updateProjectionMatrix();

    // The walker, seen only in the chase view: a capsule as tall as the eye.
    this.walker = new THREE.Mesh(new THREE.CapsuleGeometry(0.22, EYE_HEIGHT - 0.44, 4, 12),
                                 new THREE.MeshBasicMaterial({color: WALKER_COLOR}));     // unlit: a marker, readable in shade
    this.walker.name = 'walker';
    this.walker.visible = false;
    this.scene.add(this.walker);

    this._listen(this.canvas, 'pointerdown', e => this._down(e));
    this._listen(this.canvas, 'pointermove', e => this._move(e));
    for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) {
      this._listen(this.canvas, type, e => { if (this._drag && this._drag.id === e.pointerId) this._drag = null; });
    }
    this._listen(this.canvas, 'dblclick', () => this.recentre());
    this._listen(window, 'keydown', e => this._key(e));

    Object.assign(this, {active: true, playing: false, time: model.start, chase: false, walkback: null});
    this._evaStart = model.start;
    this.guide = this._guideRoute(mainRoute(this.plan), 'plan');
    this._spoken.clear();
    this._extra = [];
    el('rh-alert').hidden = true;
    for (const id of ['rh-home', 'rh-detour', 'rh-storm']) el(id).disabled = !this.guide;
    this.look = {yaw: 0, pitch: 0};
    this.speed = Number(el('rh-speed').value) || 60;
    hideCard();
    document.body.classList.add('rehearsing');
    el('player').hidden = false;
    el('rehearse').textContent = 'Exit rehearsal';
    el('rh-play').textContent = '▶ Play';
    el('rh-chase').setAttribute('aria-pressed', 'false');
    el('rh-scrub').min = model.start;
    el('rh-scrub').max = model.end;
    this._note();
    this._snap = true;
    this._place(0);
    this._dirty = true;
    return true;
  }

  // Back to free flight exactly as it was: camera view, field of view and relief.
  exit() {
    if (!this.active) return false;
    const {controls, camera} = this, saved = this._saved;
    this.playing = false;
    this._extra = [];
    this._clearWalkback();
    if (this._replaced) {                      // a way home or a rejoin: back to the plan
      this.model = buildRehearsal(mainRoute(this.plan), this.plan.points);
      this._replaced = false;
    }
    if (typeof speechSynthesis !== 'undefined') speechSynthesis.cancel();
    hideCard();
    for (const [target, type, handler] of this._listeners) target.removeEventListener(type, handler);
    this._listeners = [];
    this._drag = null;
    this.scene.remove(this.walker);
    this.walker.geometry.dispose();
    this.walker.material.dispose();
    this.walker = null;
    this.active = false;
    this.state = null;
    document.body.classList.remove('rehearsing');
    el('player').hidden = true;
    el('rehearse').textContent = 'Rehearse the route';
    camera.near = saved.near;
    this.relief.unlock(saved.relief);          // the ground first: the saved camera height belongs to it
    controls.enabled = true;
    controls.restore(saved.pose);              // also puts the field of view back
    this.onTime(null);
    return true;
  }

  play() {
    if (!this.active || this.playing) return;
    // At the end: start again. The scrubber dragged to its end stops a hair before it
    // (a range input keeps 15 digits of its value), and that is the end too.
    if (this.model.end - this.time < 1e-3) this.seek(this.model.start);
    this._clearWalkback();
    if (this._stopCard) hideCard();
    this.playing = true;
    el('rh-play').textContent = '❚❚ Pause';
  }

  // settle: also ask for the walkback lines from here, as the 2D planner does on pause.
  pause(settle = true) {
    if (!this.active) return;
    const was = this.playing;
    this.playing = false;
    el('rh-play').textContent = '▶ Play';
    if (settle && was) this._settle();
  }

  togglePlay() { if (this.playing) this.pause(); else this.play(); }

  // Jump to a playback time (seconds on the plan's clock).
  seek(time) {
    if (!this.active) return;
    this.time = clamp(time, this.model.start, this.model.end);
    this._clearWalkback();
    this._snap = true;
    this._place(0);
    // Landing inside a wait shows where the walker is standing.
    if (this.state.standing && this.state.stop) this._showStop(this.state.stop);
    else if (this._stopCard) hideCard();
    this._dirty = true;
  }

  setChase(on) {
    if (!this.active) return;
    this.chase = Boolean(on);
    this.look = {yaw: 0, pitch: 0};
    el('rh-chase').setAttribute('aria-pressed', String(this.chase));
    this._dirty = true;
  }

  // Look forward again.
  recentre() {
    this.look = {yaw: 0, pitch: 0};
    this._dirty = true;
  }

  // Call once per frame with the seconds elapsed. Returns true when the view changed
  // (always while playing or dragging; otherwise only after an input).
  update(dt) {
    if (!this.active) return false;
    const step = clamp(dt, 0, MAX_FRAME);
    let changed = this._dirty || this._easing;
    if (this.playing) { this._advance(step); changed = true; }
    if (changed) this._place(step);
    this._dirty = false;
    return changed;
  }

  // Where the walker is, for the readout of main.js.
  positionText() {
    const s = this.state, {terrain} = this;
    if (!s) return '';
    const [X, Z] = terrain.toLocal(s.x, s.y);
    return `Walker at x ${s.x.toFixed(0)} m · y ${s.y.toFixed(0)} m · elevation ` +
           `${terrain.elevation(terrain.heightAt(X, Z, 1)).toFixed(0)} m`;
  }

  // ---- playback ----------------------------------------------------------------

  _advance(step) {
    const {model} = this, from = this.time, to = Math.min(model.end, from + step * this.speed);
    const stop = model.stops.find(s => s.arrive > from && s.arrive <= to);
    if (stop) {                                // arrive, stop the clock and say where we are
      this.time = stop.arrive;
      this.playing = false;
      el('rh-play').textContent = '▶ Play';
      this._place(step);
      this._showStop(stop);
      this._settle();
      return;
    }
    this.time = to;
    if (to >= model.end) {
      this._place(step); this.pause();
      this.voice.say('You have arrived at the habitat.');
    }
  }

  _showStop(stop) {
    const {model} = this, s = stop.station;
    const base = s ? stationCard(s, this.rubric()) : {title: 'Stop', subtitle: '', rows: []};
    const rows = [...base.rows, ['Arrival', `${clock(stop.arrive - this._evaStart)} into the EVA`]];
    if (stop.waitS > 0) rows.push(['Standing here', `${clock(stop.waitS)} min`]);
    // Guide: why the station matters and its tasks, as on the arm tablet.
    const g = s ? G.stationCard({id: s.id, type: s.type, service_time_min: s.serviceMin}, this.rubric()) : null;
    if (g && g.why) rows.push(['Why', g.why]);
    if (g) g.tasks.forEach((t, k) => rows.push([k ? '' : 'Tasks', `• ${t}`]));
    showCard({...base, rows, color: s ? TYPE_COLORS[s.type] || null : null,
              note: stop.waitS > 0
                ? 'Press play: the time here runs at the playback speed, with the walker standing.'
                : 'Press play to walk on.',
              actions: [{label: 'Done, continue', onClick: () => { hideCard(); this.play(); }}],
              onClose: () => { this._stopCard = false; }});
    if (g && this.playing === false && !this._spoken.has(`stop-${stop.index}`)) {
      this._spoken.add(`stop-${stop.index}`);
      this.voice.say(g.speech);
    }
    this._stopCard = true;
  }

  // ---- camera ------------------------------------------------------------------

  // Shown ground height under the camera path at a distance along the route.
  _ground(d) {
    const [x, y] = this.model.cameraAt(d), [X, Z] = this.terrain.toLocal(x, y);
    return this.terrain.surfaceAt(X, Z);
  }

  // Put the camera (and the player's texts) where the playback time says. step: seconds
  // since the last frame, for the easing of the view.
  _place(step) {
    const {terrain, model, camera} = this, s = this.state = model.stateAt(this.time);
    const [X, Z] = terrain.toLocal(s.cx, s.cy), ground = terrain.surfaceAt(X, Z);
    const [AX, AZ] = terrain.toLocal(s.ahead[0], s.ahead[1]);
    // Look along the slope of the path, a little down: the ground ahead stays in view
    // uphill and downhill.
    const slope = Math.atan2(terrain.surfaceAt(AX, AZ) - ground, Math.max(3, Math.hypot(AX - X, AZ - Z)));
    const want = {heading: s.heading, pitch: LOOK_DOWN - slope};
    // While playing, a sudden change of direction (leaving a stop, fast playback) is
    // followed over a few frames instead of in one.
    const k = this._snap || !this.playing && !this._easing ? 1 : 1 - Math.exp(-VIEW_EASE * step);
    this.view.heading += M.angleDelta(want.heading, this.view.heading) * k;
    this.view.pitch += (want.pitch - this.view.pitch) * k;
    const off = Math.abs(M.angleDelta(want.heading, this.view.heading)) + Math.abs(want.pitch - this.view.pitch);
    this._easing = off > 5e-4;                 // under 0.03 degrees: there
    if (!this._easing) Object.assign(this.view, want);
    this._snap = false;

    let position, yaw = this.view.heading + this.look.yaw, pitch;
    if (this.chase) {
      const target = [X, ground + CHASE_TARGET, Z];
      const tilt = clamp(CHASE_TILT + this.look.pitch, ...CHASE_PITCH);
      position = M.along(target, M.basis(yaw, tilt).forward, -CHASE_RANGE);
      // A slope behind the walker: the camera rides over it and keeps looking at the walker.
      position[1] = Math.max(position[1], terrain.surfaceAt(position[0], position[2]) + CHASE_FLOOR);
      pitch = Math.atan2(position[1] - target[1], Math.hypot(position[0] - X, position[2] - Z));
    } else {
      position = [X, eyeAltitude(d => this._ground(d), s.distance, model.length), Z];
      pitch = clamp(this.view.pitch + this.look.pitch, -PITCH_LIMIT, PITCH_LIMIT);
    }
    const {right, up, forward} = M.basis(yaw, pitch);
    camera.position.set(position[0], position[1], position[2]);
    camera.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(
      new THREE.Vector3(...right), new THREE.Vector3(...up), new THREE.Vector3(...forward).negate()));
    camera.updateMatrixWorld();
    this.viewYaw = yaw;
    this.pose = {position, yaw, pitch, ground};

    this.walker.visible = this.chase;
    this.walker.position.set(X, ground + EYE_HEIGHT / 2, Z);
    this._show();
    this._showGuide();
    this.onTime(s.time - this._evaStart);
  }

  _show() {
    const {model, state} = this;
    el('rh-scrub').value = state.time;
    el('rh-progress').textContent = progressText(model, state);
    const bar = energyReadout(state.profile, model.usableWh);
    el('rh-energy').hidden = !bar;
    if (!bar) return;
    el('rh-bar-used').style.width = `${bar.usedPct}%`;
    el('rh-bar-rv').style.width = `${bar.rvPct}%`;
    el('rh-bar-free').style.width = `${bar.freePct}%`;
    el('rh-energy-text').replaceChildren(...bar.lines.map(text => Object.assign(document.createElement('div'), {textContent: text})));
  }

  // ---- input (only while rehearsing) -------------------------------------------

  _listen(target, type, handler) {
    target.addEventListener(type, handler);
    this._listeners.push([target, type, handler]);
  }

  _down(e) {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    try { this.canvas.setPointerCapture(e.pointerId); } catch { /* pointer already gone */ }
    this._drag = {id: e.pointerId, x: e.clientX, y: e.clientY};
  }

  // Dragging moves the scene with the cursor, as in a street-level viewer: drag right to
  // look left. In the chase view the same drag turns the camera around the walker.
  _move(e) {
    const d = this._drag;
    if (!d || d.id !== e.pointerId) return;
    const scale = this.camera.fov * DEG / this.canvas.clientHeight;
    this.look.yaw = M.angleDelta(this.look.yaw - (e.clientX - d.x) * scale, 0);
    const tilt = (e.clientY - d.y) * scale * (this.chase ? 1 : -1);
    const range = this.chase ? CHASE_PITCH.map(p => p - CHASE_TILT)
                             : [-PITCH_LIMIT - this.view.pitch, PITCH_LIMIT - this.view.pitch];
    this.look.pitch = clamp(this.look.pitch + tilt, ...range);
    d.x = e.clientX; d.y = e.clientY;
    this._dirty = true;
  }

  _key(e) {
    if (e.code !== 'Space' || e.repeat) return;
    // On a list, a link or a slider the space bar already does something.
    if (e.target.closest && e.target.closest('select, a, summary, input')) return;
    // A button keeps the focus after a click, and a space would press it again (on
    // "Exit rehearsal" that leaves the mode). While rehearsing, space is always
    // play/pause: drop the focus so the key-up does not click the button.
    const button = e.target.closest && e.target.closest('button');
    if (button) button.blur();
    e.preventDefault();
    this.togglePlay();
  }

  // ---- guide (web/guide_core.js, shared with the arm-tablet guide) ---------------

  // guide_core route of a parsed route; null without a time and energy profile.
  _guideRoute(route, kind) {
    const pr = route && route.profile;
    if (!pr || !pr.t_s || !pr.used_wh || !(route.totals.usable_wh > 0)) return null;
    const goal = this.plan.points.find(p => p.kind === 'goal');
    return G.prepareRoute({coords: route.coords, t: pr.t_s, used: pr.used_wh, rv: pr.rv_wh || null,
                           rvTime: pr.rv_time_s || null, usable: route.totals.usable_wh,
                           turnIndex: route.turnIndex, kind,
                           goalName: goal && goal.properties.station ? `Arrive at station ${goal.properties.station}` : 'Arrive at the goal',
                           stops: route.stops.map(st => ({i: st.index, name: st.id}))});
  }

  _vertex() { return Math.min(this.guide.coords.length - 1, Math.floor(this.state.at + 1e-6)); }

  _limitS() { return G.evaLimitS({request: {max_duration_min: this.plan && this.plan.properties.max_duration_min}}); }

  // Clock and energy of the walker now (between vertices, or standing at a stop).
  _now() {
    const s = this.state, pr = s && s.profile;
    return pr && Number.isFinite(pr.used_wh) ? {t: s.time, used: pr.used_wh} : null;
  }

  _showGuide() {
    const g = this.guide;
    el('rh-man').hidden = !g;
    el('rh-meters').hidden = !g;
    if (!g) return;
    const i = this._vertex(), {event, distText} = G.nextManeuver(g, i);
    el('rh-man-arrow').textContent = event.arrow;
    el('rh-man-text').textContent = event.text;
    el('rh-man-dist').textContent = distText;
    if (this.playing) for (const text of G.announcements(g, i, this._spoken)) this.voice.say(text);
    const m = G.meters(g, i, this._limitS());
    const fill = (id, frac, good) => {
      const f = el(id);
      f.style.width = `${Math.max(0, Math.min(1, frac)) * 100}%`;
      f.style.background = good ? METER.good : frac > 0 ? METER.warn : METER.bad;
    };
    fill('rh-m-energy', m.energy.frac, m.energy.good); el('rh-v-energy').textContent = m.energy.text;
    fill('rh-m-back', m.back.frac, m.back.good); el('rh-v-back').textContent = m.back.text;
    for (const id of ['rh-eva-label', 'rh-eva-track', 'rh-v-eva']) el(id).hidden = !m.eva;
    if (m.eva) { fill('rh-m-eva', m.eva.frac, m.eva.good); el('rh-v-eva').textContent = m.eva.text; }
  }

  // Walk a new guide route from here on (a way home or a rejoin), drawn on the ground.
  _walkRoute(groute, color, points) {
    const used = groute.used, last = used.length - 1;
    const route = {kind: 'route', coords: groute.coords, turnIndex: groute.turnIndex,
                   stops: (groute.stops || []).map(st => ({index: st.i, id: st.name})),
                   totals: {usable_wh: groute.usable},
                   profile: {t_s: groute.t, used_wh: used, rv_time_s: groute.rvTime,
                             rv_wh: groute.rv || used.map(v => used[last] - v)}};   // guide_core sets rv
    this.model = buildRehearsal(route, points);
    this._replaced = true;
    this.guide = groute;
    this._spoken.clear();
    this._extra = [{lines: [groute.coords], color, width: 4}];
    el('rh-scrub').min = this.model.start;
    el('rh-scrub').max = this.model.end;
    this.seek(this.model.start);
  }

  _planRef() { return {plan: {properties: this.plan.properties}}; }   // what guide_core asks of a saved plan

  async returnHome() {
    if (!this.active || !this.guide) return null;
    this.pause(false);
    this._note('Computing the fastest way home…');
    const token = ++this._token;               // a later click, a seek or exit drops this answer
    try {
      const i = this._vertex();
      const home = await G.returnHome(this.guide, i, this._planRef(), [this.state.x, this.state.y], this._now());
      if (token !== this._token || !this.active) return null;
      this._walkRoute(home.route, HOME_LINE, []);
      this._note(home.text);
      this.voice.say(home.speech);
      return home;
    } catch (err) { this._note(`Return home: ${err.message}`); return null; }
  }

  async detour() {
    if (!this.active || !this.guide) return;
    this.pause(false);
    const i = this._vertex(), pt = G.detourPoint(this.guide, i);
    this._note('Off route (25 m) — recalculating…');
    this.voice.say('You are off route. Recalculating.');
    const token = ++this._token;
    try {
      const out = await G.rejoin(this.guide, i, pt, this._planRef(), this._now());
      if (token !== this._token || !this.active) return;
      if (!out) { this._note('Still within 15 m of the route: no rejoin needed.'); return; }
      this._walkRoute(out.route, REJOIN_LINE, this.guide.kind === 'plan' ? this.plan.points : []);
      this._note(out.text);
      this.voice.say('New route found.');
    } catch (err) { this._note(`Rejoin: ${err.message}`); }
  }

  async solarStorm() {
    if (!this.active || !this.guide) return;
    const alert = el('rh-alert');
    alert.hidden = false;
    alert.innerHTML = G.STORM_PENDING;
    this.voice.say('Solar storm alert. Return to the habitat now.');
    if (this._radInfo === undefined) {
      try { const res = await fetch('/radiation'); this._radInfo = res.ok ? await res.json() : null; }
      catch { this._radInfo = null; }
    }
    const home = await this.returnHome();
    if (!home) {
      if (this.active) alert.innerHTML = G.stormFailedHtml(el('rh-note').textContent);
      return;
    }
    alert.innerHTML = G.stormHtml(G.stormMessage(home.route, this._radInfo));
    this.play();
  }

  // ---- walkback lines on pause -------------------------------------------------

  _note(...nodes) {
    const m = this.model, note = el('rh-note');
    if (nodes.length) { note.replaceChildren(...nodes); return; }
    note.textContent = m.assumedSpeed !== null
      ? `This plan has no times or energy: walking at an assumed ${m.assumedSpeed.toFixed(0)} m/s.` : '';
  }

  _clearWalkback() {
    this._token++;                             // an answer still on its way is dropped
    if (this._extra.length) { this.lines.set(this._extra); this._dirty = true; }
    else if (this.lines.sets.length) { this.lines.clear(); this._dirty = true; }
    this.walkback = null;
    if (this.active) this._note();
  }

  // Ask for the walkback lines from where the walker is, with the energy left.
  async _settle() {
    const {model, state, plan} = this;
    const bar = state && energyReadout(state.profile, model.usableWh);
    if (!this.active || !bar || !this.walkbackOnPause) return;
    const token = ++this._token, start = plan.points.find(p => p.kind === 'start');
    const base = start ? [start.x, start.y] : (Array.isArray(plan.properties.habitat) ? plan.properties.habitat : null);
    this._note('Walkback from here: computing…');
    const {fc, error} = await requestWalkback(walkbackRequest(
      {x: state.x, y: state.y, energyLeftWh: bar.energyLeft, base, properties: plan.properties}));
    if (token !== this._token || !this.active) return;         // played on, moved or left meanwhile
    if (!fc) { this._note(`Walkback from here: ${error}`); return; }
    const lines = kind => fc.features.filter(f => f.properties && f.properties.kind === kind && f.geometry &&
                                                  f.geometry.type === 'MultiLineString')
                                     .flatMap(f => f.geometry.coordinates);
    this.lines.set([...this._extra, {lines: lines('energy_safe_boundary'), color: SAFE_LINE, width: 2.5},
                    {lines: lines('emergency_time_boundary'), color: RED_LINE, width: 3}]);
    const p = this.walkback = fc.properties || {};
    const part = (ok, text) => Object.assign(document.createElement('span'),
                                             {className: ok ? 'wb-ok' : 'wb-bad', textContent: `${ok ? '✔' : '⚠'} ${text}`});
    const nodes = ['Walkback from here (red: 30 min return · cyan: energy-safe area): '];
    if (Number.isFinite(p.return_time_s)) {
      nodes.push(part(p.contingency_ok, `Return time ${(p.return_time_s / 60).toFixed(1)} min (limit 30)`), ' · ');
    }
    if (Number.isFinite(p.return_energy_wh) && Number.isFinite(p.energy_left_after_return_wh)) {
      nodes.push(part(p.energy_ok, `Return energy ${p.return_energy_wh.toFixed(1)} Wh · ` +
                                   `${p.energy_left_after_return_wh.toFixed(1)} Wh left after returning`));
    }
    this._note(...nodes);
    this._dirty = true;
  }
}
