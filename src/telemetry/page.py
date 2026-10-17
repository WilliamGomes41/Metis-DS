"""HTML body of the /telemetry page: one filter row, insights, charts, drill-down.

Self-contained (no external scripts). Every dynamic value is inserted with
``textContent``; charts are inline SVG with a hover layer and a table view.
Colours: validated two-slot categorical palette (blue, orange) against the
console surfaces (light #ffffff, dark #172232) plus reserved status colours,
always paired with an icon and a label.
"""
from __future__ import annotations

_STYLE = r"""
<style>
.tm { --surface-1:#ffffff; --plane:#f6f9fb; --ink:#1f2430; --ink-2:#4b5568; --muted:#6b7385;
  --grid:#e4ecf0; --axis:#c3ccd4; --ring:rgba(11,11,11,.10); --wash:rgba(42,120,214,.08);
  --series-1:#2a78d6; --series-2:#eb6834; --series-3:#1baf7a; --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
  --seq-100:#cde2fb; --seq-400:#3987e5; color:var(--ink); font-variant-numeric:normal; }
html[data-theme="dark"] .tm { --surface-1:#172232; --plane:#101a27; --ink:#f0f4f9; --ink-2:#bdcad9; --muted:#8d99a8;
  --grid:#25384a; --axis:#3c5163; --ring:rgba(255,255,255,.10); --wash:rgba(57,135,229,.14);
  --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70; --seq-100:#1c3552; --seq-400:#3987e5; }
.tm * { box-sizing:border-box; }
.tm .tm-head { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
.tm .tm-filters label { display:inline-flex; gap:6px; align-items:center; font-size:14px; color:var(--ink-2); }
.tm .tm-filters input[type=date] { font:inherit; font-size:14px; padding:6px 8px; border-radius:9px; border:1px solid var(--ring); background:var(--surface-1); color:var(--ink); }
.tm .q-cov { font-size:12px; color:var(--ink-2); }
.tm .hatch { background:repeating-linear-gradient(45deg, var(--grid) 0 4px, transparent 4px 8px); border:1px dashed var(--axis); }
.tm .tm-live { display:flex; align-items:center; gap:10px; color:var(--ink-2); font-size:14px; }
.tm .tm-dot { width:8px; height:8px; border-radius:50%; background:var(--good); box-shadow:0 0 0 3px rgba(12,163,12,.18); }
.tm .tm-dot.off { background:var(--muted); box-shadow:none; }
.tm .tm-filters { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:18px 0 6px; padding:10px;
  background:var(--surface-1); border:1px solid var(--ring); border-radius:12px; position:sticky; top:0; z-index:5; }
.tm .tm-seg { display:inline-flex; border:1px solid var(--ring); border-radius:9px; overflow:hidden; }
.tm .tm-seg button { border:0; background:transparent; color:var(--ink-2); padding:7px 11px; font:inherit; font-size:14px; cursor:pointer; }
.tm .tm-seg button[aria-pressed="true"] { background:var(--wash); color:var(--ink); font-weight:600; }
.tm select, .tm input[type="search"] { font:inherit; font-size:14px; padding:7px 9px; border-radius:9px; border:1px solid var(--ring);
  background:var(--surface-1); color:var(--ink); max-width:240px; }
.tm input[type="search"] { min-width:300px; max-width:360px; }
.tm .tm-btn { font:inherit; font-size:14px; padding:7px 11px; border-radius:9px; border:1px solid var(--ring); background:transparent; color:var(--ink); cursor:pointer; }
.tm .tm-btn:hover, .tm .tm-seg button:hover { background:var(--wash); }
.tm .tm-chips { display:flex; flex-wrap:wrap; gap:6px; margin:4px 0 14px; min-height:4px; }
.tm .tm-chip { display:inline-flex; gap:6px; align-items:center; padding:3px 9px; border-radius:999px; background:var(--wash); font-size:13px; }
.tm .tm-chip button { border:0; background:none; color:var(--ink-2); cursor:pointer; font-size:14px; padding:0; }
.tm .tm-grid { display:grid; grid-template-columns:repeat(12,1fr); gap:14px; }
.tm .tm-card { grid-column:span 12; background:var(--surface-1); border:1px solid var(--ring); border-radius:14px; padding:16px 18px; min-width:0; }
.tm .tm-card.half { grid-column:span 6; } .tm .tm-card.third { grid-column:span 4; }
@media (max-width: 1000px) { .tm .tm-card.half, .tm .tm-card.third { grid-column:span 12; } }
.tm .tm-card h2 { font-size:16px; margin:0 0 2px; } .tm .tm-sub { color:var(--ink-2); font-size:13px; margin:0 0 12px; }
.tm .tm-cardhead { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }
.tm .tm-kpis { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:14px; margin-bottom:14px; }
@media (max-width: 1000px) { .tm .tm-kpis { grid-template-columns:repeat(2,minmax(0,1fr)); } }
.tm .tm-tile { background:var(--surface-1); border:1px solid var(--ring); border-radius:14px; padding:14px 16px; }
.tm .tm-tile .label { color:var(--ink-2); font-size:13px; } .tm .tm-tile .value { font-size:28px; font-weight:650; margin:4px 0 2px; }
.tm .tm-tile .hint { color:var(--muted); font-size:12px; min-height:16px; }
.tm .tm-insights { display:grid; gap:8px; margin-bottom:14px; }
.tm .tm-insight { display:flex; gap:12px; align-items:flex-start; padding:10px 14px; border-radius:12px; background:var(--surface-1);
  border:1px solid var(--ring); cursor:pointer; text-align:left; font:inherit; color:inherit; width:100%; }
.tm .tm-insight:hover { background:var(--wash); }
.tm .tm-insight strong { display:block; font-size:15px; } .tm .tm-insight span.d { color:var(--ink-2); font-size:13px; }
.tm .sev { flex:0 0 auto; display:inline-flex; align-items:center; gap:5px; font-size:12px; font-weight:600; padding:2px 8px; border-radius:999px;
  border:1px solid currentColor; white-space:nowrap; }
.tm .sev svg { width:12px; height:12px; }
.tm .sev.critical { color:var(--critical); } .tm .sev.serious { color:var(--serious); } .tm .sev.warning { color:#b07a00; } .tm .sev.info { color:var(--series-1); } .tm .sev.good { color:var(--good); }
html[data-theme="dark"] .tm .sev.warning { color:var(--warning); }
.tm .tm-chart { position:relative; } .tm svg.chart { width:100%; height:auto; display:block; overflow:visible; }
.tm svg text { fill:var(--muted); font-size:11px; font-variant-numeric:tabular-nums; }
.tm .tm-legend { display:flex; gap:14px; flex-wrap:wrap; font-size:13px; color:var(--ink-2); margin-bottom:6px; }
.tm .tm-legend i { display:inline-block; width:14px; height:2px; border-radius:2px; vertical-align:middle; margin-right:6px; }
.tm .tm-legend i.box { height:10px; width:10px; border-radius:3px; }
.tm .tm-tip { position:fixed; pointer-events:none; z-index:50; background:var(--surface-1); color:var(--ink); border:1px solid var(--ring);
  border-radius:10px; padding:8px 10px; font-size:13px; box-shadow:0 8px 24px rgba(0,0,0,.14); min-width:140px; display:none; }
.tm .tm-tip .row { display:flex; justify-content:space-between; gap:14px; align-items:center; }
.tm .tm-tip .row b { font-variant-numeric:tabular-nums; } .tm .tm-tip .k { color:var(--ink-2); display:flex; align-items:center; gap:6px; }
.tm .tm-tip .k i { width:12px; height:2px; display:inline-block; border-radius:2px; }
.tm table { width:100%; border-collapse:collapse; font-size:13px; }
.tm th { text-align:left; color:var(--ink-2); font-weight:600; border-bottom:1px solid var(--grid); padding:7px 8px; white-space:nowrap; cursor:pointer; user-select:none; }
.tm td { border-bottom:1px solid var(--grid); padding:7px 8px; vertical-align:top; }
.tm td.num, .tm th.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.tm .st-error svg, .tm .tm-empty svg { vertical-align:-1px; }
.tm tbody tr[tabindex] { cursor:pointer; } .tm tbody tr[tabindex]:hover, .tm tbody tr[tabindex]:focus { background:var(--wash); outline:none; }
.tm .tm-scroll { overflow:auto; max-height:460px; }
.tm code, .tm .mono { font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12px; }
.tm .bar { height:8px; border-radius:0 4px 4px 0; background:var(--series-1); min-width:2px; }
.tm .barcell { display:flex; align-items:center; gap:8px; } .tm .barcell .bar { flex:0 0 auto; }
.tm .tm-badge { display:inline-flex; align-items:center; gap:4px; padding:1px 7px; border-radius:999px; font-size:12px; border:1px solid var(--ring); white-space:nowrap; }
.tm .tm-badge svg { width:11px; height:11px; }
.tm .st-ok { color:var(--good); } .tm .st-error { color:var(--critical); } .tm .st-aborted { color:var(--critical); } .tm .st-running { color:var(--series-1); } .tm .st-other { color:var(--ink-2); }
.tm .group { border:1px solid var(--ring); border-radius:12px; padding:12px 14px; margin-bottom:10px; }
.tm .group-head { display:flex; gap:12px; align-items:center; justify-content:space-between; flex-wrap:wrap; }
.tm .group-head strong { font-size:15px; } .tm .group .meta { color:var(--ink-2); font-size:13px; margin-top:4px; }
.tm details summary { cursor:pointer; color:var(--series-1); font-size:13px; margin-top:8px; }
.tm .frames { margin:6px 0 0; padding-left:18px; } .tm .frames li { font-family:ui-monospace, Menlo, monospace; font-size:12px; color:var(--ink-2); }
.tm .frames li:last-child { color:var(--ink); font-weight:600; }
.tm .steps { margin:6px 0 0; padding-left:18px; font-size:13px; }
.tm .linkbtn { border:0; background:none; color:var(--paars, #5D3297); cursor:pointer; padding:0; font:inherit; font-size:13px; text-decoration:underline; }
.tm .tm-empty { color:var(--muted); font-size:14px; padding:14px 0; }
.tm .tm-loading { opacity:.55; transition:opacity .2s; }
.tm dialog.tm-drawer { margin:0 0 0 auto; height:100vh; max-height:100vh; width:min(760px,100vw); border:0; padding:0; background:var(--plane); color:var(--ink);
  box-shadow:-12px 0 40px rgba(0,0,0,.25); }
.tm dialog.tm-drawer::backdrop { background:rgba(10,20,30,.35); }
.tm .drawer-in { padding:20px 22px 40px; display:grid; gap:14px; }
.tm .drawer-top { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }
.tm .kv { display:grid; grid-template-columns:max-content 1fr; gap:4px 14px; font-size:13px; } .tm .kv dt { color:var(--ink-2); } .tm .kv dd { margin:0; word-break:break-all; }
.tm .tree-row { display:grid; grid-template-columns:minmax(150px,38%) 1fr 78px; gap:8px; align-items:center; font-size:12px; padding:3px 0; }
.tm .tree-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-family:ui-monospace, Menlo, monospace; }
.tm .tree-track { position:relative; height:12px; background:var(--grid); border-radius:0 4px 4px 0; }
.tm .tree-inc { position:absolute; left:0; top:0; bottom:0; background:var(--seq-100); border-radius:0 4px 4px 0; }
.tm .tree-exc { position:absolute; left:0; top:0; bottom:0; background:var(--series-1); border-radius:0 4px 4px 0; }
.tm .help { color:var(--ink-2); font-size:13px; }
.tm .sr { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }
@media (forced-colors: active) { .tm .bar, .tm .tree-exc { forced-color-adjust:none; background:CanvasText; } }
</style>
"""

_BODY = r"""
<section class="room tm" id="tm" data-initial-tab="__TAB__">
  <p class="eyebrow">Instellingen</p>
  <h1>Inzicht</h1>
  <p class="lead">Eén plek om te begrijpen wat Metis doet en hoe het werk verloopt: het systeem tot op de milliseconde, de kwaliteit van voorstellen en review, de verwerking per document en de controles. Klik door van het ene naar het andere.</p>
  __TABS__
  <div class="tm-panel" data-panel="systeem" role="tabpanel">
  <div class="tm-head">
    <p class="tm-sub" style="margin:0">Elk verzoek met fasen in milliseconden, fouten gegroepeerd per oorzaak, samenhang over routes, fasen en deploys. Ververst elke 30 seconden zolang dit tabblad open is.</p>
    <div class="tm-live">
      <span class="tm-dot" id="tm-dot" aria-hidden="true"></span>
      <span id="tm-updated">Laden…</span>
      <button class="tm-btn" id="tm-auto" type="button" aria-pressed="true">Live: aan</button>
      <a class="tm-btn" id="tm-export" href="/telemetry/api/export?window=24h">Exporteer (JSONL)</a>
    </div>
  </div>

  <div class="tm-filters" role="search" aria-label="Filters">
    <div class="tm-seg" id="tm-window" role="group" aria-label="Tijdvenster">
      <button type="button" data-w="15m">15 min</button><button type="button" data-w="1h">1 uur</button>
      <button type="button" data-w="6h">6 uur</button><button type="button" data-w="24h">24 uur</button><button type="button" data-w="7d">7 dagen</button>
    </div>
    <label class="sr" for="tm-route">Route</label><select id="tm-route" data-f="route"><option value="">Alle routes</option></select>
    <label class="sr" for="tm-state">Uitkomst</label>
    <select id="tm-state" data-f="state"><option value="">Alle uitkomsten</option><option value="ok">Gelukt</option><option value="error">Fout</option>
      <option value="aborted">Afgebroken</option><option value="running">Lopend</option><option value="cancelled">Geannuleerd</option></select>
    <label class="sr" for="tm-status">Status</label>
    <select id="tm-status" data-f="status"><option value="">Alle statussen</option><option value="2xx">2xx</option><option value="3xx">3xx</option><option value="4xx">4xx</option><option value="5xx">5xx</option></select>
    <label class="sr" for="tm-commit">Deploy</label><select id="tm-commit" data-f="commit"><option value="">Alle deploys</option></select>
    <label class="sr" for="tm-q">Zoek</label><input type="search" id="tm-q" data-f="q" placeholder="Zoek op request-, trace-, poging- of document-id">
    <button class="tm-btn" type="button" id="tm-reset">Wis filters</button>
  </div>
  <div class="tm-chips" id="tm-chips" aria-live="polite"></div>

  <div id="tm-body">
    <div class="tm-insights" id="tm-insights" aria-label="Inzichten"></div>
    <div class="tm-kpis" id="tm-kpis"></div>
    <div class="tm-grid">
      <div class="tm-card half">
        <div class="tm-cardhead"><div><h2>Responstijd</h2><p class="tm-sub">p50 en p95 per tijdvak, in milliseconden</p></div>
          <button class="tm-btn" type="button" data-table="latency">Tabel</button></div>
        <div class="tm-legend"><span><i style="background:var(--series-1)"></i>p50</span><span><i style="background:var(--series-2)"></i>p95</span></div>
        <div class="tm-chart" id="chart-latency"></div>
      </div>
      <div class="tm-card half">
        <div class="tm-cardhead"><div><h2>Verzoeken en fouten</h2><p class="tm-sub">Aantal verzoeken per tijdvak; fouten en afgebroken verzoeken apart</p></div>
          <button class="tm-btn" type="button" data-table="volume">Tabel</button></div>
        <div class="tm-legend"><span><i class="box" style="background:var(--series-1)"></i>Gelukt</span><span><i class="box" style="background:var(--critical)"></i>⚠ Fout of afgebroken</span></div>
        <div class="tm-chart" id="chart-volume"></div>
      </div>
      <div class="tm-card">
        <div class="tm-cardhead"><div><h2>Foutgroepen</h2><p class="tm-sub">Gegroepeerd per oorzaak (vingerafdruk van type en code-locatie), met uitleg en volgende stap</p></div></div>
        <div id="tm-errors"></div>
      </div>
      <div class="tm-card half">
        <h2>Routes</h2><p class="tm-sub">Klik op een route om alles daarop te filteren</p>
        <div class="tm-scroll" id="tm-routes"></div>
      </div>
      <div class="tm-card half">
        <h2>Waar gaat de tijd heen</h2><p class="tm-sub">Aandeel van de eigen (exclusieve) tijd per fase over alle verzoeken</p>
        <div id="tm-phases"></div>
      </div>
      <div class="tm-card half">
        <h2>Samenhang</h2><p class="tm-sub">Wat komt vaker voor bij fouten of trage verzoeken dan gemiddeld (lift ≥ 1,5×)</p>
        <div id="tm-correlations"></div>
      </div>
      <div class="tm-card half">
        <h2>Deploys</h2><p class="tm-sub">Per commit: verkeer, foutpercentage en p95, met verschil ten opzichte van de vorige</p>
        <div class="tm-scroll" id="tm-commits"></div>
      </div>
      <div class="tm-card">
        <div class="tm-cardhead"><div><h2>Verzoeken</h2><p class="tm-sub">Klik op een verzoek voor de fasenboom, fouten, logs en gerelateerde verzoeken</p></div>
          <div class="tm-seg" id="tm-reqmode" role="group" aria-label="Weergave"><button type="button" data-m="recent" aria-pressed="true">Recent</button><button type="button" data-m="slowest">Traagst</button></div></div>
        <div class="tm-scroll" id="tm-requests"></div>
      </div>
      <div class="tm-card third">
        <h2>Processen</h2><p class="tm-sub">Starts en stops van workers (herstarts vallen hier op)</p>
        <div id="tm-process"></div>
      </div>
      <div class="tm-card" style="grid-column:span 8">
        <h2>Over deze gegevens</h2>
        <p class="help" id="tm-about"></p>
      </div>
    </div>
  </div>
  </div>

  <div class="tm-panel" data-panel="kwaliteit" role="tabpanel" hidden>
    <form class="tm-filters" id="q-form" aria-label="Ingestcohort">
      <label>Vanaf <input type="date" name="from"></label>
      <label>Tot en met <input type="date" name="to"></label>
      <label>Inhoudstype <input type="search" name="kind" style="min-width:120px"></label>
      <label>Ingesttype <input type="search" name="ingest" style="min-width:120px"></label>
      <label>Route <select name="route"><option value="">Alle routes</option><option value="deterministic">Deterministisch</option>
        <option value="semantic">Semantisch</option><option value="mixed">Gemengd</option><option value="remainder">Resterende bronpassages</option><option value="unknown">Onbekend</option></select></label>
      <button class="tm-btn" type="submit">Toon meting</button>
      <a class="tm-btn" id="q-table" href="/settings/quality">Tabelweergave en rapporthistorie</a>
    </form>
    <p class="tm-sub" id="q-status">Nog niet geladen.</p>
    <div id="q-body">
      <div class="tm-kpis" id="q-kpis"></div>
      <div class="tm-grid">
        <div class="tm-card half"><h2>Hoe vaak is een voorstel direct bruikbaar?</h2><p class="tm-sub">Eerste inhoudelijke besluiten per route; onvolledig meetbaar is gemarkeerd, nooit als succes geteld</p><div id="q-direct"></div></div>
        <div class="tm-card half"><h2>Herstel, correcties en afwijzingen</h2><p class="tm-sub">Aantallen per route van het voorstel</p>
          <div class="tm-legend"><span><i class="box" style="background:var(--series-1)"></i>Herstelverzoeken</span><span><i class="box" style="background:var(--series-2)"></i>Correcties</span><span><i class="box" style="background:var(--series-3)"></i>Afwijzingen</span></div>
          <div id="q-repairs"></div></div>
        <div class="tm-card"><h2>Waar blijft werk liggen?</h2><p class="tm-sub">Open passages per bron, met leeftijd van de onafgeronde bron. Klik voor de documentdiagnose of de verzoeken op dit document.</p><div class="tm-scroll" id="q-open"></div></div>
        <div class="tm-card half"><h2>Open werk over tijd</h2><p class="tm-sub">Open passages per bewaarde meting (rapporthistorie)</p><div class="tm-chart" id="q-trend"></div></div>
        <div class="tm-card half"><h2>Wat wordt er aangepast?</h2><p class="tm-sub">Gewijzigde inhoud bij besluiten en correcties</p><div id="q-fields"></div></div>
        <div class="tm-card half"><h2>Verwerkingsruns</h2><p class="tm-sub">Uitkomst van de verwerkingsruns in het cohort</p><div id="q-runs"></div></div>
        <div class="tm-card half"><h2>Meetdefinities en beperkingen</h2><div id="q-defs" class="help"></div></div>
      </div>
    </div>
  </div>

  <div class="tm-panel" data-panel="documenten" role="tabpanel" hidden>
    <div class="tm-filters" aria-label="Documenten filteren">
      <label class="sr" for="d-q">Zoek document</label><input type="search" id="d-q" placeholder="Zoek op titel of document-id">
      <label class="sr" for="d-state">Toestand</label><select id="d-state"><option value="">Alle documenten</option><option value="blocked">Met geblokkeerde kandidaten</option><option value="errors">Met fouten in het systeem (24 uur)</option><option value="retry">Nieuwe poging mogelijk</option></select>
      <span class="tm-sub" id="d-status" style="margin:0"></span>
    </div>
    <div class="tm-card"><h2>Verwerking en diagnostiek per document</h2><p class="tm-sub">Verwerkingsstatus, geblokkeerde kandidaten met hun belangrijkste redenen en systeemfouten in de laatste 24 uur. Alleen documenten waarvoor je bevoegd bent.</p><div class="tm-scroll" id="d-table" style="max-height:none"></div><p><button type="button" class="linkbtn" id="d-more" hidden>Meer documenten laden</button></p></div>
  </div>

  <div class="tm-panel" data-panel="controles" role="tabpanel" hidden>
    <p class="tm-sub">Controles en experimenten die je bewust start. Hun resultaten blijven bewaard en zijn geen inhoudelijke beoordeling van documenten.</p>
    <div class="doc-list">
      <a class="doc-card" style="text-decoration:none;" href="/audit"><p class="doc-title">Audit &amp; diagnostiek</p><p>Open controles, experimenten en bewaarde resultaten.</p></a>
      <a class="doc-card" style="text-decoration:none;" href="/audit/semantic-safety"><p class="doc-title">Semantische veiligheidstests</p><p>Vaste testgevallen voor weglatingen, voorwaarden, uitzonderingen en ontkenningen.</p></a>
      <a class="doc-card" style="text-decoration:none;" href="/settings/quality/compare"><p class="doc-title">Routevergelijking</p><p>Vergelijk verwerkingsroutes op dezelfde bron.</p></a>
      <a class="doc-card" style="text-decoration:none;" href="/audit/review-signals"><p class="doc-title">Reviewsignalen</p><p>Signalen uit review die op structurele problemen wijzen.</p></a>
      <a class="doc-card" style="text-decoration:none;" href="/audit/archive"><p class="doc-title">Archief</p><p>Gearchiveerde audits terugzetten of definitief verwijderen.</p></a>
      <a class="doc-card" style="text-decoration:none;" href="/settings/technical/exports"><p class="doc-title">Exports</p><p>Passages, verwerkingsbewijs en diagnostiek als bestand.</p></a>
    </div>
  </div>

  <div class="tm-tip" id="tm-tip" role="status"></div>
  <dialog class="tm-drawer" id="tm-drawer" aria-label="Verzoekdetail"><div class="drawer-in" id="tm-drawer-in"></div></dialog>
</section>
"""

_SCRIPT = r"""
<script>
(() => {
const root = document.getElementById('tm');
const $ = (sel, scope = root) => scope.querySelector(sel);
const params = new URLSearchParams(location.search);
const state = { window: params.get('window') || '24h', filters: {}, mode: 'recent', data: null, timer: null, live: true, sort: {},
  tab: root.dataset.initialTab || 'systeem', loaded: {}, qparams: '', docs: null };
// The URL carries the filters of the open tab only: quality filters on Kwaliteit, telemetry filters elsewhere.
if (state.tab === 'kwaliteit') {
  const quality = new URLSearchParams();
  for (const key of ['from', 'to', 'kind', 'ingest', 'route', 'report']) if (params.get(key)) quality.set(key, params.get(key));
  state.qparams = quality.toString();
} else {
  for (const key of ['route', 'state', 'status', 'commit', 'q', 'error']) if (params.get(key)) state.filters[key] = params.get(key);
}

const LABELS = { route: 'Route', state: 'Uitkomst', status: 'Status', commit: 'Deploy', q: 'Zoek', error: 'Foutgroep' };
const STATE_NL = { ok: 'Gelukt', error: 'Fout', aborted: 'Afgebroken', running: 'Lopend', cancelled: 'Geannuleerd', incomplete: 'Onvolledig' };
const SEV_NL = { critical: 'Kritiek', serious: 'Ernstig', warning: 'Let op', info: 'Inzicht', good: 'Goed' };
const ICON = {
  critical: '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M6 1 11 10H1z" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M6 4.5v2.5M6 8.6v.1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
  serious: '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4.8" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M6 3.4v3M6 8.4v.1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
  warning: '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M6 1 11 10H1z" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>',
  info: '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4.8" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M6 5.4v3M6 3.5v.1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
  good: '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M2 6.5 5 9l5-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
};

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) if (child !== null && child !== undefined) node.append(child.nodeType ? child : document.createTextNode(String(child)));
  return node;
}
function icon(kind) { const span = el('span'); span.innerHTML = ICON[kind] || ''; return span.firstChild; }
function sev(kind) { return el('span', { class: 'sev ' + kind }, icon(kind), SEV_NL[kind] || kind); }
const nf = new Intl.NumberFormat('nl-NL');
const ms = (value) => value === null || value === undefined ? '—' : value >= 10000 ? nf.format(Math.round(value / 100) / 10) + ' s' : nf.format(Math.round(value)) + ' ms';
const pct = (value) => value === null || value === undefined ? '—' : (value * 100).toLocaleString('nl-NL', { maximumFractionDigits: 1 }) + '%';
const compact = (value) => value >= 1000 ? (value / 1000).toLocaleString('nl-NL', { maximumFractionDigits: 1 }) + 'K' : nf.format(value);
const time = (t, long) => new Date(t * 1000).toLocaleString('nl-NL', long ? { dateStyle: 'short', timeStyle: 'medium' } : { hour: '2-digit', minute: '2-digit' });
const shortId = (value) => value ? String(value).slice(0, 8) : '—';
function stateBadge(value) {
  const cls = value === 'ok' ? 'st-ok' : value === 'error' || value === 'aborted' ? 'st-error' : value === 'running' ? 'st-running' : 'st-other';
  const kind = value === 'ok' ? 'good' : value === 'error' || value === 'aborted' ? 'critical' : 'info';
  return el('span', { class: 'tm-badge ' + cls }, icon(kind), STATE_NL[value] || value);
}

function query() {
  const q = new URLSearchParams({ window: state.window, ...state.filters });
  return q.toString();
}
function syncUrl() {
  const extra = state.tab === 'systeem' ? '&' + query() : state.tab === 'kwaliteit' && state.qparams ? '&' + state.qparams : '';
  history.replaceState(null, '', location.pathname + '?tab=' + state.tab + extra);
  $('#tm-export').href = '/telemetry/api/export?window=' + state.window;
}

async function load() {
  const body = $('#tm-body');
  body.classList.add('tm-loading');
  try {
    const response = await fetch('/telemetry/api/summary?' + query(), { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    state.data = await response.json();
    render();
    $('#tm-updated').textContent = 'Bijgewerkt ' + new Date().toLocaleTimeString('nl-NL');
    $('#tm-dot').classList.toggle('off', !state.live);
  } catch (error) {
    $('#tm-updated').textContent = 'Kon telemetrie niet laden (' + error.message + ')';
    $('#tm-dot').classList.add('off');
  } finally { body.classList.remove('tm-loading'); }
}
function schedule() { clearInterval(state.timer); if (state.live) state.timer = setInterval(() => { if (!document.hidden && !$('#tm-drawer').open && state.tab === 'systeem') load(); }, 30000); }
function setFilter(key, value) { if (value) state.filters[key] = value; else delete state.filters[key]; syncUrl(); renderControls(); load(); }
function applyFilters(filters) { for (const [key, value] of Object.entries(filters || {})) state.filters[key] = value; syncUrl(); renderControls(); load(); window.scrollTo({ top: root.offsetTop, behavior: 'smooth' }); }

function fillSelect(id, values, current, label) {
  const select = $(id);
  const keep = select.value;
  select.replaceChildren(el('option', { value: '' , text: label }));
  for (const value of values || []) select.append(el('option', { value, text: id === '#tm-commit' ? String(value).slice(0, 12) : value }));
  if (current && !(values || []).includes(current)) select.append(el('option', { value: current, text: current }));
  select.value = current || '';
}
function renderControls() {
  for (const button of root.querySelectorAll('#tm-window button')) button.setAttribute('aria-pressed', String(button.dataset.w === state.window));
  for (const select of root.querySelectorAll('[data-f]')) if (select.tagName === 'SELECT' || select.type === 'search') select.value = state.filters[select.dataset.f] || '';
  const chips = $('#tm-chips');
  chips.replaceChildren(...Object.entries(state.filters).map(([key, value]) => el('span', { class: 'tm-chip' },
    `${LABELS[key] || key}: ${key === 'commit' ? value.slice(0, 12) : value}`,
    el('button', { type: 'button', 'aria-label': 'Verwijder filter ' + (LABELS[key] || key), onclick: () => setFilter(key, '') }, '×'))));
}

function render() {
  const data = state.data;
  fillSelect('#tm-route', data.options.routes, state.filters.route, 'Alle routes');
  fillSelect('#tm-commit', data.options.commits, state.filters.commit, 'Alle deploys');
  renderControls();
  renderInsights(data.insights);
  renderKpis(data);
  lineChart($('#chart-latency'), data.series, [{ key: 'p50', label: 'p50', color: 'var(--series-1)' }, { key: 'p95', label: 'p95', color: 'var(--series-2)' }], data.window.bucket_seconds);
  stackChart($('#chart-volume'), data.series, data.window.bucket_seconds);
  renderErrors(data.errors);
  renderRoutes(data.routes);
  renderPhases(data.phases);
  renderCorrelations(data.correlations);
  renderCommits(data.commits);
  renderRequests();
  renderProcess(data.process);
  $('#tm-about').textContent = `${nf.format(data.telemetry.events)} events in dit venster, opgeslagen ${data.telemetry.store === 'disk' ? 'op schijf (alle workers, 7 dagen, max. 64 MB)' : 'alleen in het geheugen van deze worker'}. ` +
    'Alleen vaste velden: route-sjablonen, statussen, tijden, fasenamen, begrensde id’s, commit, exceptietype, foutcode en Metis-codelocaties. Documenten alleen als pseudoniem (doc_ref). Nooit inhoud, gebruikers, SQL of foutteksten.' +
    (data.telemetry.dropped ? ` ${data.telemetry.dropped} events konden niet worden vastgelegd.` : '') +
    (data.telemetry.truncated ? ' Alleen de nieuwste 50.000 events zijn geanalyseerd; kies een korter venster voor het volledige beeld.' : '');
}

function renderInsights(items) {
  const box = $('#tm-insights');
  box.replaceChildren(...(items || []).map((item) => el('button', { type: 'button', class: 'tm-insight', onclick: () => applyFilters(item.filter) },
    sev(item.severity), el('div', {}, el('strong', { text: item.title }), el('span', { class: 'd', text: item.detail })))));
}

function sparkline(values, color) {
  const w = 120, h = 28, max = Math.max(1, ...values.map((v) => v || 0));
  const points = values.map((v, i) => `${(i / Math.max(1, values.length - 1)) * w},${h - ((v || 0) / max) * (h - 4) - 2}`).join(' ');
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.setAttribute('width', w); svg.setAttribute('height', h); svg.setAttribute('aria-hidden', 'true');
  const line = document.createElementNS(svg.namespaceURI, 'polyline');
  line.setAttribute('points', points); line.setAttribute('fill', 'none'); line.setAttribute('stroke', color || 'var(--series-1)');
  line.setAttribute('stroke-width', '2'); line.setAttribute('stroke-linejoin', 'round'); line.setAttribute('stroke-linecap', 'round');
  svg.append(line); return svg;
}
function renderKpis(data) {
  const k = data.kpis, s = data.series;
  const tiles = [
    ['Verzoeken', compact(k.requests), `${k.running} lopend`, s.map((b) => b.count)],
    ['Foutpercentage', pct(k.error_rate), `${nf.format(k.errors)} fout of afgebroken`, s.map((b) => b.count ? b.errors / b.count : 0)],
    ['Responstijd p95', ms(k.p95_ms), `p50 ${ms(k.p50_ms)} · p99 ${ms(k.p99_ms)}`, s.map((b) => b.p95 || 0)],
    ['Afgebroken', nf.format(k.aborted), k.aborted ? '⚠ crash, time-out of herstart' : 'geen', null],
    ['Wachten op store-lock (p95)', ms(k.lock_wait_p95_ms), 'tijd tot de Storeopdracht mag starten', null],
  ];
  $('#tm-kpis').replaceChildren(...tiles.map(([label, value, hint, trend]) => el('div', { class: 'tm-tile' },
    el('div', { class: 'label', text: label }), el('div', { class: 'value', text: value }), el('div', { class: 'hint', text: hint }),
    trend && trend.length > 1 ? sparkline(trend) : null)));
}

const tip = $('#tm-tip');
function showTip(event, title, rows) {
  tip.replaceChildren(el('div', { style: 'color:var(--ink-2);margin-bottom:4px', text: title }),
    ...rows.map(([label, value, color]) => el('div', { class: 'row' }, el('b', { text: value }), el('span', { class: 'k' }, color ? el('i', { style: `background:${color}` }) : null, label))));
  tip.style.display = 'block';
  const x = Math.min(window.innerWidth - tip.offsetWidth - 12, event.clientX + 14);
  const y = Math.min(window.innerHeight - tip.offsetHeight - 12, event.clientY + 14);
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
}
function hideTip() { tip.style.display = 'none'; }

function svgEl(tag, attrs) { const node = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v); return node; }
function niceMax(value) { if (!value) return 1; const p = Math.pow(10, Math.floor(Math.log10(value))); for (const m of [1, 2, 2.5, 5, 10]) if (value <= m * p) return m * p; return 10 * p; }
function axisLabels(svg, series, x, H, bucket) {
  const n = series.length; const every = Math.max(1, Math.ceil(n / 6));
  series.forEach((b, i) => { if (i % every === 0) { const t = svgEl('text', { x: x(i), y: H + 16, 'text-anchor': 'middle' }); t.textContent = bucket >= 86400 ? new Date(b.t * 1000).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' }) : time(b.t); svg.append(t); } });
}
function gridY(svg, max, W, H, L, fmt) {
  for (let i = 0; i <= 4; i++) {
    const value = (max / 4) * i, y = H - (value / max) * H;
    svg.append(svgEl('line', { x1: L, x2: W, y1: y, y2: y, stroke: i ? 'var(--grid)' : 'var(--axis)', 'stroke-width': 1 }));
    const t = svgEl('text', { x: L - 6, y: y + 4, 'text-anchor': 'end' }); t.textContent = fmt(value); svg.append(t);
  }
}
function lineChart(box, series, lines, bucket) {
  box.replaceChildren();
  if (!series.length || !series.some((b) => lines.some((l) => b[l.key] !== null))) { box.append(el('p', { class: 'tm-empty', text: 'Geen afgeronde verzoeken in dit venster.' })); return; }
  const W = 640, H = 200, L = 52, R = 40;
  const max = niceMax(Math.max(...series.flatMap((b) => lines.map((l) => b[l.key] || 0))));
  const x = (i) => L + (series.length === 1 ? (W - L - R) / 2 : (i / (series.length - 1)) * (W - L - R));
  const y = (v) => H - (v / max) * H;
  const svg = svgEl('svg', { viewBox: `0 -14 ${W} ${H + 38}`, class: 'chart', role: 'img', 'aria-label': 'Responstijd p50 en p95 over tijd' });
  gridY(svg, max, W - R, H, L, (v) => v >= 1000 ? (v / 1000).toLocaleString('nl-NL') + ' s' : Math.round(v) + '');
  axisLabels(svg, series, x, H, bucket);
  for (const line of lines) {
    const pts = series.map((b, i) => b[line.key] === null ? null : [x(i), y(b[line.key])]);
    let d = ''; pts.forEach((p, i) => { if (!p) return; d += (d && pts[i - 1] ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1); });
    svg.append(svgEl('path', { d, fill: 'none', stroke: line.color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    const last = [...pts].reverse().find(Boolean);
    if (last) {
      svg.append(svgEl('circle', { cx: last[0], cy: last[1], r: 4, fill: line.color, stroke: 'var(--surface-1)', 'stroke-width': 2 }));
      const t = svgEl('text', { x: last[0] + 7, y: last[1] + 4 }); t.textContent = line.label; svg.append(t);
    }
  }
  const cross = svgEl('line', { y1: 0, y2: H, stroke: 'var(--axis)', 'stroke-width': 1, visibility: 'hidden' });
  svg.append(cross);
  const hit = svgEl('rect', { x: L, y: 0, width: W - L - R, height: H, fill: 'transparent' });
  hit.addEventListener('pointermove', (event) => {
    const box = svg.getBoundingClientRect(); const px = (event.clientX - box.left) / box.width * W;
    const i = Math.max(0, Math.min(series.length - 1, Math.round(((px - L) / (W - L - R)) * (series.length - 1))));
    cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('visibility', 'visible');
    showTip(event, time(series[i].t, true), lines.map((l) => [l.label, ms(series[i][l.key]), l.color]).concat([['verzoeken', nf.format(series[i].count)]]));
  });
  hit.addEventListener('pointerleave', () => { cross.setAttribute('visibility', 'hidden'); hideTip(); });
  svg.append(hit); box.append(svg);
  box.append(tableFor(box, 'latency', ['Tijdvak', 'p50', 'p95', 'Verzoeken'], series.map((b) => [time(b.t, true), ms(b.p50), ms(b.p95), nf.format(b.count)])));
}
function stackChart(box, series, bucket) {
  box.replaceChildren();
  if (!series.some((b) => b.count)) { box.append(el('p', { class: 'tm-empty', text: 'Geen verzoeken in dit venster.' })); return; }
  const W = 640, H = 200, L = 52, R = 10;
  const max = niceMax(Math.max(...series.map((b) => b.count)));
  const slot = (W - L - R) / series.length, bw = Math.max(2, Math.min(24, slot - 2));
  const svg = svgEl('svg', { viewBox: `0 -14 ${W} ${H + 38}`, class: 'chart', role: 'img', 'aria-label': 'Verzoeken en fouten per tijdvak' });
  gridY(svg, max, W - R, H, L, (v) => compact(Math.round(v)));
  const x = (i) => L + slot * i + slot / 2;
  axisLabels(svg, series, x, H, bucket);
  series.forEach((b, i) => {
    const ok = b.count - b.errors, hOk = (ok / max) * H, hErr = (b.errors / max) * H, left = x(i) - bw / 2;
    const r = Math.min(4, bw / 2);
    if (b.errors) svg.append(svgEl('path', { d: roundedTop(left, H - hErr, bw, hErr, ok ? 0 : r), fill: 'var(--critical)' }));
    if (ok) svg.append(svgEl('path', { d: roundedTop(left, H - hErr - hOk - (b.errors ? 2 : 0), bw, hOk, r), fill: 'var(--series-1)' }));
    const hit = svgEl('rect', { x: L + slot * i, y: 0, width: slot, height: H, fill: 'transparent', tabindex: 0 });
    const show = (event) => showTip(event, time(b.t, true), [['gelukt', nf.format(ok), 'var(--series-1)'], ['fout of afgebroken', nf.format(b.errors), 'var(--critical)']]);
    hit.addEventListener('pointermove', show); hit.addEventListener('pointerleave', hideTip);
    hit.addEventListener('focus', (event) => { const r2 = hit.getBoundingClientRect(); show({ clientX: r2.left + r2.width / 2, clientY: r2.top + 20 }); });
    hit.addEventListener('blur', hideTip);
    svg.append(hit);
  });
  box.append(svg);
  box.append(tableFor(box, 'volume', ['Tijdvak', 'Gelukt', 'Fout of afgebroken'], series.map((b) => [time(b.t, true), nf.format(b.count - b.errors), nf.format(b.errors)])));
}
function roundedTop(x, y, w, h, r) { if (h <= 0) return ''; r = Math.min(r, h); return `M${x} ${y + h}V${y + r}Q${x} ${y} ${x + r} ${y}H${x + w - r}Q${x + w} ${y} ${x + w} ${y + r}V${y + h}Z`; }
function tableFor(box, key, head, rows) {
  const wrap = el('div', { class: 'tm-scroll', hidden: true, 'data-table-for': key, style: 'margin-top:10px;max-height:220px' },
    el('table', {}, el('thead', {}, el('tr', {}, head.map((h, i) => el('th', { class: i ? 'num' : '', text: h })))),
      el('tbody', {}, rows.map((r) => el('tr', {}, r.map((c, i) => el('td', { class: i ? 'num' : '', text: c })))))));
  return wrap;
}

function renderErrors(groups) {
  const box = $('#tm-errors');
  if (!groups.length) { box.replaceChildren(el('p', { class: 'tm-empty' }, icon('good'), ' Geen fouten in dit venster.')); return; }
  const kindNl = { aborted: 'Afgebroken', unhandled: 'Onafgevangen', exception: 'Exceptie', status: 'Serverfout', log: 'Log', handled: 'Afgehandeld' };
  const kindSev = { aborted: 'critical', unhandled: 'critical', exception: 'serious', status: 'serious', log: 'warning', handled: 'info' };
  box.replaceChildren(...groups.slice(0, 25).map((g) => {
    const guidance = g.guidance || {};
    const frames = (guidance.frames || g.frames || []);
    return el('div', { class: 'group' },
      el('div', { class: 'group-head' },
        el('div', { style: 'display:flex;gap:10px;align-items:center;flex-wrap:wrap' }, sev(kindSev[g.kind] || 'info'),
          el('strong', { text: guidance.title || g.label }), el('span', { class: 'tm-badge', text: kindNl[g.kind] || g.kind })),
        el('div', { style: 'display:flex;gap:14px;align-items:center' }, sparkline(g.spark, kindSev[g.kind] === 'info' ? 'var(--series-1)' : 'var(--critical)'),
          el('strong', { text: nf.format(g.count) + '×' }),
          el('button', { type: 'button', class: 'tm-btn', onclick: () => applyFilters({ error: g.key }) }, 'Filter'))),
      el('div', { class: 'meta', text: `${guidance.explanation || ''} Eerst ${g.first_seen ? time(g.first_seen, true) : '—'}, laatst ${g.last_seen ? time(g.last_seen, true) : '—'}` +
        (g.routes.length ? ` · ${g.routes.join(', ')}` : '') + (g.commits.length ? ` · deploy ${g.commits.map((c) => String(c).slice(0, 8)).join(', ')}` : '') }),
      el('details', {}, el('summary', { text: 'Waar en wat nu?' }),
        frames.length ? el('div', {}, el('p', { class: 'help', text: 'Metis-codelocaties (diepste onderaan):' }), el('ol', { class: 'frames' }, frames.map((f) => el('li', { text: f })))) : null,
        (guidance.steps || []).length ? el('ol', { class: 'steps' }, guidance.steps.map((s) => el('li', { text: s }))) : null,
        g.examples.length ? el('p', { class: 'help' }, 'Voorbeelden: ', ...g.examples.map((id, i) => [i ? ', ' : '', el('button', { type: 'button', class: 'linkbtn', onclick: () => openRequest(id) }, shortId(id))])) : null));
  }));
}

function sortable(box, head, rows, key, onRow, rerender) {
  const sort = state.sort[key] || { i: -1, dir: 1 };
  if (sort.i >= 0) rows = [...rows].sort((a, b) => { const x = a.sort[sort.i], y = b.sort[sort.i]; return (x > y ? 1 : x < y ? -1 : 0) * sort.dir; });
  const table = el('table', {}, el('thead', {}, el('tr', {}, head.map(([label, num], i) => el('th', { class: num ? 'num' : '', scope: 'col', 'aria-sort': sort.i === i ? (sort.dir > 0 ? 'ascending' : 'descending') : 'none',
    onclick: () => { state.sort[key] = { i, dir: sort.i === i ? -sort.dir : (num ? -1 : 1) }; (rerender || render)(); } }, label + (sort.i === i ? (sort.dir > 0 ? ' ↑' : ' ↓') : ''))))),
    el('tbody', {}, rows.map((row) => el('tr', onRow ? { tabindex: 0, onclick: () => onRow(row), onkeydown: (e) => { if (e.key === 'Enter') onRow(row); } } : {},
      row.cells.map((cell, i) => el('td', { class: head[i][1] ? 'num' : '' }, cell))))));
  box.replaceChildren(rows.length ? table : el('p', { class: 'tm-empty', text: 'Geen gegevens.' }));
}
function renderRoutes(routes) {
  const max = Math.max(1, ...routes.map((r) => r.p95_ms || 0));
  sortable($('#tm-routes'), [['Route'], ['Aantal', 1], ['Fout%', 1], ['p50', 1], ['p95', 1], ['Topfase'], ['Queries', 1]],
    routes.map((r) => ({ route: r.route, sort: [r.route, r.count, r.error_rate, r.p50_ms || 0, r.p95_ms || 0, r.top_phase || '', r.avg_db_queries || 0],
      cells: [el('span', { class: 'mono', text: `${r.method} ${r.route}` }), nf.format(r.count),
        el('span', { class: r.errors ? 'st-error' : '' }, r.errors ? icon('critical') : null, ' ' + pct(r.error_rate)), ms(r.p50_ms),
        el('div', { class: 'barcell', style: 'justify-content:flex-end' }, el('span', { class: 'bar', style: `width:${Math.max(2, (r.p95_ms || 0) / max * 70)}px` }), ms(r.p95_ms)),
        el('span', { class: 'mono', text: r.top_phase || '—' }), r.avg_db_queries === null ? '—' : nf.format(r.avg_db_queries)] })),
    'routes', (row) => setFilter('route', row.route));
}
function renderPhases(phases) {
  const box = $('#tm-phases');
  if (!phases.length) { box.replaceChildren(el('p', { class: 'tm-empty', text: 'Nog geen fasen gemeten.' })); return; }
  const top = phases.slice(0, 12), max = Math.max(...top.map((p) => p.share)) || 1;
  box.replaceChildren(...top.map((p) => el('div', { class: 'tree-row', style: 'grid-template-columns:minmax(140px,34%) 1fr 120px', tabindex: 0,
    onpointermove: (e) => showTip(e, p.phase, [['aandeel', pct(p.share), 'var(--series-1)'], ['eigen tijd', ms(p.exclusive_ms)], ['aanroepen', nf.format(p.calls)], ['p95 per verzoek', ms(p.p95_inclusive_ms)]]),
    onpointerleave: hideTip },
    el('span', { class: 'tree-name', text: p.phase }),
    el('div', { class: 'tree-track', style: 'background:transparent' }, el('div', { class: 'tree-exc', style: `width:${(p.share / max) * 100}%` })),
    el('span', { class: 'num', style: 'text-align:right;font-variant-numeric:tabular-nums', text: `${pct(p.share)} · ${ms(p.exclusive_ms)}` }))));
}
function renderCorrelations(rows) {
  const box = $('#tm-correlations');
  if (!rows.length) { box.replaceChildren(el('p', { class: 'tm-empty', text: 'Geen opvallende samenhang (of te weinig fouten en trage verzoeken).' })); return; }
  sortable(box, [['Bij'], ['Factor'], ['Lift', 1], ['Onderbouwing', 1]], rows.map((r) => ({ raw: r, sort: [r.outcome, r.value, r.lift, r.support],
    cells: [r.outcome, el('span', {}, r.dimension + ': ', el('span', { class: 'mono', text: String(r.value).slice(0, 48) })),
      r.lift.toLocaleString('nl-NL') + '×', r.dimension === 'meting' ? `${r.mean_in} vs ${r.mean_out}` : `${pct(r.rate)} vs ${pct(r.base_rate)} (${r.support})`] })),
    'corr', (row) => { const r = row.raw; if (r.dimension === 'route') setFilter('route', r.value); else if (r.dimension === 'commit') setFilter('commit', r.value); });
}
function renderCommits(rows) {
  const delta = (value, unit) => value === undefined ? '—' : (value > 0 ? '+' : '') + (unit === 'pp' ? (value * 100).toLocaleString('nl-NL', { maximumFractionDigits: 1 }) + ' pp' : value.toLocaleString('nl-NL') + '×');
  sortable($('#tm-commits'), [['Deploy'], ['Sinds'], ['Verzoeken', 1], ['Fout%', 1], ['Δ fout', 1], ['p95', 1], ['Δ p95', 1]],
    [...rows].reverse().map((r) => ({ commit: r.commit, sort: [r.commit, r.first_seen, r.requests, r.error_rate, r.delta_error_rate || 0, r.p95_ms || 0, r.delta_p95_ratio || 0],
      cells: [el('span', { class: 'mono', text: String(r.commit).slice(0, 12) }), time(r.first_seen, true), nf.format(r.requests), pct(r.error_rate),
        el('span', { class: (r.delta_error_rate || 0) >= 0.02 ? 'st-error' : '' }, delta(r.delta_error_rate, 'pp')), ms(r.p95_ms),
        el('span', { class: (r.delta_p95_ratio || 0) >= 1.5 ? 'st-error' : '' }, delta(r.delta_p95_ratio))] })),
    'commits', (row) => setFilter('commit', row.commit));
}
function renderRequests() {
  const data = state.data, rows = state.mode === 'slowest' ? data.slowest : data.requests;
  for (const b of root.querySelectorAll('#tm-reqmode button')) b.setAttribute('aria-pressed', String(b.dataset.m === state.mode));
  const max = Math.max(1, ...rows.map((r) => r.duration_ms));
  sortable($('#tm-requests'), [['Tijd'], ['Route'], ['Uitkomst'], ['Status', 1], ['Duur', 1], ['Document'], ['Fout']],
    rows.map((r) => ({ id: r.request_id, sort: [r.started, r.route, r.state, r.status || 0, r.duration_ms, r.doc_ref || '', r.error_code || r.error_type || ''],
      cells: [time(r.started, true), el('span', { class: 'mono', text: `${r.method} ${r.route}` }), stateBadge(r.state), r.status === null ? '—' : String(r.status),
        el('div', { class: 'barcell', style: 'justify-content:flex-end' }, el('span', { class: 'bar', style: `width:${Math.max(2, r.duration_ms / max * 90)}px` }), ms(r.duration_ms)),
        el('span', { class: 'mono', text: r.doc_ref || '—' }),
        el('span', { class: 'mono', text: r.error_code || r.error_type || (r.state === 'aborted' && r.last_phase ? 'laatste fase: ' + r.last_phase : '') })] })),
    'requests', (row) => openRequest(row.id));
}
function renderProcess(rows) {
  const box = $('#tm-process');
  if (!rows.length) { box.replaceChildren(el('p', { class: 'tm-empty', text: 'Geen processen geregistreerd in dit venster.' })); return; }
  box.replaceChildren(el('table', {}, el('tbody', {}, rows.slice(0, 12).map((r) => el('tr', {},
    el('td', { text: time(r.t, true) }), el('td', {}, r.event === 'process_started' ? '▶ gestart' : '■ gestopt'), el('td', { class: 'mono', text: `pid ${r.pid} · ${String(r.commit || '').slice(0, 8)}` }))))));
}

async function openRequest(id) {
  const drawer = $('#tm-drawer'), inner = $('#tm-drawer-in');
  inner.replaceChildren(el('p', { text: 'Laden…' }));
  if (!drawer.open) drawer.showModal();
  const response = await fetch('/telemetry/api/request/' + encodeURIComponent(id), { credentials: 'same-origin' });
  if (!response.ok) { inner.replaceChildren(el('p', { text: 'Dit verzoek is niet (meer) beschikbaar.' }), closeButton()); return; }
  const d = await response.json(), r = d.request;
  const copy = (value) => value ? el('button', { type: 'button', class: 'linkbtn mono', title: 'Kopieer', onclick: () => navigator.clipboard && navigator.clipboard.writeText(value) }, value) : '—';
  const nodes = d.tree || [], max = Math.max(1, ...nodes.map((n) => n.inclusive_ms || 0));
  const g = d.guidance;
  inner.replaceChildren(...[
    el('div', { class: 'drawer-top' }, el('div', {}, el('p', { class: 'eyebrow', text: 'Verzoek' }), el('h2', { style: 'margin:0' }, el('span', { class: 'mono', text: `${r.method} ${r.route}` })),
      el('p', { class: 'help', style: 'margin:6px 0 0' }, stateBadge(r.state), `  ${r.status === null ? '' : 'HTTP ' + r.status + ' · '}${ms(r.duration_ms)} · ${time(r.started, true)}`)), closeButton()),
    g ? el('div', { class: 'tm-card', style: 'padding:14px' }, el('div', { style: 'display:flex;gap:8px;align-items:center' }, sev(r.state === 'aborted' ? 'critical' : 'serious'), el('strong', { text: g.title })),
      el('p', { class: 'help', text: g.explanation }), g.frames && g.frames.length ? el('ol', { class: 'frames' }, g.frames.map((f) => el('li', { text: f }))) : null,
      g.steps && g.steps.length ? el('ol', { class: 'steps' }, g.steps.map((s) => el('li', { text: s }))) : null) : null,
    el('div', { class: 'tm-card', style: 'padding:14px' }, el('h2', { text: 'Fasenboom' }), el('p', { class: 'tm-sub', text: 'Lichte balk: totale tijd van de fase (incl. onderliggende); donkere balk: eigen tijd. Inspringing = nesting.' }),
      nodes.length ? el('div', {}, nodes.map((n) => el('div', { class: 'tree-row', tabindex: 0,
        onpointermove: (e) => showTip(e, n.path, [['totaal', ms(n.inclusive_ms), 'var(--seq-100)'], ['eigen', ms(n.exclusive_ms), 'var(--series-1)'], ['aanroepen', nf.format(n.calls || 0)]]), onpointerleave: hideTip },
        el('span', { class: 'tree-name', style: `padding-left:${n.depth * 14}px`, text: n.name }),
        el('div', { class: 'tree-track' }, el('div', { class: 'tree-inc', style: `width:${(n.inclusive_ms || 0) / max * 100}%` }), el('div', { class: 'tree-exc', style: `width:${(n.exclusive_ms || 0) / max * 100}%` })),
        el('span', { style: 'text-align:right;font-variant-numeric:tabular-nums', text: ms(n.inclusive_ms) })))) : el('p', { class: 'tm-empty', text: 'Geen fasen gemeten voor dit verzoek.' })),
    el('div', { class: 'tm-card', style: 'padding:14px' }, el('h2', { text: 'Correlatie' }), el('dl', { class: 'kv' },
      el('dt', { text: 'Request-id' }), el('dd', {}, copy(r.request_id)), el('dt', { text: 'Trace-id' }), el('dd', {}, copy(r.trace_id)),
      el('dt', { text: 'Poging' }), el('dd', {}, copy(r.attempt_id)), el('dt', { text: 'Document (pseudoniem)' }), el('dd', {}, r.doc_ref ? el('span', {}, copy(r.doc_ref), ' · ', el('button', { type: 'button', class: 'linkbtn', onclick: () => { drawer.close(); setFilter('q', r.doc_ref); } }, 'alle verzoeken op dit document'), ' · ',
        el('button', { type: 'button', class: 'linkbtn', onclick: () => { drawer.close(); openDocuments(r.doc_ref); } }, 'documentdiagnose')) : '—'),
      el('dt', { text: 'Deploy' }), el('dd', { class: 'mono', text: r.commit }),
      el('dt', { text: 'Database' }), el('dd', { text: d.db && d.db.db_queries !== undefined ? `${d.db.db_queries} queries · ${ms(d.db.db_query_ms)} query · ${d.db.db_connections} verbindingen · ${ms(d.db.db_connect_ms)} verbinden` : '—' }))),
    el('div', { class: 'tm-card', style: 'padding:14px' }, el('h2', { text: 'Tijdlijn' }), el('table', {}, el('tbody', {}, d.timeline.map((t) => el('tr', {},
      el('td', { class: 'mono', text: new Date(t.t * 1000).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 }) }), el('td', { text: t.event }), el('td', { class: 'num', text: t.elapsed_ms === undefined || t.elapsed_ms === null ? '' : ms(t.elapsed_ms) }), el('td', { class: 'mono', text: t.phase || (t.status || '') }))))),
      d.related.length ? el('div', {}, el('h2', { style: 'margin-top:12px', text: 'Logregels van dit verzoek' }), el('table', {}, el('tbody', {}, d.related.map((t) => el('tr', {},
        el('td', { class: 'mono', text: new Date(t.t * 1000).toLocaleTimeString('nl-NL') }), el('td', { text: t.level || t.kind || '' }), el('td', { class: 'mono', text: (t.logger || t.event || '') }), el('td', { text: t.message || '' })))))) : null),
    d.same_snapshot.length ? el('div', { class: 'tm-card', style: 'padding:14px' }, el('h2', { text: 'Andere verzoeken op dit document' }), el('table', {}, el('tbody', {}, d.same_snapshot.map((o) => el('tr', { tabindex: 0, onclick: () => openRequest(o.request_id) },
      el('td', { text: time(o.started, true) }), el('td', { class: 'mono', text: `${o.method} ${o.route}` }), el('td', {}, stateBadge(o.state)), el('td', { class: 'num', text: ms(o.duration_ms) })))))) : null].filter(Boolean));
}
function closeButton() { return el('button', { type: 'button', class: 'tm-btn', onclick: () => $('#tm-drawer').close(), 'aria-label': 'Sluiten' }, 'Sluiten ✕'); }

root.addEventListener('click', (event) => {
  const w = event.target.closest('#tm-window button'); if (w) { state.window = w.dataset.w; syncUrl(); renderControls(); load(); }
  const m = event.target.closest('#tm-reqmode button'); if (m) { state.mode = m.dataset.m; renderRequests(); }
  const t = event.target.closest('[data-table]'); if (t) { const wrap = root.querySelector(`[data-table-for="${t.dataset.table}"]`); if (wrap) { wrap.hidden = !wrap.hidden; t.textContent = wrap.hidden ? 'Tabel' : 'Grafiek'; } }
});
for (const control of root.querySelectorAll('select[data-f]')) control.addEventListener('change', () => setFilter(control.dataset.f, control.value));
let typing; $('#tm-q').addEventListener('input', (e) => { clearTimeout(typing); typing = setTimeout(() => setFilter('q', e.target.value.trim()), 350); });
$('#tm-reset').addEventListener('click', () => { state.filters = {}; syncUrl(); renderControls(); load(); });
$('#tm-auto').addEventListener('click', (e) => { state.live = !state.live; e.target.setAttribute('aria-pressed', String(state.live)); e.target.textContent = 'Live: ' + (state.live ? 'aan' : 'uit'); $('#tm-dot').classList.toggle('off', !state.live); schedule(); });
$('#tm-drawer').addEventListener('click', (e) => { if (e.target.id === 'tm-drawer') e.target.close(); });

// ---- Tabs -------------------------------------------------------------
function activate(tab, push) {
  state.tab = tab;
  for (const link of document.querySelectorAll('.insight-tabs a[data-tab]')) {
    const on = link.dataset.tab === tab;
    link.setAttribute('aria-selected', String(on));
    if (on) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  }
  for (const panel of root.querySelectorAll('[data-panel]')) panel.hidden = panel.dataset.panel !== tab;
  syncUrl();
  if (tab === 'systeem') { load(); schedule(); }
  if (tab === 'kwaliteit' && !state.loaded.kwaliteit) loadQuality();
  if (tab === 'documenten' && !state.loaded.documenten) loadDocuments();
}
document.addEventListener('click', (event) => {
  const link = event.target.closest('.insight-tabs a[data-tab]');
  if (!link || event.metaKey || event.ctrlKey) return;
  event.preventDefault(); activate(link.dataset.tab);
});
function openSystem(docRef) { state.filters = docRef ? { q: docRef } : {}; activate('systeem'); renderControls(); }
function openDocuments(search) { $('#d-q').value = search || ''; activate('documenten'); if (state.loaded.documenten) loadDocuments(false); }

// ---- Kwaliteit & werkproces ------------------------------------------
const ROUTE_NL = { deterministic: 'Deterministisch', semantic: 'Semantisch', remainder: 'Resterende bronpassages', unknown: 'Onbekend', mixed: 'Gemengd' };
const FIELD_NL = { text: 'tekst', type: 'type', relations: 'relaties', semantics: 'aanbevelingsbetekenis' };
const PROC_NL = { succeeded: 'Geslaagd', failed: 'Mislukt', running: 'Bezig', reserved: 'Gereserveerd', pending: 'In wachtrij', stopped: 'Gestopt', blocked: 'Geblokkeerd', none: 'Nog niet gestart', cancelled: 'Geannuleerd' };
const RUN_NL = { succeeded: 'Geslaagd', failed: 'Mislukt', running: 'Lopend', unknown: 'Onbekend', stopped: 'Gestopt' };
async function loadQuality(qs) {
  if (qs !== undefined) state.qparams = qs;
  const body = $('#q-body'); body.classList.add('tm-loading');
  $('#q-status').textContent = 'Meting berekenen…';
  try {
    const response = await fetch('/inzicht/api/quality' + (state.qparams ? '?' + state.qparams : ''), { credentials: 'same-origin' });
    const data = await response.json();
    if (!response.ok) { $('#q-status').textContent = data.error || ('Niet beschikbaar (HTTP ' + response.status + ')'); return; }
    state.loaded.kwaliteit = true; renderQuality(data); syncUrl();
  } catch (error) { $('#q-status').textContent = 'De meting is niet beschikbaar (' + error.message + ').'; }
  finally { body.classList.remove('tm-loading'); }
}
function hbars(box, rows, opts = {}) {
  if (!rows.length) { box.replaceChildren(el('p', { class: 'tm-empty', text: opts.empty || 'Geen gegevens.' })); return; }
  const max = Math.max(1, ...rows.map((r) => r.value || 0));
  box.replaceChildren(...rows.map((r) => el('div', { class: 'tree-row', style: 'grid-template-columns:minmax(150px,36%) 1fr 150px', tabindex: 0,
    onpointermove: (e) => showTip(e, r.label, r.tip || [[r.text, '', opts.color || 'var(--series-1)']]), onpointerleave: hideTip },
    el('span', { class: 'tree-name', style: 'font-family:inherit', text: r.label }),
    el('div', { class: 'tree-track', style: 'background:transparent' }, r.unmeasured ? el('div', { class: 'tree-exc hatch', style: 'width:100%;background-color:transparent' })
      : el('div', { class: 'tree-exc', style: `width:${((r.value || 0) / max) * 100}%;background:${opts.color || 'var(--series-1)'}` })),
    el('span', { style: 'text-align:right;font-variant-numeric:tabular-nums', text: r.text }))));
}
function renderQuality(d) {
  const f = d.filters || {};
  for (const input of $('#q-form').elements) if (input.name) input.value = f[input.name] || '';
  $('#q-table').href = '/settings/quality' + (state.qparams ? '?' + state.qparams : '');
  $('#q-status').textContent = `Gegevensgrens ${new Date(d.as_of).toLocaleString('nl-NL')} · definitie ${d.definition_version} · ${d.cohort_size} bronnen in het cohort`;
  const pub = d.publication || {};
  const days = (s) => s === null || s === undefined ? '—' : (s / 86400).toLocaleString('nl-NL', { maximumFractionDigits: 1 }) + ' dagen';
  const tiles = [
    ['Bronnen in cohort', nf.format(d.cohort_size), 'jouw bronnen als uploader of reviewer'],
    ['Open passages', nf.format(d.open_passages), 'onafgehandeld, momentopname'],
    ['Oudste onafgeronde bron', d.oldest_unfinished_source_days === null ? '—' : days(d.oldest_unfinished_source_days * 86400), 'leeftijd van de bron, niet van de taak'],
    ['Ingest tot publicatie (mediaan)', days(pub.median), `${pub.samples || 0} waarnemingen · p90 ${days(pub.p90)}`],
    ['Beslisinteracties', nf.format(d.burden.review_interactions || 0), `${nf.format(d.burden.object_decisions || 0)} objectbesluiten`],
  ];
  $('#q-kpis').replaceChildren(...tiles.map(([label, value, hint]) => el('div', { class: 'tm-tile' }, el('div', { class: 'label', text: label }), el('div', { class: 'value', text: value }), el('div', { class: 'hint', text: hint }))));
  const routes = Object.entries(d.routes || {});
  hbars($('#q-direct'), routes.map(([route, row]) => ({ label: ROUTE_NL[route] || route, value: row.direct_rate === null ? 0 : row.direct_rate * 100,
    unmeasured: row.direct_rate === null && row.first_decisions > 0,
    text: row.first_decisions ? (row.direct_rate === null ? `niet volledig meetbaar (${row.known_comparisons}/${row.first_decisions})` : `${pct(row.direct_rate)} · ${row.direct}/${row.first_decisions}`) : 'geen besluiten',
    tip: [[row.direct_rate === null ? 'niet volledig meetbaar' : pct(row.direct_rate), 'direct bruikbaar', 'var(--series-1)'], [`${row.direct} / ${row.first_decisions}`, 'direct / eerste besluiten'], [`${row.known_comparisons} / ${row.first_decisions}`, 'vergelijkbaar']] })));
  const series = [['repair_requests', 'Herstelverzoeken', 'var(--series-1)'], ['corrections', 'Correcties', 'var(--series-2)'], ['rejections', 'Afwijzingen', 'var(--series-3)']];
  const maxRepair = Math.max(1, ...routes.flatMap(([, row]) => series.map(([k]) => row[k] || 0)));
  $('#q-repairs').replaceChildren(el('table', {}, el('thead', {}, el('tr', {}, el('th', { text: 'Route' }), series.map(([, label]) => el('th', { class: 'num', text: label })))),
    el('tbody', {}, routes.map(([route, row]) => el('tr', {}, el('td', { text: ROUTE_NL[route] || route }),
      series.map(([key, label, color]) => el('td', { class: 'num' }, el('div', { class: 'barcell', style: 'justify-content:flex-end' },
        el('span', { class: 'bar', style: `width:${Math.max(2, (row[key] || 0) / maxRepair * 60)}px;background:${color}` }), nf.format(row[key] || 0)))))))));
  const docs = [...(d.documents || [])].sort((a, b) => (b.open_passages || 0) - (a.open_passages || 0) || (b.source_age_days || 0) - (a.source_age_days || 0));
  const maxOpen = Math.max(1, ...docs.map((x) => x.open_passages || 0));
  $('#q-open').replaceChildren(docs.length ? el('table', {}, el('thead', {}, el('tr', {}, ['Bron', 'Route', 'Open passages', 'Leeftijd', 'Blokkade', ''].map((h, i) => el('th', { class: i === 2 || i === 3 ? 'num' : '', text: h })))),
    el('tbody', {}, docs.map((x) => el('tr', {}, el('td', { text: x.title }), el('td', { text: ROUTE_NL[x.route] || x.route || '—' }),
      el('td', { class: 'num' }, el('div', { class: 'barcell', style: 'justify-content:flex-end' }, el('span', { class: 'bar', style: `width:${Math.max(2, (x.open_passages || 0) / maxOpen * 90)}px` }), nf.format(x.open_passages || 0))),
      el('td', { class: 'num', text: x.source_age_days === null || x.source_age_days === undefined ? '—' : x.source_age_days.toLocaleString('nl-NL', { maximumFractionDigits: 1 }) + ' d' }),
      el('td', { class: 'mono', text: x.processing_blocker || '—' }),
      el('td', {}, el('button', { type: 'button', class: 'linkbtn', onclick: () => openDocuments(x.snapshot_id) }, 'Diagnose'), ' · ',
        el('button', { type: 'button', class: 'linkbtn', onclick: () => openSystem(x.doc_ref) }, 'Verzoeken'))))))
    : el('p', { class: 'tm-empty', text: 'Geen bronnen in dit cohort.' }));
  qualityTrend($('#q-trend'), d.trend || []);
  const fields = Object.entries(d.changed_fields || {}).sort((a, b) => b[1] - a[1]);
  hbars($('#q-fields'), fields.map(([k, v]) => ({ label: FIELD_NL[k] || k, value: v, text: nf.format(v) })), { empty: 'Geen vastgelegde inhoudswijzigingen.' });
  const runs = Object.entries(d.processing_runs || {}).sort((a, b) => b[1] - a[1]);
  hbars($('#q-runs'), runs.map(([k, v]) => ({ label: RUN_NL[k] || k, value: v, text: nf.format(v) })), { empty: 'Geen verwerkingsruns in dit cohort.' });
  $('#q-defs').replaceChildren(el('ul', {}, [...Object.values(d.definitions || {}), ...(d.limitations || []), d.readiness_reason, d.clinical_reason].filter(Boolean).map((t) => el('li', { text: t }))));
}
function qualityTrend(box, trend) {
  box.replaceChildren();
  if (trend.length < 2) { box.append(el('p', { class: 'tm-empty', text: 'Nog te weinig bewaarde metingen voor een trend. Elke nieuwe meting wordt bewaard.' })); return; }
  const W = 640, H = 170, L = 44, R = 30;
  const max = niceMax(Math.max(...trend.map((t) => t.open_passages || 0)));
  const x = (i) => L + (i / (trend.length - 1)) * (W - L - R), y = (v) => H - (v / max) * H;
  const svg = svgEl('svg', { viewBox: `0 -14 ${W} ${H + 38}`, class: 'chart', role: 'img', 'aria-label': 'Open passages per meting' });
  gridY(svg, max, W - R, H, L, (v) => compact(Math.round(v)));
  trend.forEach((t, i) => { if (i % Math.max(1, Math.ceil(trend.length / 6)) === 0) { const label = svgEl('text', { x: x(i), y: H + 16, 'text-anchor': 'middle' }); label.textContent = new Date(t.as_of).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' }); svg.append(label); } });
  svg.append(svgEl('path', { d: trend.map((t, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(t.open_passages || 0).toFixed(1)).join(''), fill: 'none', stroke: 'var(--series-1)', 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
  const last = trend[trend.length - 1];
  svg.append(svgEl('circle', { cx: x(trend.length - 1), cy: y(last.open_passages || 0), r: 4, fill: 'var(--series-1)', stroke: 'var(--surface-1)', 'stroke-width': 2 }));
  const cross = svgEl('line', { y1: 0, y2: H, stroke: 'var(--axis)', 'stroke-width': 1, visibility: 'hidden' }); svg.append(cross);
  const hit = svgEl('rect', { x: L, y: 0, width: W - L - R, height: H, fill: 'transparent' });
  hit.addEventListener('pointermove', (event) => { const b = svg.getBoundingClientRect(); const px = (event.clientX - b.left) / b.width * W;
    const i = Math.max(0, Math.min(trend.length - 1, Math.round(((px - L) / (W - L - R)) * (trend.length - 1))));
    cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('visibility', 'visible');
    showTip(event, new Date(trend[i].as_of).toLocaleString('nl-NL'), [['open passages', nf.format(trend[i].open_passages || 0), 'var(--series-1)'], ['bronnen', nf.format(trend[i].cohort_size || 0)]]); });
  hit.addEventListener('pointerleave', () => { cross.setAttribute('visibility', 'hidden'); hideTip(); });
  svg.append(hit); box.append(svg);
}
for (const [key, value] of new URLSearchParams(state.qparams)) { const field = $('#q-form').elements[key]; if (field) field.value = value; }
$('#q-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const data = new URLSearchParams(); for (const [k, v] of new FormData(event.target)) if (String(v).trim()) data.set(k, String(v).trim());
  loadQuality(data.toString());
});

// ---- Documenten -------------------------------------------------------
// Pages of at most 200 authorized documents; search and state filter run on the server over all of them.
async function loadDocuments(more) {
  $('#d-status').textContent = 'Laden…';
  const offset = more ? (state.docNext || 0) : 0;
  const q = new URLSearchParams({ q: $('#d-q').value.trim(), state: $('#d-state').value, offset: String(offset) });
  try {
    const response = await fetch('/inzicht/api/documents?' + q, { credentials: 'same-origin' });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const page = await response.json();
    state.docs = more ? (state.docs || []).concat(page.documents) : page.documents;
    state.docTotal = page.total; state.docNext = page.next_offset; state.loaded.documenten = true; renderDocuments();
  } catch (error) { $('#d-status').textContent = 'Kon documenten niet laden (' + error.message + ').'; }
}
function renderDocuments() {
  const rows = state.docs || [];
  const more = state.docNext !== null && state.docNext !== undefined;
  $('#d-status').textContent = state.docTotal === null
    ? `${rows.length} gevonden${more ? ' tot nu toe' : ''}` : `${rows.length} van ${state.docTotal} documenten geladen`;
  $('#d-more').hidden = !more;
  const maxBlocked = Math.max(1, ...rows.map((d) => d.blocked || 0));
  sortable($('#d-table'), [['Document'], ['Verwerking'], ['Geblokkeerd', 1], ['Belangrijkste redenen'], ['Systeem 24 u', 1], ['Ga naar']],
    rows.map((d) => ({ sort: [d.title, d.state || '', d.blocked || 0, (d.reasons[0] || {}).code || '', d.telemetry.errors * 1000 + d.telemetry.requests, ''],
      cells: [el('div', {}, el('strong', { text: d.title }), el('div', { class: 'help', text: [d.version, d.class].filter(Boolean).join(' · ') })),
        el('div', {}, el('span', { text: PROC_NL[d.state] || d.state || '—' }), d.code ? el('div', { class: 'mono help', text: d.code }) : null),
        d.blocked === null ? '—' : el('div', { class: 'barcell', style: 'justify-content:flex-end' }, el('span', { class: 'bar', style: `width:${Math.max(2, (d.blocked || 0) / maxBlocked * 70)}px` }), nf.format(d.blocked || 0)),
        el('div', {}, d.reasons.length ? d.reasons.map((r) => el('div', { class: 'mono', text: `${r.code} (${r.count})` })) : '—'),
        el('span', { class: d.telemetry.errors ? 'st-error' : '' }, d.telemetry.errors ? icon('critical') : null, ` ${d.telemetry.errors} / ${d.telemetry.requests}`),
        el('div', { style: 'display:flex;flex-direction:column;gap:2px' },
          el('button', { type: 'button', class: 'linkbtn', onclick: () => openSystem(d.doc_ref) }, 'Verzoeken en fouten'),
          el('a', { href: '/settings/technical/processing?document=' + encodeURIComponent(d.snapshot_id) }, 'Verwerkingsbeheer'),
          d.named_reviewer ? el('a', { href: '/settings/technical?document=' + encodeURIComponent(d.snapshot_id) }, 'Diagnostiek en brondekking') : null,
          d.named_reviewer ? el('a', { href: '/review?document=' + encodeURIComponent(d.snapshot_id) + '&task=repair' }, 'Passages corrigeren') : null)] })),
    'documents', null, renderDocuments);
}
let docTyping; $('#d-q').addEventListener('input', () => { clearTimeout(docTyping); docTyping = setTimeout(() => loadDocuments(false), 250); });
$('#d-more').addEventListener('click', () => loadDocuments(true));
$('#d-state').addEventListener('change', () => loadDocuments(false));

renderControls(); activate(state.tab);
})();
</script>
"""


def insight_body(tabs_html: str, tab: str) -> str:
    """The /inzicht page body: shared header, tab bar and the four panels."""
    return _STYLE + _BODY.replace("__TABS__", tabs_html).replace("__TAB__", tab) + _SCRIPT
