// Zorgmaatje: read-only page companion. It only reads existing routes, starts the
// existing view check through its own form and composes reports in the browser.
// All server data is rendered with textContent; nothing is stored server side.
(() => {
  'use strict';
  const root = document.querySelector('[data-care-companion]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = '1';
  const toggle = root.querySelector('[data-care-toggle]');
  const panel = root.querySelector('.care-panel');
  const body = root.querySelector('[data-care-body]');
  const dot = root.querySelector('[data-care-dot]');
  const room = root.dataset.room || 'page';
  const commit = root.dataset.commit || '';
  const browserErrors = [];
  const OPEN_KEY = 'metis-care-open';

  const HELP = {
    home: 'Mijn werk is je startpunt. Kies de volgende stap: inleveren, bronselectie, review, publicatie of documenten.',
    ingest: 'Hier lever je een nieuwe bron in. Kies het bestand, de documentklasse en wie de review doet. Na inleveren ga je verder in Bronselectie.',
    selection: 'Bronselectie start of hervat de verwerking per document. Een geblokkeerd document toont hier waarom; de diagnose staat in Inzicht.',
    review: 'Hier beoordeel je de voorgestelde passages. Je beoordeling is pas vastgelegd na opslaan. Bij vier-ogen is een tweede, onafhankelijke reviewer nodig.',
    publish: 'Publicatie toont wat klaar is om te publiceren en wat nog ontbreekt. Publiceren gebeurt pas na een volledige, geldige review.',
    tree: 'Documenten toont alle bronnen per familie en klasse. Open een document voor details, versies en diagnose.',
    settings: 'Instellingen bevat accounts, verwerkingsinstellingen en technische informatie. Wijzigingen hier gelden voor iedereen.',
    accounts: 'Accountbeheer: rollen bepalen wat iemand mag. Een reviewer moet bij een document als reviewer zijn genoemd.',
    page: 'Ik help je deze pagina te begrijpen, laat zien waar het misgaat en maak samen met jou een melding.'
  };
  const REASONS = {
    not_configured: 'De weergavecontrole is in deze omgeving nog niet aangezet.',
    not_named_reviewer: 'Alleen een toegewezen reviewer van dit document kan de weergave laten controleren.',
    not_available: 'Dit document is nu niet beschikbaar voor een weergavecontrole.',
    not_supported: 'De weergavecontrole ondersteunt dit document of deze verwerkingspoging (nog) niet.',
    no_document: ''
  };
  const CHECK_STATES = {
    queued: 'In wachtrij', running: 'Wordt gecontroleerd', completed: 'Klaar',
    failed: 'Niet vastgesteld', cancelled: 'Geannuleerd'
  };

  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else node.setAttribute(key, value);
    }
    for (const child of children) if (child) node.append(child);
    return node;
  };
  const section = (title, ...children) => el('section', {class: 'care-section'}, el('h3', {text: title}), ...children);
  const storage = (action) => { try { return action(sessionStorage); } catch (_) { return null; } };

  window.addEventListener('error', (event) => {
    browserErrors.push(String(event.message || 'scriptfout').slice(0, 160));
    refreshMood();
  });
  window.addEventListener('unhandledrejection', () => {
    browserErrors.push('onafgehandelde fout in de pagina');
    refreshMood();
  });

  const pageError = () => {
    const banner = document.querySelector('[data-error-code]');
    if (!banner) return null;
    return {
      code: banner.getAttribute('data-error-code') || '',
      text: (banner.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 400),
      reference: banner.getAttribute('data-request-id') || ''
    };
  };
  const refreshMood = () => {
    const troubled = Boolean(pageError()) || browserErrors.length > 0;
    root.dataset.mood = troubled ? 'concerned' : 'calm';
    dot.hidden = !troubled;
  };

  const reportText = (error) => [
    'Melding Metis-console',
    'Tijd: ' + new Date().toISOString(),
    'Pagina: ' + location.pathname + location.search,
    'Foutcode: ' + (error && error.code ? error.code : '-'),
    'Melding op de pagina: ' + (error && error.text ? error.text : '-'),
    'Referentie: ' + (error && error.reference ? error.reference : '-'),
    'Versie: ' + (commit || '-'),
    'Browserfouten: ' + (browserErrors.length ? browserErrors.slice(0, 5).join(' | ') : 'geen'),
    '',
    'Wat deed je net, en wat verwachtte je?',
    ''
  ].join('\n');

  const reportSection = (error) => {
    const area = el('textarea', {class: 'care-report', rows: '9', 'aria-label': 'Tekst van de melding'});
    area.value = reportText(error);
    const status = el('p', {class: 'care-muted', role: 'status'});
    const copy = el('button', {type: 'button', class: 'btn-primary', text: 'Kopieer melding'});
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(area.value);
        status.textContent = 'Gekopieerd. Plak de melding in Teams, e-mail of het issue.';
      } catch (_) {
        area.select();
        status.textContent = 'Kopiëren lukte niet automatisch. De tekst is geselecteerd: gebruik Ctrl+C.';
      }
    });
    const mail = el('a', {class: 'care-link', text: 'Open in e-mail'});
    const updateMail = () => mail.setAttribute('href', 'mailto:?subject=' + encodeURIComponent('Melding Metis-console')
      + '&body=' + encodeURIComponent(area.value));
    area.addEventListener('input', updateMail);
    updateMail();
    return section('Melding maken',
      el('p', {text: 'Vul aan wat je deed. De melding blijft op jouw scherm totdat je hem zelf deelt.'}),
      area, el('div', {class: 'care-actions'}, copy, mail), status);
  };

  const problemSection = () => {
    const error = pageError();
    if (!error && !browserErrors.length) return null;
    const items = el('ol', {class: 'care-steps'},
      el('li', {text: 'Lees de melding op de pagina: die zegt wat er niet is gelukt.'}),
      el('li', {text: 'Controleer de huidige status voordat je het opnieuw probeert; een actie kan al half zichtbaar zijn voor anderen.'}),
      el('li', {text: 'Blijft het gebeuren? Maak hieronder een melding met de code en referentie.'}));
    const facts = el('p', {class: 'care-muted'});
    facts.textContent = [error && error.code ? 'Foutcode: ' + error.code : '',
      error && error.reference ? 'Referentie: ' + error.reference : '',
      browserErrors.length ? browserErrors.length + ' fout(en) in de pagina zelf' : ''].filter(Boolean).join(' · ');
    return section('Er ging iets mis', items, facts);
  };

  const fetchJson = async (url) => {
    const response = await fetch(url, {credentials: 'same-origin', headers: {Accept: 'application/json'}});
    if (!response.ok) throw new Error(String(response.status));
    return response.json();
  };

  const documentsSection = () => {
    const list = el('ul', {class: 'care-list'});
    const status = el('p', {class: 'care-muted', text: 'Meldingen worden opgehaald…'});
    const cached = storage((s) => JSON.parse(s.getItem('metis-care-notices') || 'null'));
    const render = (rows) => {
      list.replaceChildren();
      if (!rows.length) {
        status.textContent = 'Geen geblokkeerde documenten of recente fouten in jouw documenten.';
        return;
      }
      status.textContent = rows.length + ' document(en) vragen aandacht:';
      for (const row of rows) {
        const link = el('a', {href: '/inzicht/document?' + new URLSearchParams({document: row.snapshot_id}), text: row.title || row.snapshot_id});
        const detail = [row.code, ...(row.reasons || []).map((reason) => reason.code)].filter(Boolean).slice(0, 3).join(', ');
        const why = [row.blocked ? row.blocked + ' geblokkeerd' : '',
          row.telemetry && row.telemetry.errors ? row.telemetry.errors + ' fout(en) in 24 uur' : '', detail].filter(Boolean).join(' · ');
        list.append(el('li', {}, link, why ? el('span', {class: 'care-muted', text: ' — ' + why}) : null));
      }
    };
    if (cached && Date.now() - cached.at < 60000) {
      render(cached.rows);
    } else {
      Promise.all(['blocked', 'errors'].map((filter) =>
        fetchJson('/inzicht/api/documents?' + new URLSearchParams({state: filter, limit: '5'}))
          .then((page) => page.documents || [])))
        .then(([blocked, errors]) => {
          const seen = new Set();
          const rows = [...blocked, ...errors].filter((row) => !seen.has(row.snapshot_id) && seen.add(row.snapshot_id)).slice(0, 8);
          storage((s) => s.setItem('metis-care-notices', JSON.stringify({at: Date.now(), rows})));
          render(rows);
        })
        .catch(() => { status.textContent = 'Meldingen zijn nu niet op te halen. Open Inzicht voor het volledige overzicht.'; });
    }
    return section('Meldingen', status, list, el('a', {class: 'care-link', href: '/inzicht', text: 'Naar Inzicht'}));
  };

  const viewCheckSection = (documentId, attempt) => {
    const holder = section('Weergavecontrole', el('p', {class: 'care-muted', text: 'Status wordt opgehaald…'}));
    fetchJson('/zorgmaatje/weergavecontrole?' + new URLSearchParams({document: documentId, attempt}))
      .then((data) => {
        const children = [el('h3', {text: 'Weergavecontrole'})];
        if (!data.available || !data.form) {
          const reason = REASONS[data.reason] ?? REASONS.not_available;
          if (reason) children.push(el('p', {class: 'care-muted', text: reason}));
        }
        if (data.form) {
          const form = el('form', {method: 'post', action: '/inzicht/document/weergavecontrole'});
          for (const [name, value] of Object.entries(data.form)) form.append(el('input', {type: 'hidden', name, value}));
          form.append(el('button', {type: 'submit', class: 'btn-primary', text: 'Controleer weergave'}));
          children.push(el('p', {text: 'Laat de browser nagaan of dit scherm overeenkomt met de vastgelegde gegevens. Dit is geen inhoudelijke beoordeling.'}), form);
        }
        if (data.checks && data.checks.length) {
          const list = el('ul', {class: 'care-list'});
          for (const check of data.checks) {
            const summary = check.state === 'completed'
              ? `${check.passed} geslaagd, ${check.differences} afwijking(en), ${check.not_established} niet vastgesteld`
              : (check.reason || '');
            list.append(el('li', {},
              el('a', {href: '/inzicht/document?' + new URLSearchParams({document: documentId, attempt}) + '#weergavecontrole',
                text: CHECK_STATES[check.state] || check.state}),
              el('span', {class: 'care-muted', text: ' — ' + [summary, check.created_at.slice(0, 16).replace('T', ' ')].filter(Boolean).join(' · ')})));
          }
          children.push(list);
        }
        holder.replaceChildren(...children);
      })
      .catch(() => holder.replaceChildren(el('h3', {text: 'Weergavecontrole'}),
        el('p', {class: 'care-muted', text: 'De status is nu niet op te halen.'})));
    return holder;
  };

  const render = () => {
    const params = new URLSearchParams(location.search);
    const documentId = params.get('document') || '';
    const error = pageError();
    const parts = [
      problemSection(),
      section('Op deze pagina', el('p', {text: HELP[room] || HELP.page})),
      documentId ? viewCheckSection(documentId, params.get('attempt') || '') : null,
      documentsSection(),
      reportSection(error)
    ];
    body.replaceChildren(...parts.filter(Boolean));
  };

  const setOpen = (open, focus = true) => {
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    root.dataset.open = open ? '1' : '';
    storage((s) => (open ? s.setItem(OPEN_KEY, '1') : s.removeItem(OPEN_KEY)));
    if (open) {
      render();
      if (focus) root.querySelector('[data-care-close]').focus();
    } else if (focus) {
      toggle.focus();
    }
  };

  toggle.addEventListener('click', () => setOpen(panel.hidden));
  root.querySelector('[data-care-close]').addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !panel.hidden) setOpen(false);
  });
  refreshMood();
  if (storage((s) => s.getItem(OPEN_KEY)) === '1') setOpen(true, false);
})();
