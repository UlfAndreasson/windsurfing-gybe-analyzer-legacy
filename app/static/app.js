const $ = (id) => document.getElementById(id);
let selectedFile = null;
let analysis = null;
let activeSessionId = null;
let selectedGybeId = null;
let selectedPointIndex = null;
let navigationMode = "gybes";

const dropzone = $("dropzone");
const fileInput = $("fileInput");
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("drag"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault(); dropzone.classList.remove("drag");
  if (e.dataTransfer.files.length) chooseFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => { if (fileInput.files.length) chooseFile(fileInput.files[0]); });
$("analyzeBtn").addEventListener("click", runAnalysis);
$("savedSessions").addEventListener("change", () => { $("loadSavedBtn").disabled = !$("savedSessions").value; });
$("loadSavedBtn").addEventListener("click", loadSelectedSession);
$("gybeTable").addEventListener("focus", () => { navigationMode = "gybes"; });
$("pointsTable").addEventListener("focus", () => { navigationMode = "points"; });

document.addEventListener("keydown", (event) => {
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  const tag = event.target?.tagName?.toLowerCase();
  if (["input", "select", "textarea", "button"].includes(tag)) return;
  if (!analysis?.gybes?.length) return;
  event.preventDefault();
  const delta = event.key === "ArrowDown" ? 1 : -1;
  if (navigationMode === "points" && selectedGybeId !== null) stepPoint(delta);
  else stepGybe(delta);
});

function chooseFile(file) {
  selectedFile = file;
  activeSessionId = null;
  $("filename").textContent = `${file.name} · ${(file.size / 1024).toFixed(0)} KB`;
  $("analyzeBtn").disabled = false;
  setStatus("");
}

function setStatus(text, error = false) {
  const el = $("status");
  el.textContent = text;
  el.classList.toggle("error", error);
}

function settingsForm() {
  const fd = new FormData();
  fd.append("min_course_change_deg", $("courseChange").value);
  fd.append("min_entry_speed_kt", $("entrySpeed").value);
  fd.append("min_exit_speed_kt", $("exitSpeed").value);
  fd.append("planning_threshold_kt", $("planningSpeed").value);
  fd.append("wind_from_deg", $("windFrom").value.trim());
  return fd;
}

async function runAnalysis() {
  if (!selectedFile && !activeSessionId) return;
  const fd = settingsForm();
  let url = "/api/analyze";
  if (selectedFile) fd.append("file", selectedFile);
  else url = `/api/sessions/${activeSessionId}/reanalyze`;

  $("analyzeBtn").disabled = true;
  setStatus(selectedFile ? "Analyserar FIT-spår …" : "Analyserar sparad session …");
  try {
    const response = await fetch(url, { method: "POST", body: fd });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Analysen misslyckades");
    analysis = payload;
    activeSessionId = payload.session_id || activeSessionId;
    selectedGybeId = null;
    selectedPointIndex = null;
    navigationMode = "gybes";
    renderAll();
    setStatus(`${payload.summary.gps_points} GPS-punkter · ${payload.summary.detected_turns} svängkandidater · sparad lokalt`);
    await refreshSavedSessions(activeSessionId);
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    $("analyzeBtn").disabled = false;
  }
}

async function refreshSavedSessions(selectId = null) {
  try {
    const response = await fetch("/api/sessions");
    const payload = await response.json();
    if (!response.ok) return;
    const select = $("savedSessions");
    select.innerHTML = "";
    if (!payload.sessions.length) {
      select.innerHTML = '<option value="">Inga sparade analyser</option>';
      $("loadSavedBtn").disabled = true;
      return;
    }
    select.appendChild(new Option("Välj sparad session …", ""));
    payload.sessions.forEach((session) => {
      const start = session.summary?.start_utc ? new Date(session.summary.start_utc).toLocaleString() : "Okänt datum";
      const name = session.source?.filename || session.session_id;
      const turns = session.summary?.detected_turns ?? "–";
      select.appendChild(new Option(`${start} · ${name} · ${turns} svängar`, session.session_id));
    });
    if (selectId && [...select.options].some((o) => o.value === selectId)) select.value = selectId;
    $("loadSavedBtn").disabled = !select.value;
  } catch (_) {
    // Persistence is a convenience; a list failure must not block fresh analysis.
  }
}

async function loadSelectedSession() {
  const id = $("savedSessions").value;
  if (!id) return;
  $("loadSavedBtn").disabled = true;
  setStatus("Laddar sparad analys …");
  try {
    const response = await fetch(`/api/sessions/${id}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Kunde inte ladda analysen");
    analysis = payload;
    activeSessionId = id;
    selectedFile = null;
    fileInput.value = "";
    $("filename").textContent = `${payload.source?.filename || id} · sparad lokalt`;
    applySettings(payload.settings || {});
    $("analyzeBtn").disabled = false;
    selectedGybeId = null;
    selectedPointIndex = null;
    navigationMode = "gybes";
    renderAll();
    setStatus(`${payload.summary.gps_points} GPS-punkter · ${payload.summary.detected_turns} svängkandidater · laddad från disk`);
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    $("loadSavedBtn").disabled = false;
  }
}

function applySettings(settings) {
  if (settings.min_course_change_deg !== undefined) $("courseChange").value = settings.min_course_change_deg;
  if (settings.min_entry_speed_kt !== undefined) $("entrySpeed").value = settings.min_entry_speed_kt;
  if (settings.min_exit_speed_kt !== undefined) $("exitSpeed").value = settings.min_exit_speed_kt;
  if (settings.planning_threshold_kt !== undefined) $("planningSpeed").value = settings.planning_threshold_kt;
  $("windFrom").value = settings.wind_from_deg ?? "";
}

function metric(label, value) {
  return `<div class="metric"><span class="label">${label}</span><span class="value">${value}</span></div>`;
}
function fmtDuration(sec) {
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}
function localTime(iso) { return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
function directionLabel(g) { return g.direction === "right" ? "Höger/SB" : "Vänster/BB"; }
function maneuverLabel(g) { return g.maneuver === "gybe" ? "Gipp" : g.maneuver === "tack" ? "Tack" : "Okänd"; }

function renderAll() {
  $("results").classList.remove("hidden");
  const s = analysis.summary;
  const typeMetric = analysis.wind?.from_deg == null ? `${s.detected_turns}` : `${s.detected_gybes} / ${s.detected_tacks}`;
  $("summary").innerHTML = [
    metric("Distans", `${s.distance_km.toFixed(2)} km`),
    metric("Tid", fmtDuration(s.duration_s)),
    metric("Max", `${s.max_speed_kt.toFixed(1)} kt`),
    metric("GPS-punkter", s.gps_points),
    metric(analysis.wind?.from_deg == null ? "Svängar" : "Gipp / Tack", typeMetric),
    metric(`Planing ≥ ${analysis.settings.planning_threshold_kt} kt`, s.planning_through),
  ].join("");
  renderTrack();
  renderTable();
  if (analysis.gybes.length) selectGybe(analysis.gybes[0].id, false);
}

function bounds(points, xKey = "x", yKey = "y") {
  const xs = points.map((p) => p[xKey]), ys = points.map((p) => p[yKey]);
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
}
function scaler(b, w, h, pad = 35) {
  const dx = Math.max(1, b.maxX - b.minX), dy = Math.max(1, b.maxY - b.minY), scale = Math.min((w - 2 * pad) / dx, (h - 2 * pad) / dy);
  const ox = (w - dx * scale) / 2, oy = (h - dy * scale) / 2;
  return (x, y) => [ox + (x - b.minX) * scale, h - (oy + (y - b.minY) * scale)];
}
function svgEl(name, attrs = {}) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
  return el;
}

function renderTrack() {
  const svg = $("trackSvg");
  svg.innerHTML = "";
  const pts = analysis.track;
  if (!pts.length) return;
  const map = scaler(bounds(pts), 1000, 540, 35);
  svg.appendChild(svgEl("polyline", { class: "track-line", points: pts.map((p) => map(p.x, p.y).join(",")).join(" ") }));
  analysis.gybes.forEach((g) => {
    const [x, y] = map(g.center.x, g.center.y);
    const classes = ["marker", g.confidence < 55 ? "very-low" : g.confidence < 70 ? "low" : "", g.id === selectedGybeId ? "selected" : ""].filter(Boolean).join(" ");
    const group = svgEl("g", { class: classes });
    group.appendChild(svgEl("circle", { cx: x, cy: y, r: 13 }));
    const text = svgEl("text", { x, y }); text.textContent = g.id; group.appendChild(text);
    group.addEventListener("click", () => { navigationMode = "gybes"; selectGybe(g.id); });
    svg.appendChild(group);
  });
}

function renderTable() {
  const body = $("gybeTable").querySelector("tbody");
  body.innerHTML = "";
  analysis.gybes.forEach((g) => {
    const tr = document.createElement("tr");
    tr.dataset.id = g.id;
    tr.innerHTML = `
      <td>${g.id}</td><td>${localTime(g.time_utc)}</td><td>${maneuverLabel(g)}</td><td>${directionLabel(g)}</td>
      <td>${g.entry_speed_kt.toFixed(1)}</td><td>${g.min_speed_kt.toFixed(1)}</td><td>${g.exit_speed_kt.toFixed(1)}</td>
      <td>${g.exit_retention_pct?.toFixed(0) ?? "–"}%</td><td>${Math.abs(g.course_change_deg).toFixed(0)}°</td><td>${g.duration_s.toFixed(1)} s</td>
      <td>${g.effective_radius_m?.toFixed(1) ?? "–"} m</td><td>${g.confidence}%</td>`;
    tr.addEventListener("click", () => { navigationMode = "gybes"; $("gybeTable").focus(); selectGybe(g.id); });
    body.appendChild(tr);
  });
}

function stepGybe(delta) {
  if (!analysis?.gybes?.length) return;
  let index = analysis.gybes.findIndex((g) => g.id === selectedGybeId);
  if (index < 0) index = 0;
  else index = Math.max(0, Math.min(analysis.gybes.length - 1, index + delta));
  selectGybe(analysis.gybes[index].id);
}

function selectGybe(id, scroll = true) {
  const g = analysis.gybes.find((x) => x.id === id);
  if (!g) return;
  selectedGybeId = id;
  selectedPointIndex = null;
  document.querySelectorAll("#gybeTable tbody tr").forEach((tr) => tr.classList.toggle("selected", Number(tr.dataset.id) === id));
  const selectedRow = document.querySelector(`#gybeTable tbody tr[data-id="${id}"]`);
  if (scroll && selectedRow) selectedRow.scrollIntoView({ block: "nearest" });
  $("detailPanel").classList.remove("hidden");
  const type = maneuverLabel(g);
  $("detailTitle").textContent = `${type === "Okänd" ? "Sväng" : type} #${g.id}`;
  const windText = analysis.wind?.from_deg == null ? "vind ej satt" : `vind från ${analysis.wind.from_deg.toFixed(0)}°T`;
  $("detailSubtitle").textContent = `${localTime(g.time_utc)} · ${directionLabel(g)} · ${windText} · confidence ${g.confidence}%`;
  $("detailMetrics").innerHTML = [
    metric("In", `${g.entry_speed_kt.toFixed(1)} kt`), metric("Minimum", `${g.min_speed_kt.toFixed(1)} kt`),
    metric("Ut", `${g.exit_speed_kt.toFixed(1)} kt`), metric("Ut/In", `${g.exit_retention_pct?.toFixed(0) ?? "–"}%`),
    metric("Δ kurs", `${Math.abs(g.course_change_deg).toFixed(0)}°`), metric("Effektiv radie", `${g.effective_radius_m?.toFixed(1) ?? "–"} m`),
  ].join("");
  renderTrack();
  renderArc(g);
  renderSpeed(g);
  renderPoints(g);
}

function speedColor(speed, minSpeed, maxSpeed) {
  const span = Math.max(0.1, maxSpeed - minSpeed);
  const t = Math.max(0, Math.min(1, (speed - minSpeed) / span));
  const stops = [
    [0.0, [30, 80, 220]],
    [0.34, [20, 170, 100]],
    [0.67, [245, 190, 35]],
    [1.0, [220, 45, 40]],
  ];
  let left = stops[0], right = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (t >= stops[i][0] && t <= stops[i + 1][0]) { left = stops[i]; right = stops[i + 1]; break; }
  }
  const q = (t - left[0]) / Math.max(0.001, right[0] - left[0]);
  const rgb = left[1].map((v, i) => Math.round(v + (right[1][i] - v) * q));
  return `rgb(${rgb.join(",")})`;
}

function drawWindArrow(svg, windFromDeg) {
  if (windFromDeg == null) return;
  const cx = 505, cy = 70, length = 72;
  const windTo = (windFromDeg + 180) % 360;
  const rad = windTo * Math.PI / 180;
  const dx = Math.sin(rad), dy = -Math.cos(rad);
  const x1 = cx - dx * length / 2, y1 = cy - dy * length / 2;
  const x2 = cx + dx * length / 2, y2 = cy + dy * length / 2;
  svg.appendChild(svgEl("line", { x1, y1, x2, y2, class: "wind-line" }));
  const side = 8, back = 14;
  const px = -dy, py = dx;
  const points = [
    [x2, y2],
    [x2 - dx * back + px * side, y2 - dy * back + py * side],
    [x2 - dx * back - px * side, y2 - dy * back - py * side],
  ].map((p) => p.join(",")).join(" ");
  svg.appendChild(svgEl("polygon", { points, class: "wind-arrowhead" }));
  const label = svgEl("text", { x: 390, y: 24, class: "wind-label" });
  label.textContent = `Vind från ${windFromDeg.toFixed(0)}°T`;
  svg.appendChild(label);
}

function renderArc(g) {
  const svg = $("arcSvg");
  svg.innerHTML = "";
  const pts = g.points;
  if (pts.length < 2) return;
  const map = scaler(bounds(pts), 600, 420, 50);
  const minSpeed = Math.min(...pts.map((p) => p.speed_kt));
  const maxSpeed = Math.max(...pts.map((p) => p.speed_kt));
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1], [x1, y1] = map(a.x, a.y), [x2, y2] = map(b.x, b.y);
    const turn = a.phase === "turn" || b.phase === "turn";
    svg.appendChild(svgEl("line", {
      x1, y1, x2, y2,
      stroke: speedColor((a.speed_kt + b.speed_kt) / 2, minSpeed, maxSpeed),
      "stroke-width": turn ? 5 : 3,
      opacity: turn ? 1 : 0.35,
      "stroke-linecap": "round",
    }));
  }
  const apexIndex = pts.reduce((best, p, i) => p.speed_kt < pts[best].speed_kt ? i : best, 0);
  const apex = pts[apexIndex], [ax, ay] = map(apex.x, apex.y);
  svg.appendChild(svgEl("circle", { cx: ax, cy: ay, r: 6, class: "apex-dot" }));
  const label = svgEl("text", { x: ax + 9, y: ay - 9, class: "axis-label" });
  label.textContent = `min ${apex.speed_kt.toFixed(1)} kt`; svg.appendChild(label);

  if (selectedPointIndex !== null && pts[selectedPointIndex]) {
    const p = pts[selectedPointIndex], [px, py] = map(p.x, p.y);
    svg.appendChild(svgEl("circle", { cx: px, cy: py, r: 8, class: "point-highlight" }));
    const text = svgEl("text", { x: px + 11, y: py + 4, class: "axis-label" });
    text.textContent = `${p.t > 0 ? "+" : ""}${p.t}s · ${p.speed_kt.toFixed(1)} kt`; svg.appendChild(text);
  }
  drawWindArrow(svg, analysis.wind?.from_deg);
}

function renderSpeed(g) {
  const svg = $("speedSvg");
  svg.innerHTML = "";
  const pts = g.points;
  if (pts.length < 2) return;
  const w = 600, h = 420, pad = 48;
  const minT = Math.min(...pts.map((p) => p.t)), maxT = Math.max(...pts.map((p) => p.t)), maxS = Math.max(5, ...pts.map((p) => p.speed_kt)) * 1.1;
  const xy = (t, s) => [pad + (t - minT) / (maxT - minT || 1) * (w - 2 * pad), h - pad - s / maxS * (h - 2 * pad)];
  [0, .25, .5, .75, 1].forEach((q) => {
    const y = h - pad - q * (h - 2 * pad);
    svg.appendChild(svgEl("line", { x1: pad, y1: y, x2: w - pad, y2: y, class: "gridline" }));
    const tx = svgEl("text", { x: 8, y: y + 4, class: "axis-label" }); tx.textContent = `${(q * maxS).toFixed(0)} kt`; svg.appendChild(tx);
  });
  const [zx] = xy(0, 0);
  svg.appendChild(svgEl("line", { x1: zx, y1: pad, x2: zx, y2: h - pad, class: "gridline" }));
  svg.appendChild(svgEl("polyline", { class: "plot-line", points: pts.map((p) => xy(p.t, p.speed_kt).join(",")).join(" ") }));
  pts.forEach((p, index) => {
    const [x, y] = xy(p.t, p.speed_kt);
    const c = svgEl("circle", { cx: x, cy: y, r: p.t === 0 ? 5 : 3, fill: p.t === 0 ? "var(--danger)" : "currentColor" });
    svg.appendChild(c);
    if (index === selectedPointIndex) svg.appendChild(svgEl("circle", { cx: x, cy: y, r: 8, class: "point-highlight" }));
  });
  const lbl = svgEl("text", { x: zx + 6, y: pad + 14, class: "axis-label" }); lbl.textContent = "t=0: minfart"; svg.appendChild(lbl);
}

function renderPoints(g) {
  const body = $("pointsTable").querySelector("tbody");
  body.innerHTML = "";
  g.points.forEach((p, index) => {
    const tr = document.createElement("tr");
    tr.dataset.index = index;
    if (index === selectedPointIndex) tr.classList.add("selected");
    tr.innerHTML = `<td>${p.t > 0 ? "+" : ""}${p.t}s</td><td>${p.speed_kt.toFixed(1)} kt</td><td>${p.course_deg === null ? "–" : p.course_deg.toFixed(0) + "°"}</td><td>${p.turn_rate_dps === null ? "–" : p.turn_rate_dps.toFixed(1) + "°/s"}</td><td>${p.phase === "turn" ? "sväng" : "kontext"}</td>`;
    tr.addEventListener("click", () => { navigationMode = "points"; $("pointsTable").focus(); selectPoint(index); });
    body.appendChild(tr);
  });
}

function stepPoint(delta) {
  const g = analysis.gybes.find((x) => x.id === selectedGybeId);
  if (!g?.points?.length) return;
  let index = selectedPointIndex;
  if (index === null) index = g.points.findIndex((p) => p.t === 0);
  if (index < 0) index = 0;
  index = Math.max(0, Math.min(g.points.length - 1, index + delta));
  selectPoint(index);
}

function selectPoint(index) {
  const g = analysis.gybes.find((x) => x.id === selectedGybeId);
  if (!g || !g.points[index]) return;
  selectedPointIndex = index;
  renderArc(g);
  renderSpeed(g);
  renderPoints(g);
  const row = document.querySelector(`#pointsTable tbody tr[data-index="${index}"]`);
  if (row) row.scrollIntoView({ block: "nearest" });
}

refreshSavedSessions();
