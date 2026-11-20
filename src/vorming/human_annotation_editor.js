/* Source references only. Canonical text and object identity belong to the kernel. */
import {bindRange} from '/annotations/binding.mjs';
// #1060 slice 5: the card is the only way to annotate. The worker selects source text and chooses, in the menu
// next to the selection, where it goes: the statement, what belongs to it, or its evidence. '−' in the card
// removes. Metis derives the meaning; the reviewer confirms it. (Besluit William 2026-11-15: one way to add.)
(() => {
  'use strict';
  const state = JSON.parse(document.getElementById('annotation-data').textContent);
  const el = id => document.getElementById('annotation-' + id);
  const fieldContract = state.field_contract;
  const clone = value => JSON.parse(JSON.stringify(value));
  // #1067: what to select in each card row, and what '−' does there.
  const HELP={
    core:['Zegt de bron hier iets wat afzonderlijk kan worden begrepen en beoordeeld, zoals een aanbeveling, definitie of verklaring? Selecteer die uitspraak letterlijk.',
      'Kies één betekenis met de tekst die nodig is om haar goed te begrijpen. Eén zin kan twee uitspraken bevatten; één uitspraak kan meerdere bronbereiken beslaan. Gebruik niet automatisch de hele alinea.',
      ['“Voer A uit en controleer daarna B.” kan twee afzonderlijk te beoordelen adviezen bevatten. Maak dan twee kaarten.',
       '“Voor de volgende gevallen geldt:” en een opsommingspunt kunnen samen één uitspraak vormen. Voeg de noodzakelijke inleiding toe bij Hoort erbij.',
       'Een kopnummer, documentdatum of “Figuur 3” bevat op zichzelf niets wat afzonderlijk te beoordelen is.'],
      'Twijfel je of dit een aparte uitspraak is? Laat het bronstuk open voor documentcontrole. Twijfel is geen reden om het weg te laten.',
      'Met − haal je de selectie weg.'],
    type:['Het soort zegt wat voor uitspraak dit is, bijvoorbeeld een aanbeveling of een definitie. Metis stelt het voor; de reviewer controleert het.'],
    belongs:['Selecteer tekst die nodig is om de uitspraak te begrijpen of toe te passen. Bijvoorbeeld:',
      ['de inleidende zin van een opsomming;','voor wie of wanneer het geldt (‘Bij volwassenen in de thuiszorg’);','een voorwaarde of uitzondering die de betekenis begrenst;','een begrip dat in de uitspraak wordt gebruikt.'],
      '“Voer handeling A uit bij groep B. Niet bij conditie C.” kan één aanbeveling zijn met een uitzondering bij Hoort erbij. Een uitzondering is niet automatisch een eigen uitspraak; een afzonderlijk advies kan dat wel zijn.',
      '“Bij groep C is de effectiviteit onzeker.” kan een eigen uitspraak of een beperking bij een andere uitspraak zijn. Lees de omliggende tekst.',
      'Niet: waarom het klopt. Dat hoort bij Onderbouwing.','Met − haal je tekst weg, of wijs je een voorstel van Metis af.'],
    evidence:['Selecteer tekst waarmee de bron de uitspraak ondersteunt of verklaart. Bijvoorbeeld:',
      ['een beschrijving van onderzoek;','de mate van bewijs;','een verwijzing of een afweging van de werkgroep.'],
      '“De studie omvatte 238 deelnemers.” kan onderzoekscontext zijn; niet iedere feitelijke zin is een eigen uitspraak. Bevat de tekst een afzonderlijk te beoordelen bevinding? Controleer dan of die past bij de toegelaten soorten voor deze bron.',
      'Niet: voorwaarden of doelgroep. Die horen bij Hoort erbij.','Geen onderbouwing in de bron? Laat de regel leeg; de reviewer beoordeelt dat.'],
  };
  const helpOpen=new Set();
  const savedRows=new Map();
  let savedBindings=state.object_bindings || {},buildPhase=state.current_build,buildNotice='';
  // Signals a worker can act on, shown in the row they are about.
  const leaning=new Set(['supported_object_missing','condition_target_missing','exception_target_missing','annotation_relation_target_missing','no_independent_claim']);
  const broken=new Set(['incomplete_sentence','recommendation_core_incomplete']);
  const LOST_SELECTION='Wijs één bereik binnen een tekstblok aan. Voeg een volgende alinea afzonderlijk toe.';

  // The card's state. Nothing here is a form field: the kernel stores what flush() sends.
  let entry, selected=null, dirty=0, committed=0, timer, running=null, retryRequest=null, retryVersion=0, failed=false;
  let selectingFromSource=false, lostSelection='';
  let check=null, checking=false, finalizing=false, saving=false, deriving=false, rebuilding=false;
  // A selection made while Metis reads waits in 'queued'. The menu stands at the selection; 'menuClosed' says the
  // worker closed it for this selection.
  // #1060 slice 4: a proposal is answered with + or −, never by ignoring it; 'asked' says saving met an open one.
  let queued=null, asked=false, menuClosed=false;
  // Besluit William 2026-11-14: switching the kind back restores Metis' proposal for that kind, for this statement.
  const kindMemory={};

  // #1067: the kind row stays mounted while it is shown. Moving or re-inserting the control would drop its focus and
  // close an open choice, so the other rows are rebuilt around it.
  const kindBox=document.createElement('div'),kindSelect=document.createElement('select');
  {
    const label=document.createElement('label');
    kindBox.id='annotation-simple-type';kindBox.className='annotation-type-row';
    kindSelect.id='annotation-simple-type-select';label.htmlFor=kindSelect.id;label.className='sr-only';label.textContent='Soort uitspraak';
    kindSelect.add(new Option('Kies het soort',''));
    for(const kind of state.kinds) kindSelect.add(new Option(kind.label,kind.value));
    kindSelect.addEventListener('change',()=>{setKind(kindSelect.value);});
    kindBox.append(label,kindSelect);
  }
  const typeDt=document.createElement('dt'),typeDd=document.createElement('dd');
  typeDt.dataset.row=typeDd.dataset.row='type';

  const hasCore = () => entry.ranges.some(a => a.role==='core');
  const built = () => state.object_bindings?.[entry.annotation_id];
  const checkIsCurrent = () => check && dirty===committed && check.annotation_id===entry.annotation_id &&
    check.revision===entry.revision && check.basis.snapshot_id===state.snapshot_id &&
    check.basis.working_revision_id===state.working_revision_id && check.basis.normalization===state.normalization &&
    check.basis.generation===state.generation &&
    check.basis.extraction_hash===state.extraction_hash && check.basis.objects_revision===state.objects_revision;
  const openProposals = () => checkIsCurrent() ? check.proposals || [] : [];
  const linkId = a => a.relationship_id || 'link-v1:'+JSON.stringify([entry.annotation_id,a.role,a.block_id,a.start,a.end]);
  const literal = span => {
    const block=state.blocks.find(b => b.block_id === span.block_id);
    return block ? Array.from(block.text).slice(span.start,span.end).join('') : '';
  };
  const status = text => { el('status').textContent = text; };
  // A built object is not in the document check any more: its card speaks of the object, not the phase.
  const loadedStatus = () => built() ? (built().pending ? 'Aanpassing opgeslagen, nog niet opnieuw gebouwd.' : 'Opgebouwd kennisobject.') :
    entry.revision ? entry.status==='ready' ? 'Klaar voor documentcontrole en opgeslagen.' : 'Concept opgeslagen.' : 'Nieuwe annotatie. Nog niets opgeslagen.';
  function setEntryUrl(id) {
    const url=new URL(location.href);
    if(id) url.searchParams.set('annotation',id);else url.searchParams.delete('annotation');
    history.replaceState(null,'',url);
  }

  // The meaning parts a kind has: the kernel binds exactly these, and a kind keeps no others.
  function relevantFields(kind) {
    const relevant=new Set(['subject_span','predicate_span',...(fieldContract.type_fields[kind] || [])]);
    if(kind==='recommendation') for(const field of ['actor_span','target_group_span','scope_span','condition_span']) relevant.add(field);
    return relevant;
  }
  function resetFields() {
    entry.field_evidence ||= Object.fromEntries(fieldContract.fields.map(f => [f,{span:null,missing_reason:'uncertain'}]));
    for(const field of Object.values(fieldContract.type_core_fields))
      if(entry.field_evidence[field]?.core) entry.field_evidence[field]={span:null,missing_reason:'uncertain'};
    // Parts of another kind would be stored and built unseen; switching back restores them from kindMemory only.
    const relevant=relevantFields(entry.object_type);
    for(const field of fieldContract.fields)
      if(field!=='type_evidence_spans' && !relevant.has(field)) entry.field_evidence[field]={span:null,missing_reason:'uncertain'};
    entry.field_evidence.type_evidence_spans={core:true};
    const core=fieldContract.type_core_fields[entry.object_type];
    if(core) entry.field_evidence[core]={core:true};
    if(entry.object_type!=='recommendation') entry.recommendation_semantics=null;
  }
  // A meaning reference that lay only inside a removed range no longer has a source.
  function clearDependentFields(removed) {
    const contains=(outer,inner)=>outer.block_id===inner.block_id && outer.start<=inner.start && outer.end>=inner.end;
    for(const [field,evidence] of Object.entries(entry.field_evidence || {}))
      if(evidence.span && contains(removed,evidence.span) && !entry.ranges.some(range=>contains(range,evidence.span)))
        entry.field_evidence[field]={span:null,missing_reason:'uncertain'};
  }

  // ---- Binding: the selection becomes the statement, or text that belongs to it, or its evidence.
  function bindAs(role) {
    try {
      // What the card links belongs; '−' simply removes it. Evidence supports the statement.
      entry=bindRange(entry,selected,{role,evidenceFunction:'supported_by'},fieldContract).entry;
      if(role==='core') resetFields();
    } catch(error) {status(error.message);return;}
    window.getSelection().removeAllRanges();
    selected=null;entry.pending_range=null;
    change();render();
  }
  async function useAs(kind) {
    if(!selected || finalizing || deriving) return;
    if(kind==='core') {bindAs('core');if(selected) return;await derive();return;}
    if(kind==='evidence') entry.evidence_not_applicable=false;
    bindAs(kind==='evidence' ? 'evidence' : 'context');await runCheck();
  }
  // The menu next to the selection: the selection goes where the worker chooses. Without a statement it can only
  // become the statement; with one, 'Uitspraak' adds the next piece of it.
  function add(kind) {
    (async()=>{
      if(finalizing || deriving || !selected) return;
      await useAs(hasCore() ? kind : 'core');
    })().catch(()=>{});
  }
  function onSelection() {
    // A selection alone is already the statement: check it so Metis can propose what belongs to it.
    renderCard();
    if(!hasCore()) runCheck();
  }
  function removeRange(anchor) {
    const index=entry.ranges.indexOf(anchor);if(index<0) return;
    entry.ranges.splice(index,1);clearDependentFields(anchor);
    // '−' means: this does not belong. For a list introduction that is the answer to Metis' proposal.
    if(anchor.role==='list_introduction') decline(anchor);
    change();render();runCheck();
  }
  function decline(span) {
    const same=row=>['block_id','start','end'].every(key=>row[key]===span[key]);
    entry.declined_context=(entry.declined_context || []).filter(row=>!same(row));
    entry.declined_context.push({block_id:span.block_id,start:span.start,end:span.end,quote:span.quote});
  }
  async function answerProposal(proposal,add) {
    if(finalizing || deriving) return;
    asked=false;
    // The selection is the statement; answering the proposal commits it first.
    if(!hasCore() && selected) {await useAs('core');if(!hasCore()) return;}
    if(add) {
      try {entry=bindRange(entry,proposal,{role:'list_introduction',evidenceFunction:null},fieldContract).entry;}
      catch(error) {status(error.message);return;}
    } else decline(proposal);
    change();render();runCheck();
  }
  // Removing a piece changes the statement: what Metis derived from it no longer holds.
  // Removing the last piece removes the object itself, so no empty draft is left to block the document.
  function removeStatement(anchor) {
    const rest=anchor ? entry.ranges.filter(a=>a.role==='core' && a!==anchor) : [];
    if(!rest.length && !built()) {discardObject().catch(()=>{});return;}
    entry.ranges=entry.ranges.filter(a=>anchor ? a!==anchor : a.role!=='core');entry.object_type=null;
    entry.field_evidence=null;resetFields();change();render();
    if(hasCore()) derive().catch(()=>{});
  }
  async function discardObject() {
    queued=null;
    try {
      // Withdraw what is stored as it now is; a refused edit (such as a duplicate) is not sent first.
      if(entry.revision) {entry.status='withdrawn';dirty+=1;await flush();}
      load('');status('Weggehaald. Selecteer de volgende uitspraak.');
    } catch(_) { /* The save status says what failed; the work stays visible. */ }
  }
  async function setNoEvidence(value) {
    if(value && !hasCore()) {await useAs('core');if(!hasCore()) return;}
    entry.evidence_not_applicable=value;change();await runCheck();
  }
  // A changed kind keeps the selections; meaning parts of the old kind are cleared and stay open for the reviewer.
  function setKind(value) {
    if(saving || finalizing || deriving) {kindSelect.value=entry.object_type || '';return;}
    // The visible control always shows the stored kind; an empty choice never hides a kind that is still saved.
    if(!value || value===entry.object_type) {kindSelect.value=entry.object_type || '';return;}
    // The memory belongs to this exact statement: a changed statement never gets meaning derived from the old one.
    const statement=entry.annotation_id+'|'+JSON.stringify(entry.ranges.filter(a=>a.role==='core').map(a=>[a.block_id,a.start,a.end]));
    const memory=kindMemory[statement] ||= {};
    if(entry.object_type) memory[entry.object_type]={field_evidence:clone(entry.field_evidence || null),
      recommendation_semantics:clone(entry.recommendation_semantics || null)};
    delete entry.disposition;entry.object_type=value;
    if(memory[value]) {
      entry.field_evidence=clone(memory[value].field_evidence);entry.recommendation_semantics=clone(memory[value].recommendation_semantics);
    } else resetFields();
    change();renderCard();runCheck();
  }

  // ---- Metis' proposal: kind and meaning, derived in the background from the statement.
  const suggestionBasis=()=>Object.fromEntries(['snapshot_id','working_revision_id','extraction_hash','normalization','generation','objects_revision'].map(key=>[key,state[key]]));
  async function derive() {
    deriving=true;renderCard();
    try {await proposeMeaning();}
    finally {
      deriving=false;el('suggestion-note').textContent='';await runCheck();
      if(queued) {const value=queued;queued=null;captureSelection(value);}
    }
  }
  async function proposeMeaning() {
    if(entry.disposition) return;
    const controller=new AbortController(),deadline=setTimeout(()=>controller.abort(),55000);
    el('suggestion-note').textContent='Metis leest je selectie. Dit kan tot een minuut duren.';
    try {
      if(!hasCore()) throw Error('Selecteer eerst de volledige uitspraak.');
      await flush();
      const id=entry.annotation_id,version=dirty,revision=entry.revision,basis=suggestionBasis();
      // Controls cannot change the meaning while this response is outstanding.
      // Source selection remains usable; its dirty version invalidates the answer.
      el('editor-inputs').disabled=true;
      const response=await fetch('/annotations/suggest',{method:'POST',headers:{'Content-Type':'application/json'},
        signal:controller.signal,body:JSON.stringify({snapshot_id:state.snapshot_id,annotation_id:id,revision,basis})});
      const data=await response.json();
      if(!response.ok) throw Error(data.error==='annotation_suggestion_stale' ? 'Het opgeslagen werk is gewijzigd. Heropen de annotatie voordat je opnieuw een voorstel vraagt.' : data.message || 'Het voorstel kon niet worden gemaakt.');
      if(entry.annotation_id!==id || entry.revision!==revision || dirty!==version || data.annotation_id!==id || data.revision!==revision || JSON.stringify(data.basis)!==JSON.stringify(basis))
        throw Error('Je selectie of opgeslagen werk is gewijzigd. Het oude voorstel is niet toegepast.');
      // Ordinary draft save remains the only writer; no approval/status shortcut.
      entry.object_type=data.object_type;entry.field_evidence=data.field_evidence;
      entry.recommendation_semantics=data.recommendation_semantics;
      change();
      el('controls').scrollTop=0;
      if(window.matchMedia('(max-width:800px)').matches) el('controls').scrollIntoView({block:'start'});
      await flush();
      await runCheck();
      el('suggestion-note').textContent='';
    } catch(error) {
      el('suggestion-note').textContent=(error.name==='AbortError' ? 'Het voorstel duurde te lang.' : error.message)+' Je opgeslagen werk blijft bewaard. Kies het soort en ga verder.';
    } finally {
      clearTimeout(deadline);el('editor-inputs').disabled=false;renderCard();
    }
  }

  // ---- The card.
  function renderCard() {
    const confirmedReady=entry.status==='ready' && dirty===committed;
    // An open proposal keeps the buttons usable: saving then points at the proposal to answer.
    const complete=confirmedReady || checkIsCurrent() && !check.findings.some(f=>f.code!=='annotation_context_proposal_open');
    // A selected statement alone is a complete object: saving commits it first.
    // A saved object that lost its statement must get one back before leaving.
    const provisional=!hasCore() && !!selected,busy=finalizing || checking || deriving,object=built();
    el('ready').hidden=!!object || !hasCore() && !provisional;
    el('ready').disabled=busy || !(provisional || complete);
    el('finish').hidden=!!object;
    el('finish').disabled=busy || hasCore() && !complete;
    // #1064: an object that is already built has one way forward: rebuild it when something changed,
    // otherwise go back to its review.
    el('rebuild').hidden=!object;
    if(object) {
      el('rebuild').textContent=changedSinceBuild() ? 'Kennisobject opnieuw bouwen' : 'Terug naar review';
      el('rebuild').disabled=finalizing || checking || deriving || rebuilding || changedSinceBuild() && (!hasCore() || !complete);
    }
    renderRows();
    renderMenu();
    renderSavedAnnotations();
  }

  // Only acknowledged versions belong here. The active card may contain newer, unsaved work.
  function renderSavedAnnotations() {
    const entries=state.entries.filter(item=>item.revision>0 && item.status!=='withdrawn' && !item.disposition &&
      (item.ranges.some(range=>range.role==='core') || item.pending_range));
    const list=el('saved-list'),ids=new Set(entries.map(item=>item.annotation_id));
    for(const [id,row] of savedRows) if(!ids.has(id)) {row.remove();savedRows.delete(id);}
    entries.forEach((item,index)=>{
      const id=item.annotation_id,binding=savedBindings[id],changed=id===entry.annotation_id && dirty!==committed;
      let label='Opgeslagen',detail='Nog niet gebouwd voor Review.';
      if(changed) {label='Nog aanpassen';detail='Wijzigingen nog niet opgeslagen; de opgeslagen versie is bewaard.';}
      else if(item.status!=='ready') {label='Nog aanpassen';detail='Concept opgeslagen.';}
      else if(binding && !binding.pending) {label='Beschikbaar voor Review';detail='Kennisobject opgebouwd.';}
      else if(buildPhase?.state==='running') {label='Wordt gebouwd';detail='Annotatie opgeslagen.';}
      else if(binding?.pending) {label='Nog aanpassen';detail='Aanpassing opgeslagen; opnieuw bouwen.';}
      let row=savedRows.get(id);
      if(!row) {
        row=document.createElement('li');row.dataset.annotationId=id;
        const link=document.createElement('a'),status=document.createElement('span'),note=document.createElement('span');
        status.className='annotation-saved-status';note.className='annotation-saved-detail';
        link.addEventListener('click',async event=>{
          if(event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
          event.preventDefault();
          if(finalizing || saving || checking || deriving || rebuilding) return;
          try {await flush();window.location.assign(link.href);}
          catch(error) {el('status').textContent=error.message;}
        });
        row.append(link,status,note);savedRows.set(id,row);
      }
      const [link,status,note]=row.children;
      const text=item.ranges.filter(range=>range.role==='core').map(range=>range.quote).join(' ') || item.pending_range?.quote || 'Uitspraak nog aanvullen';
      const chars=Array.from(text),excerpt=chars.slice(0,100).join('')+(chars.length>100 ? '…' : '');
      link.textContent=excerpt;link.setAttribute('aria-label','Opgeslagen annotatie openen: '+excerpt);
      link.href='/annotations?'+new URLSearchParams({document:state.snapshot_id,annotation:id})+'#annotation-controls';
      if(id===entry.annotation_id) link.setAttribute('aria-current','true');else link.removeAttribute('aria-current');
      link.setAttribute('aria-disabled',String(finalizing || saving || checking || deriving || rebuilding));
      status.textContent=label;note.textContent=detail;
      if(list.children[index]!==row) list.insertBefore(row,list.children[index] || null);
    });
    el('saved-summary').textContent=entries.length ? entries.length+' '+(entries.length===1 ? 'annotatie opgeslagen.' : 'annotaties opgeslagen.') :
      'Nog geen annotaties opgeslagen. Je opgeslagen uitspraken verschijnen hier.';
    const notice=buildNotice || (buildPhase && !['running','succeeded'].includes(buildPhase.state) ?
      'De laatste opbouw is gestopt. Je opgeslagen annotaties zijn bewaard. Controleer het documentoverzicht.' : '');
    el('saved-notice').textContent=notice;el('saved-notice').hidden=!notice;
    el('saved-overview').hidden=!entries.length;
    el('saved-overview').setAttribute('aria-disabled',String(finalizing || saving || checking || deriving || rebuilding));
    el('saved-build').hidden=!buildPhase;
    if(buildPhase) el('saved-build').href='/annotations/build?'+new URLSearchParams({document:state.snapshot_id,attempt:buildPhase.attempt_id});
  }

  // Refresh only the read-side list during a known build. Never change the active editor's CAS basis.
  async function refreshSavedBuild() {
    if(buildPhase?.state!=='running') return;
    try {
      const response=await fetch('/annotations/build/api?'+new URLSearchParams({document:state.snapshot_id,attempt:buildPhase.attempt_id}),{cache:'no-store'});
      if(!response.ok) throw new Error();
      const progress=await response.json();
      buildNotice='';
      if(progress.state!=='running') {
        const completed=await fetch('/annotations/api?'+new URLSearchParams({document:state.snapshot_id}),{cache:'no-store'});
        if(!completed.ok) throw new Error();
        const view=await completed.json();
        if(view.generation===state.generation) {
          savedBindings=view.object_bindings || {};buildPhase=view.current_build;
        } else if(view.generation>state.generation) {
          buildNotice='De opgeslagen annotaties zijn elders gewijzigd. Herlaad de pagina voor de actuele voortgang.';
          renderSavedAnnotations();return;
        }
      }
    } catch(_) {buildNotice='De voortgang kon niet worden opgehaald. De laatst bevestigde opslag blijft zichtbaar; probeer Opbouw bekijken.';}
    renderSavedAnnotations();
    if(buildPhase?.state==='running') setTimeout(refreshSavedBuild,2000);
  }
  // ---- The menu at the selection. It sits in the scrolling document next to the selected text, so it scrolls with
  // it; it comes right after the source block, so Tab reaches it from a keyboard selection.
  const menu=document.createElement('span'),menuButtons={};
  {
    menu.id='annotation-selection-menu';menu.className='annotation-selection-menu';menu.setAttribute('role','toolbar');
    menu.setAttribute('aria-label','Selectie toevoegen aan');menu.hidden=true;
    const label=document.createElement('span');label.className='annotation-selection-label';label.textContent='Toevoegen aan';label.setAttribute('aria-hidden','true');
    menu.append(label);
    for(const [kind,text] of [['core','Uitspraak'],['context','Hoort erbij'],['evidence','Onderbouwing']]) {
      const button=document.createElement('button');button.type='button';button.dataset.add=kind;button.textContent=text;
      button.addEventListener('click',()=>add(kind));menuButtons[kind]=button;menu.append(button);
    }
    // Pressing a choice must not take the selection away before it is used.
    menu.addEventListener('mousedown',event=>event.preventDefault());
    menu.addEventListener('keydown',event=>{
      const buttons=[...menu.querySelectorAll('button:not([hidden])')],at=buttons.indexOf(document.activeElement);
      if(event.key==='Escape') {const block=menu.previousElementSibling;dismissMenu();block?.focus?.();event.preventDefault();}
      else if((event.key==='ArrowRight' || event.key==='ArrowLeft') && at>=0) {
        buttons[(at+(event.key==='ArrowRight' ? 1 : buttons.length-1))%buttons.length].focus();event.preventDefault();
      }
    });
  }
  // The menu is placed from the selection as the card holds it, not from the browser's live selection, so a
  // selection restored from a save (pending_range) gets its menu back after a reload (Codex P2).
  function spanRange(span) {
    const node=sourceElements.get(span.block_id);if(!node) return null;
    const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT),range=document.createRange();
    let seen=0,text,started=false;
    while((text=walker.nextNode())) {
      const points=Array.from(text.data),units=at=>points.slice(0,at).join('').length;
      if(!started && span.start<=seen+points.length) {range.setStart(text,units(span.start-seen));started=true;}
      if(started && span.end<=seen+points.length) {range.setEnd(text,units(span.end-seen));return range;}
      seen+=points.length;
    }
    return null;
  }
  // Putting the menu away. Without a statement the selection stays visible in the card as the statement, with its
  // own '−'. With one, the selection is shown nowhere else, so putting the menu away cancels it (Codex P2): no
  // hidden pending selection keeps the card from being finished.
  function dismissMenu() {
    if(!hasCore()) {menuClosed=true;renderMenu();return;}
    if(!selected && !entry.pending_range) {menuClosed=true;renderMenu();return;}
    // Like every other edit ('−' included): save, then check again, so finishing is offered again at once.
    selected=null;entry.pending_range=null;window.getSelection().removeAllRanges();
    change();renderMenu();runCheck();
  }
  function renderMenu() {
    const show=!!selected && !menuClosed && !entry.disposition && !finalizing && !deriving;
    const block=show ? sourceElements.get(selected.block_id) : null,host=block?.closest('.annotation-document'),range=block ? spanRange(selected) : null;
    // A choice clears the selection before the menu hides: focus returns to the passage the menu stood by, so
    // the next Tab continues from there (Codex P2).
    if(!range || !host) {if(menu.contains(document.activeElement)) (menu.previousElementSibling?.closest('[data-source-block]') || sourceElements.get(selected?.block_id))?.focus();menu.hidden=true;return;}
    // A selection restored inside folded source (the table of contents) opens it, as revealSource() does (Codex P2).
    const folded=block.closest('details');
    if(folded && !folded.open) folded.open=true;
    if(menu.previousSibling!==block) block.after(menu);
    const core=hasCore();
    menuButtons.core.setAttribute('aria-label',core ? 'Toevoegen aan de uitspraak, als volgend stuk' : 'Toevoegen als uitspraak');
    menuButtons.context.hidden=menuButtons.evidence.hidden=!core;
    menuButtons.context.setAttribute('aria-label','Toevoegen aan Hoort erbij');
    menuButtons.evidence.setAttribute('aria-label','Toevoegen aan Onderbouwing');
    menu.hidden=false;
    // Below the selection: a phone shows its own menu above it.
    const rects=[...range.getClientRects()].filter(r=>r.width || r.height),last=rects.at(-1) || range.getBoundingClientRect();
    const box=host.getBoundingClientRect(),room=host.clientWidth-menu.offsetWidth-8;
    menu.style.top=(last.bottom-box.top+host.scrollTop+6)+'px';
    menu.style.left=Math.max(8,Math.min((rects[0] || last).left-box.left+host.scrollLeft,room))+'px';
  }
  function renderRows() {
    el('save-current-format').hidden = entry.historical_finding !== 'annotation_historical_format';
    const core=entry.ranges.filter(a=>a.role==='core'),belongs=entry.ranges.filter(a=>a.role!=='core' && a.role!=='evidence'),evidence=entry.ranges.filter(a=>a.role==='evidence');
    const done=entry.status==='ready' && dirty===committed && !built(),current=checkIsCurrent(),provisional=!core.length && !!selected;
    el('simple-heading').textContent=!core.length && !selected ? 'Selecteer de uitspraak in de bron' : done ? 'Klaar voor documentcontrole' : '';
    el('simple-heading').hidden=!el('simple-heading').textContent;
    const findings=current ? check.findings : [],signals=current ? check.signals || [] : [],proposals=openProposals();
    const rows=el('simple-rows'),showType=!entry.disposition && core.length>0 && !deriving;
    for(const child of [...rows.childNodes]) if(!showType || (child!==typeDt && child!==typeDd)) child.remove();
    let beforeType=typeDt.isConnected ? typeDt : null;
    const hint=(dd,value)=>{const p=document.createElement('p');p.textContent=value;p.className='annotation-hint';dd.append(p);};
    const sign=(parent,glyph,label,run,pressed=null)=>{const button=document.createElement('button');button.type='button';button.className='annotation-sign';button.textContent=glyph;button.setAttribute('aria-label',label);button.title=label;if(pressed!==null) button.setAttribute('aria-pressed',String(pressed));button.addEventListener('click',run);parent.append(button);return button;};
    const line=(dd,value,label,remove)=>{const div=document.createElement('div'),p=document.createElement('p');div.className='annotation-line';p.textContent=value;div.append(p);sign(div,'−',label,remove);dd.append(div);};
    // #1067: a '?' opens what to select in this row, under the row itself; it stays open while you work.
    const explain=(name,dd,key,label)=>{
      const button=document.createElement('button'),box=document.createElement('div');
      button.type='button';button.className='annotation-help-toggle';button.textContent='?';
      button.setAttribute('aria-label','Uitleg bij '+label);button.setAttribute('aria-controls','annotation-help-'+key);
      button.setAttribute('aria-expanded',String(helpOpen.has(key)));
      box.id='annotation-help-'+key;box.className='annotation-help';box.hidden=!helpOpen.has(key);
      for(const part of HELP[key]) {
        if(Array.isArray(part)) {const ul=document.createElement('ul');for(const item of part) {const li=document.createElement('li');li.textContent=item;ul.append(li);}box.append(ul);}
        else {const p=document.createElement('p');p.textContent=part;box.append(p);}
      }
      button.addEventListener('click',()=>{
        const open=!helpOpen.has(key);if(open) helpOpen.add(key);else helpOpen.delete(key);
        button.setAttribute('aria-expanded',String(open));box.hidden=!open;
      });
      name.append(button);dd.append(box);
    };
    const row=(key,label,build)=>{
      const kind=key==='type',dt=kind ? typeDt : document.createElement('dt'),dd=kind ? typeDd : document.createElement('dd');
      const name=document.createElement('span'),text=document.createElement('span');
      if(kind) {dt.replaceChildren();for(const child of [...dd.childNodes]) if(child!==kindBox) child.remove();}
      else {dt.dataset.row=key;dd.dataset.row=key;}
      text.textContent=label;name.className='annotation-row-name';name.append(text);dt.append(name);
      if(HELP[key]) explain(name,dd,key,label);
      if(adoptedCard===entry.annotation_id && !kind && !deriving) {
        sign(dt,'+','Brontekst toevoegen aan '+label,()=>{
          if(selected) {add(key==='belongs' ? 'context' : key);return;}
          status('Selecteer tekst in de bron en kies '+label+'.');
          sourceElements.get(entry.ranges[0]?.block_id)?.focus();
        });
      }
      if(kind && kindBox.parentNode===dd) for(const child of [...dd.childNodes]) if(child!==kindBox) dd.insertBefore(child,kindBox);
      build(dd);
      if(kind) {if(!dt.isConnected) rows.append(dt,dd);beforeType=null;}
      else if(beforeType) {rows.insertBefore(dt,beforeType);rows.insertBefore(dd,beforeType);}
      else rows.append(dt,dd);
    };
    // #1067: source text that is no statement (recorded in the document check) shows what it is, nothing to fill in.
    if(entry.disposition) {
      const reasons=Object.values(fieldContract.source_roles).flat();
      const kind=reasons.find(r=>r.value===entry.disposition.reason)?.label || 'Geen uitspraak';
      row('core','Geen uitspraak: '+kind.toLowerCase(),dd=>{for(const a of core) line(dd,a.quote,'Weghalen: '+a.quote,()=>{discardObject().catch(()=>{});});});
      el('simple-status').textContent='';el('simple-notes').replaceChildren();
      return;
    }
    if(core.length || provisional) row('core','Uitspraak',dd=>{
      if(provisional) line(dd,selected.quote,'Selectie weghalen',()=>removeStatement());
      for(const a of core) line(dd,a.quote,'Weghalen uit de uitspraak: '+a.quote,()=>removeStatement(a));
      if(signals.some(item=>broken.has(item.code))) hint(dd,'Dit lijkt een afgebroken zin. Is de hele zin geselecteerd?');
    });
    // #1067: the kind of statement is a row like the others: Metis proposes it, anyone working in the card corrects it.
    if(showType) row('type','Soort',dd=>{
      // The control stays mounted (see typeDd), so a choice in progress keeps its focus.
      if(document.activeElement!==kindSelect) kindSelect.value=entry.object_type || '';
      kindSelect.disabled=saving;kindSelect.options[0].disabled=!!entry.object_type;
      if(kindBox.parentNode!==dd) dd.append(kindBox);
      hint(dd,entry.object_type ? 'Klopt het soort niet? Kies het juiste soort.' : 'Metis kon het soort niet bepalen. Kies het soort.');
    });
    if(core.length || provisional) {
      row('belongs','Hoort erbij',dd=>{
        for(const a of belongs) line(dd,a.quote,'Weghalen: '+a.quote,()=>removeRange(a));
        for(const proposal of proposals) {
          const div=document.createElement('div'),text=document.createElement('p'),label=document.createElement('span'),quote=document.createElement('span'),signs=document.createElement('span');
          div.className='annotation-line annotation-proposal';label.className='annotation-proposal-label';label.textContent='Voorstel van Metis';
          quote.textContent=proposal.quote;text.append(label,quote);signs.className='annotation-signs';
          sign(signs,'+','Toevoegen aan Hoort erbij: '+proposal.quote,()=>{answerProposal(proposal,true).catch(()=>{});}).dataset.proposal='add';
          sign(signs,'−','Afwijzen, hoort er niet bij: '+proposal.quote,()=>{answerProposal(proposal,false).catch(()=>{});}).dataset.proposal='decline';
          div.append(text,signs);dd.append(div);
        }
        if(asked && proposals.length) hint(dd,'Beantwoord eerst het voorstel: + voegt de tekst toe, − wijst het af.');
        if(!belongs.length && !proposals.length && signals.some(item=>leaning.has(item.code))) hint(dd,'De uitspraak leunt mogelijk op andere tekst. Hoort er een zin bij?');
      });
      row('evidence','Onderbouwing',dd=>{
        for(const a of evidence) line(dd,a.quote,'Weghalen: '+a.quote,()=>removeRange(a));
        // An earlier explicit choice stays visible and removable; the card no longer asks for it.
        if(!evidence.length && entry.evidence_not_applicable) line(dd,'Vastgelegd als niet van toepassing.','Keuze weghalen: niet van toepassing',()=>{setNoEvidence(false).catch(()=>{});});
        if(!evidence.length && !entry.evidence_not_applicable) hint(dd,'Niets gekoppeld. Staat de onderbouwing in de bron? Selecteer haar en kies Onderbouwing.');
      });
    }
    const own=finding=>finding.code==='annotation_core_required' && !entry.object_type || finding.code==='annotation_context_proposal_open';
    el('simple-status').textContent=deriving ? 'Metis leest de uitspraak…'+(queued ? ' Je selectie wordt daarna toegevoegd.' : '') : !selected && lostSelection ||
      (core.length && selected ? 'Kies bij je selectie waar de tekst bij hoort.' : !core.length ? '' :
       done ? 'Dit is geen inhoudelijke goedkeuring of publicatie.' : checking ? 'Controleren…' : '');
    const notes=el('simple-notes');notes.replaceChildren();
    // A check that failed or never ran must not strand a complete object: offer the retry here.
    if(core.length && !current && !checking && !deriving && !done) {
      const li=document.createElement('li'),button=document.createElement('button');button.type='button';button.className='btn-secondary';
      button.id='annotation-simple-recheck';button.textContent='Opnieuw controleren';button.addEventListener('click',()=>{runCheck();});li.append(button);notes.append(li);
    }
    // Before the statement is committed, the open points are about committing it, which saving does.
    for(const finding of core.length ? findings.filter(f=>!own(f)) : []) {
      const li=document.createElement('li');li.textContent=finding.message;notes.append(li);
    }
  }
  function render() {renderSourceHighlights();renderCard();}

  // ---- The source: marks for what is linked and proposed, and the selection being made.
  const sourceElements = new Map([...document.querySelectorAll('[data-source-block]')].map(node => [node.dataset.sourceBlock,node]));
  // #1067: re-rendering a source block must not drop a selection the user is making in it. The block's text never
  // changes, so the selection is kept as text positions and put back on the new nodes, direction included.
  function replaceBlock(node, children) {
    const next=document.createElement('div');next.append(...children);
    if(next.innerHTML===node.innerHTML) return;
    const selection=getSelection(), inside=selection.rangeCount && node.contains(selection.anchorNode) && node.contains(selection.focusNode);
    const position=(container,offset)=>{const range=document.createRange();range.setStart(node,0);range.setEnd(container,offset);return range.toString().length;};
    const kept=inside ? [position(selection.anchorNode,selection.anchorOffset),position(selection.focusNode,selection.focusOffset)] : null;
    node.replaceChildren(...next.childNodes);
    if(!kept) return;
    const point=at=>{
      const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);let text,last=null;
      while((text=walker.nextNode())) {if(at<=text.length) return [text,at];at-=text.length;last=text;}
      return last ? [last,last.length] : [node,0];
    };
    selection.setBaseAndExtent(...point(kept[0]),...point(kept[1]));
  }
  function renderSourceHighlights() {
    const ranges = new Map();
    for (const saved of [...state.entries.filter(e => e.annotation_id !== entry.annotation_id && e.status !== 'withdrawn'),entry]) {
      for (const anchor of saved.ranges || []) {
        if (!ranges.has(anchor.block_id)) ranges.set(anchor.block_id,[]);
        ranges.get(anchor.block_id).push({...anchor,current:saved.annotation_id === entry.annotation_id,owner:saved.annotation_id});
      }
    }
    // A proposal is marked apart: exact source text that is not linked yet.
    for (const proposal of [...(entry ? openProposals() : []), ...offerRanges]) {
      if (!ranges.has(proposal.block_id)) ranges.set(proposal.block_id,[]);
      ranges.get(proposal.block_id).push({...proposal,proposal:true});
    }
    for (const block of state.blocks) {
      const node = sourceElements.get(block.block_id);
      if (!node) continue;
      const anchors = ranges.get(block.block_id) || [];
      if (!anchors.length) {
        replaceBlock(node,[document.createTextNode(block.text)]);
        continue;
      }
      const chars = Array.from(block.text);
      const cuts = [...new Set([0,chars.length,...anchors.flatMap(a => [a.start,a.end])])].sort((a,b) => a-b);
      const content = document.createDocumentFragment();
      for (let i=0;i<cuts.length-1;i++) {
        const from=cuts[i], to=cuts[i+1], value=chars.slice(from,to).join('');
        const covering=anchors.filter(a => a.start<=from && a.end>=to);
        if (covering.length) {
          const mark=document.createElement('mark');
          if (covering.some(a => a.proposal)) {mark.dataset.proposal='true';mark.title='Voorstel van Metis';}
          else if (covering.some(a => a.current)) mark.dataset.current='true';
          else {mark.dataset.annotation=covering[0].owner;mark.title='Deze annotatie openen';}
          mark.textContent=value;content.append(mark);
        } else content.append(document.createTextNode(value));
      }
      replaceBlock(node,[content]);
    }
  }
  function captureSelection(value) {
    dismissOffer();
    // A selection made while Metis reads the statement waits; it must not make that answer stale.
    if(deriving) {queued=value;renderCard();return;}
    selected=value;lostSelection='';
    el('to-source').href='#'+value.block_id;
    const role=!hasCore() ? 'core' : 'context';
    entry.pending_range={...selected,role,evidence_function:null};
    change();
    onSelection();
  }
  function rememberSelection(event) {
    // Sidebar clicks must never replace an explicitly chosen block with the
    // browser's older, still-visible selection.
    if (event.type==='mouseup' || event.type==='touchend') {
      const started=selectingFromSource; selectingFromSource=false;
      if (!started) return;
    } else if (!event.target.closest?.('[data-source-block]')) return;
    const selection = window.getSelection();
    if (!selection.rangeCount || selection.isCollapsed) return;
    const range = selection.getRangeAt(0);
    const parent = node => (node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement).closest('[data-source-block]');
    const first = parent(range.startContainer), last = parent(range.endContainer);
    if (!first || first !== last) {
      // Nothing was selected, so nothing changes: an invalid drag must not create an empty draft.
      const had=!!(selected || entry.pending_range);selected = null;entry.pending_range=null;lostSelection=LOST_SELECTION;
      if(had) change();else renderCard();
      return;
    }
    const prefix = document.createRange(); prefix.selectNodeContents(first); prefix.setEnd(range.startContainer,range.startOffset);
    const endPrefix = document.createRange(); endPrefix.selectNodeContents(first); endPrefix.setEnd(range.endContainer,range.endOffset);
    const value={block_id:first.dataset.sourceBlock,start:Array.from(prefix.toString()).length,end:Array.from(endPrefix.toString()).length,quote:range.toString()};
    // A key that does not change the selection (Escape, Tab back) does not reopen a menu the worker closed.
    if(event.type==='keyup' && selected && ['block_id','start','end'].every(key=>selected[key]===value[key])) return;
    menuClosed=false;
    captureSelection(value);
  }
  document.addEventListener('mouseup',rememberSelection);
  document.addEventListener('touchend',rememberSelection);
  // Starting a new selection in the source puts the menu away; it returns at the new selection. Only its buttons
  // take a click or tap, so the text it lies over stays selectable.
  const startSelecting=event=>{
    selectingFromSource=!!event.target.closest?.('[data-source-block]');
    if(selectingFromSource && !menu.hidden) dismissMenu();
  };
  document.addEventListener('mousedown',startSelecting);
  document.addEventListener('touchstart',startSelecting);
  document.addEventListener('keyup',rememberSelection);
  for (const node of sourceElements.values()) node.addEventListener('keydown',event => moveSourceSelection(event,node));
  function moveSourceSelection(event,node) {
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key) || event.altKey || event.metaKey || event.ctrlKey && !['Home','End'].includes(event.key)) return;
    event.preventDefault();
    const selection=window.getSelection(),text=node.textContent;
    const inside=node.contains(selection.anchorNode) && node.contains(selection.focusNode);
    const offset=(container,position)=>{
      const prefix=document.createRange();prefix.selectNodeContents(node);prefix.setEnd(container,position);
      return prefix.toString().length;
    };
    const anchor=inside?offset(selection.anchorNode,selection.anchorOffset):0;
    const focus=inside?offset(selection.focusNode,selection.focusOffset):0;
    const boundaries=[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(text)].map(part=>part.index);
    boundaries.push(text.length);
    let next;
    if(event.key==='Home') next=0;
    else if(event.key==='End') next=text.length;
    else if(!event.shiftKey && anchor!==focus) next=event.key==='ArrowLeft'?Math.min(anchor,focus):Math.max(anchor,focus);
    else next=event.key==='ArrowLeft'?boundaries.filter(n=>n<focus).at(-1)??0:boundaries.find(n=>n>focus)??text.length;
    const point=position=>{
      const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);let child,last;
      while((child=walker.nextNode())) {
        if(position<=child.length) return [child,position];
        position-=child.length;last=child;
      }
      return last?[last,last.length]:[node,0];
    };
    const start=point(event.shiftKey?anchor:next),end=point(next);
    selection.setBaseAndExtent(start[0],start[1],end[0],end[1]);
    // The existing keyup handler captures exact source codepoint offsets;
    // source text and the save/receipt owner remain unchanged.
  }
  function revealSource(target) {
    const node = document.getElementById(target);
    if (!node || !node.closest('.annotation-document')) return;
    const folded = node.closest('details');
    if (folded) folded.open = true;
    node.scrollIntoView({block:'start'});
  }
  const pageNav = el('page-nav');
  if (pageNav) pageNav.addEventListener('change',() => revealSource(pageNav.value));
  document.addEventListener('click',event => {
    const link=event.target.closest?.('a[href^="#"]');
    if (link?.hash) revealSource(decodeURIComponent(link.hash.slice(1)));
    // A marked passage of another statement opens that statement's card.
    const mark=event.target.closest?.('mark[data-annotation]');
    if(mark && window.getSelection().isCollapsed) switchEntry(mark.dataset.annotation).catch(()=>{});
  });
  window.addEventListener('hashchange',() => revealSource(decodeURIComponent(location.hash.slice(1))));
  if (location.hash) revealSource(decodeURIComponent(location.hash.slice(1)));

  // ---- Saving: one writer, the kernel's annotation command; every edit is a numbered version.
  function change() {
    entry.status = 'draft'; dirty += 1;check=null;renderCard();
    status('Wijzigingen nog niet opgeslagen.'); clearTimeout(timer);
    timer = setTimeout(() => { flush().catch(() => {}); },600);
  }
  function requestForCurrent() {
    const reference = a => ({block_id:a.block_id,start:a.start,end:a.end,quote:a.quote,role:a.role,evidence_function:a.evidence_function,
      ...(a.relationship_id ? {relationship_id:a.relationship_id} : {})});
    const ranges = entry.ranges.map(reference);
    return {snapshot_id:state.snapshot_id,command_id:crypto.randomUUID(),annotation_id:entry.annotation_id,
      expected_revision:entry.revision,expected_generation:state.generation,extraction_hash:state.extraction_hash,normalization:state.normalization,
      expected_objects_revision:state.objects_revision,
      selection:{status:entry.status,object_type:entry.object_type,ranges,pending_range:entry.pending_range ? reference(entry.pending_range) : null,evidence_not_applicable:entry.evidence_not_applicable,
        ...(entry.declined_context?.length && !entry.disposition ? {declined_context:entry.declined_context.map(row=>({block_id:row.block_id,start:row.start,end:row.end,quote:row.quote ?? literal(row)}))} : {}),
        ...(entry.disposition ? {disposition:clone(entry.disposition)} : {
        field_evidence:Object.fromEntries(Object.entries(entry.field_evidence).map(([f,e]) =>
          [f,f==='type_evidence_spans' || f===fieldContract.type_core_fields[entry.object_type] ? {core:true} : e.span ? {...clone(e),quote:literal(e.span)} : clone(e)])),
        recommendation_semantics: entry.recommendation_semantics ? {...clone(entry.recommendation_semantics),
          direction_evidence:entry.recommendation_semantics.direction_evidence ? {span:entry.recommendation_semantics.direction_evidence,quote:literal(entry.recommendation_semantics.direction_evidence)} : null,
          strength_evidence:entry.recommendation_semantics.strength_evidence ? {span:entry.recommendation_semantics.strength_evidence,quote:literal(entry.recommendation_semantics.strength_evidence)} : null} : null})}};
  }
  async function flush() {
    clearTimeout(timer);
    if (running) { await running; if (dirty !== committed) return flush(); return; }
    if (failed) throw new Error('Los eerst de opslagfout op.');
    if (dirty === committed) return;
    running = (async () => {
      while (dirty !== committed) {
        const version = retryRequest ? retryVersion : dirty;
        const body = retryRequest || requestForCurrent(); retryRequest = body; retryVersion = version;
        status('Opslaan…');
        try {
          // A lost connection is said in the worker's language; the browser's own text is not.
          const response = await fetch('/annotations/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
            .catch(() => {throw new Error('Geen verbinding met de server. Je werk staat nog hier; probeer opnieuw.');});
          const data = await response.json();
          el('conflict').hidden = true;
          if (!response.ok) {
            if (data.error === 'annotation_core_duplicate' && data.conflicting_annotation_id) {
              el('conflict-link').href = '/annotations?' + new URLSearchParams({document:state.snapshot_id,annotation:data.conflicting_annotation_id});
              el('conflict').hidden = false;
            }
            if(['annotation_write_conflict','annotation_objects_stale','annotation_representation_stale','annotation_client_contract_stale'].includes(data.error)) {
              el('save-conflict').hidden=false;el('local-work').textContent=body.selection.ranges.map(a=>a.quote).join('\n\n');
              el('server-work').href='/annotations?'+new URLSearchParams({document:state.snapshot_id,annotation:entry.annotation_id});
            }
            // A duplicate statement is an answer about the input, like a validation error: change the
            // selection (or remove it with −) instead of retrying the same request.
            const answer = response.status === 422 || data.error === 'annotation_core_duplicate';
            if (answer) { retryRequest = null; }
            const error = new Error(data.message || 'Opslaan mislukt.'); error.validation = answer; throw error;
          }
          entry.revision = data.revision; state.generation = data.generation;
          if (data.objects_revision) state.objects_revision = data.objects_revision;
          if (built() && data.revision > body.expected_revision) built().pending = true;
          if (savedBindings[entry.annotation_id] && data.revision > body.expected_revision) savedBindings[entry.annotation_id].pending = true;
          // Only the sent snapshot is committed; edits made during fetch remain dirty.
          delete entry.historical_finding;
          const saved = {...clone(entry),...body.selection,revision:data.revision};
          const index = state.entries.findIndex(e => e.annotation_id === entry.annotation_id);
          if (index < 0) state.entries.push(saved); else state.entries[index] = saved;
          committed = version; retryRequest = null;setEntryUrl(entry.annotation_id);
          el('retry').hidden = true;
          status(built() ? 'Aanpassing opgeslagen.' : data.status === 'ready' ? 'Klaar voor documentcontrole en opgeslagen.' : data.status === 'withdrawn' ? 'Annotatie teruggenomen en opgeslagen.' : 'Concept opgeslagen.');renderCard();
        } catch (error) {
          failed = !error.validation; el('retry').hidden = false;
          status('Opslaan mislukt. ' + error.message); throw error;
        }
      }
    })();
    try { await running; } finally { running = null; }
  }
  el('save-current-format').addEventListener('click', async () => {
    if (entry.historical_finding !== 'annotation_historical_format' || running || failed) return;
    dirty += 1;
    try { await flush(); await runCheck(); } catch { /* flush shows the server response */ }
  });
  el('retry').addEventListener('click',() => { failed = false; el('retry').hidden = true; flush().catch(() => {}); });

  // ---- The check: one at a time. An edit made while a check is running invalidates that
  // answer, so the same run checks again instead of leaving the card unchecked.
  let checkRun=null, checkAgain=false;
  function runCheck() {
    if(checkRun) {checkAgain=true;return checkRun;}
    checkRun=(async()=>{
      do {
        checkAgain=false;checking=true;check=null;renderCard();
        try {
          await flush();
          if(!entry.revision) {status('Wijs eerst een uitspraak aan.');break;}
          const id=entry.annotation_id, version=dirty;
          const response=await fetch('/annotations/check?'+new URLSearchParams({document:state.snapshot_id,annotation:id}),{cache:'no-store'});
          const data=await response.json();
          if(!response.ok) throw new Error(data.message || 'Controle kon niet worden gelezen. Probeer opnieuw.');
          if(entry.annotation_id===id && dirty===version) check=data;
          else checkAgain=true;
          if(check && !checkIsCurrent()) {check=null;status('Het opgeslagen werk is gewijzigd. Heropen de annotatie om de actuele versie te controleren.');}
        } catch(error) {status((failed ? 'Opslaan mislukt. ' : 'Controle niet gelukt. ')+error.message);checkAgain=false;}
      } while(checkAgain);
    })().finally(()=>{checkRun=null;checking=false;render();});
    return checkRun;
  }

  // ---- Finishing: this object, then the next; or the document check; or a rebuild of a built object.
  // Marks the current object ready through the existing check and save. True when it is saved as ready.
  async function finishCurrent() {
    if(entry.status==='ready' && dirty===committed) return true;
    if(finalizing || !checkIsCurrent() || check.findings.length) return false;
    finalizing=true;el('editor-inputs').disabled=true;
    try {
      await flush();
      await runCheck();
      if(!checkIsCurrent() || check.findings.length) return false;
      entry.status='ready';dirty+=1;await flush();
      return entry.status==='ready' && dirty===committed;
    } catch(_) { return false; /* Preserve current work and the exact uncertain request. */ }
    finally {finalizing=false;el('editor-inputs').disabled=false;renderCard();}
  }
  // Saving first commits a statement that was only selected.
  async function saveCard() {
    // #1067: while 'Gereed' runs the kind cannot change; a choice made now would complete this save unseen.
    saving=true;kindSelect.disabled=true;
    let saved=false;
    try {
      if(!hasCore() && selected) await useAs('core');
      saved=hasCore() && await finishCurrent();
    } finally {saving=false;kindSelect.disabled=deriving;}
    if(!saved && openProposals().length) {
      asked=true;renderCard();
      document.querySelector('#annotation-simple-rows [data-proposal=add]')?.focus();
    }
    return saved;
  }
  const toOverview = () => { window.location.href = '/annotations?' + new URLSearchParams({document:state.snapshot_id,overview:'true'}); };
  el('ready').addEventListener('click',async()=>{
    if(await saveCard()) {
      const focus=entry.ranges.find(a=>a.role==='core')?.block_id;
      load('');status('Opgeslagen. Selecteer de volgende uitspraak.');requestOffer(focus);
    }
  });
  async function finishSourceSelection() {
    if(finalizing || saving || checking || deriving || rebuilding) return;
    if(hasCore() || selected) {if(await saveCard()) toOverview();return;}
    // An object that holds nothing is not left behind to block the document.
    if(entry.revision) {await discardObject();if(entry.revision) return;}
    toOverview();
  }
  el('finish').addEventListener('click',finishSourceSelection);
  el('saved-overview').addEventListener('click',event=>{
    event.preventDefault();finishSourceSelection().catch(error=>status(error.message));
  });
  const changedSinceBuild = () => !!built()?.pending || dirty!==committed || entry.status!=='ready';
  el('rebuild').addEventListener('click',async()=>{
    const object=built();
    if(!object || rebuilding) return;
    const review='/review?'+new URLSearchParams({document:state.snapshot_id,object:object.object_id});
    if(!changedSinceBuild()) {window.location.href=review;return;}
    if(!await saveCard()) return;
    rebuilding=true;renderCard();status('Kennisobject wordt opnieuw gebouwd…');
    try {
      const response=await fetch('/annotations/rebuild',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({document:state.snapshot_id,annotation:entry.annotation_id,command_id:crypto.randomUUID(),expected_generation:state.generation})});
      const data=await response.json();
      if(!response.ok) throw new Error(data.message || 'Opnieuw bouwen is niet gestart. Je aanpassing is bewaard.');
      window.location.href=data.review_url;
    } catch(error) {status(error.message);rebuilding=false;renderCard();}
  });

  // ---- Loading a statement's card.
  let offerRanges=[], offerRequest=null, adoptedCard=null;
  function dismissOffer() {
    offerRequest?.abort();
    offerRequest=null;
    const highlighted=offerRanges.length;
    offerRanges=[];
    el('offer').hidden=true;
    if(highlighted) renderSourceHighlights();
  }
  async function requestOffer(focus) {
    dismissOffer();
    if(entry.revision || selected || hasCore()) return;
    const controller=new AbortController(), basis=suggestionBasis(), id=entry.annotation_id;
    offerRequest=controller;
    el('offer').hidden=false;
    el('offer-message').textContent='Metis zoekt een uitspraak…';
    el('offer-ranges').replaceChildren();
    el('take-offer').hidden=true;
    el('skip-offer').hidden=false;
    try {
      const response=await fetch('/annotations/passage-offer',{method:'POST',signal:controller.signal,
        headers:{'Content-Type':'application/json'},body:JSON.stringify({snapshot_id:state.snapshot_id,focus:focus || null,basis})});
      if(!response.ok) throw Error();
      const {ranges}=await response.json();
      if(controller.signal.aborted || entry.annotation_id!==id || selected || dirty!==0 ||
          JSON.stringify(basis)!==JSON.stringify(suggestionBasis())) return;
      offerRanges=ranges;
      const labels={core:'Uitspraak',context:'Hoort erbij',evidence:'Onderbouwing'};
      for(const range of ranges) {
        const title=document.createElement('dt'),quote=document.createElement('dd');
        title.textContent=labels[range.role];quote.textContent=literal(range);
        el('offer-ranges').append(title,quote);
      }
      el('offer-message').textContent=ranges.length ? 'Voorstel van Metis' : 'Geen voorstel gevonden. Selecteer zelf een uitspraak.';
      el('take-offer').hidden=!ranges.length;
      el('skip-offer').hidden=!ranges.length;
      renderSourceHighlights();
    } catch(error) {
      if(controller.signal.aborted) return;
      el('offer-message').textContent='Voorstel niet beschikbaar. Selecteer zelf een uitspraak.';
      el('skip-offer').hidden=true;
    }
  }
  el('skip-offer').addEventListener('click',()=>{dismissOffer();status('Selecteer zelf een uitspraak.');});
  el('take-offer').addEventListener('click',async()=>{
    if(!offerRanges.length || hasCore() || selected || entry.revision) return;
    let draft=entry;
    for(const range of offerRanges)
      draft=bindRange(draft,range,{role:range.role,evidenceFunction:'supported_by'},fieldContract).entry;
    dismissOffer();adoptedCard=draft.annotation_id;entry=draft;resetFields();change();render();
    await derive();
  });
  function load(id) {
    dismissOffer();
    const saved = state.entries.find(e => e.annotation_id === id);
    if (saved?.historical_finding === 'annotation_historical_read_only') {
      const query = new URLSearchParams({document:state.snapshot_id, overview:'true'});
      window.location.assign('/annotations?' + query + '#historisch-' + encodeURIComponent(id));
      return false;
    }
    entry = saved ? clone(saved) : {annotation_id:crypto.randomUUID(),revision:0,status:'draft',object_type:null,ranges:[],evidence_not_applicable:false};
    for(const a of entry.ranges) if(a.role!=='core') a.relationship_id=linkId(a);
    if(!entry.field_evidence) resetFields();
    check=null;deriving=false;queued=null;asked=false;lostSelection='';menuClosed=false;
    el('suggestion-note').textContent='';
    selected = entry.pending_range ? clone(entry.pending_range) : null;
    if (selected) el('to-source').href='#'+selected.block_id;
    dirty = committed = 0;setEntryUrl(saved?.annotation_id);
    el('conflict').hidden = true;
    render();
    if(hasCore()) runCheck();
    return true;
  }
  async function switchEntry(id) { await flush(); if (load(id)) status(loadedStatus()); }
  window.addEventListener('beforeunload',event => { if (dirty !== committed || running) { event.preventDefault(); event.returnValue = ''; } });
  // #1067: a browser that remembered the retired step form forgets it.
  try {localStorage.removeItem('metis-annotation-form');} catch(_) { /* nothing remembered */ }
  if (!load(new URLSearchParams(window.location.search).get('annotation'))) return;
  el('editor-inputs').disabled=false;
  el('initializing').hidden=true;
  status(loadedStatus());
  if(!entry.revision) requestOffer(state.blocks.find(b=>location.hash==='#'+b.block_id)?.block_id);
  if(buildPhase?.state==='running') setTimeout(refreshSavedBuild,2000);
})();
