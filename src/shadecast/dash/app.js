/* shadecast walkthrough: step-by-step render of the pipeline and what it found. */

const EXPLAIN = {
  assemble: [
    ["bundle", "What a city bundle is",
     "Five raster layers covering one square kilometre at <em>one metre</em> per pixel, all snapped to the same grid: building heights, bare ground elevation, tree canopy height, land cover class, and an hourly weather file. The physics engine requires every layer to share an extent and a pixel size, so we guarantee that by construction rather than by hope."],
    ["credfree", "Why credential-free matters",
     "Every source here is public and unauthenticated, so anyone can rebuild any city without an account, a quota, or a paid key. Credentials are needed at <em>build</em> time by nobody and at <em>use</em> time by nobody. That is what makes this a benchmark others can actually run rather than a result others must take on trust."],
    ["designday", "Design day",
     "One representative hot day drawn from reanalysis weather, which the whole simulation runs on. Using a real day rather than a monthly average keeps sun angles, air temperature and solar load physically consistent with each other."],
    ["tier", "Quality tier",
     "A label recording how good the inputs were for this city, because global open data is uneven. A result carries its tier so a weak-input city is never silently compared against a strong-input one."]
  ],
  simulate: [
    ["tmrt", "Mean radiant temperature, or Tmrt",
     "The single temperature of an imaginary uniform enclosure that would load a human body with the same radiant heat as the real surroundings do. It sums the sunlight striking you plus the infrared radiating off pavement, walls and sky. On an open sunny street it runs <em>15 to 25 °C above air temperature</em>; step into shade and it falls within seconds. This is the quantity a body actually feels."],
    ["notair", "Why not just air temperature",
     "Air temperature barely changes across a street. Planting a tree moves it by a few tenths of a degree, which is why shade looks almost worthless if you measure air. The same tree can drop Tmrt by <em>more than 20 °C</em> in its own shadow. Measuring the wrong variable is the fastest way to conclude that shade does not work."],
    ["solweig", "SOLWEIG",
     "The radiation model that computes Tmrt. For every square metre and every hour it works out what that point can see of sun, sky, ground and building, then sums the energy arriving from each direction. We run it as a separate process so that its GPL licence stays outside this Apache-2.0 codebase."],
    ["readmap", "Reading the map",
     "Colour is Tmrt on a single scale held fixed across all 24 hours, so the animation shows the city genuinely heating and cooling rather than rescaling itself. <em>Hover any pixel to read its actual temperature.</em>"]
  ],
  surrogate: [
    ["slow", "The problem",
     "One physics run takes about <em>160 seconds</em>. Searching even a few thousand candidate plans would take weeks of compute, so the search that actually matters is unaffordable if every candidate needs the engine."],
    ["doe", "Design of experiments",
     "Instead of simulating one plan per run, we scatter many small probes through a single run, spaced further apart than the distance over which one probe's cooling can reach. Because their effects never overlap, they can be read back as independent measurements: one engine call yields roughly <em>a hundred</em> observations instead of one."],
    ["surrogate", "The surrogate",
     "A convolutional network trained on those observations to predict the cooling field a plan produces, without running the physics. It answers in about half a second instead of 160."],
    ["skill", "Skill score, and why plain error would mislead",
     "Skill measures how much better a prediction is than predicting <em>no change at all</em>. Zero means no better than doing nothing; one means perfect. It matters because a cooling field is almost entirely zero, so a model that confidently predicts nothing everywhere earns a flattering low average error while being completely useless. Skill is the metric that refuses to reward that."],
    ["transfer", "Transfer",
     "Whether a model trained on some cities can predict a city it has never seen. This is the difference between a tool that works anywhere and one that must be refitted per city."]
  ],
  factorial: [
    ["factorial", "Full factorial",
     "Every combination of the things being varied, run in full: each intervention type, at each budget, in each city. Running the complete grid rather than a sample is what allows a claim that the ranking holds <em>everywhere</em>, instead of merely on average."],
    ["efficiency", "Efficiency",
     "Degree-hours of dangerous heat removed per <em>$1,000</em> spent. It counts only outdoor ground, because the model is a pedestrian model and its value over a rooftop is not a temperature anyone experiences, and it weights each place by how many people are near it."],
    ["prereg", "Pre-registration",
     "The hypotheses, their predicted numbers, and the conditions that would prove them wrong, all committed to version control <em>before</em> the experiment ran. It removes the option of deciding afterwards which result was the one we meant to test. An earlier finding of ours was retracted for exactly that missing discipline."],
    ["arms", "What the two arms are",
     "<em>Trees</em> are living canopy: they cast shade and cool by evaporation, but take years to mature and need water. <em>Shade structures</em> are built canopies such as sails or pergolas: instant, maintenance-light, and far more expensive per square metre covered."]
  ],
  channel: [
    ["depave", "De-paving",
     "Lifting sealed surface and putting vegetation in its place. Here it is asphalt replaced by unmanaged grass, and permeable paving is the halfway house: a lighter, rougher surface that still takes traffic."],
    ["channel", "Which channel it works through",
     "Not reflectivity. The model's own table gives asphalt a surface heating coefficient of <em>0.58</em> and grass <em>0.21</em>, so the ground simply emits less infrared at the people standing on it. Nothing is bounced at anybody, which is what makes this arm trustworthy."],
    ["control", "The control that makes it a measurement",
     "Every run here feeds the engine a land cover map, and the ordinary baseline was produced without one. Comparing against that baseline would have measured <em>land cover switched on</em> mixed together with <em>asphalt became grass</em>, inseparably. So each city pays for an extra run holding land cover unchanged, and every number is measured against that."],
    ["aggregate", "Why it barely moves the city average",
     "De-paving cools the ground you actually replace and almost nothing beyond it. A tree also shades well past its own trunk. So a large local effect, <em>4.4 °C</em> on treated ground, becomes a small city-wide one once it is spread over the people who live there."]
  ],
  corridor: [
    ["question", "The question",
     "A budget can cool the <em>hottest ground</em>, or it can cool the ground <em>people actually walk on</em>. Those are not the same places, and until you build both plans and simulate both, there is no way to know how far apart they are."],
    ["network", "Walking network",
     "Every footway, path and street a person on foot may use, taken from OpenStreetMap and laid on the same grid as the heat. About 19 km of it inside one square kilometre."],
    ["walker", "How a walker is modelled",
     "People do not take the coolest possible route at any cost, nor the shortest regardless of sun. Each street is given a <em>perceived</em> length that grows with its heat, so a walker trades distance against exposure. Routes are chosen on perceived cost and then scored on the heat actually met along the route chosen, which keeps the choosing and the scoring honest about each other."],
    ["corridorvalue", "Corridor value",
     "For each street, the total trip heat carried along it: how many people-trips pass, multiplied by how hot it is where they pass. It is high where many unavoidable routes funnel through the same hot ground, and low where a street is hot but easy to walk around. An area average cannot tell those two apart; this is the whole reason for the objective."],
    ["overlap", "Plan overlap",
     "The share of planted positions the two plans have in common. Near zero means the two objectives are choosing almost entirely different places, so the choice of objective is not a detail, it decides what gets built."],
    ["caveat", "The honest caveat",
     "That corridor targeting wins on the corridor measure is partly definitional, since that is what it optimises. The findings that are <em>not</em> definitional are how little the two plans overlap, how large the gap is, and that in Ahmedabad the corridor plan wins on the area measure too."]
  ],
  plans: [
    ["coverage", "Coverage",
     "The fraction of the square kilometre that receives an intervention. It is the simplest dial a planner has and it doubles as a stand-in for budget."],
    ["arrangement", "Arrangement",
     "How the same quantity of canopy is distributed: <em>clustered</em> into a few dense groves, or <em>scattered</em> evenly across the area. Same money, same total canopy, different geometry."],
    ["tradeoff", "The trade-off",
     "Two reasonable objectives disagree. Spreading canopy lowers the <em>average</em> exposure across everyone, while concentrating it pulls more individual people below the dangerous threshold. There is no arrangement that wins both, so the benchmark reports both and refuses to collapse them into one score. Choosing between them is a political decision, not a modelling one."]
  ]
};

/* Definitions live once, at the foot of the page, and steps point at them by number.
   Inline they crowded out the thing each step was actually showing. */
const TERM_ORDER = ["assemble","simulate","surrogate","factorial","plans","corridor","channel"];
const TERMS = [];
const TERM_BY_SLUG = {};
TERM_ORDER.forEach(key=>(EXPLAIN[key]||[]).forEach(([slug,title,body])=>{
  const t={n:TERMS.length+1, key, slug, title, body};
  TERMS.push(t); TERM_BY_SLUG[slug]=t;
}));

/* A term is cited where it is used, as a superscript, and defined once at the foot. */
function ref(slug){
  const t=TERM_BY_SLUG[slug];
  return t ? `<sup class="ref"><a href="#t${t.n}" title="${t.title}">${t.n}</a></sup>` : "";
}



function prose(...paras){
  return `<div class="prose">${paras.map(x=>`<p>${x}</p>`).join("")}</div>`;
}

/* Everything this work stands on, grouped by what it was used for. A flat alphabetical
   list would hide which sources are load-bearing and which are context. */
const REFERENCES = [
["The radiation model", [
 ["SOLWEIG 1.0: modelling spatial variations of 3D radiant fluxes and mean radiant temperature in complex urban settings", "Lindberg, Holmer and Thorsson, International Journal of Biometeorology 52, 2008", ""],
 ["Urban Multi-scale Environmental Predictor (UMEP): an integrated tool for city-based climate services", "Lindberg et al., Environmental Modelling and Software 99, 2018", "https://umep-docs.readthedocs.io/"],
 ["solweig-gpu, the implementation this benchmark calls", "GPL-3.0, invoked across a process boundary so this codebase stays Apache-2.0", "https://solweig-gpu.readthedocs.io/en/latest/input_data.html"],
 ["SOLWEIG model source and documentation", "UMEP development group", "https://umep-dev.github.io/solweig/"],
 ["Deriving the operational procedure for the Universal Thermal Climate Index", "Bröde et al., International Journal of Biometeorology 56, 2012", ""]]],

["Reflective surfaces, and why those arms are quarantined", [
 ["Evidence-based guidance on reflective pavement for urban heat mitigation in Arizona", "Nature Communications 14, 1467, 2023. Field measurement across 58 km of treated street in Phoenix: pedestrian mean radiant temperature rises significantly on the road, with no significant change on the sidewalk", "https://www.nature.com/articles/s41467-023-36972-5"],
 ["Limited application of reflective surfaces can mitigate urban heat pollution", "Nature Communications 12, 2021", "https://www.nature.com/articles/s41467-021-23634-7"],
 ["Optimizing retro-reflective surfaces to untrap radiation and cool cities", "Nature Cities, 2024. The physically correct version of the albedo arm, and one this engine cannot represent", "https://www.nature.com/articles/s44284-024-00047-3"],
 ["Harnessing retro-reflective materials for urban heat island mitigation", "Discover Cities, 2025", "https://link.springer.com/article/10.1007/s44327-025-00086-y"]]],

["Shaded routing, the forward problem this inverts", [
 ["CoolWalks for active mobility in urban street networks", "Scientific Reports, 2025", "https://www.nature.com/articles/s41598-025-97200-2"],
 ["CoolWalks: assessing the potential of shaded routing for active mobility", "arXiv:2405.01225", "https://arxiv.org/html/2405.01225v1"],
 ["Cool routes: real-time human thermal exposure routing", "Building and Environment", "https://www.sciencedirect.com/science/article/abs/pii/S0360132326004270"],
 ["Mitigating heat stress by reducing solar exposure in pedestrian routing", "Kolaxidis et al., Transactions in GIS, 2025", "https://onlinelibrary.wiley.com/doi/10.1111/tgis.70110"]]],

["Prior systems this builds on and compares against", [
 ["WRI Cool Cities Lab, UTCI methods", "World Resources Institute", "https://coolcities.wri.org/data-and-methods/utci"],
 ["cities-cif, WRI's city indicator framework", "World Resources Institute", "https://github.com/wri/cities-cif"],
 ["cities-OpenUrban, WRI's land cover and opportunity layers", "Source of the cool-roof albedo targets, 0.62 low slope and 0.28 high slope", "https://github.com/wri/cities-OpenUrban"],
 ["En-ROADS climate policy simulator", "Climate Interactive. Checked for overlap: it is global and policy-scale, this is street-scale and spatial", "https://www.climateinteractive.org/en-roads/"],
 ["Handbook on urban heat management in the Global South", "UN-Habitat", "https://unhabitat.org/handbook-on-urban-heat-management-in-the-global-south"]]],

["Data, every source unauthenticated", [
 ["GlobalBuildingAtlas LoD1 footprints and heights", "Source Cooperative. Chosen over Overture, which carried heights for 1 of 14,213 buildings in Ahmedabad", "https://source.coop/tge-labs/globalbuildingatlas-lod1"],
 ["Copernicus DEM GLO-30 terrain", "AWS Open Data, unsigned", ""],
 ["ESA WorldCover 10 m v200 2021 land cover", "AWS Open Data, unsigned", ""],
 ["Meta and WRI Canopy Height Model, 1 m", "AWS Open Data", "https://registry.opendata.aws/dataforgood-fb-forests/"],
 ["GHS-POP R2023A population, 100 m", "European Commission JRC, redistributed here by building volume", "https://human-settlement.emergency.copernicus.eu/ghs_pop2023.php"],
 ["Open-Meteo ERA5 historical archive", "Hourly meteorology, no key required", "https://open-meteo.com/en/docs/historical-weather-api"],
 ["OpenStreetMap, via Overpass", "The walkable network behind the corridor objective", "https://www.openstreetmap.org/copyright"]]],

["Method", [
 ["OSMnx: new methods for acquiring, constructing, analyzing and visualizing complex street networks", "Boeing, Computers, Environment and Urban Systems 65, 2017", ""],
 ["U-Net: convolutional networks for biomedical image segmentation", "Ronneberger, Fischer and Brox, MICCAI 2015. The surrogate architecture", "https://arxiv.org/abs/1505.04597"],
 ["Evolutionary surrogate-assisted prescription", "Cognizant AI Labs. The framing behind treating this as a prescriptor over a learned predictor", "https://arxiv.org/pdf/2012.10504"],
 ["en-roads-py, evolutionary prescription applied to En-ROADS", "Cognizant AI Labs. A working implementation of the prescriptor pattern over a fixed simulator, and the closest existing analogue to what the planner here does over SOLWEIG", "https://github.com/cognizant-ai-labs/en-roads-py"]]],
];

function stepReferences(){
  return `<section class="step" id="references"><h2><i>10</i> References</h2>
  <p class="sub">Everything this work rests on. Sources that changed a decision carry a note saying what they changed.</p>
  <div class="card"><div class="refs">${REFERENCES.map(([group,items])=>
    `<div class="refgroup"><h3>${group}</h3><ul>${items.map(([title,where,url])=>
      `<li>${url?`<a href="${url}" target="_blank" rel="noopener">${title}</a>`:`<span>${title}</span>`}<em>${where}</em></li>`
    ).join("")}</ul></div>`).join("")}</div></div></section>`;
}

function stepGlossary(){
  return `<section class="step" id="terminology"><h2><i>09</i> Terminology</h2>
  <p class="sub">Every term the walkthrough uses, defined once. Each is linked from the step that first needs it.</p>
  <div class="card"><ol class="glossary">${TERMS.map(t=>
    `<li id="t${t.n}"><span class="rn">${t.n}</span><div><b>${t.title}</b><p>${t.body}</p></div></li>`).join("")}</ol></div></section>`;
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
  <p class="sub">A budget can cool the hottest ground or the ground people walk on${ref("question")}, and those are not the same places. Over the walking network${ref("network")}, with a walker who trades distance against sun${ref("walker")}, each street earns a corridor value${ref("corridorvalue")}. Both plans are then built, simulated, and their plan overlap${ref("overlap")} measured. One honest caveat${ref("caveat")} is stated up front.</p>
  ${prose("Published work on shaded routing solves the forward problem: given the shade a city already has, find the coolest way across it. That is useful to a walker and no use at all to a planner, who has to decide where the shade should go in the first place. This is the inverse of that question, and as far as we can tell it is unclaimed.", "The mechanism is that trip heat concentrates. Where alternatives exist, walkers already route around the worst streets, so cooling those streets buys less than the heat map suggests. Where a route is forced, everyone funnels through the same hot ground and cooling it buys a great deal. An area average scores those two situations identically, which is precisely the failure this objective exists to fix.")}
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
  <p class="sub">Before any physics the city has to exist as numbers: a city bundle${ref("bundle")} of five layers at one metre on one grid, assembled from public sources with no credentials anywhere${ref("credfree")}, pinned to a single design day${ref("designday")} and labelled with a quality tier${ref("tier")}.</p>
  ${prose("Every layer is a raster, and they have to agree exactly. The engine will not run if the building model, the terrain, the canopy and the land cover disagree about extent or pixel size by even one cell. Rather than checking for that afterwards, the builder resamples everything onto a single grid defined by the study area itself, so agreement holds by construction rather than by inspection.", "The harder constraint is the credential rule. It would be far easier to pull building heights from a commercial API, but a benchmark that needs three accounts is one almost nobody will reproduce. Everything here came from unauthenticated public endpoints, and each layer carries its source with it, which is what the chips below record.")}
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
  <p class="sub">SOLWEIG${ref("solweig")} computes mean radiant temperature${ref("tmrt")} for every square metre and every hour. That is the heat a body actually feels, which is not air temperature${ref("notair")} and behaves very differently from it. Hover any pixel to read its value${ref("readmap")}.</p>
  ${prose("The model works by asking, for every square metre, what that point can see. Ground under dense canopy sees little sky and little sun. Ground in the middle of a car park sees all of both, plus hot asphalt radiating back up at it. Adding the energy arriving from every direction gives the radiant load on a body standing there.", "Watch the whole day rather than any single hour. The peak does not fall at noon, and the shade pattern sweeps across the city as the sun moves, which is exactly why a plan judged at one instant can look far better or far worse than it really is.")}
  <div class="scrub map">
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
  <p class="sub">Physics is too slow to search with${ref("slow")}. A design of experiments${ref("doe")} scatters non-overlapping probes through a single run, so it yields around a hundred measurements instead of one, and the surrogate${ref("surrogate")} trained on them answers in half a second. It is judged on skill score${ref("skill")} rather than plain error, and on transfer${ref("transfer")} to a city it has never seen.</p>
  ${prose("The engine remains the ground truth, and every headline number on this page is a real run. The surrogate exists only to make the search step affordable, by ranking thousands of candidate plans well enough that scarce physics time gets spent on the few worth simulating properly.", "Transfer is the result that decides whether any of this scales. A model that must be refitted for each new city is a per-city tool, not a benchmark. Held out of training entirely, Rio was predicted better by a model that had seen two other cities than by one that had seen a single city, which is the concrete argument for growing the corpus.")}
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
  <p class="sub">A full factorial${ref("factorial")} of ${x.cells} cells, every one a real physics run: trees against shade structures${ref("arms")}, three budgets, three cities on three continents, ranked by efficiency${ref("efficiency")} and tested against pre-registered${ref("prereg")} predictions.</p>
  ${prose("Price per square metre is misleading on its own. Shade structures cost roughly four times what trees cost for the same ground covered, but they work the day they go up and need very little maintenance, while a tree takes years to reach the canopy assumed here and wants water in the meantime. The question stays genuinely open until the radiation budget settles it.", "The ranking held in every city and the margin barely moved across an eighteenfold span of budget. What did move, by a factor of twenty, is how many people happen to be standing in the cooled space. The same physics is worth very different amounts depending on who is nearby, and that is what pushes this whole problem toward targeting.")}
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
  <p class="sub">Same budget and the same total canopy, at each level of coverage${ref("coverage")} and in different arrangements${ref("arrangement")}. Two reasonable objectives disagree about which wins, and that trade-off${ref("tradeoff")} is reported rather than quietly resolved. Select a plan to see where the trees go and what cooling arrives.</p>
  ${prose("These plans were generated to sweep the design space rather than to be good, so several are deliberately poor. What matters is the shape of the frontier they trace, not any single point on it.", "The disagreement between the two objectives is real and does not go away with a larger budget. Spreading canopy thinly helps almost everyone a little; concentrating it rescues fewer people more completely. Both are defensible, so the benchmark reports both and leaves the weighting to whoever is accountable for the decision.")}
  <div class="scrub wide">
    <div class="card">
      <div style="font-size:.74rem;color:var(--ink-3);margin-bottom:.3rem">Every generated plan, scored on both objectives</div>
      <figure class="chart" id="tradeoff"></figure>
      <div class="legend"><span><i style="background:var(--s2)"></i>clustered</span><span><i style="background:var(--s1)"></i>scattered</span><span><i style="background:var(--s3)"></i>corridor</span></div>
    </div>
    <div class="card">
      <div style="font-size:.74rem;color:var(--ink-3);margin-bottom:.3rem">Pick a plan</div>
      <div class="plist" id="plist"></div>
      <div class="outcome" id="outcome"></div>
    </div>
  </div>
  <div class="card" style="margin-top:.8rem">
    <div class="maps">
      <figure><figcaption>where the trees go</figcaption>
        <div class="frame plain"><canvas id="mplace"></canvas><span class="readout" id="placeout">hover to read</span></div></figure>
      <figure><figcaption>cooling delivered, hover to read</figcaption>
        <div class="frame plain"><canvas id="mcool"></canvas><span class="readout" id="coolout">hover to read</span></div></figure>
    </div>
  </div></section>`;
}

function stepChannel(f){
  const x=f.channel;
  if(x.status!=="done") return "";
  const v=x.verdict||{}, m=v.mean_treated_drop_C||{};
  const cells=x.rows.flatMap(r=>r.cells.filter(c=>c.pixels).map(c=>({city:r.city,...c})));
  return `<section class="step"><h2><i>07</i> Try a second cooling mechanism, not just shade</h2>
  <p class="sub">Trees and awnings both work by blocking sun. De-paving${ref("depave")} instead makes the ground itself cooler, through emission rather than reflection${ref("channel")}, which is why it stays usable while the albedo arms are quarantined. Each city pays for a control run that makes it a measurement${ref("control")}. Watch how little it moves the city figure${ref("aggregate")}.</p>
  ${prose("This arm exists because the shortwave arms are quarantined. Cool roofs and reflective pavement both work by bouncing sunlight, and this engine reports cooling where its own constants and field measurement in Phoenix both say warming, so nothing it produces about them can be trusted. De-paving acts through a different channel and is unaffected by that defect.", "The result splits cleanly into a large local effect and a small city-wide one, and the gap is the instructive part. Replacing a square metre of asphalt cools that square metre. A tree standing on it also shades the square metres around it. Shade wins budgets because its effect travels, which is the same reason trees beat de-paving on cost-effectiveness.")}
  <div class="grid g3">
    <div class="card">
      <table><thead><tr><th>City</th><th>Surface</th><th class="n">Heating coef.</th><th class="n">Treated ground</th><th class="n">City-wide</th></tr></thead><tbody>
      ${cells.map(c=>`<tr><td>${c.city}</td><td>${c.kind==="depave"?"grass":"permeable"}</td><td class="n">${c.ts_deg}</td><td class="n">${c.treated_drop_C.toFixed(2)} °C</td><td class="n">${c.exposure_drop_C.toFixed(3)} °C</td></tr>`).join("")}
      </tbody></table>
    </div>
    <div class="card">
      <div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.6rem">
        <span class="tag ${v.h5_cools?"ok":"pend"}">H5 cools</span>
        <span class="tag ${v.h5_in_predicted_range?"ok":"pend"}">H5 size ${v.h5_in_predicted_range?"as predicted":"missed"}</span>
        <span class="tag ${v.h6_monotone?"ok":"pend"}">H6 ${v.h6_monotone?"supported":"open"}</span>
      </div>
      <ul class="hyp" style="padding:0;margin:0">
        <li><code>H5</code><span>De-paving cools, predicted 0.5 to 3 °C on treated ground. It cooled in <b>every one of the six cells</b>, but averaged <b>${m.depave} °C</b>, <b>above the band we wrote down</b>. Direction confirmed, magnitude mispredicted, recorded as a partial miss rather than rounded into a success.</span></li>
        <li><code>H6</code><span>Cooling should follow the surface heating coefficient, grass ahead of permeable paving. <b>It did</b>, ${m.depave} °C against ${m.permeable} °C, and in every city separately.</span></li>
      </ul>
      <p class="outcome">Note the last two columns. The same intervention that cools treated ground by <b>${m.depave} °C</b> moves the
      population-weighted city figure by under <b>0.4 °C</b>, because it cools only the ground it replaces while a tree shades far
      beyond its own footprint. That gap is why shade still wins a budget.</p>
    </div>
  </div></section>`;
}

function stepOpen(f){
  const pending=[f.channel,f.targeting].filter(x=>x.status==="pending");
  let s=`<section class="step"><h2><i>08</i> What we have, and what the benchmark still needs</h2>
  <p class="sub">Set out for the same reason the hypotheses were: so the gap between the goal and the state of things stays visible.</p>
  ${prose(
    "The goal set at the outset was an open benchmark for urban heat adaptation planning: a standard set of cities, a fixed way of scoring a plan, and results anyone can reproduce without an account. That is not finished. What exists today is the machinery and a first set of results. The pipeline runs end to end from public data, the scoring is fixed in advance and reported rather than collapsed into a single number, the hypotheses were committed before testing, and five of them have now been answered. That is a study built with a benchmark's architecture, not yet a benchmark.",
    "Three cities do test something real. Ahmedabad is hot and dry, Lagos hot and humid, Rio coastal and hilly, and they differ in density and street pattern as much as in climate. Trees beat shade structures in all three, at every budget, by a margin that barely moved. But three supports the claim that a ranking held where we looked, not that it holds generally, and it is too few to test the one hypothesis that needs variation across many cities rather than agreement among a few.",
    "Finished would look like this: nine or more cities spanning climate and urban form, every intervention arm either trusted or excluded for a stated reason, a held-out set that nothing was tuned against, and a published spec and data bundle a stranger can run and score against without asking us for anything. Four things stand between here and there."
  )}
  <div class="grid g3">`;
  pending.forEach(x=>{
    s+=`<div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:.5rem">
      <span>${x.name}</span><span class="tag pend">running</span></div>
      <p class="outcome">${x.detail}</p></div>`;
  });
  s+=`<div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline"><span>One. Scale the corpus</span><span class="tag pend">next</span></div>
    <p class="outcome">Six more city bundles are already built and unused: Phoenix, Sydney, Nairobi, Jakarta, Khartoum and
    London. Adding them turns "the ranking held in three cities" into a claim with enough spread to defend, and the
    transfer curve in section 3 already shows each extra city improving prediction on a city the model has never seen.
    This is the single step that most separates what exists from what was intended.</p></div>

    <div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline"><span>Two. H9, blocked on breadth</span><span class="tag pend">blocked</span></div>
    <p class="outcome">Shaded routing is known to give no benefit on a perfectly regular grid, because every alternative is
    equivalent. The corridor advantage should therefore grow with how irregular a street network is. Ours already spans
    9.7x, 3.8x and 2.1x across the three cities, which is suggestive and nothing more, because three points is not a
    correlation. The method is ready; only the cities are missing.</p></div>

    <div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline"><span>Three. Settle the albedo defect</span><span class="tag pend">next</span></div>
    <p class="outcome">Cool roofs and reflective pavement are excluded from every result here, because the engine reports
    cooling where its own constants and field measurement both say warming. That removes half the action space a real city
    has, so a benchmark that stays silent on it is incomplete. The test is already to hand: the field study was carried out
    in Phoenix, and a Phoenix bundle is built and waiting. Running the arm there either rehabilitates two interventions or
    turns a suspicion into a reportable upstream defect.</p></div>

    <div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline"><span>Four. Publish a runnable spec</span><span class="tag pend">next</span></div>
    <p class="outcome">A benchmark is something other people run. That needs frozen city bundles anyone can download, a fixed
    task definition, a held-out set nothing was tuned against, and a scoring script. The pieces exist as a command line
    today; what is missing is the packaging and the held-out split.</p></div>

    <div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline"><span>Standing limits</span><span class="tag pend">known</span></div>
    <p class="outcome">One square kilometre per city, not a whole city. One design day, so nothing here speaks to a season
    or to a heatwave sequence. Outdoor exposure only: indoor heat drives most heat mortality among older people and this
    does not address it. Costs are order-of-magnitude placeholders and should be replaced with local figures before any of
    these numbers inform real spending. Retro-reflective materials cannot be represented at all.</p></div>
  </div></section>`;
  return s;
}
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
  $("app").innerHTML=stepAssemble(c)+stepSimulate(c)+stepSurrogate(f)+stepFactorial(f)+stepPlans(c)+stepCorridor(f)+stepChannel(f)+stepOpen(f)+stepGlossary()+stepReferences();
  $("hour").value=S.hour;
  $("hour").oninput=e=>{S.hour=+e.target.value;paintHour();};
  $("play").onclick=()=>{
    S.playing=!S.playing;
    $("play").textContent=S.playing?"Pause":"Play";
    $("play").setAttribute("aria-pressed",String(S.playing));
    if(S.playing) tick();
  };
  attachReadout($("frame"),$("readout"),()=>S.atlas[c.hours.file],()=>S.hour," °C");
  const tileOf=()=>{const p=c.plans.list.find(x=>x.id===S.plan); return p?p.tile:0;};
  attachReadout($("mcool"),$("coolout"),()=>S.atlas[c.plans.cooling.file],tileOf," °C cooler");
  attachReadout($("mplace"),$("placeout"),()=>S.atlas[c.plans.placement.file],tileOf,"");
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
