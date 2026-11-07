export const title = "Metis: menselijke annotatie tot publicatie (ontwerp)";
const names = {
 received: "Bron ontvangen", extracting: "Bron voorbereiden", source_error: "Bronherstel nodig",
 annotating: "Selecties aanwijzen en opslaan", overview: "Documentoverzicht controleren",
 building: "Afgeronde selectie opbouwen", build_error: "Bouwherstel nodig",
 review: "Beoordeling volgens ingest", ready: "Gereed voor publicatie",
 published: "Gepubliceerd", withdrawn: "Ingetrokken"
};
export const state = v => v.phase === "review" && v.approved.length > 0 ? "Aanvullende ingestbeoordeling nodig" : names[v.phase];
const labels = {
 PrepareSource: "Voorbereiding starten", SourceReady: "Bron beschikbaar",
 SourceFailed: "Extractie mislukt", RetrySource: "Bronvoorbereiding hervatten",
 SaveSelection: "Selectie opslaan", OpenOverview: "Klaar met dit document",
 ReturnToSelections: "Selecties aanpassen", SealAndBuild: "Afronden en opbouwen [scope afgehandeld]",
 BuildFailed: "Opbouwen mislukt", RetryBuild: "Dezelfde bouwopdracht hervatten",
 EditSelection: "Bronselectie corrigeren; oordelen vervallen",
 ActivateBuild: "Actuele bouw activeren", Approve: "Vereist oordeel opslaan",
 Publish: "Bevoegd publiceren [ingestbeoordeling compleet]", Withdraw: "Bevoegd intrekken",
 Restart: "Herstart; duurzaam werk blijft behouden", Done: "Geen wijziging"
};
export const step = (action, from, to) => {
 if (action === "ActivateBuild" && from.revision !== from.job) return "Verouderde bouw activeren";
 if (action === "Publish" && !from.policy.every(r => from.approved.includes(r))) return "Publiceren zonder vereiste oordelen";
 if (action === "Approve") return to.phase === "ready" ? "Laatste vereiste oordeel opslaan" : "Eerste vereiste oordeel opslaan";
 return labels[action] || action;
};
