// origen's page: draws the sky right now from /v1/sky and /v1/stars on the same origin.
// It draws, never computes: positions come from origen; the stars are placed with the
// rotation matrix /v1/sky gives for each sample (spec §5.3, §8).
(function () {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const R = 100; // horizon radius on the chart
  const REFRESH_MS = 10 * 60 * 1000;
  const NAMES = {
    sun: "Sun", moon: "Moon", mercury: "Mercury", venus: "Venus", mars: "Mars",
    jupiter: "Jupiter", saturn: "Saturn", uranus: "Uranus", neptune: "Neptune", pluto: "Pluto",
  };
  const SUN_EVENTS = {
    astronomical_dawn: "Astronomical dawn (−18°)", nautical_dawn: "Nautical dawn (−12°)",
    civil_dawn: "Civil dawn (−6°)", rise: "Sunrise", transit: "Noon (transit)", set: "Sunset",
    civil_dusk: "Civil dusk (−6°)", nautical_dusk: "Nautical dusk (−12°)",
    astronomical_dusk: "Astronomical dusk (−18°)",
  };
  const PHASES = { new: "new Moon", first_quarter: "first quarter", full: "full Moon", last_quarter: "last quarter" };

  const section = document.getElementById("sky");
  if (!section) return;
  const place = {
    lat: section.dataset.lat, lon: section.dataset.lon, elev: section.dataset.elev,
  };
  const svg = document.getElementById("chart");
  const status = document.getElementById("sky-status");
  let stars = null;

  let tz = section.dataset.tz || "UTC";
  try { new Intl.DateTimeFormat("en-GB", { timeZone: tz }); } catch (e) { tz = "UTC"; }
  const clock = new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", minute: "2-digit" });
  const dayClock = new Intl.DateTimeFormat("en-GB", {
    timeZone: tz, weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }

  function text(parent, x, y, content, cls) {
    const t = el("text", { x: x.toFixed(2), y: y.toFixed(2), class: cls }, parent);
    t.textContent = content;
    return t;
  }

  // Altitude/azimuth (degrees) to chart x, y: zenith at the centre, north up, east left.
  function project(alt, az) {
    const r = R * (90 - alt) / 90;
    const a = az * Math.PI / 180;
    return [-r * Math.sin(a), -r * Math.cos(a)];
  }

  function enuToAltAz(e, n, u) {
    return [Math.asin(Math.max(-1, Math.min(1, u))) * 180 / Math.PI, (Math.atan2(e, n) * 180 / Math.PI + 360) % 360];
  }

  function starColour(bv) {
    if (bv === null) return "#ffffff";
    if (bv < 0) return "#b5c7ff";
    if (bv < 0.3) return "#dfe6ff";
    if (bv < 0.6) return "#fff8e8";
    if (bv < 1.0) return "#ffe2b0";
    if (bv < 1.4) return "#ffc98a";
    return "#ffad70";
  }

  function drawFrame() {
    el("circle", { cx: 0, cy: 0, r: R, class: "horizon" }, svg);
    for (const alt of [30, 60]) el("circle", { cx: 0, cy: 0, r: R * (90 - alt) / 90, class: "grid" }, svg);
    for (const [label, az] of [["N", 0], ["E", 90], ["S", 180], ["W", 270]]) {
      const [x, y] = project(-7, az);
      text(svg, x, y + 2, label, "cardinal");
    }
  }

  function drawStars(m) {
    const g = el("g", { class: "stars" }, svg);
    const s = stars.stars;
    for (let k = 0; k < s.hip.length; k++) {
      const ra = s.ra_deg[k] * Math.PI / 180, dec = s.dec_deg[k] * Math.PI / 180;
      const x = Math.cos(dec) * Math.cos(ra), y = Math.cos(dec) * Math.sin(ra), z = Math.sin(dec);
      const e = m[0] * x + m[1] * y + m[2] * z;
      const n = m[3] * x + m[4] * y + m[5] * z;
      const u = m[6] * x + m[7] * y + m[8] * z;
      if (u <= 0) continue;
      const [alt, az] = enuToAltAz(e, n, u);
      const [px, py] = project(alt, az);
      const r = Math.max(0.3, 1.5 - 0.25 * s.vmag[k]);
      const c = el("circle", { cx: px.toFixed(2), cy: py.toFixed(2), r: r.toFixed(2), fill: starColour(s.bv[k]) }, g);
      if (s.name[k]) {
        const t = el("title", {}, c);
        t.textContent = s.name[k] + " (V " + s.vmag[k] + ")";
        if (s.vmag[k] < 1.0) text(g, px + r + 0.8, py + 1.2, s.name[k], "star-label");
      }
    }
  }

  // The lit part of the Moon: a disc lit from local +x, rotated to where the Sun is.
  function drawMoon(parent, x, y, body, i) {
    const r = 4;
    const k = body.illuminated_fraction[i];
    const alt = body.alt_deg[i] * Math.PI / 180, az = body.az_deg[i] * Math.PI / 180;
    const m = [Math.cos(alt) * Math.sin(az), Math.cos(alt) * Math.cos(az), Math.sin(alt)];
    const l = body.light_dir[i];
    const p = [m[0] + 0.02 * l[0], m[1] + 0.02 * l[1], m[2] + 0.02 * l[2]];
    const [a2, z2] = enuToAltAz(p[0], p[1], p[2] / Math.hypot(p[0], p[1], p[2]));
    const [x2, y2] = project(a2, z2);
    const angle = Math.atan2(y2 - y, x2 - x) * 180 / Math.PI;
    const g = el("g", { transform: "translate(" + x.toFixed(2) + " " + y.toFixed(2) + ") rotate(" + angle.toFixed(1) + ")" }, parent);
    el("circle", { cx: 0, cy: 0, r: r, class: "moon-dark" }, g);
    const rx = (r * Math.abs(1 - 2 * k)).toFixed(3);
    const sweep = k > 0.5 ? 1 : 0;
    el("path", { d: "M0," + (-r) + " A" + r + "," + r + " 0 0 1 0," + r + " A" + rx + "," + r + " 0 0 " + sweep + " 0," + (-r) + "Z", class: "moon-lit" }, g);
    const t = el("title", {}, g);
    t.textContent = "Moon, " + Math.round(k * 100) + "% lit";
  }

  function drawBodies(sky, i) {
    const g = el("g", { class: "bodies" }, svg);
    for (const key of Object.keys(NAMES)) {
      const b = sky.bodies[key];
      if (b.alt_deg[i] <= 0) continue;
      const [x, y] = project(b.alt_deg[i], b.az_deg[i]);
      if (key === "moon") drawMoon(g, x, y, b, i);
      else el("circle", { cx: x.toFixed(2), cy: y.toFixed(2), r: key === "sun" ? 4 : 1.8, class: "body " + key }, g);
      text(g, x + 4.8, y + 1.5, NAMES[key], "body-label");
    }
  }

  function nextEvent(sky, body, kind, now) {
    const e = sky.events.find((ev) => ev.body === body && ev.kind === kind && Date.parse(ev.at) >= now);
    return e ? dayClock.format(new Date(e.at)) : "—";
  }

  function fillTables(sky, i, now) {
    const tbody = document.querySelector("#bodies tbody");
    tbody.replaceChildren();
    for (const key of Object.keys(NAMES)) {
      const b = sky.bodies[key];
      const tr = document.createElement("tr");
      if (b.alt_deg[i] <= 0) tr.className = "below";
      const mag = b.magnitude[i] === null ? "—" : b.magnitude[i].toFixed(1);
      const rises = key === "sun" || key === "moon" ? nextEvent(sky, key, "rise", now) : "—";
      const sets = key === "sun" || key === "moon" ? nextEvent(sky, key, "set", now) : "—";
      for (const cell of [NAMES[key], b.alt_deg[i].toFixed(1) + "°", b.az_deg[i].toFixed(1) + "°", mag, rises, sets]) {
        const td = document.createElement("td");
        td.textContent = cell;
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    const tw = document.querySelector("#twilights tbody");
    tw.replaceChildren();
    const day = sky.events.filter((ev) => ev.body === "sun" && Date.parse(ev.at) >= now && Date.parse(ev.at) < now + 864e5);
    for (const ev of day) {
      const tr = document.createElement("tr");
      for (const cell of [SUN_EVENTS[ev.kind], dayClock.format(new Date(ev.at))]) {
        const td = document.createElement("td");
        td.textContent = cell;
        tr.appendChild(td);
      }
      tw.appendChild(tr);
    }
    if (!day.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 2;
      td.textContent = "No sunrise, sunset or twilight in the next 24 hours.";
      tr.appendChild(td);
      tw.appendChild(tr);
    }
    const moon = sky.bodies.moon;
    const phase = sky.moon_phase.phase_deg[i];
    const next = sky.moon_phase.next[0];
    document.getElementById("moon-line").textContent =
      "The Moon is " + Math.round(moon.illuminated_fraction[i] * 100) + "% lit and " +
      (phase < 180 ? "waxing" : "waning") + ". Next: " + PHASES[next.phase] + ", " +
      dayClock.format(new Date(next.at)) + ".";
  }

  function draw(sky) {
    const now = Date.now();
    const step = sky.step_min * 60000;
    const i = Math.max(0, Math.min(sky.count - 1, Math.round((now - Date.parse(sky.from)) / step)));
    svg.replaceChildren();
    drawFrame();
    drawStars(sky.stars_rotation[i]);
    drawBodies(sky, i);
    fillTables(sky, i, now);
    status.textContent = "Sky at " + clock.format(new Date(sky.times[i])) + " (" + tz + "), refreshed every 10 minutes.";
  }

  async function getJSON(url) {
    const res = await fetch(url);
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || res.statusText);
    return body;
  }

  async function load() {
    try {
      if (!stars) stars = await getJSON("/v1/stars");
      const q = new URLSearchParams({ lat: place.lat, lon: place.lon, elev_m: place.elev, hours: "26", step_min: "10" });
      draw(await getJSON("/v1/sky?" + q.toString()));
    } catch (err) {
      status.textContent = "Could not load the sky: " + err.message;
    }
  }

  load();
  setInterval(load, REFRESH_MS);
})();
