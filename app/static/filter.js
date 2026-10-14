// Display-only minimum entry speed filter.
// This intentionally never changes analyzer settings or re-runs detection.
(() => {
  let displayMinEntryKt = 0;

  const visibleGybes = () => {
    if (!analysis?.gybes) return [];
    return analysis.gybes.filter((g) => Number(g.entry_speed_kt) >= displayMinEntryKt);
  };

  const withVisibleGybes = (fn) => {
    if (!analysis?.gybes) return fn();
    const all = analysis.gybes;
    analysis.gybes = visibleGybes();
    try {
      return fn();
    } finally {
      analysis.gybes = all;
    }
  };

  const originalRenderTrack = renderTrack;
  const originalRenderTable = renderTable;
  const originalRenderAll = renderAll;

  renderTrack = function () {
    return withVisibleGybes(() => originalRenderTrack());
  };

  renderTable = function () {
    const visible = visibleGybes();
    if (!visible.length) {
      const body = $("gybeTable").querySelector("tbody");
      body.innerHTML = `<tr><td colspan="14" class="filter-empty">Inga svängar matchar Min ingång ${displayMinEntryKt} kt. Sänk filtret för att visa fler.</td></tr>`;
      return;
    }
    return withVisibleGybes(() => originalRenderTable());
  };

  stepGybe = function (delta) {
    const visible = visibleGybes();
    if (!visible.length) return;
    let index = visible.findIndex((g) => g.id === selectedGybeId);
    if (index < 0) index = delta > 0 ? -1 : visible.length;
    index = Math.max(0, Math.min(visible.length - 1, index + delta));
    selectGybe(visible[index].id);
  };

  renderAll = function () {
    originalRenderAll();
    const visible = visibleGybes();
    if (!visible.length) {
      selectedGybeId = null;
      selectedPointIndex = null;
      $("detailPanel").classList.add("hidden");
      renderTrack();
      renderTable();
    } else if (!visible.some((g) => g.id === selectedGybeId)) {
      selectGybe(visible[0].id, false);
    }
    updateFilterCount();
  };

  function updateFilterCount() {
    const count = document.getElementById("entryFilterCount");
    if (!count) return;
    const shown = visibleGybes().length;
    const total = analysis?.gybes?.length ?? 0;
    count.textContent = analysis ? `${shown} / ${total} svängar` : "";
  }

  function applyFilter() {
    if (!analysis) return;
    const visible = visibleGybes();
    if (!visible.length) {
      selectedGybeId = null;
      selectedPointIndex = null;
      $("detailPanel").classList.add("hidden");
      renderTrack();
      renderTable();
    } else if (!visible.some((g) => g.id === selectedGybeId)) {
      navigationMode = "gybes";
      selectGybe(visible[0].id, false);
      renderTable();
    } else {
      renderTrack();
      renderTable();
    }
    updateFilterCount();
  }

  function installFilter() {
    const sessionPanel = $("trackSvg")?.closest("section.panel");
    const heading = sessionPanel?.querySelector(".section-heading");
    if (!heading || document.getElementById("displayMinEntry")) return;

    const control = document.createElement("div");
    control.className = "entry-filter";
    control.innerHTML = `
      <label for="displayMinEntry">Min ingång <strong id="entryFilterValue">0 kt</strong></label>
      <input id="displayMinEntry" type="range" min="0" max="35" step="1" value="0" aria-label="Minsta ingångsfart som visas">
      <span id="entryFilterCount" class="entry-filter-count"></span>`;
    heading.appendChild(control);

    const style = document.createElement("style");
    style.textContent = `
      .entry-filter{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-left:auto;font-size:13px;white-space:nowrap}
      .entry-filter label{color:var(--muted);display:flex;gap:5px;align-items:center}
      .entry-filter strong{color:var(--text)}
      .entry-filter input[type=range]{width:150px;accent-color:#f3a712;cursor:pointer}
      .entry-filter-count{color:var(--muted);min-width:82px;text-align:right}
      .filter-empty{text-align:center;padding:24px!important;color:var(--muted)}
      @media(max-width:760px){.entry-filter{width:100%;margin-left:0}.entry-filter input[type=range]{flex:1;min-width:130px}}
    `;
    document.head.appendChild(style);

    const input = document.getElementById("displayMinEntry");
    input.addEventListener("input", () => {
      displayMinEntryKt = Number(input.value) || 0;
      document.getElementById("entryFilterValue").textContent = `${displayMinEntryKt} kt`;
      applyFilter();
    });
    updateFilterCount();
  }

  installFilter();
})();
