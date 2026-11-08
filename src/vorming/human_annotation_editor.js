/* Source references only. Canonical text and object identity belong to the kernel. */
(() => {
  'use strict';
  const state = JSON.parse(document.getElementById('annotation-data').textContent);
  const el = id => document.getElementById('annotation-' + id);
  const labels = {core:'Kernuitspraak',population:'Doelgroep',context:'Context',condition:'Voorwaarde',exception:'Uitzondering',explanation:'Toelichting',evidence:'Onderbouwing'};
  let entry, selected = null, dirty = 0, committed = 0, timer, running = null, retryRequest = null, retryVersion = 0, failed = false;
  let selectingFromSource = false;
  const clone = value => JSON.parse(JSON.stringify(value));
  const status = text => { el('status').textContent = text; };
  function load(id) {
    const saved = state.entries.find(e => e.annotation_id === id);
    entry = saved ? clone(saved) : {annotation_id:crypto.randomUUID(),revision:0,status:'draft',object_type:null,ranges:[],evidence_not_applicable:false};
    selected = entry.pending_range ? clone(entry.pending_range) : null;
    el('selection').textContent = selected ? 'Nog te koppelen: '+selected.quote : '';
    if (selected) {
      el('role').value=selected.role; el('essential').checked=selected.required_for_meaning;
      el('function').value=selected.evidence_function || 'supported_by';
    }
    dirty = committed = 0;
    el('type').value = entry.object_type || '';
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
    el('ranges').replaceChildren();
    entry.ranges.forEach((a,index) => {
      const li = document.createElement('li');
      const p = document.createElement('p');
      p.textContent = labels[a.role] + (a.required_for_meaning ? ' (essentieel)' : '') + ': ' + a.quote;
      const link = document.createElement('a'); link.href = '#' + a.block_id; link.textContent = 'Open in bron';
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Bereik verwijderen';
      remove.className = 'btn-secondary';
      remove.addEventListener('click',() => { entry.ranges.splice(index,1); change(); render(); });
      li.append(p,link,' ',remove); el('ranges').append(li);
    });
  }
  function change() {
    entry.status = 'draft'; dirty += 1;
    status('Niet opgeslagen.'); clearTimeout(timer);
    timer = setTimeout(() => { flush().catch(() => {}); },600);
  }
  function requestForCurrent() {
    const reference = a => ({block_id:a.block_id,start:a.start,end:a.end,quote:a.quote,role:a.role,required_for_meaning:a.required_for_meaning,evidence_function:a.evidence_function});
    const ranges = entry.ranges.map(reference);
    return {snapshot_id:state.snapshot_id,command_id:crypto.randomUUID(),annotation_id:entry.annotation_id,
      expected_revision:entry.revision,expected_generation:state.generation,extraction_hash:state.extraction_hash,normalization:state.normalization,
      selection:{status:entry.status,object_type:entry.object_type,ranges,pending_range:entry.pending_range ? reference(entry.pending_range) : null,evidence_not_applicable:entry.evidence_not_applicable}};
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
          if (!response.ok) {
            if (response.status === 422) { retryRequest = null; }
            const error = new Error(data.message || 'Opslaan mislukt.'); error.validation = response.status === 422; throw error;
          }
          entry.revision = data.revision; state.generation = data.generation;
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
    selected=value;
    const role=el('role').value;
    entry.pending_range={...selected,role,required_for_meaning:el('essential').checked,evidence_function:role==='evidence'?el('function').value:null};
    el('selection').textContent='Aangewezen: '+selected.quote;
    change();
  }
  function rememberSelection(event) {
    // Sidebar clicks must never replace an explicitly chosen block with the
    // browser's older, still-visible selection. Textareas own their select event.
    if (event.type==='mouseup') {
      const started=selectingFromSource; selectingFromSource=false;
      if (!started) return;
    } else if (!event.target.closest?.('[data-source-block]')) return;
    const selection = window.getSelection();
    if (!selection.rangeCount || selection.isCollapsed) return;
    const range = selection.getRangeAt(0);
    const parent = node => (node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement).closest('[data-source-block]');
    const first = parent(range.startContainer), last = parent(range.endContainer);
    if (!first || first !== last) {
      selected = null; el('selection').textContent = 'Wijs één bereik binnen een tekstblok aan. Voeg een volgende alinea afzonderlijk toe.'; return;
    }
    const prefix = document.createRange(); prefix.selectNodeContents(first); prefix.setEnd(range.startContainer,range.startOffset);
    const endPrefix = document.createRange(); endPrefix.selectNodeContents(first); endPrefix.setEnd(range.endContainer,range.endOffset);
    captureSelection({block_id:first.dataset.sourceBlock,start:Array.from(prefix.toString()).length,end:Array.from(endPrefix.toString()).length,quote:range.toString()});
  }
  document.addEventListener('mouseup',rememberSelection);
  document.addEventListener('mousedown',event => { selectingFromSource=!!event.target.closest?.('[data-source-block]'); });
  document.addEventListener('keyup',rememberSelection);
  for (const input of document.querySelectorAll('[data-source-input]')) {
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
      captureSelection({block_id:input.dataset.sourceInput,start:Array.from(input.value.slice(0,input.selectionStart)).length,
        end:Array.from(input.value.slice(0,input.selectionEnd)).length,quote:input.value.slice(input.selectionStart,input.selectionEnd)});
    });
  }
  for (const button of document.querySelectorAll('[data-select-block]')) button.addEventListener('click',() => {
    const block = state.blocks.find(b => b.block_id === button.dataset.selectBlock);
    captureSelection({block_id:block.block_id,start:0,end:Array.from(block.text).length,quote:block.text});
  });
  el('add').addEventListener('click',() => {
    if (!selected) { status('Wijs eerst tekst in één bronblok aan.'); return; }
    const role = el('role').value;
    entry.ranges.push({...selected,role,required_for_meaning:el('essential').checked,evidence_function:role==='evidence' ? el('function').value : null});
    window.getSelection().removeAllRanges();
    selected = null; entry.pending_range=null; el('selection').textContent = ''; change(); render();
  });
  el('discard').addEventListener('click',() => { selected=null;entry.pending_range=null;el('selection').textContent='';change(); });
  for (const id of ['role','essential','function']) el(id).addEventListener('change',() => { if (selected) captureSelection(selected); });
  el('type').addEventListener('change',() => { entry.object_type = el('type').value || null; change(); });
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
})();
