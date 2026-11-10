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
  const clone = value => JSON.parse(JSON.stringify(value));
  const fieldContract = state.field_contract;
  let repairingLink=null;
  const linkId = a => a.relationship_id || 'link-v1:'+JSON.stringify([entry.annotation_id,a.role,a.block_id,a.start,a.end]);
  const literal = span => {
    const block=state.blocks.find(b => b.block_id === span.block_id);
    return block ? Array.from(block.text).slice(span.start,span.end).join('') : '';
  };
  const sourceElements = new Map([...document.querySelectorAll('[data-source-block]')].map(node => [node.dataset.sourceBlock,node]));
  function activateBlock(block) {
    if (!block || activeBlock?.block_id === block.block_id) return;
    activeBlock = block;
    el('source-input').value = block.text;
    updateBindingControls();
  }
  function essentialChoice() {
    return el('essential').checked ? true : el('additional').checked ? false : null;
  }
  function clearChoice() { el('essential').checked=false;el('additional').checked=false; }
  function updateBindingControls() {
    const role=el('role').value, context=role!=='core' && !entry?.disposition;
    el('essential-choice').hidden=!context;
    el('additional').disabled=!!repairingLink;
    el('add').textContent=role==='core' ? entry?.disposition ? 'Gebruik als bronstuk' : 'Gebruik als kernuitspraak' : 'Voeg toe als '+labels[role].toLowerCase();
    el('add').disabled=!selected || context && !repairingLink && essentialChoice()===null;
    el('select-block').disabled=!activeBlock;
    el('discard').disabled=!selected;
  }
  el('source-input').value = activeBlock?.text || '';
  function renderSourceHighlights() {
    const ranges = new Map();
    for (const saved of [...state.entries.filter(e => e.annotation_id !== entry.annotation_id && e.status !== 'withdrawn'),entry]) {
      for (const anchor of saved.ranges || []) {
        if (!ranges.has(anchor.block_id)) ranges.set(anchor.block_id,[]);
        ranges.get(anchor.block_id).push({...anchor,current:saved.annotation_id === entry.annotation_id});
      }
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
          if (covering.some(a => a.current)) mark.dataset.current='true';
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
    el('recommendation').hidden=entry.object_type !== 'recommendation';
    el('source-disposition').hidden=!entry.disposition;
    el('field').closest('details').hidden=!!entry.disposition;
    el('na').closest('label').hidden=!!entry.disposition;
    for(const option of el('role').options) {
      option.disabled=!!entry.disposition && option.value!=='core';
      if(option.value==='core') option.text=entry.disposition ? 'Bronstuk' : 'Kernuitspraak';
    }
    if(entry.disposition) {el('role').value='core';el('essential').checked=false;}
    el('role').disabled=!!repairingLink;
    el('essential').disabled=!!entry.disposition || !!repairingLink;
    el('function').disabled=!!repairingLink;
    el('source-reason').value=entry.disposition?.role ? entry.disposition.role+':'+entry.disposition.reason : '';
    for(const [field,label] of Object.entries(fieldContract.labels)) {
      const evidence=entry.field_evidence?.[field];
      if(!relevant.has(field) || !evidence?.span && evidence?.missing_reason !== 'not_stated') continue;
      const dt=document.createElement('dt');dt.textContent=label;
      const dd=document.createElement('dd');dd.textContent=evidence.span ? literal(evidence.span) : 'Niet in de bron genoemd';
      el('fields').append(dt,dd);
    }
    const semantics=entry.recommendation_semantics || {};
    el('direction').value=semantics.direction || '';
    el('strength-status').value=semantics.strength_status || '';
    el('strength').value=semantics.strength || '';
    for(const field of ['direction','strength']) el(field+'-proof').textContent=semantics[field+'_evidence'] ? literal(semantics[field+'_evidence']) :
      field==='strength' && semantics.strength_status==='not_stated' ? 'Sterkte expliciet als niet vermeld vastgelegd.' : 'Nog geen brontekst hiervoor aangewezen.';
    updateBindingControls();
  }
  const status = text => { el('status').textContent = text; };
  function load(id) {
    const saved = state.entries.find(e => e.annotation_id === id);
    entry = saved ? clone(saved) : {annotation_id:crypto.randomUUID(),revision:0,status:'draft',object_type:null,ranges:[],evidence_not_applicable:false};
    entry.required_links ||= [];repairingLink=null;
    for(const a of entry.ranges) if(a.role!=='core') a.relationship_id=linkId(a);
    if(!entry.field_evidence) resetFields();
    selected = entry.pending_range ? clone(entry.pending_range) : null;
    clearChoice();el('binding-note').textContent='';
    activeBlock=null;el('source-input').value='';el('role').value='core';
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
    dirty = committed = 0;
    if (el('conflict')) el('conflict').hidden = true;
    el('type').value = entry.disposition ? 'source_disposition' : entry.object_type || '';
    el('na').checked = entry.evidence_not_applicable;
    render();
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
    el('current-object').hidden = !binding;
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
        repairingLink=link.relationship_id;el('role').value=link.role;el('essential').checked=true;
        el('function').value=link.evidence_function || 'supported_by';
        if(selected) captureSelection(selected);
        renderFields();status(selected ? 'Voeg de aangewezen tekst toe aan dit essentiële verband.' : 'Wijs de brontekst voor dit essentiële verband aan.');
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
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Bereik verwijderen';
      remove.className = 'btn-secondary';
      remove.addEventListener('click',() => {
        if(a.role==='core') resetFields();
        else if(a.required_for_meaning) entry.required_links.push({relationship_id:linkId(a),role:a.role,evidence_function:a.evidence_function,required_for_meaning:true,withdrawal_reason:null});
        entry.ranges.splice(index,1);change();render();
      });
      li.append(p,link,' ',remove); el('ranges').append(li);
    });
  }
  function change() {
    entry.status = 'draft'; dirty += 1;
    status('Niet opgeslagen.'); clearTimeout(timer);
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
        ...(entry.disposition ? {disposition:clone(entry.disposition)} : {
        field_evidence:Object.fromEntries(Object.entries(entry.field_evidence).map(([f,e]) => [f,e.span ? {...clone(e),quote:literal(e.span)} : clone(e)])),
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
            if (response.status === 422) { retryRequest = null; }
            const error = new Error(data.message || 'Opslaan mislukt.'); error.validation = response.status === 422; throw error;
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
          committed = version; retryRequest = null; entries();
          el('retry').hidden = true;
          status(data.status === 'ready' ? 'Selectie gereed en opgeslagen.' : data.status === 'withdrawn' ? 'Annotatie teruggenomen en opgeslagen.' : 'Concept opgeslagen.');
        } catch (error) {
          failed = !error.validation; el('retry').hidden = false;
          status('Opslaan mislukt. ' + error.message); throw error;
        }
      }
    })();
    try { await running; } finally { running = null; }
  }
  function captureSelection(value) {
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
  }
  function rememberSelection(event) {
    // Sidebar clicks must never replace an explicitly chosen block with the
    // browser's older, still-visible selection. Textareas own their select event.
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
      selected = null;entry.pending_range=null;change();updateBindingControls();el('selection').textContent = 'Wijs één bereik binnen een tekstblok aan. Voeg een volgende alinea afzonderlijk toe.'; return;
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
  for (const input of [el('source-input')]) {
    // Chromium does not move the caret with arrows in readonly textareas.
    // Keep the source readonly and provide selection-only keyboard movement.
    input.addEventListener('keydown',event => {
      if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault();
      const backwards=input.selectionDirection==='backward';
      const anchor=backwards ? input.selectionEnd : input.selectionStart;
      const focus=backwards ? input.selectionStart : input.selectionEnd;
      const boundaries=[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(input.value)].map(s=>s.index);
      boundaries.push(input.value.length);
      let next;
      if (event.key==='Home') next=0;
      else if (event.key==='End') next=input.value.length;
      else if (!event.shiftKey && input.selectionStart!==input.selectionEnd) next=event.key==='ArrowLeft'?input.selectionStart:input.selectionEnd;
      else next=event.key==='ArrowLeft' ? boundaries.filter(n=>n<focus).at(-1) ?? 0 : boundaries.find(n=>n>focus) ?? input.value.length;
      input.setSelectionRange(event.shiftKey?Math.min(anchor,next):next,event.shiftKey?Math.max(anchor,next):next,next<anchor?'backward':'forward');
    });
    input.addEventListener('select',() => {
      if (input.selectionStart === input.selectionEnd) return;
      if (!activeBlock) return;
      captureSelection({block_id:activeBlock.block_id,start:Array.from(input.value.slice(0,input.selectionStart)).length,
        end:Array.from(input.value.slice(0,input.selectionEnd)).length,quote:input.value.slice(input.selectionStart,input.selectionEnd)});
    });
  }
  el('select-block').addEventListener('click',() => {
    if (!activeBlock) return;
    captureSelection({block_id:activeBlock.block_id,start:0,end:Array.from(activeBlock.text).length,quote:activeBlock.text});
  });
  el('add').addEventListener('click',() => {
    if (!selected) { status('Wijs eerst tekst in één bronblok aan.'); return; }
    try {
      const result=bindRange(entry,selected,{role:el('role').value,essential:essentialChoice(),
        repairingLink,evidenceFunction:el('function').value},fieldContract);
      entry=result.entry;
      if(el('role').value==='core') resetFields();
      el('binding-note').textContent=result.fieldBinding==='preserved' ?
        'Context toegevoegd. Het bestaande betekenisveld is behouden. Controleer bij ‘Betekenis van de uitspraak aanwijzen’ welke tekst daarbij hoort.' :
        result.fieldBinding==='bound' ? 'Context en betekenisveld zijn samen gekoppeld.' : '';
    } catch(error) {status(error.message);return;}
    repairingLink=null;clearChoice();
    window.getSelection().removeAllRanges();
    selected = null; entry.pending_range=null; el('selection').textContent = ''; change(); render();
  });
  el('discard').addEventListener('click',() => { selected=null;repairingLink=null;clearChoice();entry.pending_range=null;el('selection').textContent='';change();renderFields(); });
  for (const id of ['role','essential','additional','function']) el(id).addEventListener('change',() => {
    if(id==='role') clearChoice();
    if (selected) captureSelection(selected);
    updateBindingControls();
  });
  el('type').addEventListener('change',() => {
    const source=el('type').value==='source_disposition';
    entry.object_type=source ? null : el('type').value || null;
    if(source) {entry.disposition={role:null,reason:null};entry.evidence_not_applicable=false;el('na').checked=false;}
    else delete entry.disposition;
    resetFields();change();renderFields();
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
  el('bind-field').addEventListener('click',() => {
    const span=consumeSelected();if(!span) return;
    entry.field_evidence[el('field').value]={span,missing_reason:null};change();renderFields();
  });
  el('field-absent').addEventListener('click',() => {
    entry.field_evidence[el('field').value]={span:null,missing_reason:'not_stated'};change();renderFields();
  });
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
  for(const field of ['direction','strength']) el(field+'-evidence').addEventListener('click',() => {
    const span=consumeSelected();if(!span) return;semantics()[field+'_evidence']=span;change();renderFields();
  });
  el('na').addEventListener('change',() => { entry.evidence_not_applicable = el('na').checked; change(); });
  el('retry').addEventListener('click',() => { failed = false; el('retry').hidden = true; flush().catch(() => {}); });
  el('ready').addEventListener('click',async () => {
    try { await flush(); entry.status = 'ready'; dirty += 1; await flush(); } catch (_) { /* Keep original work visible. */ }
  });
  el('withdraw').addEventListener('click',async () => {
    try { await flush();entry.status='withdrawn';dirty+=1;await flush();load('');entries(); } catch (_) {}
  });
  async function switchEntry(id) { await flush(); load(id); entries(); status('Opgeslagen werk geladen.'); }
  el('new').addEventListener('click',() => { switchEntry('').catch(() => {}); });
  el('entry').addEventListener('change',() => { switchEntry(el('entry').value).catch(() => {}); });
  el('pause').addEventListener('click',async () => { try { await flush(); window.location.href = '/'; } catch (_) {} });
  el('overview').addEventListener('click',async () => { try { await flush(); window.location.href = '/annotations?' + new URLSearchParams({document:state.snapshot_id,overview:'true'}); } catch (_) {} });
  window.addEventListener('beforeunload',event => { if (dirty !== committed || running) { event.preventDefault(); event.returnValue = ''; } });
  load(new URLSearchParams(window.location.search).get('annotation')); entries();
  el('editor-inputs').disabled=false;
  el('initializing').hidden=true;
  status('Opgeslagen werk geladen.');
})();
