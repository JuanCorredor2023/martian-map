// In-context tips for the 2D HUD, in the spirit of Apple's TipKit (#125): one short tip
// at a time, next to the control it is about, at the moment it is useful. A tip closes
// with "Got it", with ×, with Esc (while it has focus) or by doing what it suggests,
// and it does not come back. Seen tips are remembered in the browser.
//   ?tips=reset  show every tip again (demo)      ?tips=off  no tips
// No libraries. The HUD is only read (tab state, station count, plan, panels): no id or
// function of web/index.html is changed. The tip list and the choice of the next tip
// are pure functions, tested with Node (tests/web/tips.test.mjs).

export const STORAGE_KEY = "martian.tips.v1";

// Order = the demo flow. `when(s)`: the moment the tip helps. `done(s)`: the user already
// did it, so the tip is retired without being shown. `anchor`: CSS selector of the control.
export const TIPS = [
  {
    id: "layers",
    anchor: "#show-slope",
    title: "Start with the terrain",
    text: "Switch layers on to see slope, sand and boulders. Hatched cells are too steep to walk.",
    when: s => s.tab === "terrain",
    done: s => s.planned,
  },
  {
    id: "stations",
    anchor: "#load-candidates",
    title: "Add science stations",
    text: "Load Curiosity's drill sites, or tick “Add stations” and click the map. Each type has a science value.",
    when: s => s.tab === "stations",
    done: s => s.planned,
  },
  {
    id: "go-plan",
    anchor: '#panel-stations .next[data-go="plan"]',
    title: "Ready to plan",
    text: "Edit work minutes or science values if you like, then go to step 3.",
    when: s => s.tab === "stations" && s.stations > 0 && s.seen.includes("stations"),
    done: s => s.planned || s.visited.includes("plan"),
  },
  {
    id: "plan",
    anchor: "#plan-btn",
    title: "Plan the walk",
    text: "Set the habitat and the limits, then plan. At every point of the route the planner keeps enough energy and time to walk home.",
    when: s => s.tab === "plan" && !s.planned,
    done: s => s.planned,
  },
  {
    id: "rehearse",
    anchor: "#walk-it",
    title: "Rehearse it",
    text: "Walk the plan step by step and watch the energy used, the energy needed to return and the spare.",
    when: s => s.tab === "plan" && s.planned,
    done: s => s.visited.includes("walk"),
  },
  {
    id: "play",
    anchor: "#play-btn",
    title: "Play the walk",
    text: "Space plays or pauses. The red line on the map is 30 min from the habitat; the dark shade is out of reach with the energy left.",
    when: s => s.tab === "walk" && s.profile,
    done: () => false,
  },
  {
    id: "probe",
    anchor: "#probe > summary",
    title: "Could they still get home?",
    text: "Place the astronaut anywhere on the map with some energy left and see the way back.",
    when: s => s.tab === "walk" && s.seen.includes("play"),
    done: s => s.probeOpen,
  },
  {
    id: "views",
    anchor: 'a[href="/3d/"]',
    title: "Other views of the same plan",
    text: "Open the tablet guide for turn-by-turn steps, or the 3D view to walk it at eye height.",
    when: s => s.tab === "walk" && s.profile && s.seen.includes("probe"),
    done: () => false,
  },
  {
    id: "storm",
    anchor: "#sep-btn",
    title: "What if a solar storm comes?",
    text: "Simulate the alert: the planner sends the astronaut home by the fastest way.",
    when: s => s.tab === "context",
    done: () => false,
  },
];

/** Parse the ?tips= switch: "reset", "off" or null. */
export function tipsMode(search) {
  const v = new URLSearchParams(search || "").get("tips");
  return v === "reset" || v === "off" ? v : null;
}

/** Tips the user already did: they count as seen, so they never show. */
export function retired(state, tips = TIPS) {
  return tips.filter(t => t.done(state)).map(t => t.id);
}

/** The one tip to show now, or null: the first unseen, not done, whose moment is now
 *  and whose control is on screen (state.visible(selector)). */
export function nextTip(state, tips = TIPS) {
  const seen = new Set(state.seen);
  for (const t of tips) {
    if (seen.has(t.id) || t.done(state) || !t.when(state)) continue;
    if (state.visible && !state.visible(t.anchor)) continue;
    return t;
  }
  return null;
}

// ------------------------------------------------------------------ browser part

function loadSeen(storage) {
  try { return JSON.parse(storage.getItem(STORAGE_KEY) || "[]"); } catch { return []; }
}

function saveSeen(storage, seen) {
  try { storage.setItem(STORAGE_KEY, JSON.stringify([...new Set(seen)])); } catch { /* private mode */ }
}

const CSS = `
.tipkit { position: fixed; z-index: 9000; width: 280px; max-width: calc(100vw - 24px);
  background: var(--surface-2, #1c232c); color: var(--text, #e8ecf1);
  border: 1px solid var(--accent, #ff7a45); border-radius: 10px; padding: 12px 14px 10px;
  box-shadow: 0 8px 28px rgba(0,0,0,.45); font-size: 13px; line-height: 1.4; }
.tipkit[hidden] { display: none; }
.tipkit:focus { outline: none; }
.tipkit:focus-visible { outline: 2px solid var(--accent, #ff7a45); outline-offset: 2px; }
.tipkit h3 { margin: 0 22px 4px 0; font-size: 13.5px; color: var(--accent, #ff7a45); }
.tipkit p { margin: 0 0 10px; }
.tipkit .tip-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.tipkit .tip-count { color: var(--muted, #a3aebb); font-size: 11.5px; white-space: nowrap; }
.tipkit button.tip-ok { background: var(--accent, #ff7a45); color: var(--accent-ink, #1a0f08); border: 0;
  border-radius: 6px; padding: 4px 12px; font: inherit; font-weight: 600; cursor: pointer; }
.tipkit button.tip-x { position: absolute; top: 6px; right: 6px; width: 26px; height: 26px; border: 0;
  background: transparent; color: var(--muted, #a3aebb); font-size: 18px; line-height: 1; cursor: pointer;
  border-radius: 6px; }
.tipkit button.tip-x:hover { color: var(--text, #e8ecf1); background: var(--surface-3, #262f3a); }
.tipkit::before { content: ""; position: absolute; width: 12px; height: 12px; background: inherit;
  border: inherit; transform: rotate(45deg); }
.tipkit[data-side="right"]::before { left: -7px; top: var(--tip-arrow, 18px); border-top: 0; border-right: 0; }
.tipkit[data-side="below"]::before { top: -7px; left: var(--tip-arrow, 24px); border-right: 0; border-bottom: 0; }
.tipkit[data-side="above"]::before { bottom: -7px; left: var(--tip-arrow, 24px); border-left: 0; border-top: 0; }
.tip-target { outline: 2px dashed var(--accent, #ff7a45) !important; outline-offset: 3px; }
.tip-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
@media (prefers-reduced-motion: no-preference) { .tipkit { animation: tipin .18s ease-out; } }
@keyframes tipin { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
`;

function isVisible(sel) {
  const el = document.querySelector(sel);
  if (!el || el.closest("[hidden]")) return false;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight && r.left < innerWidth;
}

function readState(seen, visited) {
  const tab = document.querySelector('.tabs [role="tab"][aria-selected="true"]')?.dataset.tab || "terrain";
  const count = parseInt(document.getElementById("station-count")?.textContent || "0", 10);
  const profile = document.getElementById("profile");
  return {
    tab,
    stations: Number.isFinite(count) ? count : 0,
    planned: Boolean(document.getElementById("walk-it")) || Boolean(profile && !profile.hidden),
    profile: Boolean(profile && !profile.hidden),
    probeOpen: Boolean(document.getElementById("probe")?.open),
    seen, visited,
    visible: isVisible,
  };
}

function place(box, target) {
  const r = target.getBoundingClientRect(), w = box.offsetWidth, h = box.offsetHeight, gap = 12;
  // Controls in the sidebar: the tip sits just right of the sidebar, over the map, so it
  // never covers the controls themselves.
  const side0 = target.closest("#side");
  const left = side0 ? side0.getBoundingClientRect().right : r.right;
  let side, x, y;
  if (left + gap + w <= innerWidth - 8) {
    side = "right"; x = left + gap; y = Math.min(Math.max(8, r.top + r.height / 2 - 24), innerHeight - h - 8);
    box.style.setProperty("--tip-arrow", `${Math.max(10, Math.min(h - 22, r.top + r.height / 2 - y - 6))}px`);
  } else {
    side = r.bottom + gap + h <= innerHeight - 8 ? "below" : "above";
    x = Math.min(Math.max(8, r.left), innerWidth - w - 8);
    y = side === "below" ? r.bottom + gap : r.top - gap - h;
    box.style.setProperty("--tip-arrow", `${Math.max(12, Math.min(w - 24, r.left + 16 - x))}px`);
  }
  box.dataset.side = side;
  box.style.left = `${Math.round(x)}px`;
  box.style.top = `${Math.round(y)}px`;
}

export function start({ win = window, storage = window.localStorage } = {}) {
  const mode = tipsMode(win.location.search);
  if (mode === "off") return null;
  let seen = mode === "reset" ? [] : loadSeen(storage);
  if (mode === "reset") saveSeen(storage, seen);
  const visited = [];

  const style = document.createElement("style");
  style.textContent = CSS;
  document.head.appendChild(style);
  const box = document.createElement("div");
  box.className = "tipkit";
  box.id = "tipkit";
  box.hidden = true;
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "false");
  box.setAttribute("aria-labelledby", "tipkit-title");
  box.setAttribute("aria-describedby", "tipkit-text");
  box.tabIndex = -1;        // a click on the tip's text puts the focus in it, so Esc closes it
  box.innerHTML = `<button class="tip-x" type="button" aria-label="Close tip" title="Close (Esc)">×</button>
    <h3 id="tipkit-title"></h3><p id="tipkit-text"></p>
    <div class="tip-row"><span class="tip-count"></span><button class="tip-ok" type="button">Got it</button></div>`;
  const live = document.createElement("div");
  live.className = "tip-sr";
  live.setAttribute("role", "status");
  live.setAttribute("aria-live", "polite");
  document.body.append(box, live);

  let current = null, target = null;

  function remember(id) {
    if (!seen.includes(id)) { seen = [...seen, id]; saveSeen(storage, seen); }
  }
  function hide() {
    if (target) { target.classList.remove("tip-target"); target.removeAttribute("aria-describedby"); }
    box.hidden = true; current = null; target = null;
  }
  function dismiss() {
    if (!current) return;
    const id = current.id, hadFocus = box.contains(document.activeElement), back = target;
    remember(id); hide();
    if (hadFocus && back) back.focus({preventScroll: true});
    schedule();
  }
  function show(tip) {
    hide();
    current = tip;
    const el = document.querySelector(tip.anchor);
    target = el.closest("label") || el;            // a checkbox is pointed at with its whole row
    box.querySelector("#tipkit-title").textContent = tip.title;
    box.querySelector("#tipkit-text").textContent = tip.text;
    const n = TIPS.findIndex(t => t.id === tip.id) + 1;
    box.querySelector(".tip-count").textContent = `${n} / ${TIPS.length}`;
    box.querySelector(".tip-count").setAttribute("aria-label", `Tip ${n} of ${TIPS.length}`);
    box.hidden = false;
    target.classList.add("tip-target");
    target.setAttribute("aria-describedby", "tipkit-text");
    place(box, target);
    live.textContent = `Tip: ${tip.title}. ${tip.text}`;
  }
  function update() {
    const s = readState(seen, visited);
    if (!visited.includes(s.tab)) visited.push(s.tab);
    for (const id of retired(s)) remember(id);
    s.seen = seen;
    const tip = nextTip(s);
    if (!tip) { if (current) hide(); return; }
    if (current && current.id === tip.id && target && document.body.contains(target)) { place(box, target); return; }
    show(tip);
  }
  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; update(); });
  }

  box.querySelector(".tip-ok").addEventListener("click", dismiss);
  box.querySelector(".tip-x").addEventListener("click", dismiss);
  box.addEventListener("keydown", e => { if (e.key === "Escape") { e.stopPropagation(); dismiss(); } });
  // Keyboard users hear the tip as the control's description (aria-describedby); Esc on
  // the control closes it too.
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && current && target && target.contains(document.activeElement)) dismiss();
  });
  // Using the control the tip points at also closes it for good.
  document.addEventListener("click", e => {
    if (current && target && target.contains(e.target)) { remember(current.id); hide(); schedule(); }
  }, true);
  new MutationObserver(schedule).observe(document.body, {
    subtree: true, childList: true, attributes: true,
    attributeFilter: ["hidden", "aria-selected", "open", "class"],
  });
  win.addEventListener("resize", schedule);
  document.addEventListener("scroll", schedule, true);
  schedule();
  return { update, dismiss, get current() { return current; } };
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  const go = () => { window.martianTips = start(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go);
  else go();
}
