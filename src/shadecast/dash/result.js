/* The measured results page. Everything here is read from results.json, which the bundle
   build writes from the scored plans of every tile with physics and from the experiment
   files. No number on the page is typed in. */

const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt = (n, d = 0) => n === null || n === undefined || !isFinite(n) ? "–"
  : Number(n).toLocaleString(undefined, {minimumFractionDigits: d, maximumFractionDigits: d});
const pct = (x, d = 1) => x === null || x === undefined ? "–" : `${(x * 100).toFixed(d)}%`;
const money = m => m === null || m === undefined ? "–" : `$${fmt(m, m < 1 ? 2 : 1)}M`;

/* One colour per arrangement, fixed, never cycled: an arrangement keeps its hue on every chart. */
const COLOUR = {clustered: "var(--s1)", scattered: "var(--s2)", corridor: "var(--s3)"};
const ORDER = ["clustered", "scattered", "corridor"];
const LABEL = {clustered: "clustered, what greedy produces", scattered: "scattered", corridor: "corridor, along streets"};

async function main(){
  let data;
  try {
    const response = await fetch("results.json");
    if (!response.ok) throw new Error(String(response.status));
    data = await response.json();
  } catch (error) {
    $("lede").textContent = "No results.json beside this page yet. Run sdc dash build after a tile has physics.";
    $("lede").className = "lede empty";
    return;
  }
  renderLead(data);
  renderFacets(data);
  renderArrangement(data);
  renderRanking(data);
  renderMeasures(data);
  renderPlans(data);
  renderFooter(data);
}

function renderLead(data){
  const t = data.totals, a = data.arrangement;
  const names = data.cities.map(c => c.name).join(", ");
  const arranged = a.cities_compared
    ? ` In ${a.scattered_wins} of ${a.cities_compared} cities the scattered plan delivered more cooling per dollar than the clustered plan at the same coverage, by ${a.ratio_min} to ${a.ratio_max} times.`
    : "";
  $("lede").textContent =
    `Every plan below was simulated with real physics across ${t.cities} ${t.cities === 1 ? "city" : "cities"}.${arranged}`;
  $("meta").innerHTML = [
    ["As of", data.as_of],
    ["Plans", `${fmt(t.plans)}, all engine-simulated`],
    ["Cities", names],
    ["Budgets", t.budget_min_m === null ? "–" : `${money(t.budget_min_m)} to ${money(t.budget_max_m)}`],
    ["Physics", "SOLWEIG at 1 m"],
    ["Threshold", `${data.threshold_C} C`],
  ].map(([k, v]) => `<span>${esc(k)} <b>${esc(v)}</b></span>`).join("");
}

/* ---------- the trade-off facets ------------------------------------------------------ */

function renderFacets(data){
  const host = $("facets");
  host.innerHTML = data.cities.map(facet).join("");
  $("legend").innerHTML = ORDER.map(a =>
    `<span><i style="background:${COLOUR[a]}"></i>${esc(LABEL[a])}</span>`).join("");
}

function facet(city){
  const plans = city.plans;
  const W = 290, H = 250, L = 46, R = 14, T = 12, B = 34;
  const xmax = Math.max(0.1, ...plans.map(p => p.exposure_drop)) * 1.08;
  const ymax = Math.max(1, ...plans.map(p => p.people)) * 1.08;
  const x = v => L + v / xmax * (W - L - R);
  const y = v => H - B - v / ymax * (H - T - B);
  const grid = [];
  for (let i = 0; i <= 3; i++) {
    const gy = y(ymax / 3 * i), gx = x(xmax / 3 * i);
    grid.push(`<line x1="${L}" y1="${gy}" x2="${W - R}" y2="${gy}" class="grid"/>`);
    grid.push(`<text x="${L - 6}" y="${gy + 3}" class="ax" text-anchor="end">${thousands(ymax / 3 * i)}</text>`);
    grid.push(`<text x="${gx}" y="${H - B + 14}" class="ax" text-anchor="middle">${(xmax / 3 * i).toFixed(1)}</text>`);
  }
  const series = ORDER.map(a => {
    const pts = plans.filter(p => p.arrangement === a).sort((p, q) => p.coverage - q.coverage);
    if (!pts.length) return "";
    const path = pts.map((p, i) => `${i ? "L" : "M"}${x(p.exposure_drop).toFixed(1)},${y(p.people).toFixed(1)}`).join(" ");
    const dots = pts.map(p =>
      `<circle class="dot" cx="${x(p.exposure_drop).toFixed(1)}" cy="${y(p.people).toFixed(1)}" r="4" fill="${COLOUR[a]}"><title>${esc(a)} ${pct(p.coverage)} coverage, ${money(p.cost_m)}: ${p.exposure_drop.toFixed(2)} C, ${fmt(p.people)} people</title></circle>`).join("");
    return `<path class="series" d="${path}" stroke="${COLOUR[a]}"/>${dots}`;
  }).join("");
  const f = city.facts;
  const facts = [pct(f.canopy) + " canopy", pct(f.built_fraction, 0) + " built", f.tier ? `tier ${f.tier}` : ""].filter(Boolean).join(" · ");
  return `<div class="facet"><h4>${esc(city.name)}</h4><p class="sub">${esc(facts)}</p>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(city.name)}: exposure drop against people moved below the threshold, by arrangement">
      ${grid.join("")}${series}
      <text x="${(L + W - R) / 2}" y="${H - 4}" class="ax" text-anchor="middle">exposure drop, C</text>
    </svg></div>`;
}

function thousands(v){ return v >= 1000 ? `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k` : v.toFixed(0); }

/* ---------- arrangement at matched coverage ------------------------------------------- */

function renderArrangement(data){
  const rows = data.cities.filter(c => c.matched);
  const table = $("arrangement-table");
  if (!rows.length) { table.innerHTML = `<tr><td class="empty">No city has both a clustered and a scattered plan yet.</td></tr>`; $("arrangement-verdict").textContent = ""; return; }
  table.innerHTML = `<thead><tr><th>City</th><th>Matched coverage</th><th class="n">Clustered per $1k</th><th class="n">Scattered per $1k</th><th class="n">Scattered over clustered</th></tr></thead><tbody>` +
    rows.map(c => `<tr><td class="city">${esc(c.name)}</td><td>${pct(c.matched.clustered.coverage)} against ${pct(c.matched.scattered.coverage)}, ${money(c.matched.clustered.cost_m)}</td><td class="n">${fmt(c.matched.clustered.efficiency, 1)}</td><td class="n">${fmt(c.matched.scattered.efficiency, 1)}</td><td class="n">${c.matched.ratio === null ? "–" : c.matched.ratio.toFixed(1) + "x"}</td></tr>`).join("") + "</tbody>";
  const a = data.arrangement;
  const every = a.scattered_wins === a.cities_compared ? "in every city compared" : `in ${a.scattered_wins} of ${a.cities_compared} cities`;
  $("arrangement-verdict").textContent = `Same trees, same money: scattered planting delivered more cooling per dollar than clustered planting ${every}, by ${a.ratio_min} to ${a.ratio_max} times.`;
}

/* ---------- which city buys the most ------------------------------------------------- */

function renderRanking(data){
  const r = data.ranking;
  const table = $("ranking-table");
  if (!r.rows.length) { table.innerHTML = `<tr><td class="empty">No scored plans yet.</td></tr>`; return; }
  table.innerHTML = `<thead><tr><th>City</th><th>Regime</th><th class="n">Clustered per $1k</th><th class="n">Scattered per $1k</th><th class="n">Gain from arranging</th></tr></thead><tbody>` +
    r.rows.map(row => `<tr><td class="city">${esc(row.name)}</td><td>${pct(row.canopy, 0)} canopy, ${pct(row.built_fraction, 0)} built</td><td class="n">${fmt(row.clustered_per_1k, 1)}</td><td class="n">${fmt(row.scattered_per_1k, 1)}</td><td class="n">${row.gain === null ? "–" : row.gain.toFixed(1) + "x"}</td></tr>`).join("") + "</tbody>";
  const top = r.rows[0], bottom = r.rows[r.rows.length - 1];
  $("ranking-verdict").textContent = r.spread && r.rows.length > 1
    ? `${top.name} returns ${r.spread}x more cooling per dollar than ${bottom.name}, measured on the median scattered plan of each. Per $1k is excess degree-hours above the threshold removed per thousand dollars over a 20 year horizon.`
    : "One city so far; the comparison needs a second.";
}

/* ---------- which measure buys the most ---------------------------------------------- */

function renderMeasures(data){
  const rows = Array.isArray(data.factorial) ? data.factorial : [];
  const table = $("measures-table");
  if (!rows.length) { table.innerHTML = `<tr><td class="empty">The factorial experiment has not run on any tile with physics yet.</td></tr>`; return; }
  const sorted = [...rows].sort((a, b) => a.city.localeCompare(b.city) || a.budget_usd - b.budget_usd || a.kind.localeCompare(b.kind));
  table.innerHTML = `<thead><tr><th>City</th><th>Measure</th><th class="n">Budget</th><th class="n">Units</th><th class="n">Exposure drop, C</th><th class="n">People below threshold</th><th class="n">Per $1k</th></tr></thead><tbody>` +
    sorted.map(r => `<tr><td class="city">${esc(cap(r.city))}</td><td>${esc(r.kind)}</td><td class="n">${money(r.budget_usd / 1e6)}</td><td class="n">${fmt(r.units)}</td><td class="n">${fmt(r.exposure_drop_C, 3)}</td><td class="n">${fmt(r.people)}</td><td class="n">${fmt(r.efficiency, 1)}</td></tr>`).join("") + "</tbody>";
}

function cap(s){ return s ? s[0].toUpperCase() + s.slice(1) : s; }

/* ---------- every plan ---------------------------------------------------------------- */

function renderPlans(data){
  const table = $("plans-table");
  const rows = [];
  for (const city of data.cities) {
    const plans = [...city.plans].sort((a, b) => ORDER.indexOf(a.arrangement) - ORDER.indexOf(b.arrangement) || a.coverage - b.coverage);
    plans.forEach((p, i) => rows.push(`<tr>${i === 0 ? `<td class="city" rowspan="${plans.length}">${esc(city.name)}</td>` : ""}<td>${esc(p.arrangement)}</td><td class="n">${pct(p.coverage)}</td><td class="n">${money(p.cost_m)}</td><td class="n">${fmt(p.exposure_drop, 4)}</td><td class="n">${fmt(p.people)}</td><td class="n">${fmt(p.efficiency, 2)}</td></tr>`));
  }
  table.innerHTML = `<thead><tr><th>City</th><th>Arrangement</th><th class="n">Coverage</th><th class="n">Cost</th><th class="n">Exposure drop, C</th><th class="n">People below threshold</th><th class="n">Per $1k</th></tr></thead><tbody>${rows.join("")}</tbody>`;
}

/* ---------- footer ---------------------------------------------------------------------- */

function renderFooter(data){
  const physics = data.cities.map(c => c.physics).filter(p => p && p.designs);
  const designs = physics.length ? [...new Set(physics.map(p => p.designs))].join(" or ") : "–";
  const minutes = physics.length ? `${fmt(Math.min(...physics.map(p => p.engine_minutes)))} to ${fmt(Math.max(...physics.map(p => p.engine_minutes)))} minutes of physics per tile` : "";
  $("footer").innerHTML = `Every number is a real SOLWEIG run at 1 m, not a surrogate. ${esc(designs)} designed experiments per tile${minutes ? ", " + esc(minutes) : ""}. Study areas are the densest tile of each urban centre unless chosen otherwise. Sparse probe designs are omitted from the charts: they exist to characterise the response kernel, not to be candidate plans. Built ${esc(data.as_of)} by <a href="https://github.com/deepsaia/shadecast">shadecast</a>.`;
}

main();
