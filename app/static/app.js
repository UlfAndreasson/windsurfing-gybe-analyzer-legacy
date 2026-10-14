const $ = (id) => document.getElementById(id);
let selectedFile = null;
let analysis = null;

const dropzone = $("dropzone");
const fileInput = $("fileInput");
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("drag"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
dropzone.addEventListener("drop", (e) => { e.preventDefault(); dropzone.classList.remove("drag"); if (e.dataTransfer.files.length) chooseFile(e.dataTransfer.files[0]); });
fileInput.addEventListener("change", () => { if (fileInput.files.length) chooseFile(fileInput.files[0]); });
$("analyzeBtn").addEventListener("click", runAnalysis);

function chooseFile(file) {
  selectedFile = file;
  $("filename").textContent = `${file.name} · ${(file.size/1024).toFixed(0)} KB`;
  $("analyzeBtn").disabled = false;
  setStatus("");
}
function setStatus(text, error=false) { const el=$("status"); el.textContent=text; el.classList.toggle("error", error); }

async function runAnalysis() {
  if (!selectedFile) return;
  const fd = new FormData();
  fd.append("file", selectedFile);
  fd.append("min_course_change_deg", $("courseChange").value);
  fd.append("min_entry_speed_kt", $("entrySpeed").value);
  fd.append("min_exit_speed_kt", $("exitSpeed").value);
  fd.append("planning_threshold_kt", $("planningSpeed").value);
  $("analyzeBtn").disabled = true;
  setStatus("Analyserar FIT-spår …");
  try {
    const response = await fetch("/api/analyze", { method:"POST", body:fd });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Analysen misslyckades");
    analysis = payload;
    renderAll();
    setStatus(`${payload.summary.gps_points} GPS-punkter · ${payload.summary.detected_turns} svängkandidater`);
  } catch (err) { setStatus(err.message, true); }
  finally { $("analyzeBtn").disabled = false; }
}

function metric(label, value) { return `<div class="metric"><span class="label">${label}</span><span class="value">${value}</span></div>`; }
function fmtDuration(sec) { sec=Math.max(0,Math.round(sec)); const h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),s=sec%60; return h?`${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`:`${m}:${String(s).padStart(2,"0")}`; }
function localTime(iso) { return new Date(iso).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"}); }
function renderAll() {
  $("results").classList.remove("hidden");
  const s=analysis.summary;
  $("summary").innerHTML = [
    metric("Distans", `${s.distance_km.toFixed(2)} km`), metric("Tid", fmtDuration(s.duration_s)), metric("Max", `${s.max_speed_kt.toFixed(1)} kt`),
    metric("GPS-punkter", s.gps_points), metric("Svängar", s.detected_turns), metric(`Planing ≥ ${analysis.settings.planning_threshold_kt} kt`, s.planning_through)
  ].join("");
  renderTrack(); renderTable();
  if (analysis.gybes.length) selectGybe(analysis.gybes[0].id);
}

function bounds(points, xKey="x", yKey="y") {
  const xs=points.map(p=>p[xKey]), ys=points.map(p=>p[yKey]);
  return {minX:Math.min(...xs),maxX:Math.max(...xs),minY:Math.min(...ys),maxY:Math.max(...ys)};
}
function scaler(b,w,h,pad=35) {
  const dx=Math.max(1,b.maxX-b.minX),dy=Math.max(1,b.maxY-b.minY),scale=Math.min((w-2*pad)/dx,(h-2*pad)/dy);
  const ox=(w-dx*scale)/2, oy=(h-dy*scale)/2;
  return (x,y)=>[ox+(x-b.minX)*scale,h-(oy+(y-b.minY)*scale)];
}
function svgEl(name, attrs={}) { const el=document.createElementNS("http://www.w3.org/2000/svg",name); Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v)); return el; }

function renderTrack() {
  const svg=$("trackSvg"); svg.innerHTML=""; const pts=analysis.track; if(!pts.length)return;
  const map=scaler(bounds(pts),1000,540,35);
  const poly=svgEl("polyline",{class:"track-line",points:pts.map(p=>map(p.x,p.y).join(",")).join(" ")}); svg.appendChild(poly);
  analysis.gybes.forEach(g=>{
    const [x,y]=map(g.center.x,g.center.y), group=svgEl("g",{class:`marker ${g.confidence<55?"very-low":g.confidence<70?"low":""}`});
    group.appendChild(svgEl("circle",{cx:x,cy:y,r:13})); const text=svgEl("text",{x,y}); text.textContent=g.id; group.appendChild(text);
    group.addEventListener("click",()=>selectGybe(g.id)); svg.appendChild(group);
  });
}
function renderTable() {
  const body=$("gybeTable").querySelector("tbody"); body.innerHTML="";
  analysis.gybes.forEach(g=>{ const tr=document.createElement("tr"); tr.dataset.id=g.id; tr.innerHTML=`
    <td>${g.id}</td><td>${localTime(g.time_utc)}</td><td>${g.direction==="right"?"Höger":"Vänster"}</td>
    <td>${g.entry_speed_kt.toFixed(1)}</td><td>${g.min_speed_kt.toFixed(1)}</td><td>${g.exit_speed_kt.toFixed(1)}</td>
    <td>${g.exit_retention_pct?.toFixed(0) ?? "–"}%</td><td>${Math.abs(g.course_change_deg).toFixed(0)}°</td><td>${g.duration_s.toFixed(1)} s</td>
    <td>${g.effective_radius_m?.toFixed(1) ?? "–"} m</td><td>${g.confidence}%</td>`;
    tr.addEventListener("click",()=>selectGybe(g.id)); body.appendChild(tr); });
}
function selectGybe(id) {
  const g=analysis.gybes.find(x=>x.id===id); if(!g)return;
  document.querySelectorAll("#gybeTable tbody tr").forEach(tr=>tr.classList.toggle("selected",Number(tr.dataset.id)===id));
  $("detailPanel").classList.remove("hidden"); $("detailTitle").textContent=`Sväng #${g.id}`;
  $("detailSubtitle").textContent=`${localTime(g.time_utc)} · ${g.direction==="right"?"höger":"vänster"} · confidence ${g.confidence}%`;
  $("detailMetrics").innerHTML=[metric("In",`${g.entry_speed_kt.toFixed(1)} kt`),metric("Minimum",`${g.min_speed_kt.toFixed(1)} kt`),metric("Ut",`${g.exit_speed_kt.toFixed(1)} kt`),metric("Ut/In",`${g.exit_retention_pct?.toFixed(0)??"–"}%`),metric("Δ kurs",`${Math.abs(g.course_change_deg).toFixed(0)}°`),metric("Effektiv radie",`${g.effective_radius_m?.toFixed(1)??"–"} m`)].join("");
  renderArc(g); renderSpeed(g); renderPoints(g);
}
function renderArc(g) {
  const svg=$("arcSvg");svg.innerHTML="";const pts=g.points;if(pts.length<2)return;const map=scaler(bounds(pts),600,420,45);
  for(let i=0;i<pts.length-1;i++){const a=pts[i],b=pts[i+1],[x1,y1]=map(a.x,a.y),[x2,y2]=map(b.x,b.y);svg.appendChild(svgEl("line",{x1,y1,x2,y2,class:(a.phase==="turn"||b.phase==="turn")?"turn-segment":"context-segment"}));}
  const apex=pts.reduce((best,p)=>p.speed_kt<best.speed_kt?p:best,pts[0]);const [ax,ay]=map(apex.x,apex.y);svg.appendChild(svgEl("circle",{cx:ax,cy:ay,r:6,class:"apex-dot"}));
  const label=svgEl("text",{x:ax+9,y:ay-9,class:"axis-label"});label.textContent=`min ${apex.speed_kt.toFixed(1)} kt`;svg.appendChild(label);
}
function renderSpeed(g) {
  const svg=$("speedSvg");svg.innerHTML="";const pts=g.points;if(pts.length<2)return;const w=600,h=420,pad=48;const minT=Math.min(...pts.map(p=>p.t)),maxT=Math.max(...pts.map(p=>p.t)),maxS=Math.max(5,...pts.map(p=>p.speed_kt))*1.1;
  const xy=(t,s)=>[pad+(t-minT)/(maxT-minT||1)*(w-2*pad),h-pad-s/maxS*(h-2*pad)];
  [0,.25,.5,.75,1].forEach(q=>{const y=h-pad-q*(h-2*pad);svg.appendChild(svgEl("line",{x1:pad,y1:y,x2:w-pad,y2:y,class:"gridline"}));const tx=svgEl("text",{x:8,y:y+4,class:"axis-label"});tx.textContent=`${(q*maxS).toFixed(0)} kt`;svg.appendChild(tx);});
  const [zx]=xy(0,0);svg.appendChild(svgEl("line",{x1:zx,y1:pad,x2:zx,y2:h-pad,class:"gridline"}));
  const poly=svgEl("polyline",{class:"plot-line",points:pts.map(p=>xy(p.t,p.speed_kt).join(",")).join(" ")});svg.appendChild(poly);
  pts.forEach(p=>{const [x,y]=xy(p.t,p.speed_kt);const c=svgEl("circle",{cx:x,cy:y,r:p.t===0?5:3,class:p.t===0?"apex-dot":""}); if(p.t!==0)c.setAttribute("fill","currentColor");svg.appendChild(c);});
  const lbl=svgEl("text",{x:zx+6,y:pad+14,class:"axis-label"});lbl.textContent="t=0: minfart";svg.appendChild(lbl);
}
function renderPoints(g) {
  const body=$("pointsTable").querySelector("tbody");body.innerHTML="";g.points.forEach(p=>{const tr=document.createElement("tr");tr.innerHTML=`<td>${p.t>0?"+":""}${p.t}s</td><td>${p.speed_kt.toFixed(1)} kt</td><td>${p.course_deg===null?"–":p.course_deg.toFixed(0)+"°"}</td><td>${p.turn_rate_dps===null?"–":p.turn_rate_dps.toFixed(1)+"°/s"}</td><td>${p.phase==="turn"?"sväng":"kontext"}</td>`;body.appendChild(tr);});
}
