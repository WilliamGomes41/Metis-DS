(() => {
  const element = id => document.getElementById('tree-' + id);
  const {command, graph, export: fromExport, blocks, evidence} = JSON.parse(element('input').textContent);
  const byBlock = new Map(blocks.map(b => [b.block_id, b]));
  const roles = {start:'Start', question:'Vraag', action:'Actie', outcome:'Uitkomst', context:'Context'};
  const choices = {single:'Enkelvoudig', multiple:'Meervoudig'};
  const doubts = {role_ambiguous:'Rol onduidelijk', route_ambiguous:'Route onduidelijk', target_unknown:'Doel onbekend',
    label_ambiguous:'Antwoordlabel onduidelijk', direction_unverified:'Richting onzeker', evidence_missing:'Bewijs ontbreekt'};
  const option = (select, value, label) => select.add(new Option(label, value));
  const selectedText = span => Array.from(byBlock.get(span.block_id).text).slice(span.start, span.end).join('');
  const unitText = unit => unit.spans.map(selectedText).join(' ');
  function changed() {
    if (element('build')) element('build').hidden = true;
    element('status').textContent = 'Wijzigingen nog niet opgeslagen.';
  }
  let lastSelection;
  function selection() {
    const block = byBlock.get(element('block').value), text = block.text;
    const range = window.getSelection();
    if (range.rangeCount && !range.isCollapsed) {
      const r = range.getRangeAt(0), node = element('passage').firstChild;
      if (r.startContainer === node && r.endContainer === node)
        return lastSelection = {block_id:block.block_id, start:Array.from(text.slice(0,r.startOffset)).length,
          end:Array.from(text.slice(0,r.endOffset)).length};
    }
    return lastSelection || {block_id:block.block_id, start:0, end:Array.from(text).length};
  }
  function dropdown(box, name, values, value, update) {
    const label = document.createElement('label'), select = document.createElement('select');
    label.append(name+' ', select);
    for (const [id,text] of Object.entries(values)) option(select,id,text);
    select.value=value;
    select.onchange=()=>{ update(select.value); changed(); render(); };
    box.append(label);
  }
  function removable(list, text, remove) {
    const li=document.createElement('li');
    li.textContent=text+' ';
    if(remove) {
      const button=document.createElement('button');
      button.type='button'; button.textContent='Verwijderen';
      button.onclick=()=>{remove(); changed(); render();}; li.append(button);
    }
    list.append(li);
  }
  function render() {
    for(const id of ['units','edges','doubts','from','to','subject','context','applies','bindings']) element(id)?.replaceChildren();
    if(element('to')) option(element('to'),'','Doel onbekend');
    for(const unit of graph.units) {
      const title=unitText(unit), box=document.createElement('fieldset'), legend=document.createElement('legend');
      legend.textContent=title; box.append(legend);
      let allowed = roles;
      if(fromExport) allowed = ['action','question'].includes(unit.role) ? {action:roles.action,question:roles.question} : {[unit.role]:roles[unit.role]};
      dropdown(box,'Rol',allowed,unit.role,value=>{unit.role=value; unit.selection=value==='question'?'single':null;});
      if(unit.role==='question') dropdown(box,'Keuzesoort',choices,unit.selection,value=>unit.selection=value);
      const label=document.createElement('label'), check=document.createElement('input');
      check.type='checkbox'; check.checked=unit.entry;
      check.disabled=fromExport && graph.connections.some(edge=>edge.to===unit.ref);
      check.onchange=()=>{unit.entry=check.checked;changed();};
      label.append(check,' Startpunt'); box.append(label); element('units').append(box);
      if(!fromExport) {
        option(element(unit.role==='context'?'context':'applies'),unit.ref,title);
        const remove=document.createElement('button');
        remove.type='button'; remove.textContent='Vak verwijderen';
        remove.onclick=()=>{
          const affected=new Set([unit.ref,...graph.connections.filter(edge=>edge.from===unit.ref||edge.to===unit.ref).map(edge=>edge.ref)]);
          graph.units=graph.units.filter(row=>row!==unit);
          graph.connections=graph.connections.filter(edge=>!affected.has(edge.ref));
          graph.context_bindings=graph.context_bindings.filter(b=>b.context!==unit.ref).map(b=>({...b,applies_to:b.applies_to.filter(r=>r!==unit.ref)})).filter(b=>b.applies_to.length);
          graph.unresolved=graph.unresolved.filter(d=>!affected.has(d.subject));
          changed();render();
        };
        box.append(remove);
      }
      for(const id of ['from','to','subject']) if(element(id)) option(element(id),unit.ref,title);
    }
    const names=new Map(graph.units.map(u=>[u.ref,unitText(u)]));
    for(const edge of graph.connections) {
      const label=edge.label_span?selectedText(edge.label_span):edge.evidence_ids.map(id=>evidence[id]?.record?.label).filter(Boolean).join(' ');
      const text=[names.get(edge.from),label,names.get(edge.to)].filter(Boolean).join(' → ');
      removable(element('edges'),text,fromExport?null:()=>{graph.connections=graph.connections.filter(e=>e!==edge);
        graph.unresolved=graph.unresolved.filter(d=>d.subject!==edge.ref);});
      if(element('subject')) option(element('subject'),edge.ref,text);
    }
    if(!fromExport) for(const binding of graph.context_bindings) {
      removable(element('bindings'),names.get(binding.context)+' → '+binding.applies_to.map(target=>names.get(target)).join(', '),
        ()=>graph.context_bindings=graph.context_bindings.filter(b=>b!==binding));
    }
    for(const d of graph.unresolved) removable(element('doubts'),(names.get(d.subject)||d.subject)+' · '+doubts[d.code],
      ()=>graph.unresolved=graph.unresolved.filter(row=>row!==d));
  }
  const ref = prefix => prefix+crypto.randomUUID().replaceAll('-','');
  if(!fromExport) {
    for(const block of blocks) option(element('block'),block.block_id,block.text);
    element('block').onchange=()=>{
      lastSelection=null;
      element('passage').textContent=byBlock.get(element('block').value)?.text||'';
    };
    document.addEventListener('selectionchange', ()=>{
      if(window.getSelection().anchorNode===element('passage').firstChild && !window.getSelection().isCollapsed) selection();
    });
    element('block').onchange();
    for(const [id,item] of Object.entries(evidence)) option(element('evidence'),id,item.kind==='graphic' ? ('Pagina '+item.page+' · lijn '+id+' · '+item.bbox.join(', ')) : (item.text || id));
    for(const [id,label] of Object.entries(doubts)) option(element('code'),id,label);
    element('add-unit').onclick=()=>{ if(!blocks.length)return; graph.units.push({ref:ref('u'),role:'action',entry:false,selection:null,spans:[selection()]}); changed();render(); };
    element('add-edge').onclick=()=>{
      if(!graph.units.length)return;
      graph.connections.push({ref:ref('c'),from:element('from').value,to:element('to').value||null,kind:element('kind').value,
        label_span:element('kind').value==='answer'?selection():null,evidence_ids:Array.from(element('evidence').selectedOptions,o=>o.value)});
      changed();render();
    };
    element('bind').onclick=()=>{
      const context=element('context').value, applies_to=Array.from(element('applies').selectedOptions,o=>o.value);
      if(!context||!applies_to.length)return;
      graph.context_bindings.push({ref:ref('b'),context,applies_to});changed();render();
    };
    element('add-doubt').onclick=()=>{if(!element('subject').value)return;
      graph.unresolved.push({ref:ref('r'),subject:element('subject').value,code:element('code').value});changed();render();};
  }
  element('save').onclick=async()=>{
    const button=element('save'); button.disabled=true;
    try {
      const response=await fetch('/annotations/api',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({...command,command_id:crypto.randomUUID(),selection:graph})});
      if(response.ok){location.reload();return;}
      const error=await response.json();element('status').textContent=(error.message||'Opslaan mislukt.')+' '+(error.error||'');
    } catch {element('status').textContent='Opslaan mislukt. Probeer opnieuw.';}
    finally {button.disabled=false;}
  };
  render();
})();
