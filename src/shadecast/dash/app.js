/* shadecast walkthrough: step-by-step render of the pipeline and what it found. */

const EXPLAIN = {
  assemble: [
    ["What a city bundle is",
     "Five raster layers covering one square kilometre at <em>one metre</em> per pixel, all snapped to the same grid: building heights, bare ground elevation, tree canopy height, land cover class, and an hourly weather file. The physics engine requires every layer to share an extent and a pixel size, so we guarantee that by construction rather than by hope."],
    ["Why credential-free matters",
     "Every source here is public and unauthenticated, so anyone can rebuild any city without an account, a quota, or a paid key. Credentials are needed at <em>build</em> time by nobody and at <em>use</em> time by nobody. That is what makes this a benchmark others can actually run rather than a result others must take on trust."],
    ["Design day",
     "One representative hot day drawn from reanalysis weather, which the whole simulation runs on. Using a real day rather than a monthly average keeps sun angles, air temperature and solar load physically consistent with each other."],
    ["Quality tier",
     "A label recording how good the inputs were for this city, because global open data is uneven. A result carries its tier so a weak-input city is never silently compared against a strong-input one."]
  ],
  simulate: [
    ["Mean radiant temperature, or Tmrt",
     "The single temperature of an imaginary uniform enclosure that would load a human body with the same radiant heat as the real surroundings do. It sums the sunlight striking you plus the infrared radiating off pavement, walls and sky. On an open sunny street it runs <em>15 to 25 °C above air temperature</em>; step into shade and it falls within seconds. This is the quantity a body actually feels."],
    ["Why not just air temperature",
     "Air temperature barely changes across a street. Planting a tree moves it by a few tenths of a degree, which is why shade looks almost worthless if you measure air. The same tree can drop Tmrt by <em>more than 20 °C</em> in its own shadow. Measuring the wrong variable is the fastest way to conclude that shade does not work."],
    ["SOLWEIG",
     "The radiation model that computes Tmrt. For every square metre and every hour it works out what that point can see of sun, sky, ground and building, then sums the energy arriving from each direction. We run it as a separate process so that its GPL licence stays outside this Apache-2.0 codebase."],
    ["Reading the map",
     "Colour is Tmrt on a single scale held fixed across all 24 hours, so the animation shows the city genuinely heating and cooling rather than rescaling itself. <em>Hover any pixel to read its actual temperature.</em>"]
  ],
  surrogate: [
    ["The problem",
     "One physics run takes about <em>160 seconds</em>. Searching even a few thousand candidate plans would take weeks of compute, so the search that actually matters is unaffordable if every candidate needs the engine."],
    ["Design of experiments",
     "Instead of simulating one plan per run, we scatter many small probes through a single run, spaced further apart than the distance over which one probe's cooling can reach. Because their effects never overlap, they can be read back as independent measurements: one engine call yields roughly <em>a hundred</em> observations instead of one."],
    ["The surrogate",
     "A convolutional network trained on those observations to predict the cooling field a plan produces, without running the physics. It answers in about half a second instead of 160."],
    ["Skill score, and why plain error would mislead",
     "Skill measures how much better a prediction is than predicting <em>no change at all</em>. Zero means no better than doing nothing; one means perfect. It matters because a cooling field is almost entirely zero, so a model that confidently predicts nothing everywhere earns a flattering low average error while being completely useless. Skill is the metric that refuses to reward that."],
    ["Transfer",
     "Whether a model trained on some cities can predict a city it has never seen. This is the difference between a tool that works anywhere and one that must be refitted per city."]
  ],
  factorial: [
    ["Full factorial",
     "Every combination of the things being varied, run in full: each intervention type, at each budget, in each city. Running the complete grid rather than a sample is what allows a claim that the ranking holds <em>everywhere</em>, instead of merely on average."],
    ["Efficiency",
     "Degree-hours of dangerous heat removed per <em>$1,000</em> spent. It counts only outdoor ground, because the model is a pedestrian model and its value over a rooftop is not a temperature anyone experiences, and it weights each place by how many people are near it."],
    ["Pre-registration",
     "The hypotheses, their predicted numbers, and the conditions that would prove them wrong, all committed to version control <em>before</em> the experiment ran. It removes the option of deciding afterwards which result was the one we meant to test. An earlier finding of ours was retracted for exactly that missing discipline."],
    ["What the two arms are",
     "<em>Trees</em> are living canopy: they cast shade and cool by evaporation, but take years to mature and need water. <em>Shade structures</em> are built canopies such as sails or pergolas: instant, maintenance-light, and far more expensive per square metre covered."]
  ],
  corridor: [
    ["The question",
     "A budget can cool the <em>hottest ground</em>, or it can cool the ground <em>people actually walk on</em>. Those are not the same places, and until you build both plans and simulate both, there is no way to know how far apart they are."],
    ["Walking network",
     "Every footway, path and street a person on foot may use, taken from OpenStreetMap and laid on the same grid as the heat. About 19 km of it inside one square kilometre."],
    ["How a walker is modelled",
     "People do not take the coolest possible route at any cost, nor the shortest regardless of sun. Each street is given a <em>perceived</em> length that grows with its heat, so a walker trades distance against exposure. Routes are chosen on perceived cost and then scored on the heat actually met along the route chosen, which keeps the choosing and the scoring honest about each other."],
    ["Corridor value",
     "For each street, the total trip heat carried along it: how many people-trips pass, multiplied by how hot it is where they pass. It is high where many unavoidable routes funnel through the same hot ground, and low where a street is hot but easy to walk around. An area average cannot tell those two apart; this is the whole reason for the objective."],
    ["Plan overlap",
     "The share of planted positions the two plans have in common. Near zero means the two objectives are choosing almost entirely different places, so the choice of objective is not a detail, it decides what gets built."],
    ["The honest caveat",
     "That corridor targeting wins on the corridor measure is partly definitional, since that is what it optimises. The findings that are <em>not</em> definitional are how little the two plans overlap, how large the gap is, and that in Ahmedabad the corridor plan wins on the area measure too."]
  ],
  plans: [
    ["Coverage",
     "The fraction of the square kilometre that receives an intervention. It is the simplest dial a planner has and it doubles as a stand-in for budget."],
    ["Arrangement",
     "How the same quantity of canopy is distributed: <em>clustered</em> into a few dense groves, or <em>scattered</em> evenly across the area. Same money, same total canopy, different geometry."],
    ["The trade-off",
     "Two reasonable objectives disagree. Spreading canopy lowers the <em>average</em> exposure across everyone, while concentrating it pulls more individual people below the dangerous threshold. There is no arrangement that wins both, so the benchmark reports both and refuses to collapse them into one score. Choosing between them is a political decision, not a modelling one."]
  ]
};

function why(items){
  return `<div class="why"><dl>${items.map(([t,d])=>`<div><dt>${t}</dt><dd>${d}</dd></div>`).join("")}</dl></div>`;
}

/* ------------------------------- charts (SVG, interactive) ---------------------------- */
function metChart(met, hour){
  const W=300,H=110,PL=30,PR=10,PT=10,PB=20;
  const air=met.map(m=>m.air_c), sol=met.map(m=>m.solar);
  const amin=Math.min(...air), amax=Math.max(...air), smax=Math.max(...sol,1);
  const X=h=>PL+(h/23)*(W-PL-PR);
  const YA=v=>PT+(1-(v-amin)/Math.max(amax-amin,1e-6))*(H-PT-PB);
  const YS=v=>PT+(1-v/smax)*(H-PT-PB);
  let s=`<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Air temperature and solar radiation through the design day">`;
  s+=`<polygon fill="var(--accent-wash)" points="${met.map(m=>`${X(m.hour).toFixed(1)},${YS(m.solar).toFixed(1)}`).join(" ")} ${X(23)},${H-PB} ${X(0)},${H-PB}"/>`;
  s+=`<polyline fill="none" stroke="var(--hot)" stroke-width="2" points="${met.map(m=>`${X(m.hour).toFixed(1)},${YA(m.air_c).toFixed(1)}`).join(" ")}"/>`;
  s+=`<line x1="${X(hour)}" y1="${PT}" x2="${X(hour)}" y2="${H-PB}" stroke="var(--ink-3)" stroke-width="1" stroke-dasharray="3 3"/>`;
  s+=`<text x="2" y="${PT+8}" font-size="8" fill="var(--ink-3)">${amax.toFixed(0)}°</text>`;
  s+=`<text x="2" y="${H-PB}" font-size="8" fill="var(--ink-3)">${amin.toFixed(0)}°</text>`;
  [0,6,12,18,23].forEach(h=>{s+=`<text x="${X(h)}" y="${H-6}" font-size="8" fill="var(--ink-3)" text-anchor="middle">${h}</text>`});
  return s+"</svg>";
}

function transferChart(t){
  if(!t || !t.length) return `<p class="sub">Transfer curve not yet computed.</p>`;
  const W=320,H=150,PL=42,PR=14,PT=14,PB=30;
  const xs=t.map(p=>p.cities), ys=t.map(p=>p.skill);
  const xmin=Math.min(...xs), xmax=Math.max(...xs,xs[0]+1);
  const ymin=0, ymax=Math.max(...ys)*1.25;
  const X=v=>PL+((v-xmin)/Math.max(xmax-xmin,1e-9))*(W-PL-PR);
  const Y=v=>PT+(1-(v-ymin)/(ymax-ymin))*(H-PT-PB);
  let s=`<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Skill against number of training cities">`;
  [0,.25,.5].forEach(g=>{ if(g<=ymax) s+=`<line x1="${PL}" y1="${Y(g)}" x2="${W-PR}" y2="${Y(g)}" stroke="var(--rule)" stroke-width="1"/><text x="${PL-5}" y="${Y(g)+3}" font-size="8" fill="var(--ink-3)" text-anchor="end">${g}</text>`;});
  s+=`<polyline fill="none" stroke="var(--accent)" stroke-width="2" points="${t.map(p=>`${X(p.cities)},${Y(p.skill)}`).join(" ")}"/>`;
  t.forEach(p=>{ s+=`<circle cx="${X(p.cities)}" cy="${Y(p.skill)}" r="4.5" fill="var(--accent)" stroke="var(--card)" stroke-width="2"><title>${p.cities} training ${p.cities===1?"city":"cities"}: skill ${p.skill}, mean error ${p.mae_C} °C</title></circle>`;
    s+=`<text x="${X(p.cities)}" y="${Y(p.skill)-10}" font-size="9" font-weight="600" fill="var(--ink)" text-anchor="middle">${p.skill}</text>`;
    s+=`<text x="${X(p.cities)}" y="${H-10}" font-size="8.5" fill="var(--ink-3)" text-anchor="middle">${p.cities}</text>`;});
  s+=`<text x="${(PL+W-PR)/2}" y="${H-1}" font-size="8" fill="var(--ink-3)" text-anchor="middle">training cities</text>`;
  return s+"</svg>";
}

function factorialChart(rows){
  const W=560,H=250,PL=48,PR=120,PT=16,PB=38;
  const budgets=[...new Set(rows.map(r=>r.budget_usd))].sort((a,b)=>a-b);
  const cities=[...new Set(rows.map(r=>r.city))].sort();
  const COL={ahmedabad:"var(--s1)",lagos:"var(--s2)",rio:"var(--s3)"};
  const emax=Math.max(...rows.map(r=>r.efficiency))*1.1;
  const X=i=>PL+(i/(budgets.length-1))*(W-PL-PR);
  const Y=v=>PT+(1-v/emax)*(H-PT-PB);
  let s=`<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Cooling efficiency against budget, by city and intervention type">`;
  [0,40,80,120].forEach(g=>{ if(g<=emax) s+=`<line x1="${PL}" y1="${Y(g)}" x2="${W-PR}" y2="${Y(g)}" stroke="var(--rule)"/><text x="${PL-5}" y="${Y(g)+3}" font-size="8.5" fill="var(--ink-3)" text-anchor="end">${g}</text>`;});
  budgets.forEach((b,i)=>{ s+=`<text x="${X(i)}" y="${H-16}" font-size="9" fill="var(--ink-2)" text-anchor="middle">$${(b/1e6).toFixed(1)}M</text>`;});
  cities.forEach(city=>["tree","shade"].forEach(kind=>{
    const pts=budgets.map((b,i)=>{const r=rows.find(r=>r.city===city&&r.kind===kind&&r.budget_usd===b); return r?{x:X(i),y:Y(r.efficiency),r}:null;}).filter(Boolean);
    if(pts.length<2) return;
    s+=`<polyline fill="none" stroke="${COL[city]||"var(--accent)"}" stroke-width="2" ${kind==="shade"?'stroke-dasharray="4 3" opacity=".75"':""} points="${pts.map(p=>`${p.x},${p.y}`).join(" ")}"/>`;
    pts.forEach(p=>{ s+=`<circle cx="${p.x}" cy="${p.y}" r="${kind==="tree"?4:3}" fill="${kind==="tree"?(COL[city]||"var(--accent)"):"var(--card)"}" stroke="${COL[city]||"var(--accent)"}" stroke-width="2"><title>${city} ${kind}, $${(p.r.budget_usd/1e6).toFixed(1)}M: ${p.r.efficiency} per $1k, ${p.r.exposure_drop_C} °C, ${fmt(p.r.people)} people</title></circle>`;});
    const last=pts[pts.length-1];
    s+=`<text x="${W-PR+6}" y="${last.y+3}" font-size="8.5" fill="${COL[city]||"var(--accent)"}">${city} ${kind}</text>`;
  }));
  s+=`<text x="10" y="${PT+4}" font-size="8" fill="var(--ink-3)" transform="rotate(-90 10 ${PT+4})" text-anchor="end">efficiency per $1k</text>`;
  return s+"</svg>";
}

function corridorChart(rows){
  const W=520,H=220,PL=54,PR=14,PT=14,PB=46;
  const max=Math.max(...rows.flatMap(r=>[r.area.route_exposure_drop_C,r.route.route_exposure_drop_C]))*1.15;
  const bw=26, group=(W-PL-PR)/rows.length;
  const Y=v=>PT+(1-v/max)*(H-PT-PB);
  let s=`<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Cooling along walked routes, by targeting strategy">`;
  [0,2,4,6].forEach(g=>{ if(g<=max) s+=`<line x1="${PL}" y1="${Y(g)}" x2="${W-PR}" y2="${Y(g)}" stroke="var(--rule)"/><text x="${PL-6}" y="${Y(g)+3}" font-size="8.5" fill="var(--ink-3)" text-anchor="end">${g}</text>`;});
  rows.forEach((r,i)=>{
    const cx=PL+group*i+group/2;
    [["area",r.area.route_exposure_drop_C,"var(--ink-3)"],["route",r.route.route_exposure_drop_C,"var(--accent)"]].forEach(([lab,v,col],k)=>{
      const x=cx+(k?4:-bw-4);
      s+=`<rect x="${x}" y="${Y(v)}" width="${bw}" height="${H-PB-Y(v)}" fill="${col}" rx="3"><title>${r.city}, ${lab}-targeted: ${v.toFixed(2)} °C cooler along walked routes</title></rect>`;
      s+=`<text x="${x+bw/2}" y="${Y(v)-4}" font-size="9" font-weight="600" fill="var(--ink)" text-anchor="middle">${v.toFixed(1)}</text>`;});
    s+=`<text x="${cx}" y="${H-PB+14}" font-size="9.5" fill="var(--ink-2)" text-anchor="middle">${r.city}</text>`;
    s+=`<text x="${cx}" y="${H-PB+27}" font-size="8" fill="var(--ink-3)" text-anchor="middle">plans share ${(r.plan_overlap*100).toFixed(1)}%</text>`;});
  s+=`<text x="11" y="${(PT+H-PB)/2}" font-size="8.5" fill="var(--ink-3)" text-anchor="middle" transform="rotate(-90 11 ${(PT+H-PB)/2})">°C cooler on walked routes</text>`;
  return s+"</svg>";
}

function stepCorridor(f){
  const t=f.targeting;
  if(t.status!=="done") return "";
  const v=t.verdict||{};
  return `<section class="step"><h2><i>06</i> Cool the hottest ground, or the ground people walk on?</h2>
  <p class="sub">Two plans per city at the same budget, both simulated for real, each scored on both objectives.</p>
  ${why(EXPLAIN.corridor)}
  <div class="grid g3">
    <div class="card">
      <figure class="chart scrollx">${corridorChart(t.rows)}</figure>
      <div class="legend"><span><i style="background:var(--ink-3)"></i>targeted at the hottest ground</span><span><i style="background:var(--accent)"></i>targeted at walking corridors</span></div>
    </div>
    <div class="card">
      <div style="display:flex;gap:.4rem;margin-bottom:.6rem"><span class="tag ${v.supported?"ok":"pend"}">H8 ${v.supported?"supported":"not supported"}</span></div>
      <div class="grid g4">
        <div class="kv"><div class="n">${(v.mean_plan_overlap*100).toFixed(1)}%</div><div class="l">of planted positions shared by the two plans. We pre-registered "under 70%" as the bar</div></div>
        <div class="kv"><div class="n">${v.mean_route_advantage_C} °C</div><div class="l">extra cooling on walked routes. We pre-registered "at least 0.3 °C"</div></div>
      </div>
      <table style="margin-top:.8rem"><thead><tr><th>City</th><th class="n">Hot-ground plan</th><th class="n">Corridor plan</th></tr></thead><tbody>
      ${t.rows.map(r=>`<tr><td>${r.city}</td><td class="n">${r.area.route_exposure_drop_C.toFixed(2)}</td><td class="n">${r.route.route_exposure_drop_C.toFixed(2)}</td></tr>`).join("")}
      </tbody></table>
      <p class="outcome">The two objectives select <b>almost disjoint</b> plans. In Lagos and Rio the corridor plan gives up some
      average-area cooling to buy far more along the routes people walk; in Ahmedabad it <b>wins on both</b> measures at once.</p>
    </div>
  </div></section>`;
}

function tradeoffChart(plans,selected){
  const W=330,H=210,PL=44,PR=12,PT=12,PB=34;
  const xs=plans.map(p=>p.exposure_drop), ys=plans.map(p=>p.people);
  const xmax=Math.max(...xs)*1.1||1, ymax=Math.max(...ys)*1.1||1;
  const COL={clustered:"var(--s2)",scattered:"var(--s1)",corridor:"var(--s3)"};
  const X=v=>PL+(v/xmax)*(W-PL-PR), Y=v=>PT+(1-v/ymax)*(H-PT-PB);
  let s=`<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Average exposure reduction against people moved below the danger threshold">`;
  s+=`<line x1="${PL}" y1="${H-PB}" x2="${W-PR}" y2="${H-PB}" stroke="var(--rule-2)"/><line x1="${PL}" y1="${PT}" x2="${PL}" y2="${H-PB}" stroke="var(--rule-2)"/>`;
  plans.forEach(p=>{const on=p.id===selected;
    s+=`<circle class="pt" data-id="${p.id}" cx="${X(p.exposure_drop).toFixed(1)}" cy="${Y(p.people).toFixed(1)}" r="${on?7:4.5}" fill="${COL[p.arrangement]}" stroke="var(--card)" stroke-width="${on?3:1.5}" style="cursor:pointer"><title>${p.id}: ${(p.coverage*100).toFixed(1)}% coverage, $${p.cost_m}M, ${p.exposure_drop} °C, ${fmt(p.people)} people</title></circle>`;});
  s+=`<text x="${(PL+W-PR)/2}" y="${H-4}" font-size="8.5" fill="var(--ink-3)" text-anchor="middle">average exposure drop (°C)</text>`;
  s+=`<text x="9" y="${(PT+H-PB)/2}" font-size="8.5" fill="var(--ink-3)" text-anchor="middle" transform="rotate(-90 9 ${(PT+H-PB)/2})">people below threshold</text>`;
  return s+"</svg>";
}

/* ------------------------------------ steps ------------------------------------------ */
function stepAssemble(c){
  const p=c.provenance;
  return `<section class="step"><h2><i>01</i> Assemble a city from open data</h2>
  <p class="sub">Before any physics, the city has to exist as numbers. Five layers, one metre, one grid, no credentials.</p>
  ${why(EXPLAIN.assemble)}
  <div class="card">
    <div class="grid g4" >
      <div class="kv"><div class="n">${fmt(p.buildings)}</div><div class="l">buildings with heights</div></div>
      <div class="kv"><div class="n">${(p.built_fraction*100).toFixed(0)}%</div><div class="l">of ground is built on</div></div>
      <div class="kv"><div class="n">${(p.canopy*100).toFixed(1)}%</div><div class="l">existing tree canopy over 2 m</div></div>
      <div class="kv"><div class="n">${fmt(p.population)}</div><div class="l">residents in the square kilometre</div></div>
    </div>
    <div class="chain">${Object.entries(p.sources).map(([k,v])=>`<span class="chip">${k}: ${esc(v)}</span>`).join("")}</div>
    <p class="outcome">Design day <b>${p.design_day}</b> at ${p.lat.toFixed(3)}, ${p.lon.toFixed(3)}. Input quality tier <b>${p.tier}</b>.</p>
  </div></section>`;
}

function stepSimulate(c){
  return `<section class="step"><h2><i>02</i> Simulate the heat a body actually feels</h2>
  <p class="sub">The engine computes mean radiant temperature for every square metre, every hour of the design day.</p>
  ${why(EXPLAIN.simulate)}
  <div class="scrub">
    <div class="card">
      <div class="frame">
        <canvas id="frame" width="320" height="320" aria-label="Mean radiant temperature map"></canvas>
        <span class="hour" id="hourlbl"></span><span class="readout" id="readout">hover to read</span>
      </div>
      <div class="ctrl">
        <button id="play" aria-pressed="false">Play</button>
        <input type="range" id="hour" min="0" max="23" value="15" aria-label="Hour of day">
        <span style="font-family:var(--f-m);font-size:.78rem;color:var(--ink-3)" id="hourstat"></span>
      </div>
      <div class="sc"><span>cooler</span><div class="ramp" style="background:linear-gradient(90deg,#fdf3e7,#f7c99a,#eb8f4e,#d1552a,#7e2412)"></div><span>hotter</span><span id="scalelbl" style="font-family:var(--f-m)"></span></div>
    </div>
    <div class="card">
      <div style="font-size:.74rem;color:var(--ink-3);margin-bottom:.3rem">Weather on the design day</div>
      <div id="metchart"></div>
      <div class="legend"><span><i style="background:var(--hot)"></i>air temperature</span><span><i style="background:var(--accent-wash);border:1px solid var(--rule-2)"></i>solar radiation</span></div>
      <p class="outcome" style="margin-top:.8rem">Baseline population-weighted outdoor exposure is
      <b>${c.baseline.exposure} °C</b>, with <b>${fmt(c.baseline.at_risk)}</b> people in ground above the 45 °C stress threshold.</p>
    </div>
  </div></section>`;
}

function stepSurrogate(f){
  const s=f.surrogate;
  if(s.status!=="done") return "";
  return `<section class="step"><h2><i>03</i> Learn a fast stand-in for the physics</h2>
  <p class="sub">Physics is too slow to search with. A trained model makes the search affordable without giving up the physics as ground truth.</p>
  ${why(EXPLAIN.surrogate)}
  <div class="grid g3">
    <div class="card"><div class="grid g4">
      <div class="kv"><div class="n">${s.skill}</div><div class="l">skill against predicting no change, on plans it never saw</div></div>
      <div class="kv"><div class="n">${s.ranking_spearman}</div><div class="l">rank correlation with the engine, so it orders plans correctly</div></div>
      <div class="kv"><div class="n">${Math.round(s.speedup)}×</div><div class="l">faster: ${s.engine_seconds}s of physics becomes ${s.surrogate_seconds}s</div></div>
      <div class="kv"><div class="n">${(s.aggregate_error*100).toFixed(1)}%</div><div class="l">error on a plan's total cooling</div></div>
    </div></div>
    <div class="card">
      <div style="font-size:.74rem;color:var(--ink-3);margin-bottom:.3rem">Does training on more cities help an unseen one?</div>
      <figure class="chart">${transferChart(s.transfer)}</figure>
      <p class="outcome">Held out entirely, then predicted. Adding a second training city raised skill on the unseen city
      from <b>${s.transfer[0]?.skill}</b> to <b>${s.transfer[s.transfer.length-1]?.skill}</b>: <b>more cities help</b>, which is the
      argument for growing the corpus.</p>
    </div>
  </div></section>`;
}

function stepFactorial(f){
  const x=f.factorial;
  if(x.status!=="done") return "";
  const v=x.verdict||{};
  const spread=x.spreads&&x.spreads.length?x.spreads:[];
  return `<section class="step"><h2><i>04</i> Ask which measure buys the most cooling per dollar</h2>
  <p class="sub">${x.cells} cells, every one a real physics run: two intervention types, three budgets, three cities on three continents.</p>
  ${why(EXPLAIN.factorial)}
  <div class="grid g3">
    <div class="card">
      <figure class="chart scrollx">${factorialChart(x.rows)}</figure>
      <div class="legend"><span>solid = trees</span><span>dashed = shade structures</span><span>lines fall to the right because each extra dollar buys less</span></div>
    </div>
    <div class="card">
      <div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.6rem">
        <span class="tag ${v.h3_supported?"ok":"pend"}">H3 ${v.h3_supported?"supported":"open"}</span>
        <span class="tag ${v.h4_supported?"ok":"pend"}">H4 ${v.h4_supported?"supported":"open"}</span>
      </div>
      <ul class="hyp" style="padding:0;margin:0">
        <li><code>H3</code><span>Trees win on cooling per dollar. <b>They won ${v.tree_wins} of ${v.comparisons} comparisons</b>, by ${v.advantage_ratio?.min}× to ${v.advantage_ratio?.max}×, mean <b>${v.advantage_ratio?.mean}×</b>.</span></li>
        <li><code>H4</code><span>The ranking is the same in every city. <b>It was</b>: trees led in ${Object.keys(v.winner_by_city||{}).join(", ")}. A ranking that flipped by city would not be worth publishing.</span></li>
      </ul>
      ${spread.length?`<table style="margin-top:.9rem"><thead><tr><th>Budget</th><th class="n">Cooling varies</th><th class="n">People helped varies</th></tr></thead><tbody>
      ${spread.map(s=>`<tr><td>$${(s.budget_usd/1e6).toFixed(1)}M</td><td class="n">${s.cooling_spread}×</td><td class="n">${s.people_spread}×</td></tr>`).join("")}
      </tbody></table>
      <p class="outcome">The result we were not looking for: the same money buys <b>almost the same physics</b> in every city and up to
      <b>${Math.max(...spread.map(s=>s.people_spread))}× the human benefit</b>. Cooling transfers between cities; who is standing in the cooled space does not.
      That makes targeting, not thermal prediction, the hard part of the problem.</p>`:""}
    </div>
  </div></section>`;
}

function stepPlans(c){
  return `<section class="step"><h2><i>05</i> Ask where to put it</h2>
  <p class="sub">Same budget, same canopy, different geometry. Select a plan to see where the trees go and what cooling arrives.</p>
  ${why(EXPLAIN.plans)}
  <div class="scrub">
    <div class="card">
      <div style="font-size:.74rem;color:var(--ink-3);margin-bottom:.3rem">Every generated plan, scored on both objectives</div>
      <figure class="chart" id="tradeoff"></figure>
      <div class="legend"><span><i style="background:var(--s2)"></i>clustered</span><span><i style="background:var(--s1)"></i>scattered</span><span><i style="background:var(--s3)"></i>corridor</span></div>
      <div class="plist" id="plist"></div>
    </div>
    <div class="card">
      <div class="maps">
        <figure><figcaption>where the trees go</figcaption><canvas id="mplace"></canvas></figure>
        <figure><figcaption>cooling delivered (°C)</figcaption><canvas id="mcool"></canvas></figure>
      </div>
      <div class="outcome" id="outcome"></div>
    </div>
  </div></section>`;
}

function stepOpen(f){
  const open=[f.channel,f.targeting].filter(x=>x.status==="pending");
  let s=`<section class="step"><h2><i>07</i> Open questions, running now</h2>
  <p class="sub">Written down before they were run. Listed here whether or not they turn out the way we expect.</p><div class="grid g3">`;
  open.forEach(x=>{
    s+=`<div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:.5rem">
      <b>${x.name}</b><span class="tag pend">running</span></div>
      <p class="sub" style="margin:.4rem 0 .5rem">${x.question}</p>
      <ul class="hyp" style="padding:0;margin:0">${x.hypotheses.map(h=>`<li><code>${h.split(" ")[0]}</code><span>${h.split(" ").slice(1).join(" ")}</span></li>`).join("")}</ul>
      <p class="outcome" style="font-size:.8rem">${x.detail}</p></div>`;
  });
  s+=`<div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline"><b>Next</b><span class="tag pend">queued</span></div>
    <ul class="hyp" style="padding:0;margin:.4rem 0 0">
      <li><code>H9</code><span>The gain from corridor targeting should grow with how irregular a street network is. On a perfect grid every detour is equivalent, so there should be nothing to win.</span></li>
      <li><code>scale</code><span>Grow the corpus beyond three cities. Transfer already improves with each city added, so this is a measured bet rather than a hopeful one.</span></li>
    </ul></div>`;
  return s+"</div></section>";
}

/* ------------------------------------ wiring ----------------------------------------- */
function paintHour(){
  const c=S.data.cities.find(x=>x.city===S.city);
  const A=S.atlas[c.hours.file];
  if(!A) return;
  drawTile($("frame"),A,S.hour,RAMP_HEAT);
  $("hourlbl").textContent=String(S.hour).padStart(2,"0")+":00";
  const h=(c.hours.hours||[])[S.hour];
  if(h) $("hourstat").textContent=`median ${h.median} °C · peak ${h.max} °C`;
  $("scalelbl").textContent=`${A.vmin.toFixed(0)}–${A.vmax.toFixed(0)} °C`;
  $("metchart").innerHTML=metChart(c.met,S.hour);
}

function paintPlan(){
  const c=S.data.cities.find(x=>x.city===S.city);
  const p=c.plans.list.find(x=>x.id===S.plan)||c.plans.list[0];
  if(!p) return;
  S.plan=p.id;
  const cool=S.atlas[c.plans.cooling.file], place=S.atlas[c.plans.placement.file];
  drawTile($("mcool"),cool,p.tile,RAMP_COOL,{floor:1});
  drawTile($("mplace"),place,p.tile,RAMP_PLACE,{floor:1});
  $("tradeoff").innerHTML=tradeoffChart(c.plans.list,S.plan);
  $("tradeoff").querySelectorAll(".pt").forEach(el=>el.onclick=()=>{S.plan=el.dataset.id;paintPlan();});
  $("plist").innerHTML=c.plans.list.map(x=>`<div class="prow" data-id="${x.id}" tabindex="0" aria-selected="${x.id===S.plan}">
     <span>${x.arrangement} · ${(x.coverage*100).toFixed(1)}%</span>
     <span class="m">${x.exposure_drop} °C</span><span class="m">$${x.cost_m}M</span></div>`).join("");
  $("plist").querySelectorAll(".prow").forEach(el=>{
    el.onclick=()=>{S.plan=el.dataset.id;paintPlan();};
    el.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();S.plan=el.dataset.id;paintPlan();}};
  });
  const sel=$("plist").querySelector('[aria-selected="true"]');
  if(sel) sel.scrollIntoView({block:"nearest"});
  $("outcome").innerHTML=`<b>${p.arrangement}</b> at ${(p.coverage*100).toFixed(1)}% coverage costs <b>$${p.cost_m}M</b>,
     lowers average outdoor exposure by <b>${p.exposure_drop} °C</b> and moves <b>${fmt(p.people)}</b> people below the danger threshold.`;
}

async function render(){
  const c=S.data.cities.find(x=>x.city===S.city), f=S.data.findings;
  $("citymeta").textContent=`${c.name} · design day ${c.provenance.design_day} · 1 km² at 1 m`;
  $("app").innerHTML=stepAssemble(c)+stepSimulate(c)+stepSurrogate(f)+stepFactorial(f)+stepPlans(c)+stepCorridor(f)+stepOpen(f);
  $("hour").value=S.hour;
  $("hour").oninput=e=>{S.hour=+e.target.value;paintHour();};
  $("play").onclick=()=>{
    S.playing=!S.playing;
    $("play").textContent=S.playing?"Pause":"Play";
    $("play").setAttribute("aria-pressed",String(S.playing));
    if(S.playing) tick();
  };
  attachReadout($("frame"),$("readout"),()=>S.atlas[c.hours.file],()=>S.hour," °C");
  // Text and charts are already on screen. Fields arrive after, together, so a slow or
  // missing image degrades to a blank map rather than a blank page.
  await Promise.all([c.hours, c.plans.cooling, c.plans.placement].map(loadAtlas));
  paintHour();
  paintPlan();
}
function tick(){
  if(!S.playing) return;
  S.hour=(S.hour+1)%24; $("hour").value=S.hour; paintHour();
  setTimeout(tick,320);
}

(async function(){
  S.data=await (await fetch("index.json")).json();
  const sel=$("city");
  sel.innerHTML=S.data.cities.map(c=>`<option value="${c.city}">${c.name}</option>`).join("");
  S.city=S.data.cities[0].city;
  sel.onchange=async e=>{
    S.city=e.target.value; S.plan=null;
    $("app").innerHTML='<div class="loading">loading '+e.target.value+'…</div>';
    await render();
  };
  await render();
})();
