// What the 3D map does with the Sun of Mars (P1, issue #42, block 4): the numbers.
//
// mars_sun.js says where the Sun is; this file turns "sol 4711 at 15:00 at the box
// centre, 20 minutes into the EVA" into a light direction, light levels and the words
// of the panel. No three.js and no page here, so it is tested in Node
// (tests/viz3d/sun_model.test.mjs); sun.js applies it to the scene.
//
// The time the page speaks is the LOCAL TRUE SOLAR TIME at the site (12:00 is when the
// Sun crosses the meridian), and the sol is counted on that same clock
// (mars_sun.js: trueSolarDate), so the time slider has no jump at any hour.
import { SOL_IN_SECONDS, planetographicLatitude, sunPosition, utcOfTrueSolarTime } from './mars_sun.js';

export const MARS_RADIUS_M = 3396190;          // sphere of the project's CRS (docs/contracts/crs.wkt)
export const DEFAULT_SOL = 4711;               // Curiosity in the boxwork (2025-11)
export const DEFAULT_HOURS = 15;               // mid-afternoon, like the photo's own light
export const MAX_SOL = 9999;

// Light levels. A look, not a radiometric model: no atmosphere, dust or sky brightness
// is computed. The values at full day are the ones the page had before the Sun moved.
export const SUN_FULL = 2.6;                   // directional light with the Sun high
export const SKY_DAY = 1.1, SKY_NIGHT = 0.3;   // hemisphere light: never black
const SUN_FADE_DEG = 12;                       // the sun light goes from 0 at the horizon to full here
const DUSK_DEG = 6;                            // the sky light changes between -6 and +6 degrees

const DEG = Math.PI / 180;
const smoothstep = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// Longitude east and latitude of a point of the CRS (equirectangular on a sphere with
// the origin at lon 0, lat 0). latDeg is planetographic, the one mars_sun.js expects.
export function siteFromCrs(x, y) {
  const latCentricDeg = y / MARS_RADIUS_M / DEG;
  return {lonEastDeg: x / MARS_RADIUS_M / DEG, latCentricDeg, latDeg: planetographicLatitude(latCentricDeg)};
}

// "4711" -> 4711; anything that is not a whole sol from 0 to MAX_SOL -> null.
export function parseSol(text) {
  if (!/^\s*\d+\s*$/.test(String(text ?? ''))) return null;
  const sol = Number(text);
  return sol <= MAX_SOL ? sol : null;
}

// "15:00", "7:30" or "15" -> hours in [0, 24); anything else -> null.
export function parseClock(text) {
  const m = /^\s*(\d{1,2})(?::(\d{2}))?\s*$/.exec(String(text ?? ''));
  if (!m) return null;
  const h = Number(m[1]), min = Number(m[2] || 0);
  return h < 24 && min < 60 ? h + min / 60 : null;
}

// Hours -> "07:05", to the nearest minute (24:00 is written 00:00).
export function clockText(hours) {
  const minutes = Math.round((((hours % 24) + 24) % 24) * 60) % 1440;
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

const COMPASS = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'];
export function compassWord(azimuthDeg) {
  return COMPASS[Math.round((((azimuthDeg % 360) + 360) % 360) / 45) % 8];
}

// Unit vector towards the Sun in the scene's axes (X east, Y up, Z SOUTH).
export function sunVector(azimuthDeg, elevationDeg) {
  const az = azimuthDeg * DEG, el = elevationDeg * DEG;
  return [Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el)];
}

// Light levels for a Sun elevation. sun: the directional light, zero at and below the
// horizon (the planet itself casts no shadow in the scene, so a Sun under the horizon
// must not light anything). sky: the hemisphere light. day: 0 at night to 1 by day, for
// the sky colour.
export function lightLevels(elevationDeg) {
  const day = smoothstep(-DUSK_DEG, DUSK_DEG, elevationDeg);
  return {sun: SUN_FULL * smoothstep(0, SUN_FADE_DEG, elevationDeg),
          sky: SKY_NIGHT + (SKY_DAY - SKY_NIGHT) * day, day, night: elevationDeg < 0};
}

// Everything the page shows for a start (sol, local true solar time in hours) at a
// site (siteFromCrs), elapsedS seconds of EVA later.
export function sunState({sol, hours, elapsedS = 0}, site) {
  const startUtcMs = utcOfTrueSolarTime(sol, hours, site.lonEastDeg);
  const utcMs = startUtcMs + elapsedS * 1000;
  const p = sunPosition(utcMs, site);
  return {sol, hours, elapsedS, startUtcMs, utcMs, ltst: p.ltst, lmst: p.lmst, ls: p.ls, eot: p.eot,
          elevation: p.elevation, azimuth: p.azimuth, hourAngle: p.hourAngle, declination: p.declination,
          direction: sunVector(p.azimuth, p.elevation), ...lightLevels(p.elevation)};
}

// The one-line readout, in plain words.
export function readoutText(state) {
  const ls = `Ls ${state.ls.toFixed(0)}°`;
  if (state.night) {
    return `Night: the Sun is below the horizon (${Math.max(1, Math.round(-state.elevation))}° under it) · ${ls}`;
  }
  return `Sun ${state.elevation.toFixed(0)}° above the horizon · light from the ${compassWord(state.azimuth)} ` +
         `(azimuth ${state.azimuth.toFixed(0)}°) · ${ls}`;
}

// Earth date of an instant, to the minute: "2025-11-06 13:21 UTC".
export function utcText(utcMs) {
  return `${new Date(utcMs).toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}

// How far the local solar clock moves in a given number of SI seconds, in hours.
export const solarHours = seconds => seconds / SOL_IN_SECONDS * 24;
