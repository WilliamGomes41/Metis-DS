/* Source references only. Canonical text and object identity belong to the kernel. */
import {bindRange} from '/annotations/binding.mjs';
(() => {
  'use strict';
  const state = JSON.parse(document.getElementById('annotation-data').textContent);
  const el = id => document.getElementById('annotation-' + id);
  const labels = {core:'Kernuitspraak',population:'Doelgroep',context:'Context',condition:'Voorwaarde',exception:'Uitzondering',explanation:'Toelichting',evidence:'Onderbouwing',
    actor:'Uitvoerder',scope:'Toepassingssituatie',timing:'Tijdstip of periode',list_introduction:'Inleiding bij een lijst',row_header:'Rijkop',column_header:'Kolomkop'};
  let entry, selected = null, dirty = 0, committed = 0, timer, running = null, retryRequest = null, retryVersion = 0, failed = false;
  let selectingFromSource = false, activeBlock = null;
  let suggesting=false;
  const clone = value => JSON.parse(JSON.stringify(value));
  const fieldContract = state.field_contract;
  let repairingLink=null, task=1, target=null, check=null, checking=false, finalizing=false, confirmation=null;
  // Presentation only: why the last proposal left something open, and which
  // part of the manual form answers the point the user opened. Never saved.
  let openPoints=[], only=null;
  // #1060 slice 2: the default card asks three things in the language of the
  // source. The step form remains as the advanced form until it is retired.
  // The choice of form is a per-browser convenience; the page works without storage.
  const formKey='metis-annotation-form';
  // #1067: the step form is retired; a browser that remembered it gets the card.
  try {localStorage.removeItem(formKey);} catch(_) { /* nothing remembered */ }
  const storedForm = () => false;
  // The step form also opens by itself for the one object that needs it; that never outlives the object.
  let advanced=storedForm(), replacingCore=false, deriving=false;
  // #1060 slice 4: a proposal is answered with + or −, never by ignoring it.
  // 'asked' only says the worker tried to save while one was open.
  let asked=false;
  const openProposals = () => checkIsCurrent() ? check.proposals || [] : [];
  const simple = () => true;
  // Signals a worker can act on, shown in the row they are about.
  const leaning=new Set(['supported_object_missing','condition_target_missing','exception_target_missing','annotation_relation_target_missing','no_independent_claim']);
  const broken=new Set(['incomplete_sentence','recommendation_core_incomplete']);
  const openField = field => {const e=entry.field_evidence?.[field];return !!e && !e.core && !e.span && e.missing_reason==='uncertain';};
  const pointFor = field => openPoints.find(point=>point.field===field && openField(field));
  const reason = point => point.reason==='quote_ambiguous' ? 'De tekst “'+point.quote+'” komt meer dan eens voor in je selectie. Wijs de bedoelde plaats aan.' :
    point.reason==='quote_not_in_selection' ? 'Metis vond hiervoor geen letterlijke tekst in je selectie.' : 'Metis is hier niet zeker van.';
  function answerPoint(field) {
    openPoints=openPoints.filter(point=>point.field!==field);
    if(only) {showTask(3,true);runCheck();}
  }
  const hasCore = () => entry.ranges.some(a => a.role==='core');
  const checkIsCurrent = () => check && dirty===committed && check.annotation_id===entry.annotation_id &&
    check.revision===entry.revision && check.basis.snapshot_id===state.snapshot_id &&
    check.basis.working_revision_id===state.working_revision_id && check.basis.normalization===state.normalization &&
    check.basis.generation===state.generation &&
    check.basis.extraction_hash===state.extraction_hash && check.basis.objects_revision===state.objects_revision;
  function cancelConfirmation() {
    const pending=confirmation;confirmation=null;el('confirm').hidden=true;pending?.cancel();
    if(pending?.focus?.isConnected) pending.focus.focus();
  }
  function setEntryUrl(id) {
    const url=new URL(location.href);
    if(id) url.searchParams.set('annotation',id);else url.searchParams.delete('annotation');
    history.replaceState(null,'',url);
  }
  function confirmChange(message, action, cancel=()=>{}) {
    if(confirmation) return;
    confirmation={action,cancel,focus:document.activeElement};el('confirm-message').textContent=message;el('confirm').hidden=false;
    el('confirm-title').focus();
  }
  el('confirm-cancel').addEventListener('click',cancelConfirmation);
  el('confirm-accept').addEventListener('click',()=>{const pending=confirmation;confirmation=null;el('confirm').hidden=true;pending?.action();if(pending?.focus?.isConnected) pending.focus.focus();});
  function chooseTarget(value) {
    cancelConfirmation();repairingLink=null;el('role').disabled=!!entry.disposition;
    target=value;clearChoice();
    if(value.kind==='range') el('role').value=value.role;
    for(const select of el('fields').querySelectorAll('select')) select.hidden=value.kind!=='field' || select.dataset.missingField!==value.field;
    for(const button of el('fields').querySelectorAll('button[data-field]')) button.setAttribute('aria-pressed',String(value.kind==='field' && button.dataset.field===value.field));
    updateBindingControls();
  }
  function showTask(value, focus=false, part=null) {
    cancelConfirmation();task=value;
    const partChanged=only!==part;only=part;
    for(let n=1;n<=3;n++) {
      el('task-'+n).hidden=simple() || n!==task;
      if(n===task) el('step-'+n).setAttribute('aria-current','step');else el('step-'+n).removeAttribute('aria-current');
    }
    if(task===1) {repairingLink=null;clearChoice();target={kind:'range',role:'core'};el('role').value='core';el('role').disabled=!!entry.disposition;}
    else if(task===2 && target?.role==='core') target=null;
    el('selection-tools').hidden=task===3;
    el('back').hidden=task!==2 || !!only;
    if(partChanged) renderFields();else {renderSummary();updateBindingControls();}
    if(focus) el('heading-'+task).focus();
  }
  const missingText={not_stated:'Niet in de bron genoemd',not_applicable:'Niet van toepassing',uncertain:'Nog uitzoeken'};
  const coreCode = code => ['annotation_core_required','incomplete_sentence','no_independent_claim','annotation_source_disposition_unresolved'].includes(code) || code.startsWith('recommendation_core');
  const semanticCode = code => code==='recommendation_semantics_invalid' || code.startsWith('recommendation_direction') || code.startsWith('recommendation_strength');
  function renderSummary() {
    const coreText=entry.ranges.filter(a=>a.role==='core').map(a=>a.quote).join(' ');
    el('type-summary').textContent=entry.object_type ? el('type').selectedOptions[0]?.textContent : 'Nog niet vastgesteld';
    el('proposal-core').textContent=coreText;
    el('core-summary').textContent=hasCore() ? 'Gekozen uitspraak: '+coreText : '';
    el('evidence-summary').textContent=entry.ranges.some(a=>a.role==='evidence') ? 'Brononderbouwing toegevoegd.' : entry.evidence_not_applicable ? 'Onderbouwing expliciet als niet van toepassing vastgelegd.' : 'Onderbouwing: nog niet gekoppeld.';
    // One overview. A part that needs an answer says so in its own row, and
    // every part can be changed from the row that shows it.
    const current=checkIsCurrent(), findings=current ? check.findings : [], used=new Set();
    // A finding belongs to one row only: the first row that claims it.
    const take=test=>{const found=findings.filter(f=>!used.has(f) && test(f));for(const f of found) used.add(f);return found[0];};
    el('review-summary').replaceChildren();el('empty-fields').replaceChildren();
    // #1060: a signal is what Metis could not derive. It informs and never blocks.
    const signals=current ? check.signals || [] : [], shown=new Set();
    const row=(key,label,text,{open='',note='',span=null,act,parent=el('review-summary')}={})=>{
      const dt=document.createElement('dt'),dd=document.createElement('dd'),value=document.createElement('span');
      dt.textContent=label;value.textContent=text;dd.dataset.row=key;dd.append(value);
      if(span) {const link=document.createElement('a');link.href='#'+span.block_id;link.textContent='Bekijk in bron';dd.append(' ',link);}
      if(open) {const p=document.createElement('p');p.className='annotation-open';p.textContent=open;dd.dataset.open='true';dd.append(p);}
      else if(note) {const p=document.createElement('p');p.className='annotation-signal';p.textContent=note;dd.dataset.signal='true';dd.append(p);}
      {
        const button=document.createElement('button');button.type='button';
        button.className=open ? 'btn-secondary' : 'annotation-row-action';
        button.textContent=open ? 'Beantwoorden' : 'Aanpassen';button.setAttribute('aria-label',button.textContent+': '+label);
        button.addEventListener('click',act);dd.append(' ',button);
      }
      parent.append(dt,dd);
    };
    const typeFinding=!entry.object_type && !entry.disposition && hasCore() && take(f=>f.code==='annotation_core_required');
    const coreFinding=take(f=>coreCode(f.code));
    row('type','Type',entry.disposition ? 'Bronstuk' : entry.object_type ? el('type').selectedOptions[0]?.textContent : 'Nog niet gekozen',
      {open:typeFinding ? (openPoints.some(p=>p.reason==='type_unclear') ? 'Metis kon het type niet bepalen. ' : '')+'Kies het type uitspraak.' : '',act:()=>{showTask(1,true);el('type').focus();}});
    row('core',entry.disposition ? 'Bronstuk' : 'Kernuitspraak',coreText || 'Nog niet aangewezen',{open:coreFinding ? coreFinding.message : '',act:()=>showTask(1,true)});
    for(const a of entry.ranges.filter(a=>a.role!=='core'))
      row('range',labels[a.role]+(a.required_for_meaning?' (essentieel)':''),a.quote,{span:a,act:()=>{showTask(2,true,{evidence:true});el('linked').open=true;}});
    if(!entry.disposition) {
      for(const option of el('field').options) {
        const field=option.value,e=entry.field_evidence?.[field];
        if(!e || e.core) continue;
        const finding=take(f=>f.field===field),point=pointFor(field);
        const open=point ? reason(point) : finding ? finding.message : '';
        const signal=signals.find(item=>item.field===field);if(signal) shown.add(signal);
        row(field,option.textContent,e.span ? literal(e.span) : missingText[e.missing_reason] || 'Nog niet aangewezen',
          {open,note:signal?.message || '',act:()=>repairFinding({code:finding?.code || 'open_point',field}),parent:e.span || open || signal ? el('review-summary') : el('empty-fields')});
      }
      if(entry.object_type==='recommendation') {
        const semantics=entry.recommendation_semantics || {},finding=take(f=>semanticCode(f.code));
        row('semantics','Richting en sterkte',(({for:'Toepassen of overwegen',against:'Afraden of vermijden'})[semantics.direction] || 'Richting nog niet gekozen')+' · '+
          (semantics.strength_status==='not_stated' ? 'sterkte niet vermeld' : ({strong:'sterk',weak:'zwak'})[semantics.strength] || 'sterkte nog niet gekozen'),
          {open:finding ? finding.message : '',act:()=>repairFinding({code:'recommendation_semantics_invalid'})});
      }
      const evidence=take(f=>f.code==='annotation_evidence_required');
      row('evidence','Onderbouwing',entry.ranges.some(a=>a.role==='evidence') ? 'Gekoppeld' : entry.evidence_not_applicable ? 'Niet van toepassing' : 'Nog niet gekoppeld',
        {open:evidence ? 'Wijs onderbouwing aan of kies ‘niet van toepassing’.' : '',act:()=>repairFinding({code:'annotation_evidence_required'})});
    }
    const empty=el('empty-fields').children.length/2;
    el('empty').hidden=!empty;el('empty-summary').textContent='Niet ingevuld ('+empty+')';
    const confirmedReady=entry.status==='ready' && dirty===committed;
    el('check').replaceChildren();
    const p=document.createElement('p');
    p.textContent=checking ? 'Controleren…' : confirmedReady ? 'Klaar voor documentcontrole. Dit is geen inhoudelijke goedkeuring of publicatie.' :
      !current ? 'Nog niet gecontroleerd.' : findings.length ? (findings.length===1 ? 'Nog 1 controlepunt open.' : 'Nog '+findings.length+' controlepunten open.') : signals.length ? 'Je kunt afronden. Metis kon niet alles vaststellen.' : 'Alles is ingevuld. Je kunt afronden.';
    el('check').append(p);
    const rest=findings.filter(f=>!used.has(f));
    if(rest.length) {
      const list=document.createElement('ul');
      for(const finding of rest) {
        const li=document.createElement('li'),button=document.createElement('button');
        button.type='button';button.className='btn-secondary';button.textContent=finding.message+' Aanvullen';
        button.addEventListener('click',()=>repairFinding(finding));li.append(button);list.append(li);
      }
      el('check').append(list);
    }
    const loose=signals.filter(item=>!shown.has(item));
    if(loose.length && !entry.disposition) {
      const list=document.createElement('ul');list.className='annotation-signals';
      for(const message of new Set(loose.map(item=>item.message))) {const li=document.createElement('li');li.textContent=message;list.append(li);}
      el('check').append(list);
    }
    el('recheck').hidden=checking || current || confirmedReady;
  }
  // Selecting text is the statement. '+' adds text to a row, '−' removes it.
  let armed=null, queued=null;
  // A meaning reference that lay only inside a removed range no longer has a source.
  function clearDependentFields(removed) {
    const contains=(outer,inner)=>outer.block_id===inner.block_id && outer.start<=inner.start && outer.end>=inner.end;
    for(const [field,evidence] of Object.entries(entry.field_evidence || {}))
      if(evidence.span && contains(removed,evidence.span) && !entry.ranges.some(range=>contains(range,evidence.span)))
        entry.field_evidence[field]={span:null,missing_reason:'uncertain'};
  }
  function removeRange(anchor) {
    const index=entry.ranges.indexOf(anchor);if(index<0) return;
    if(anchor.required_for_meaning) entry.required_links.push({relationship_id:linkId(anchor),role:anchor.role,evidence_function:anchor.evidence_function,required_for_meaning:true,withdrawal_reason:null});
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
      try {entry=bindRange(entry,proposal,{role:'list_introduction',essential:false,repairingLink:null,evidenceFunction:null},fieldContract).entry;}
      catch(error) {status(error.message);return;}
    } else decline(proposal);
    change();render();runCheck();
  }
  // Removing a piece changes the statement: what Metis derived from it no longer holds.
  // Removing the last piece removes the object itself, so no empty draft is left to block the document.
  function removeStatement(anchor) {
    const rest=anchor ? entry.ranges.filter(a=>a.role==='core' && a!==anchor) : [];
    if(!rest.length && !state.object_bindings?.[entry.annotation_id]) {discardObject().catch(()=>{});return;}
    entry.ranges=entry.ranges.filter(a=>anchor ? a!==anchor : a.role!=='core');entry.object_type=null;el('type').value='';
    entry.field_evidence=null;resetFields();armed=null;change();render();
    if(hasCore()) derive().catch(()=>{});
  }
  async function discardObject() {
    armed=null;queued=null;
    try {
      // Withdraw what is stored as it now is; a refused edit (such as a duplicate) is not sent first.
      if(entry.revision) {entry.status='withdrawn';dirty+=1;await flush();}
      load('');entries();status('Weggehaald. Selecteer de volgende uitspraak.');
    } catch(_) { /* The save status says what failed; the work stays visible. */ }
  }
  async function setNoEvidence(value) {
    if(value && !hasCore()) {await useAs('core');if(!hasCore()) return;}
    entry.evidence_not_applicable=value;el('na').checked=value;change();await runCheck();
  }
  function renderSimple() {
    const core=entry.ranges.filter(a=>a.role==='core'),belongs=entry.ranges.filter(a=>a.role!=='core' && a.role!=='evidence'),evidence=entry.ranges.filter(a=>a.role==='evidence');
    const built=!!state.object_bindings?.[entry.annotation_id];
    const done=entry.status==='ready' && dirty===committed && !built,current=checkIsCurrent(),provisional=!core.length && !!selected;
    el('simple-heading').textContent=!core.length && !selected ? 'Selecteer de uitspraak in de bron' : done ? 'Klaar voor documentcontrole' : '';
    el('simple-heading').hidden=!el('simple-heading').textContent;
    const findings=current ? check.findings : [],signals=current ? check.signals || [] : [],proposals=openProposals();
    const rows=el('simple-rows');rows.replaceChildren();
    const hint=(dd,value)=>{const p=document.createElement('p');p.textContent=value;p.className='annotation-hint';dd.append(p);};
    const sign=(parent,glyph,label,run,pressed=null)=>{const button=document.createElement('button');button.type='button';button.className='annotation-sign';button.textContent=glyph;button.setAttribute('aria-label',label);button.title=label;if(pressed!==null) button.setAttribute('aria-pressed',String(pressed));button.addEventListener('click',run);parent.append(button);return button;};
    const line=(dd,value,label,remove)=>{const div=document.createElement('div'),p=document.createElement('p');div.className='annotation-line';p.textContent=value;div.append(p);sign(div,'−',label,remove);dd.append(div);};
    const row=(key,label,build,add=null)=>{const dt=document.createElement('dt'),dd=document.createElement('dd'),name=document.createElement('span');name.textContent=label;dt.append(name);dt.dataset.row=key;dd.dataset.row=key;if(add) sign(dt,'+',add.label,add.run,add.pressed);build(dd);rows.append(dt,dd);};
    // #1067: source text that is no statement (recorded in the document check) shows what it is, nothing to fill in.
    if(entry.disposition) {
      const reasons=Object.values(fieldContract.source_roles).flat();
      const kind=reasons.find(r=>r.value===entry.disposition.reason)?.label || 'Geen uitspraak';
      row('core','Geen uitspraak: '+kind.toLowerCase(),dd=>{for(const a of core) line(dd,a.quote,'Weghalen: '+a.quote,()=>{discardObject().catch(()=>{});});});
      el('simple-type').hidden=true;el('simple-status').textContent='';el('simple-notes').replaceChildren();
      return;
    }
    if(core.length || provisional) row('core','Uitspraak',dd=>{
      if(provisional) line(dd,selected.quote,'Selectie weghalen',()=>removeStatement());
      for(const a of core) line(dd,a.quote,'Weghalen uit de uitspraak: '+a.quote,()=>removeStatement(a));
      if(armed==='core') hint(dd,'Selecteer het volgende stuk van de uitspraak in de bron.');
      if(signals.some(item=>broken.has(item.code))) hint(dd,'Dit lijkt een afgebroken zin. Is de hele zin geselecteerd?');
    },core.length ? {label:'Nog een stuk van de uitspraak toevoegen',run:()=>arm('core'),pressed:armed==='core'} : null);
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
        if(armed==='context') hint(dd,'Selecteer de tekst in de bron.');
        else if(!belongs.length && !proposals.length && signals.some(item=>leaning.has(item.code))) hint(dd,'De uitspraak leunt mogelijk op andere tekst. Hoort er een zin bij?');
      },{label:'Tekst toevoegen aan Hoort erbij',run:()=>arm('context'),pressed:armed==='context'});
      row('evidence','Onderbouwing',dd=>{
        for(const a of evidence) line(dd,a.quote,'Weghalen: '+a.quote,()=>removeRange(a));
        // An earlier explicit choice stays visible and removable; the card no longer asks for it.
        if(!evidence.length && entry.evidence_not_applicable) line(dd,'Vastgelegd als niet van toepassing.','Keuze weghalen: niet van toepassing',()=>{setNoEvidence(false).catch(()=>{});});
        if(armed==='evidence') hint(dd,'Selecteer de onderbouwing in de bron.');
        if(!evidence.length && !entry.evidence_not_applicable && armed!=='evidence') hint(dd,'Niets gekoppeld. Staat de onderbouwing in de bron? Voeg haar toe met +.');
      },{label:'Tekst toevoegen aan Onderbouwing',run:()=>arm('evidence'),pressed:armed==='evidence'});
    }
    el('simple-type').hidden=!core.length || !!entry.object_type || deriving;
    if(!el('simple-type').hidden) el('simple-type-select').value='';
    const own=finding=>finding.code==='annotation_core_required' && !entry.object_type || finding.code==='annotation_context_proposal_open';
    const lost=!selected && el('selection').textContent.startsWith('Wijs één bereik') ? el('selection').textContent : '';
    el('simple-status').textContent=deriving ? 'Metis leest de uitspraak…'+(queued ? ' Je selectie wordt daarna toegevoegd.' : '') : lost ||
      (core.length && selected && !armed ? 'Klik op + bij de regel waar de geselecteerde tekst bij hoort.' : !core.length ? '' :
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
  async function derive() {
    deriving=true;renderSimple();
    try {await proposeMeaning();}
    finally {
      deriving=false;
      if(simple()) {
        el('suggestion-note').textContent='';await runCheck();
        if(queued) {const value=queued;queued=null;captureSelection(value);}
      }
    }
  }
  async function useAs(kind) {
    if(!selected || finalizing || deriving) return;
    if(kind==='core') {
      target={kind:'range',role:'core'};el('role').value='core';
      bindSelected();if(selected) return;
      await derive();return;
    }
    el('role').value=kind==='evidence' ? 'evidence' : 'context';target={kind:'range',role:el('role').value};
    // The card asks no essentiality question: what is linked belongs, and '−' simply removes it.
    el('essential').checked=false;el('additional').checked=true;el('function').value='supported_by';
    if(kind==='evidence') {entry.evidence_not_applicable=false;el('na').checked=false;}
    bindSelected();await runCheck();
  }
  // '+' on a row: use the current selection, or wait for the next one.
  function arm(kind) {
    (async()=>{
      if(finalizing || deriving) return;
      if(!hasCore()) {if(!selected) return;armed=kind;await useAs('core');renderSimple();return;}
      if(selected) {armed=null;await useAs(kind);return;}
      armed=armed===kind ? null : kind;renderSimple();
    })().catch(()=>{});
  }
  function simpleSelection() {
    // A selection alone is already the statement: check it so Metis can propose what belongs to it.
    if(!hasCore()) {renderSimple();if(!armed) runCheck();return;}
    if(!armed) {renderSimple();return;}
    const kind=armed;armed=null;useAs(kind).catch(()=>{});
  }
  for(const option of el('type').options) if(option.value && option.value!=='source_disposition') el('simple-type-select').add(new Option(option.textContent,option.value));
  el('simple-type-select').addEventListener('change',()=>{
    const value=el('simple-type-select').value;if(!value) return;
    el('type').value=value;el('type').dispatchEvent(new Event('change'));runCheck();
  });
  document.addEventListener('click',event=>{
    const mark=event.target.closest?.('mark[data-annotation]');
    if(!mark || !simple() || !window.getSelection().isCollapsed) return;
    switchEntry(mark.dataset.annotation).catch(()=>{});
  });
  // #1067: every point is answered in the card itself; nothing opens another form.
  function repairFinding(finding) {
    const code=finding.code;
    if(code==='annotation_context_proposal_open') {asked=true;renderSimple();return;}
    if(code==='annotation_core_required' && hasCore() && !entry.object_type) {el('simple-type-select').focus();return;}
    if(code==='annotation_required_relationship_missing') {el('required-links').scrollIntoView({block:'nearest'});return;}
    status(finding.message);
  }
  // One check at a time. An edit made while a check is running invalidates that
  // answer, so the same run checks again instead of leaving the card unchecked.
  let checkRun=null, checkAgain=false;
  function runCheck() {
    if(checkRun) {checkAgain=true;return checkRun;}
    checkRun=(async()=>{
      do {
        checkAgain=false;checking=true;check=null;renderSummary();updateBindingControls();
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
        } catch(error) {status('Controle niet gelukt. '+error.message);checkAgain=false;}
      } while(checkAgain);
    })().finally(()=>{checkRun=null;checking=false;renderSummary();updateBindingControls();renderSourceHighlights();});
    return checkRun;
  }
  for(let n=1;n<=3;n++) el('step-'+n).addEventListener('click',()=>{showTask(n,true);if(n===3) runCheck();});
  el('change-type').addEventListener('click',()=>{showTask(1,true);el('type').focus();});
  el('back').addEventListener('click',()=>showTask(task-1,true));
  el('recheck').addEventListener('click',runCheck);
  el('context-tools').addEventListener('toggle',()=>{
    if(el('context-tools').open && !target && !entry.disposition)
      chooseTarget({kind:'range',role:el('role').value==='core'?'context':el('role').value});
  });
  const linkId = a => a.relationship_id || 'link-v1:'+JSON.stringify([entry.annotation_id,a.role,a.block_id,a.start,a.end]);
  const literal = span => {
    const block=state.blocks.find(b => b.block_id === span.block_id);
    return block ? Array.from(block.text).slice(span.start,span.end).join('') : '';
  };
  const sourceElements = new Map([...document.querySelectorAll('[data-source-block]')].map(node => [node.dataset.sourceBlock,node]));
  function activateBlock(block) {
    if (!block || activeBlock?.block_id === block.block_id) return;
    activeBlock = block;
    updateBindingControls();
  }
  function essentialChoice() {
    return el('essential').checked ? true : el('additional').checked ? false : null;
  }
  function clearChoice() { el('essential').checked=false;el('additional').checked=false; }
  function updateBindingControls() {
    const role=el('role').value, context=target?.kind==='range' && role!=='core' && !entry?.disposition;
    el('essential-choice').hidden=!context;
    el('evidence-function').hidden=role!=='evidence' || target?.kind!=='range';
    el('additional').disabled=!!repairingLink;
    el('essential').disabled=!!entry?.disposition || !!repairingLink;
    el('role').disabled=!!entry?.disposition || !!repairingLink;
    el('function').disabled=!!repairingLink;
    const action=target?.kind==='field' ? 'Gebruik voor dit onderdeel' : target?.kind==='semantics' ? 'Gebruik voor '+(target.field==='direction'?'de richting':'de sterkte') : role==='core' ? entry?.disposition ? 'Gebruik als bronstuk' : 'Gebruik als kernuitspraak' : 'Voeg toe als '+labels[role].toLowerCase();
    el('add').textContent=selected ? target ? action : 'Kies eerst waarvoor je de tekst gebruikt' : task===1 ? hasCore() ? 'Verder naar betekenis' : 'Selecteer tekst in de bron' : only ? 'Terug naar overzicht' : 'Naar controleren en afronden';
    el('add').disabled=finalizing || (selected ? !target || context && !repairingLink && essentialChoice()===null : task===1 && (!hasCore() || !el('type').value));
    el('add').hidden=task===3;
    el('add').className=task===1 && !entry?.disposition ? 'btn-secondary' : 'btn-primary';
    if(task===1 && !entry?.disposition) el('add').textContent=selected ? 'Zelf betekenis invullen' : 'Verder zonder nieuw voorstel';
    el('suggest').hidden=task!==1 || !!entry?.disposition;
    el('suggest').disabled=suggesting || finalizing || entry?.status!=='draft' || (!selected && !hasCore());
    el('suggest').textContent=suggesting ? 'Betekenis wordt voorgesteld…' : 'Betekenis voorstellen';
    const confirmedReady=entry.status==='ready' && dirty===committed;
    el('ready').hidden=task!==3 || confirmedReady;
    el('ready').disabled=finalizing || checking || !checkIsCurrent() || check.findings.length>0;
    el('new').hidden=task!==3 || !confirmedReady;
    el('new').disabled=finalizing;
    el('recheck').disabled=checking || finalizing;
    el('select-block').disabled=!activeBlock;el('select-block').hidden=!!only?.field || target?.kind==='semantics';
    el('discard').hidden=!selected;
    el('linked').hidden=task===3 || !entry.ranges.length || !!only && !only.evidence;
    el('target').hidden=!!only?.field;
    el('steps').hidden=simple();el('simple').hidden=!simple();
    el('ready').textContent=simple() ? 'Opslaan en naar volgend kennisobject' : 'Annotatie klaar voor documentcontrole';
    if(!simple()) el('finish').hidden=true;
    // Switching annotations is navigation: in the card it lives with the other document actions,
    // and a marked passage in the source opens its own annotation.
    // The card has one way forward: finish this object, then the next. An earlier
    // object is reopened from its marked passage in the source.
    el('entry-box').hidden=simple();
    el('more').hidden=simple();el('simple-back').hidden=!storedForm();
    if(simple()) {
      for(const id of ['selection-tools','linked','back','add','suggest']) el(id).hidden=true;
      // An open proposal keeps the buttons usable: saving then points at the proposal to answer.
      const complete=confirmedReady || checkIsCurrent() && !check.findings.some(f=>f.code!=='annotation_context_proposal_open');
      // A selected statement alone is a complete object: saving commits it first.
      // A saved object that lost its statement must get one back before leaving.
      const provisional=!hasCore() && !!selected,busy=finalizing || checking || deriving;
      el('new').hidden=true;el('ready').hidden=!hasCore() && !provisional;el('finish').hidden=false;
      el('ready').disabled=busy || !(provisional || complete);
      el('finish').disabled=busy || (hasCore() ? !complete : !provisional && !!entry.revision && !!state.object_bindings?.[entry.annotation_id]);
      renderSimple();
    }
    // #1064: an object that is already built has one way forward, in either form:
    // rebuild it when something changed, otherwise go back to its review.
    const built=state.object_bindings?.[entry.annotation_id];
    el('rebuild').hidden=!built;
    if(built) {
      const complete=confirmedReady || checkIsCurrent() && !check.findings.some(f=>f.code!=='annotation_context_proposal_open');
      el('ready').hidden=true;el('finish').hidden=true;el('new').hidden=true;
      el('rebuild').textContent=changedSinceBuild() ? 'Kennisobject opnieuw bouwen' : 'Terug naar review';
      el('rebuild').disabled=finalizing || checking || deriving || rebuilding || changedSinceBuild() && (!hasCore() || !complete);
    }
    el('target').textContent=target?.kind==='field' ? (only ? '' : fieldContract.labels[target.field]+' ')+'Selecteer de woorden in de bron.' : target?.kind==='semantics' ? 'Wijs het bronbewijs voor '+(target.field==='direction'?'de richting':'de sterkte')+' aan.' : task===1 ? 'Wijs de kernuitspraak aan in de bron.' : target ? 'Wijs '+labels[role].toLowerCase()+' aan in de bron.' : 'Kies een betekenisvraag of voeg context of onderbouwing toe.';
  }
  let rebuilding=false;
  const changedSinceBuild = () => !!state.object_bindings?.[entry.annotation_id]?.pending || dirty!==committed || entry.status!=='ready';
  el('rebuild').addEventListener('click',async()=>{
    const built=state.object_bindings?.[entry.annotation_id];
    if(!built || rebuilding) return;
    const review='/review?'+new URLSearchParams({document:state.snapshot_id,object:built.object_id});
    if(!changedSinceBuild()) {window.location.href=review;return;}
    if(!await saveCard()) return;
    rebuilding=true;updateBindingControls();status('Kennisobject wordt opnieuw gebouwd…');
    try {
      const response=await fetch('/annotations/rebuild',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({document:state.snapshot_id,annotation:entry.annotation_id,command_id:crypto.randomUUID(),expected_generation:state.generation})});
      const data=await response.json();
      if(!response.ok) throw new Error(data.message || 'Opnieuw bouwen is niet gestart. Je aanpassing is bewaard.');
      window.location.href=data.review_url;
    } catch(error) {status(error.message);rebuilding=false;updateBindingControls();}
  });
  function renderSourceHighlights() {
    const ranges = new Map();
    for (const saved of [...state.entries.filter(e => e.annotation_id !== entry.annotation_id && e.status !== 'withdrawn'),entry]) {
      for (const anchor of saved.ranges || []) {
        if (!ranges.has(anchor.block_id)) ranges.set(anchor.block_id,[]);
        ranges.get(anchor.block_id).push({...anchor,current:saved.annotation_id === entry.annotation_id,owner:saved.annotation_id});
      }
    }
    // A proposal is marked apart: exact source text that is not linked yet.
    for (const proposal of entry ? openProposals() : []) {
      if (!ranges.has(proposal.block_id)) ranges.set(proposal.block_id,[]);
      ranges.get(proposal.block_id).push({...proposal,proposal:true});
    }
    for (const block of state.blocks) {
      const node = sourceElements.get(block.block_id);
      if (!node) continue;
      const anchors = ranges.get(block.block_id) || [];
      if (!anchors.length) {
        if (node.childNodes.length !== 1 || node.firstChild.nodeType !== Node.TEXT_NODE || node.textContent !== block.text)
          node.textContent = block.text;
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
          else if (simple()) {mark.dataset.annotation=covering[0].owner;mark.title='Deze annotatie openen';}
          mark.textContent=value;content.append(mark);
        } else content.append(document.createTextNode(value));
      }
      node.replaceChildren(content);
    }
  }
  el('source-reason').add(new Option('Functie kiezen',''));
  for(const [role,reasons] of Object.entries(fieldContract.source_roles))
    for(const reason of reasons) el('source-reason').add(new Option(reason.label,role+':'+reason.value));
  function resetFields() {
    entry.field_evidence ||= Object.fromEntries(fieldContract.fields.map(f => [f,{span:null,missing_reason:'uncertain'}]));
    for(const field of Object.values(fieldContract.type_core_fields))
      if(entry.field_evidence[field]?.core) entry.field_evidence[field]={span:null,missing_reason:'uncertain'};
    entry.field_evidence.type_evidence_spans={core:true};
    const core=fieldContract.type_core_fields[entry.object_type];
    if(core) entry.field_evidence[core]={core:true};
    if(entry.object_type!=='recommendation') entry.recommendation_semantics=null;
  }
  function renderFields() {
    el('to-controls').textContent=selected ? 'Aanwijzing koppelen' : 'Naar huidige annotatie';
    const currentField=el('field').value;
    const relevant=new Set(['subject_span','predicate_span',...(fieldContract.type_fields[entry.object_type] || [])]);
    if(entry.object_type==='recommendation') for(const field of ['actor_span','target_group_span','scope_span','condition_span']) relevant.add(field);
    el('field').replaceChildren();
    for(const [field,label] of Object.entries(fieldContract.labels)) if(relevant.has(field)) el('field').add(new Option(label,field));
    if(relevant.has(currentField)) el('field').value=currentField;
    el('fields').replaceChildren();
    el('recommendation').hidden=entry.object_type !== 'recommendation' || !!only && !only.semantics;
    el('source-disposition').hidden=!entry.disposition;
    el('meaning').hidden=!!entry.disposition || !!only && !only.field;
    el('context-tools').hidden=!!entry.disposition || !!only && !only.evidence;
    el('evidence').hidden=!!entry.disposition || !!only && !only.evidence;
    el('required-links').hidden=!!only;
    el('heading-2').textContent=only?.field ? fieldContract.labels[only.field] : only?.evidence ? 'Onderbouwing en context' : only?.semantics ? 'Richting en sterkte' : 'Betekenis aanpassen';
    el('full-intro').hidden=!!only;el('proposal-core').hidden=!!only;
    el('na').closest('label').hidden=!!entry.disposition;
    for(const option of el('role').options) {
      option.disabled=!!entry.disposition && option.value!=='core';
      option.hidden=option.value==='core';
      if(option.value==='core') option.text=entry.disposition ? 'Bronstuk' : 'Kernuitspraak';
    }
    if(entry.disposition) {el('role').value='core';el('essential').checked=false;}
    el('role').disabled=!!repairingLink;
    el('essential').disabled=!!entry.disposition || !!repairingLink;
    el('function').disabled=!!repairingLink;
    el('source-reason').value=entry.disposition?.role ? entry.disposition.role+':'+entry.disposition.reason : '';
    for(const [field,label] of Object.entries(fieldContract.labels)) {
      if(!relevant.has(field) || only && only.field!==field) continue;
      const evidence=entry.field_evidence?.[field];
      const point=only && pointFor(field);
      const dt=document.createElement('dt');dt.textContent=point ? reason(point) : label;dt.hidden=!!only && !point;
      const dd=document.createElement('dd'),answer=document.createElement('p'),actions=document.createElement('div');
      answer.textContent=evidence?.span ? literal(evidence.span) : evidence?.core ? 'De kernuitspraak is hiervoor gekoppeld.' : ({not_stated:'Niet in de bron genoemd',not_applicable:'Niet van toepassing',uncertain:'Nog uitzoeken'})[evidence?.missing_reason] || 'Nog aan te wijzen';
      const button=document.createElement('button');button.type='button';button.className='btn-secondary';button.textContent=evidence?.span?'Andere tekst aanwijzen':'Tekst aanwijzen';button.dataset.field=field;button.setAttribute('aria-pressed',String(target?.kind==='field' && target.field===field));
      button.hidden=!!only;button.addEventListener('click',()=>{el('field').value=field;chooseTarget({kind:'field',field});});
      const missing=document.createElement('select');missing.dataset.missingField=field;missing.setAttribute('aria-label','Ontbreekreden: '+label);
      missing.add(new Option(only ? 'Of kies: staat niet in de bron…' : 'Ontbreekreden kiezen',''));
      for(const [value,text] of Object.entries({uncertain:'Nog uitzoeken',not_stated:'Niet in de bron genoemd',not_applicable:'Niet van toepassing'})) missing.add(new Option(text,value));
      missing.value=only ? '' : evidence?.missing_reason || '';
      if(only) {answer.textContent=evidence?.span ? 'Nu: '+literal(evidence.span) : '';answer.hidden=!evidence?.span;
        const how=document.createElement('p');how.textContent='Selecteer de juiste woorden in de bron.';dd.append(answer,how);}
      missing.hidden=target?.kind!=='field' || target.field!==field;
      missing.addEventListener('change',()=>{if(missing.value) {entry.field_evidence[field]={span:null,missing_reason:missing.value};change();renderFields();answerPoint(field);}});
      actions.className='annotation-field-actions';actions.append(button,missing);dd.prepend(answer);dd.append(actions);el('fields').append(dt,dd);
    }
    const semantics=entry.recommendation_semantics || {};
    el('direction').value=semantics.direction || '';
    el('strength-status').value=semantics.strength_status || '';
    el('strength').value=semantics.strength || '';
    for(const field of ['direction','strength']) el(field+'-proof').textContent=semantics[field+'_evidence'] ? literal(semantics[field+'_evidence']) :
      field==='strength' && semantics.strength_status==='not_stated' ? 'Sterkte expliciet als niet vermeld vastgelegd.' : 'Nog geen brontekst hiervoor aangewezen.';
    renderSummary();updateBindingControls();
  }
  const status = text => { el('status').textContent = text; };
  // A built object is not in the document check any more: its card speaks of the object, not the phase.
  const loadedStatus = () => state.object_bindings?.[entry.annotation_id] ? (state.object_bindings[entry.annotation_id].pending ? 'Aanpassing opgeslagen, nog niet opnieuw gebouwd.' : 'Opgebouwd kennisobject.') :
    entry.revision ? entry.status==='ready' ? 'Klaar voor documentcontrole en opgeslagen.' : 'Concept opgeslagen.' : 'Nieuwe annotatie. Nog niets opgeslagen.';
  function load(id) {
    const saved = state.entries.find(e => e.annotation_id === id);
    entry = saved ? clone(saved) : {annotation_id:crypto.randomUUID(),revision:0,status:'draft',object_type:null,ranges:[],evidence_not_applicable:false};
    entry.required_links ||= [];repairingLink=null;
    for(const a of entry.ranges) if(a.role!=='core') a.relationship_id=linkId(a);
    if(!entry.field_evidence) resetFields();
    check=null;target=null;confirmation=null;el('confirm').hidden=true;openPoints=[];replacingCore=false;deriving=false;armed=null;queued=null;asked=false;
    el('suggestion-note').textContent='';
    selected = entry.pending_range ? clone(entry.pending_range) : null;
    clearChoice();el('binding-note').textContent='';
    activeBlock=null;el('role').value='core';
    if (selected) {
      activateBlock(state.blocks.find(b => b.block_id === selected.block_id));
      el('to-source').href='#'+selected.block_id;
    }
    if(selected?.relationship_id && entry.required_links.some(l => l.relationship_id===selected.relationship_id && l.required_for_meaning)) repairingLink=selected.relationship_id;
    el('selection').textContent = selected ? 'Nog te koppelen: '+selected.quote : '';
    if (selected) {
      el('role').value=selected.role; el('essential').checked=!!repairingLink;
      el('function').value=selected.evidence_function || 'supported_by';
    }
    dirty = committed = 0;setEntryUrl(saved?.annotation_id);
    if (el('conflict')) el('conflict').hidden = true;
    el('type').value = entry.disposition ? 'source_disposition' : entry.object_type || '';
    el('na').checked = entry.evidence_not_applicable;
    render();
    showTask(entry.status==='ready' || hasCore() && !selected && !entry.disposition ? 3 : hasCore() ? 2 : 1);
    if(task===2 && selected && repairingLink) target={kind:'range',role:el('role').value};
    updateBindingControls();
    if(task===3 || simple() && hasCore()) runCheck();
  }
  function entries() {
    el('entry').replaceChildren(new Option('Nieuwe annotatie',''));
    for (const item of state.entries) {
      if (item.status !== 'withdrawn') el('entry').add(new Option((item.ranges.find(a => a.role === 'core')?.quote || 'Onvolledig concept').slice(0,90),item.annotation_id));
    }
    el('entry').value = state.entries.some(e => e.annotation_id === entry?.annotation_id) ? entry.annotation_id : '';
  }
  function render() {
    renderFields();
    renderSourceHighlights();
    const binding = state.object_bindings?.[entry.annotation_id];
    el('current-object').hidden = !binding || simple();
    if (binding) {
      el('current-version').textContent = 'Huidige objectversie ' + binding.object_version;
      el('current-text').textContent = binding.text;
      el('current-state').textContent = binding.pending ? 'De opgeslagen broncorrectie moet nog worden opgebouwd en beoordeeld.' :
        'Een broncorrectie trekt de geraakte beoordelingen in. Na opbouw beoordeelt de aangewezen reviewer de nieuwe versie.';
      el('current-review').href = '/review?' + new URLSearchParams({document:state.snapshot_id,object:binding.object_id});
    }
    el('withdraw').hidden = !!binding;
    el('required-links').replaceChildren();
    for(const link of entry.required_links.filter(l => l.required_for_meaning)) {
      const section=document.createElement('section');
      const p=document.createElement('p');p.textContent='Essentieel verband ontbreekt: '+labels[link.role];
      const repair=document.createElement('button');repair.type='button';repair.className='btn-secondary';repair.textContent='Dit verband opnieuw aanwijzen';
      repair.addEventListener('click',() => {
        repairingLink=link.relationship_id;el('function').value=link.evidence_function || 'supported_by';
        status('Selecteer in de bron de tekst voor dit verband.');arm(link.role==='evidence' ? 'evidence' : 'context');
      });
      const label=document.createElement('label');label.textContent='Waarom is dit verband niet langer noodzakelijk?';
      const reason=document.createElement('input');reason.type='text';reason.maxLength=1000;label.append(reason);
      const withdraw=document.createElement('button');withdraw.type='button';withdraw.className='btn-secondary';withdraw.textContent='Verplichting met deze reden terugnemen';
      withdraw.addEventListener('click',() => {
        if(!reason.value.trim()) {status('Licht eerst toe waarom dit essentiële verband niet langer nodig is.');return;}
        link.required_for_meaning=false;link.withdrawal_reason=reason.value.trim();repairingLink=null;change();render();
      });
      section.append(p,repair,label,withdraw);el('required-links').append(section);
    }
    el('ranges').replaceChildren();
    entry.ranges.forEach((a,index) => {
      const li = document.createElement('li');
      const p = document.createElement('p');
      p.textContent = labels[a.role] + (a.required_for_meaning ? ' (essentieel)' : '') + ': ' + a.quote;
      const link = document.createElement('a'); link.href = '#' + a.block_id; link.textContent = 'Open in bron';
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Deze bronkoppeling verwijderen';
      remove.className = 'btn-secondary';
      remove.addEventListener('click',() => {
        const removeRange=()=>{
          if(a.role==='core') {entry.field_evidence=null;resetFields();}
          else if(a.required_for_meaning) entry.required_links.push({relationship_id:linkId(a),role:a.role,evidence_function:a.evidence_function,required_for_meaning:true,withdrawal_reason:null});
          entry.ranges.splice(index,1);
          // Removing a source connection also removes meaning references that
          // depended exclusively on that connection. Keep other anchors intact.
          clearDependentFields(a);
          change();render();
        };
        if(a.role==='core') confirmChange('Deze kernkoppeling verwijderen? Betekenisvelden moeten daarna opnieuw worden gecontroleerd. Opgebouwde objecten kunnen opnieuw beoordeling nodig hebben.',removeRange);
        else removeRange();
      });
      li.append(p,link,' ',remove); el('ranges').append(li);
    });
  }
  function change() {
    cancelConfirmation();entry.status = 'draft'; dirty += 1;check=null;renderSummary();updateBindingControls();
    status('Wijzigingen nog niet opgeslagen.'); clearTimeout(timer);
    timer = setTimeout(() => { flush().catch(() => {}); },600);
  }
  function requestForCurrent() {
    const reference = a => ({block_id:a.block_id,start:a.start,end:a.end,quote:a.quote,role:a.role,required_for_meaning:a.required_for_meaning,evidence_function:a.evidence_function,
      ...(a.relationship_id ? {relationship_id:a.relationship_id} : {})});
    const ranges = entry.ranges.map(reference);
    return {snapshot_id:state.snapshot_id,command_id:crypto.randomUUID(),annotation_id:entry.annotation_id,
      expected_revision:entry.revision,expected_generation:state.generation,extraction_hash:state.extraction_hash,normalization:state.normalization,
      expected_objects_revision:state.objects_revision,
      selection:{status:entry.status,object_type:entry.object_type,ranges,pending_range:entry.pending_range ? reference(entry.pending_range) : null,evidence_not_applicable:entry.evidence_not_applicable,
        required_links:clone(entry.required_links),
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
          const response = await fetch('/annotations/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
          const data = await response.json();
          if (el('conflict')) el('conflict').hidden = true;
          if (!response.ok) {
            if (data.error === 'annotation_core_duplicate' && data.conflicting_annotation_id && el('conflict-link')) {
              el('conflict-link').href = '/annotations?' + new URLSearchParams({document:state.snapshot_id,annotation:data.conflicting_annotation_id});
              el('conflict').hidden = false;
            }
            if(['annotation_write_conflict','annotation_objects_stale','annotation_representation_stale','annotation_client_contract_stale'].includes(data.error)) {
              el('save-conflict').hidden=false;el('local-work').textContent=body.selection.ranges.map(a=>labels[a.role]+': '+a.quote).join('\n\n');
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
          if (state.object_bindings?.[entry.annotation_id] && data.revision > body.expected_revision) {
            state.object_bindings[entry.annotation_id].pending = true;
            el('current-state').textContent = 'De opgeslagen broncorrectie moet nog worden opgebouwd en beoordeeld.';
          }
          // Only the sent snapshot is committed; edits made during fetch remain dirty.
          const saved = {...clone(entry),...body.selection,revision:data.revision};
          const index = state.entries.findIndex(e => e.annotation_id === entry.annotation_id);
          if (index < 0) state.entries.push(saved); else state.entries[index] = saved;
          committed = version; retryRequest = null;setEntryUrl(entry.annotation_id);entries();
          el('retry').hidden = true;
          status(state.object_bindings?.[entry.annotation_id] ? 'Aanpassing opgeslagen.' : data.status === 'ready' ? 'Klaar voor documentcontrole en opgeslagen.' : data.status === 'withdrawn' ? 'Annotatie teruggenomen en opgeslagen.' : 'Concept opgeslagen.');renderSummary();updateBindingControls();
        } catch (error) {
          failed = !error.validation; el('retry').hidden = false;
          status('Opslaan mislukt. ' + error.message); throw error;
        }
      }
    })();
    try { await running; } finally { running = null; }
  }
  function captureSelection(value) {
    // A selection made while Metis reads the statement waits; it must not make that answer stale.
    if(simple() && deriving) {queued=value;renderSimple();return;}
    activateBlock(state.blocks.find(b => b.block_id === value.block_id));
    selected=value;
    el('to-source').href='#'+value.block_id;
    el('to-controls').textContent='Aanwijzing koppelen';
    const role=el('role').value;
    entry.pending_range={...selected,role,required_for_meaning:el('essential').checked,evidence_function:role==='evidence'?el('function').value:null,
      ...(repairingLink ? {relationship_id:repairingLink} : {})};
    el('selection').textContent='Aangewezen: '+selected.quote;
    change();
    updateBindingControls();
    if(simple()) simpleSelection();
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
      const had=!!(selected || entry.pending_range);selected = null;entry.pending_range=null;if(had) change();updateBindingControls();el('selection').textContent = 'Wijs één bereik binnen een tekstblok aan. Voeg een volgende alinea afzonderlijk toe.'; return;
    }
    const prefix = document.createRange(); prefix.selectNodeContents(first); prefix.setEnd(range.startContainer,range.startOffset);
    const endPrefix = document.createRange(); endPrefix.selectNodeContents(first); endPrefix.setEnd(range.endContainer,range.endOffset);
    captureSelection({block_id:first.dataset.sourceBlock,start:Array.from(prefix.toString()).length,end:Array.from(endPrefix.toString()).length,quote:range.toString()});
  }
  document.addEventListener('mouseup',rememberSelection);
  document.addEventListener('touchend',rememberSelection);
  document.addEventListener('mousedown',event => { selectingFromSource=!!event.target.closest?.('[data-source-block]'); });
  document.addEventListener('touchstart',event => { selectingFromSource=!!event.target.closest?.('[data-source-block]'); });
  document.addEventListener('keyup',rememberSelection);
  for (const node of sourceElements.values()) {
    node.addEventListener('focus',() => activateBlock(state.blocks.find(b => b.block_id === node.dataset.sourceBlock)));
    node.addEventListener('click',() => activateBlock(state.blocks.find(b => b.block_id === node.dataset.sourceBlock)));
    node.addEventListener('keydown',event => moveSourceSelection(event,node));
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
  });
  window.addEventListener('hashchange',() => revealSource(decodeURIComponent(location.hash.slice(1))));
  if (location.hash) revealSource(decodeURIComponent(location.hash.slice(1)));
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
  el('select-block').addEventListener('click',() => {
    if (!activeBlock) return;
    captureSelection({block_id:activeBlock.block_id,start:0,end:Array.from(activeBlock.text).length,quote:activeBlock.text});
  });
  function bindSelected() {
    if(!selected || !target) return;
    if(target.kind==='field') {
      const span=consumeSelected();if(!span) return;
      const field=target.field;entry.field_evidence[field]={span,missing_reason:null};target=null;change();renderFields();answerPoint(field);return;
    }
    if(target.kind==='semantics') {
      const span=consumeSelected();if(!span) return;
      semantics()[target.field+'_evidence']=span;target=null;change();renderFields();return;
    }
    try {
      const result=bindRange(entry,selected,{role:el('role').value,essential:essentialChoice(),repairingLink,evidenceFunction:el('function').value},fieldContract);
      entry=result.entry;
      if(el('role').value==='core') resetFields();
      el('binding-note').textContent=result.fieldBinding==='preserved' ? 'Context toegevoegd. Het bestaande betekenisveld is behouden; controleer dat onderdeel.' : result.fieldBinding==='bound' ? 'Context en betekenisveld zijn samen gekoppeld.' : '';
    } catch(error) {status(error.message);return;}
    repairingLink=null;clearChoice();window.getSelection().removeAllRanges();
    selected=null;entry.pending_range=null;el('selection').textContent='';
    if(task===2) target=null;
    change();render();
    if(only?.evidence && entry.ranges.some(a=>a.role==='evidence')) {showTask(3,true);runCheck();}
  }
  el('add').addEventListener('click',()=>{
    if(!selected) {if(task===1 && hasCore()) showTask(2,true);else if(task===2) {showTask(3,true);runCheck();}return;}
    if(target?.kind==='range' && el('role').value==='core' && hasCore())
      confirmChange('Nog een kernbereik toevoegen? Controleer daarna de betekenisvelden en eventuele gevolgen voor beoordelingen.',bindSelected);
    else bindSelected();
  });
  const suggestionBasis=()=>Object.fromEntries(['snapshot_id','working_revision_id','extraction_hash','normalization','generation','objects_revision'].map(key=>[key,state[key]]));
  async function proposeMeaning() {
    if(suggesting || entry.disposition) return;
    suggesting=true;updateBindingControls();
    const controller=new AbortController(),deadline=setTimeout(()=>controller.abort(),55000);
    el('suggestion-note').textContent='Metis leest je selectie. Dit kan tot een minuut duren.';
    try {
      if(selected) {
        target={kind:'range',role:'core'};el('role').value='core';bindSelected();
        if(selected) throw Error('De kern kon niet worden gekoppeld. Controleer je selectie.');
      }
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
      openPoints=Array.isArray(data.open_points) ? data.open_points : [];
      el('type').value=entry.object_type || '';change();renderFields();showTask(3);
      el('controls').scrollTop=0;
      if(window.matchMedia('(max-width:800px)').matches) el('controls').scrollIntoView({block:'start'});
      el('heading-3').focus({preventScroll:true});
      await flush();
      await runCheck();
      el('suggestion-note').textContent='';
    } catch(error) {
      el('suggestion-note').textContent=(error.name==='AbortError' ? 'Het voorstel duurde te lang.' : error.message)+' Je opgeslagen werk blijft bewaard. Probeer opnieuw of vul de betekenis zelf in.';
    } finally {
      clearTimeout(deadline);suggesting=false;el('editor-inputs').disabled=false;updateBindingControls();
    }
  }
  el('suggest').addEventListener('click',()=>{
    const hasMeaning=Object.values(entry.field_evidence || {}).some(value=>value.span) || entry.recommendation_semantics;
    if(hasCore() && (hasMeaning || selected || entry.status!=='draft'))
      confirmChange('Een nieuw voorstel vervangt de huidige betekenisvelden in dit concept. Wil je dat? Je bestaande opgeslagen versies blijven bewaard.',proposeMeaning);
    else proposeMeaning();
  });
  el('discard').addEventListener('click',() => { selected=null;repairingLink=null;clearChoice();entry.pending_range=null;el('selection').textContent='';change();renderFields(); });
  for (const id of ['role','essential','additional','function']) el(id).addEventListener('change',() => {
    if(id==='role') {target={kind:'range',role:el('role').value};clearChoice();}
    if (selected) captureSelection(selected);
    updateBindingControls();
  });
  el('type').addEventListener('change',()=>{
    const value=el('type').value, previous=entry.disposition?'source_disposition':entry.object_type || '';
    const apply=()=>{
      const source=value==='source_disposition';entry.object_type=source?null:value || null;
      if(source) {entry.disposition={role:null,reason:null};entry.evidence_not_applicable=false;el('na').checked=false;}
      else delete entry.disposition;
      resetFields();change();renderFields();
    };
    if(previous && previous!==value && (entry.revision || state.object_bindings?.[entry.annotation_id])) {
      el('type').value=previous;
      confirmChange('Het type wijzigen? Controleer de betekenisvelden opnieuw. Opgebouwde objecten kunnen na de wijziging opnieuw beoordeling nodig hebben.',()=>{el('type').value=value;apply();});
    } else apply();
  });
  el('source-reason').addEventListener('change',() => {
    const parts=el('source-reason').value.split(':');
    entry.disposition={role:parts[0] || null,reason:parts[1] || null};change();
  });
  function consumeSelected() {
    if(!selected) { status('Wijs eerst de bedoelde brontekst aan.');return null; }
    const span={block_id:selected.block_id,start:selected.start,end:selected.end};
    repairingLink=null;
    selected=null;entry.pending_range=null;el('selection').textContent='';
    window.getSelection().removeAllRanges();
    clearChoice();updateBindingControls();
    return span;
  }
  function semantics() {
    return entry.recommendation_semantics ||= {direction:null,direction_evidence:null,strength_status:null,strength:null,strength_evidence:null};
  }
  el('direction').addEventListener('change',() => { semantics().direction=el('direction').value || null;change(); });
  el('strength-status').addEventListener('change',() => {
    const value=el('strength-status').value || null;semantics().strength_status=value;
    if(value==='not_stated') {semantics().strength=null;semantics().strength_evidence=null;}
    change();renderFields();
  });
  el('strength').addEventListener('change',() => {semantics().strength=el('strength').value || null;change();});
  for(const field of ['direction','strength']) el(field+'-evidence').addEventListener('click',()=>chooseTarget({kind:'semantics',field}));
  el('na').addEventListener('change',() => { entry.evidence_not_applicable = el('na').checked; change();renderSummary();if(only?.evidence && el('na').checked) {showTask(3,true);runCheck();} });
  el('retry').addEventListener('click',() => { failed = false; el('retry').hidden = true; flush().catch(() => {}); });
  // Marks the current object ready through the existing check and save. True when it is saved as ready.
  async function finishCurrent() {
    if(entry.status==='ready' && dirty===committed) return true;
    if(finalizing || !checkIsCurrent() || check.findings.length) return false;
    finalizing=true;el('editor-inputs').disabled=true;
    try {
      await flush();
      await runCheck();
      if(!checkIsCurrent() || check.findings.length) return false;
      entry.status='ready';dirty+=1;await flush();renderSummary();
      return entry.status==='ready' && dirty===committed;
    } catch(_) { return false; /* Preserve current work and the exact uncertain request. */ }
    finally {finalizing=false;el('editor-inputs').disabled=false;updateBindingControls();}
  }
  const toOverview = () => { window.location.href = '/annotations?' + new URLSearchParams({document:state.snapshot_id,overview:'true'}); };
  // In the card, saving first commits a statement that was only selected.
  async function saveCard() {
    if(simple() && !hasCore() && selected) await useAs('core');
    const saved=hasCore() && await finishCurrent();
    if(!saved && simple() && openProposals().length) {
      asked=true;renderSimple();
      document.querySelector('#annotation-simple-rows [data-proposal=add]')?.focus();
    }
    return saved;
  }
  el('ready').addEventListener('click',async()=>{
    const saved=await saveCard();
    if(saved && simple()) {load('');entries();status('Opgeslagen. Selecteer de volgende uitspraak.');}
  });
  el('finish').addEventListener('click',async()=>{
    if(hasCore() || selected) {if(await saveCard()) toOverview();return;}
    // An object that holds nothing is not left behind to block the document. A built
    // object keeps its identity and must get its statement back first.
    if(state.object_bindings?.[entry.annotation_id]) return;
    if(entry.revision) {await discardObject();if(entry.revision) return;}
    toOverview();
  });
  el('withdraw').addEventListener('click',()=>confirmChange('De hele annotatie terugnemen, inclusief alle gekoppelde brontekst? Dit meldt de annotatie niet gereed. De bron moet nog worden verantwoord.',async()=>{
    try {await flush();entry.status='withdrawn';dirty+=1;await flush();load('');entries();}catch(_){}
  }));
  async function switchEntry(id) { await flush(); load(id); entries(); status(loadedStatus()); }
  el('new').addEventListener('click',() => { switchEntry('').catch(() => {}); });
  el('entry').addEventListener('change',() => { switchEntry(el('entry').value).catch(() => {}); });
  el('pause').addEventListener('click',async () => { try { await flush(); window.location.href = '/'; } catch (_) {} });
  el('overview').addEventListener('click',async () => { try { await flush(); window.location.href = '/annotations?' + new URLSearchParams({document:state.snapshot_id,overview:'true'}); } catch (_) {} });
  window.addEventListener('beforeunload',event => { if (dirty !== committed || running) { event.preventDefault(); event.returnValue = ''; } });
  load(new URLSearchParams(window.location.search).get('annotation')); entries();
  el('editor-inputs').disabled=false;
  el('initializing').hidden=true;
  status(loadedStatus());
})();
