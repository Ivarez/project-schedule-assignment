/* Lógica interactiva y auditoría visual — Asignación de Horarios Estudiantiles (PUJ) */

const state = {
  scenarios: [],
  currentScenario: null,
  instance: null,
  buildingsById: {},
  results: {},
  activeAlgo: "hybrid",
  activeStudent: null,
};

const $ = (id) => document.getElementById(id);

function getWeights() {
  return {
    w1_priority: parseFloat($("w1").value),
    w2_empathy: parseFloat($("w2").value),
    w3_planning: parseFloat($("w3").value),
    w4_social: parseFloat($("w4").value),
    w5_logistics: parseFloat($("w5").value),
  };
}

function updateSliderFill(el) {
  const min = parseFloat(el.min) || 0;
  const max = parseFloat(el.max) || 8;
  const val = parseFloat(el.value) || 0;
  const pct = ((val - min) / (max - min)) * 100;
  if (el.style && typeof el.style.setProperty === "function") {
    el.style.setProperty("--pct", pct.toFixed(1) + "%");
  }
}

function setSlidersFromWeights(w) {
  if (!w) return;
  const pairs = [
    ["w1", w.w1_priority],
    ["w2", w.w2_empathy],
    ["w3", w.w3_planning],
    ["w4", w.w4_social],
    ["w5", w.w5_logistics],
  ];
  pairs.forEach(([id, val]) => {
    if (typeof val === "number" && !Number.isNaN(val)) {
      const el = $(id);
      el.value = val;
      $("val-" + id).textContent = val.toFixed(1);
      updateSliderFill(el);
    }
  });
}

function bindWeightSliders() {
  ["w1", "w2", "w3", "w4", "w5"].forEach((id) => {
    const el = $(id);
    const lbl = $("val-" + id);
    updateSliderFill(el);
    el.addEventListener("input", () => {
      lbl.textContent = parseFloat(el.value).toFixed(1);
      updateSliderFill(el);
    });
  });
}

function indexBuildings(locations) {
  const map = {};
  if (!locations || !locations.buildings) return map;
  const list = Array.isArray(locations.buildings)
    ? locations.buildings
    : Object.values(locations.buildings);
  list.forEach((b) => {
    if (b && b.id) map[b.id] = b;
  });
  return map;
}

async function fetchScenarios() {
  const res = await fetch("/api/scenarios");
  const data = await res.json();
  state.scenarios = data.scenarios || [];
  const sel = $("scenario-select");
  sel.innerHTML = "";
  state.scenarios.forEach((sc) => {
    const opt = document.createElement("option");
    opt.value = sc.name;
    opt.textContent = `${sc.name} — ${sc.stats.students} est. · ${sc.stats.courses} materias · ${sc.stats.sections} secciones`;
    sel.appendChild(opt);
  });
  if (state.scenarios.length > 0) {
    await loadScenario(state.scenarios[0].name);
  }
}

async function loadScenario(name) {
  state.currentScenario = name;
  const res = await fetch(`/api/scenario/${encodeURIComponent(name)}`);
  const data = await res.json();
  state.instance = data.instance;
  state.buildingsById = indexBuildings(state.instance.locations);

  $("scenario-desc").textContent = state.instance.description;
  $("include-exact").checked = state.instance.stats.students <= 10;
  setSlidersFromWeights(state.instance.default_weights);

  const st = state.instance.stats;
  $("instance-metrics").textContent =
    `${st.students} estudiantes · ${st.courses} materias · ${st.sections} secciones · ${st.time_slots} franjas · ${st.buildings} edificios · ${st.social_links} vínculos`;

  const stSel = $("student-select");
  stSel.innerHTML = "";
  const eids = Object.keys(state.instance.students).sort();
  eids.forEach((eid) => {
    const s = state.instance.students[eid];
    const opt = document.createElement("option");
    opt.value = eid;
    opt.textContent = `${s.name} (${eid} · ${s.requested_courses.length} materias)`;
    stSel.appendChild(opt);
  });
  state.activeStudent = eids[0] || null;

  await runSolve();
}

async function runSolve() {
  const btn = $("btn-solve");
  btn.disabled = true;
  btn.textContent = "Ejecutando...";
  try {
    const res = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario: state.currentScenario,
        weights: getWeights(),
        include_exact: $("include-exact").checked,
        exact_time_limit: 2.0,
      }),
    });
    const data = await res.json();
    state.results = data.results || {};
    if (!state.results[state.activeAlgo]) {
      state.activeAlgo = state.results.hybrid ? "hybrid" : Object.keys(state.results)[0];
    }
    renderAll();
  } finally {
    btn.disabled = false;
    btn.textContent = "Ejecutar algoritmos";
  }
}

async function generateCustomScenario() {
  const btn = $("btn-generate");
  btn.disabled = true;
  btn.textContent = "Generando...";
  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        num_students: parseInt($("gen-students").value, 10),
        num_courses: parseInt($("gen-courses").value, 10),
        seed: parseInt($("gen-seed").value, 10),
        stress_conflicts: $("gen-stress").checked,
      }),
    });
    const data = await res.json();
    if (data.error) {
      alert("Error al generar escenario: " + data.error);
      return;
    }
    const inst = data.instance;
    const sel = $("scenario-select");
    const opt = document.createElement("option");
    opt.value = inst.name;
    opt.textContent = `${inst.name} — ${inst.stats.students} est. · ${inst.stats.courses} materias · ${inst.stats.sections} secciones`;
    sel.appendChild(opt);
    sel.value = inst.name;
    $("custom-gen-box").classList.add("hidden");
    await loadScenario(inst.name);
  } finally {
    btn.disabled = false;
    btn.textContent = "Crear y resolver";
  }
}

function renderAll() {
  renderComparisonTable();
  renderBreakdownTable();
  renderStudentSchedule();
  renderOccupancyTable();
  renderCampusGraph();
}

function formatInstrumentation(key, meta) {
  if (!meta) return "—";
  if (key === "greedy") {
    return `eval=${meta.evaluations ?? "—"}`;
  }
  if (key === "hybrid") {
    const mv = meta.moves || {};
    return `iter=${meta.iterations} · vec=${meta.neighbors_evaluated} · rel=${mv.relocates || 0}, swp=${mv.swaps || 0}, ins=${mv.inserts || 0}`;
  }
  if (key === "exact") {
    const tag = meta.optimal ? "ÓPTIMO" : "LÍMITE_T";
    return `${tag} · nodos=${meta.nodes_explored} · podas=${meta.pruned_by_bound}`;
  }
  return "—";
}

function renderComparisonTable() {
  const tbody = $("comparison-tbody");
  tbody.innerHTML = "";

  const greedyZ = state.results.greedy ? state.results.greedy.evaluation.z_score : null;
  const exactRes = state.results.exact;
  const exactOptZ = exactRes && exactRes.metadata && exactRes.metadata.optimal
    ? exactRes.evaluation.z_score
    : null;

  Object.entries(state.results).forEach(([key, res]) => {
    const ev = res.evaluation;
    const tr = document.createElement("tr");
    tr.className = "comp-row" + (key === state.activeAlgo ? " selected" : "");
    tr.onclick = () => {
      state.activeAlgo = key;
      renderAll();
    };

    let vsGreedy = "base";
    if (key !== "greedy" && greedyZ !== null && greedyZ !== 0) {
      const pct = ((ev.z_score - greedyZ) / Math.abs(greedyZ)) * 100;
      vsGreedy = `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
    }

    let gapStr = "—";
    if (key === "exact") {
      gapStr = res.metadata.optimal ? "0.00% (Z*)" : "sin cert.";
    } else if (exactOptZ !== null && exactOptZ !== 0) {
      const gap = ((exactOptZ - ev.z_score) / Math.abs(exactOptZ)) * 100;
      gapStr = `${Math.max(0, gap).toFixed(2)}%`;
    }

    tr.innerHTML = `
      <td style="text-align:center;"><input type="radio" class="algo-radio" name="algo-radio" ${key === state.activeAlgo ? "checked" : ""} aria-label="Seleccionar ${res.algorithm}" /></td>
      <td><strong>${res.algorithm}</strong></td>
      <td><span class="${ev.valid ? "status-ok" : "status-err"}">${ev.valid ? "Válido (0 viol.)" : `Error (${ev.violations.length})`}</span></td>
      <td class="num"><strong>${ev.z_score.toFixed(2)}</strong></td>
      <td class="num">${vsGreedy}</td>
      <td class="num">${gapStr}</td>
      <td class="num">${ev.assigned_count}/${ev.requested_count} (${(ev.assignment_rate * 100).toFixed(1)}%)</td>
      <td class="num">${ev.social_matches}/${ev.total_social_links}</td>
      <td class="num">${ev.raw.logistics.toFixed(1)} min</td>
      <td class="mono" style="font-size:12px;">${formatInstrumentation(key, res.metadata)}</td>
      <td class="num">${res.runtime_ms.toFixed(2)} ms</td>
    `;
    tbody.appendChild(tr);
  });

  const active = state.results[state.activeAlgo];
  const convBox = $("convergence-line");
  if (active && state.activeAlgo === "hybrid" && active.metadata.convergence_history) {
    const hist = active.metadata.convergence_history;
    const shown = hist.length > 10 ? [...hist.slice(0, 6), "...", hist[hist.length - 1]] : hist;
    convBox.innerHTML =
      `<strong>Convergencia de la Búsqueda Local</strong> (semilla inicial: ${active.metadata.best_seed}, mejora <span class="mono">${active.metadata.improvement_z >= 0 ? "+" : ""}${active.metadata.improvement_z}</span>): <span class="mono">Z = [ ${shown.join(" → ")} ]</span>`;
  } else if (active && state.activeAlgo === "exact") {
    convBox.innerHTML =
      `<strong>Branch &amp; Bound:</strong> ${active.metadata.optimal ? "Óptimo global certificado Z*" : "Límite de tiempo alcanzado (mejor solución hallada)"} · <span class="mono">nodos=${active.metadata.nodes_explored} · podas=${active.metadata.pruned_by_bound}</span>`;
  } else if (active) {
    convBox.innerHTML =
      `<strong>Voraz Constructivo:</strong> asigna por orden de prioridad y escasez · <span class="mono">eval=${active.metadata.evaluations} · ${active.metadata.complexity}</span>`;
  } else {
    convBox.textContent = "";
  }
}

function renderBreakdownTable() {
  const res = state.results[state.activeAlgo];
  if (!res) return;
  const ev = res.evaluation;
  const w = getWeights();

  const rows = [
    {
      name: "Prioridad académica",
      unit: "Puntaje [1–10]",
      weight: `+${w.w1_priority.toFixed(1)}`,
      raw: ev.raw.priority,
      weighted: ev.weighted.priority,
    },
    {
      name: "Empatía con profesor",
      unit: "Afinidad [0–1]",
      weight: `+${w.w2_empathy.toFixed(1)}`,
      raw: ev.raw.empathy,
      weighted: ev.weighted.empathy,
    },
    {
      name: "Planificación personal",
      unit: "Bloques [−1 a +1]",
      weight: `+${w.w3_planning.toFixed(1)}`,
      raw: ev.raw.planning,
      weighted: ev.weighted.planning,
    },
    {
      name: "Vínculos sociales",
      unit: "Vínculos [0–1]",
      weight: `+${w.w4_social.toFixed(1)}`,
      raw: ev.raw.social,
      weighted: ev.weighted.social,
    },
    {
      name: "Desplazamiento logístico",
      unit: "Minutos de caminata",
      weight: `−${w.w5_logistics.toFixed(1)}`,
      raw: ev.raw.logistics,
      weighted: -ev.weighted.logistics,
    },
  ];

  const sumAbs = rows.reduce((acc, r) => acc + Math.abs(r.weighted), 0) || 1;
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.weighted)));

  const tbody = $("breakdown-tbody");
  tbody.innerHTML = "";

  rows.forEach((r) => {
    const pctTotal = (Math.abs(r.weighted) / sumAbs) * 100;
    const barPct = Math.min(100, (Math.abs(r.weighted) / maxAbs) * 100);
    const isNeg = r.weighted < 0;

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${r.name}</strong></td>
      <td style="color:#374151;">${r.unit}</td>
      <td class="num">${r.weight}</td>
      <td class="num">${r.raw.toFixed(2)}</td>
      <td class="num" style="font-weight:700;color:${isNeg ? "#b91c1c" : "#111827"};">${r.weighted >= 0 ? "+" : ""}${r.weighted.toFixed(2)}</td>
      <td class="num">${pctTotal.toFixed(1)}%</td>
      <td>
        <div class="div-chart" title="${r.weighted.toFixed(2)}">
          <div class="div-left">${isNeg ? `<div class="div-bar-neg" style="width:${barPct}%;"></div>` : ""}</div>
          <div class="div-axis"></div>
          <div class="div-right">${!isNeg ? `<div class="div-bar-pos" style="width:${barPct}%;"></div>` : ""}</div>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  const trTot = document.createElement("tr");
  trTot.style.background = "#f8f9fa";
  trTot.innerHTML = `
    <td colspan="4"><strong>Total Función Objetivo Z(X)</strong></td>
    <td class="num" style="font-weight:800;color:#003366;">${ev.z_score.toFixed(2)}</td>
    <td class="num">100.0%</td>
    <td class="mono" style="font-size:12px;color:#374151;">Escala eje 0: ±${maxAbs.toFixed(1)}</td>
  `;
  tbody.appendChild(trTot);
}

function renderStudentSchedule() {
  const res = state.results[state.activeAlgo];
  const inst = state.instance;
  const eid = state.activeStudent;
  if (!res || !inst || !eid) return;

  const st = inst.students[eid];
  const det = res.evaluation.student_details[eid];
  if (!st || !det) return;

  const unassignedNames = det.unassigned_courses.map((c) => inst.courses[c]?.name || c);
  $("student-metrics-bar").innerHTML = `
    <span><strong>${st.name}</strong> (${eid})</span>
    <span>Materias asignadas: <strong class="mono">${det.assigned_courses.length}/${st.requested_courses.length}</strong></span>
    <span>Prioridad: <strong class="mono">${det.priority}</strong></span>
    <span>Empatía: <strong class="mono">${det.empathy}</strong></span>
    <span>Planificación: <strong class="mono">${det.planning}</strong></span>
    <span>Coincidencias sociales: <strong class="mono">${det.social_friends.length}</strong></span>
    <span>Caminata total: <strong class="mono">${det.logistics} min</strong></span>
    ${unassignedNames.length ? `<span class="unassigned-alert">Sin asignar: ${unassignedNames.join(", ")}</span>` : ""}
  `;

  const daysMap = new Map();
  const blocksMap = new Map();
  const gridSlots = {};
  Object.values(inst.time_slots).forEach((ts) => {
    daysMap.set(ts.day_index, ts.day);
    blocksMap.set(ts.block_index, ts.label);
    gridSlots[`${ts.day_index}-${ts.block_index}`] = ts;
  });

  const dayIndices = [...daysMap.keys()].sort((a, b) => a - b);
  const blockIndices = [...blocksMap.keys()].sort((a, b) => a - b);

  const slotToSec = {};
  det.assigned_sections.forEach((sid) => {
    const sec = inst.sections[sid];
    if (!sec) return;
    sec.schedule.forEach((tid) => {
      slotToSec[tid] = sec;
    });
  });

  const transByToSlot = {};
  det.transitions.forEach((tr) => {
    transByToSlot[tr.to_slot] = tr;
  });

  const friendsBySec = {};
  det.social_friends.forEach((fr) => {
    friendsBySec[fr.section_id] = friendsBySec[fr.section_id] || [];
    friendsBySec[fr.section_id].push(fr.friend_name.split(" ")[0]);
  });

  let html = `<thead><tr><th class="time-head">Franja</th>${dayIndices.map((d) => `<th>${daysMap.get(d)}</th>`).join("")}</tr></thead><tbody>`;
  blockIndices.forEach((b) => {
    html += `<tr><td class="time-col">${blocksMap.get(b)}</td>`;
    dayIndices.forEach((d) => {
      const ts = gridSlots[`${d}-${b}`];
      if (!ts) {
        html += `<td style="background:#f3f4f6;"></td>`;
        return;
      }
      const pref = st.time_preferences[ts.id] ?? 0;
      const prefCls = pref > 0 ? "pref-pos" : pref < 0 ? "pref-neg" : "pref-neu";
      const sec = slotToSec[ts.id];

      if (!sec) {
        html += `<td class="${prefCls}"></td>`;
        return;
      }

      const course = inst.courses[sec.course_id] || { name: sec.course_id };
      const bId = sec.rooms[ts.id];
      const bldg = state.buildingsById[bId] || { short_name: bId, id: bId };
      const prio = st.priorities[sec.course_id] ?? 0;
      const emp = st.empathy[sec.id] ?? 0;
      const friends = friendsBySec[sec.id] || [];
      const tr = transByToSlot[ts.id];
      const fromBldg = tr ? (state.buildingsById[tr.from_building] || { short_name: tr.from_building }) : null;

      html += `<td class="${prefCls}">
        <div class="slot-class">
          <div class="slot-course">${course.name}</div>
          <div class="slot-meta">${sec.id} · ${sec.professor} · ${bldg.short_name}</div>
          <div class="slot-nums">Prioridad <span class="mono">${prio}</span> · Empatía <span class="mono">${emp.toFixed(2)}</span></div>
          ${friends.length ? `<div class="slot-social">Con: ${friends.join(", ")}</div>` : ""}
          ${tr ? `<div class="slot-walk">Caminata: ${fromBldg.short_name} → ${bldg.short_name} (<span class="mono">${tr.distance} min</span>)</div>` : ""}
        </div>
      </td>`;
    });
    html += `</tr>`;
  });
  html += `</tbody>`;
  $("timetable").innerHTML = html;
}

function renderOccupancyTable() {
  const res = state.results[state.activeAlgo];
  const inst = state.instance;
  if (!res || !inst) return;

  const tbody = $("occupancy-tbody");
  tbody.innerHTML = "";
  const sids = Object.keys(inst.sections).sort();
  let okCount = 0;

  sids.forEach((sid) => {
    const sec = inst.sections[sid];
    const occ = res.evaluation.section_occupancy[sid] || 0;
    const cap = sec.capacity;
    const pct = Math.min(100, (occ / cap) * 100);
    const exceeded = occ > cap;
    if (!exceeded) okCount += 1;

    const statusCls = exceeded ? "status-err" : occ === cap ? "status-warn" : "status-ok";
    const statusTxt = exceeded ? "Excedido" : occ === cap ? "Lleno" : "OK";
    const barColor = exceeded ? "#b91c1c" : occ === cap ? "#b8860b" : "#003366";

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="mono"><strong>${sid}</strong></td>
      <td>${inst.courses[sec.course_id]?.name || sec.course_id}</td>
      <td class="num">${occ} / ${cap} (${pct.toFixed(0)}%)</td>
      <td>
        <div class="occ-track"><div class="occ-fill" style="width:${pct}%;background:${barColor};"></div></div>
      </td>
      <td><span class="${statusCls}">${statusTxt}</span></td>
    `;
    tbody.appendChild(tr);
  });

  const summary = $("occupancy-summary");
  summary.className = "status-summary " + (okCount === sids.length ? "status-ok" : "status-err");
  summary.textContent = `Restricción de cupos: ${okCount}/${sids.length} cumplidas`;
}

function renderCampusGraph() {
  const res = state.results[state.activeAlgo];
  const inst = state.instance;
  const eid = state.activeStudent;
  const wrap = $("campus-graph-wrap");
  if (!res || !inst || !eid) return;

  const buildings = Object.values(state.buildingsById);
  const det = res.evaluation.student_details[eid];
  const transitions = det ? det.transitions : [];
  const activeEdges = new Set(transitions.map((t) => [t.from_building, t.to_building].sort().join("-")));

  const W = 560;
  const H = 330;
  const sx = (x) => 52 + (x / 100) * (W - 104);
  const sy = (y) => 36 + (y / 100) * (H - 78);

  let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="330" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Mapa de edificios y tiempos de caminata en el campus PUJ">`;

  // 1. Dibujar primero todas las aristas inactivas del campus con sus tiempos de caminata
  for (let i = 0; i < buildings.length; i++) {
    for (let j = i + 1; j < buildings.length; j++) {
      const b1 = buildings[i];
      const b2 = buildings[j];
      const key = [b1.id, b2.id].sort().join("-");
      if (activeEdges.has(key)) continue;
      const dist = inst.locations.distances[b1.id]?.[b2.id] ?? 0;
      const x1 = sx(b1.x), y1 = sy(b1.y), x2 = sx(b2.x), y2 = sy(b2.y);
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2;

      svg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#d1d5db" stroke-width="1.1" />`;
      svg += `<rect x="${mx - 17}" y="${my - 7}" width="34" height="13" rx="2" fill="#ffffff" fill-opacity="0.88" />`;
      svg += `<text x="${mx}" y="${my + 3}" text-anchor="middle" font-family="ui-monospace, Consolas, monospace" font-size="9" fill="#6b7280">${dist}m</text>`;
    }
  }

  // 2. Dibujar encima las rutas activas del estudiante resaltadas en dorado
  for (let i = 0; i < buildings.length; i++) {
    for (let j = i + 1; j < buildings.length; j++) {
      const b1 = buildings[i];
      const b2 = buildings[j];
      const key = [b1.id, b2.id].sort().join("-");
      if (!activeEdges.has(key)) continue;
      const dist = inst.locations.distances[b1.id]?.[b2.id] ?? 0;
      const x1 = sx(b1.x), y1 = sy(b1.y), x2 = sx(b2.x), y2 = sy(b2.y);
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2;

      svg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#b8860b" stroke-width="3" />`;
      svg += `<rect x="${mx - 23}" y="${my - 9}" width="46" height="17" rx="2" fill="#fffbeb" stroke="#b8860b" stroke-width="1.1" />`;
      svg += `<text x="${mx}" y="${my + 3}" text-anchor="middle" font-family="ui-monospace, Consolas, monospace" font-size="10.5" font-weight="700" fill="#78350f">${dist} min</text>`;
    }
  }

  // 3. Nodos de edificios
  buildings.forEach((b) => {
    const cx = sx(b.x);
    const cy = sy(b.y);
    svg += `<circle cx="${cx}" cy="${cy}" r="16" fill="#003366" stroke="#ffffff" stroke-width="2" />`;
    svg += `<text x="${cx}" y="${cy + 4}" text-anchor="middle" font-family="ui-monospace, Consolas, monospace" font-size="10" font-weight="700" fill="#ffffff">${b.id}</text>`;
    svg += `<text x="${cx}" y="${cy + 29}" text-anchor="middle" font-size="11.5" font-weight="600" fill="#111827">${b.short_name}</text>`;
  });

  svg += `</svg>`;
  wrap.innerHTML = svg;

  $("graph-note").textContent = transitions.length > 0
    ? `${transitions.length} recorrido(s) consecutivo(s) resaltado(s) en dorado (total ${det.logistics} min).`
    : `Este estudiante no tiene clases consecutivas en edificios distintos (0.0 min).`;
}

document.addEventListener("DOMContentLoaded", () => {
  bindWeightSliders();
  $("scenario-select").addEventListener("change", (e) => loadScenario(e.target.value));
  $("student-select").addEventListener("change", (e) => {
    state.activeStudent = e.target.value;
    renderStudentSchedule();
    renderCampusGraph();
  });
  $("btn-solve").addEventListener("click", runSolve);
  $("btn-toggle-gen").addEventListener("click", () => {
    $("custom-gen-box").classList.toggle("hidden");
  });
  $("btn-generate").addEventListener("click", generateCustomScenario);
  fetchScenarios();
});
