// Raad: read-only page companion. It only reads existing routes, starts the
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
  const version = root.dataset.version || '';
  const browserErrors = [];
  const OPEN_KEY = 'metis-care-open';
  const DEPLOY_KEY = 'metis-care-deploy-check';
  // Inside the deploy check's hidden frame Raad only counts errors for the parent.
  const embedded = window.self !== window.top;

  const HELP = {
    home: 'Mijn werk is je startpunt. Kies de volgende stap: inleveren, bronselectie, review, publicatie of documenten.',
    ingest: 'Hier lever je een nieuwe bron in. Kies het bestand, de documentklasse en wie de review doet. Na inleveren ga je verder in Bronselectie.',
    selection: 'Bronselectie start of hervat de verwerking per document. Een geblokkeerd document toont hier waarom; de diagnose staat in Inzicht.',
    review: 'Hier beoordeel je de voorgestelde passages. Je beoordeling is pas vastgelegd na opslaan. Bij vier-ogen is een tweede, onafhankelijke reviewer nodig.',
    formation: 'Vormingsproblemen toont welke bronproblemen nog openstaan en waar je ze kunt behandelen. Geldige voorstellen blijven bereikbaar in Review; open problemen blijven publicatie blokkeren.',
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
  const disclosure = (title, content) => el('details', {class: 'care-disclosure'}, el('summary', {text: title}), content);
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
    root.dataset.errors = String(browserErrors.length);
    dot.hidden = !troubled;
  };

  const reportText = (error) => [
    'Melding Metis-console',
    'Tijd: ' + new Date().toISOString(),
    'Pagina: ' + location.pathname + location.search,
    'Foutcode: ' + (error && error.code ? error.code : '-'),
    'Melding op de pagina: ' + (error && error.text ? error.text : '-'),
    'Referentie: ' + (error && error.reference ? error.reference : '-'),
    'Versie: ' + (version || 'niet beschikbaar'),
    'Buildreferentie: ' + (commit || '-'),
    'Browserfouten: ' + (browserErrors.length ? browserErrors.slice(0, 5).join(' | ') : 'geen'),
    '',
    'Wat deed je net, en wat verwachtte je?',
    ''
  ].join('\n');

  const reportSection = (error) => {
    const area = el('textarea', {class: 'care-report', rows: '9', 'aria-label': 'Tekst van de melding'});
    area.value = reportText(error);
    const status = el('p', {class: 'care-muted', role: 'status'});
    const copy = el('button', {type: 'button', class: 'btn-secondary', text: 'Kopieer melding'});
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

  // Share only an active request in this tab. Protected titles are never saved
  // in sessionStorage or reused after authorization may have changed.
  let noticesInFlight = null;
  const notices = () => {
    if (!noticesInFlight) {
      noticesInFlight = fetchJson('/raad/meldingen').finally(() => { noticesInFlight = null; });
    }
    return noticesInFlight;
  };

  const documentsSection = () => {
    const list = el('ul', {class: 'care-list'});
    const status = el('p', {class: 'care-muted', role: 'status', text: 'Meldingen worden opgehaald…'});
    storage((s) => s.removeItem('metis-care-notices'));
    const render = (page) => {
      const rows = page.documents || [];
      list.replaceChildren();
      if (!rows.length) {
        status.textContent = page.complete ? 'Geen opgeslagen verwerkingsblokkades, geblokkeerde kandidaten of recente fouten gevonden.' : 'Het overzicht is onvolledig; overige meldingen zijn nog niet gecontroleerd.';
        return;
      }
      status.textContent = rows.length + ' document(en) vragen aandacht:' + (page.complete ? '' : ' Het overzicht is onvolledig.');
      for (const row of rows) {
        const link = el('a', {href: '/inzicht/document?' + new URLSearchParams({document: row.snapshot_id}), text: row.title || row.snapshot_id});
        const detail = [row.code, ...(row.reasons || []).map((reason) => reason.code)].filter(Boolean).slice(0, 3).join(', ');
        const why = [row.processing_blocked ? 'opgeslagen verwerkingsblokkade' : '',
          row.processing_access ? (row.blocked === null ? 'aantal geblokkeerde kandidaten niet vastgesteld' : row.blocked + ' geblokkeerde kandidaten') : '',
          row.telemetry && row.telemetry.errors ? row.telemetry.errors + ' fout(en) in 24 uur' : '', detail].filter(Boolean).join(' · ');
        list.append(el('li', {}, link, why ? el('span', {class: 'care-muted', text: ' — ' + why}) : null));
      }
    };
    notices().then(render)
      .catch(() => { status.textContent = 'Meldingen zijn nu niet op te halen. Open Inzicht voor het volledige overzicht.'; });
    return section('Meldingen', status, list, el('a', {class: 'care-link', href: '/inzicht', text: 'Naar Inzicht'}));
  };

  const viewCheckSection = (documentId, attempt) => {
    const holder = section('Weergavecontrole', el('p', {class: 'care-muted', role: 'status', text: 'Status wordt opgehaald…'}));
    holder.setAttribute('aria-busy', 'true');
    fetchJson('/raad/weergavecontrole?' + new URLSearchParams({document: documentId, attempt}))
      .then((data) => {
        const children = [el('h3', {text: 'Weergavecontrole'})];
        if (!data.available || !data.form) {
          const reason = REASONS[data.reason] ?? REASONS.not_available;
          if (reason) children.push(el('p', {class: 'care-muted', role: 'status', text: reason}));
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
        el('p', {class: 'care-muted', role: 'status', text: 'De status is nu niet op te halen. Probeer het later opnieuw of open Inzicht.'})))
      .finally(() => holder.setAttribute('aria-busy', 'false'));
    return holder;
  };

  // Deploy check: open every main page once, in this browser with this sign-in,
  // in a hidden sandboxed frame without forms, popups or top navigation. Only
  // GET page loads; it reads what a person would see and stores nothing server side.
  const PAGE_TIMEOUT = 20000;
  const SETTLE = 1500;
  // Same rooms as the server-side navigation (_nav), plus Inzicht.
  const DEPLOY_PAGES = [
    ['Mijn werk', '/'], ['Inleveren', '/ingest'], ['Vorming', '/source-selection'], ['Review', '/review'],
    ['Publicatie', '/publish'], ['Documenten', '/tree'], ['Instellingen', '/settings'], ['Inzicht', '/inzicht']
  ].map(([label, path]) => ({label, path}));

  // The header lists the roles after "rollen:" (separated by "·" or ","); a refusal
  // for a role the account has is a fault.
  // Read the dedicated role element, so a display name containing "rollen:" cannot mislead.
  const accountRoles = () => {
    const holder = document.querySelector('header.topbar .who-roles') || document.querySelector('header.topbar .who');
    const text = (holder && holder.textContent) || '';
    const marker = text.lastIndexOf('rollen:');
    return text.slice(marker < 0 ? 0 : marker + 'rollen:'.length)
      .split(/[,·]/).map((role) => role.trim()).filter(Boolean);
  };

  const probePage = (page) => new Promise((resolve) => {
    const frame = el('iframe', {class: 'care-probe', sandbox: 'allow-same-origin allow-scripts',
      'aria-hidden': 'true', tabindex: '-1', title: 'Deploy-controle'});
    const started = performance.now();
    let settled = false;
    let lateErrors = 0;
    let readiness = {step: 'page_usability', expected: 'task_controls_available', observed: 'navigation_pending', verdict: 'not_established'};
    let poll;
    const finish = (outcome) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      clearTimeout(poll);
      frame.remove();
      const elapsed_ms = Math.round(performance.now() - started);
      const seconds = elapsed_ms / 1000;
      const verdict = outcome.skipped || outcome.problem === 'login' ? 'not_checked_access' : outcome.ok ? 'pass' :
        ['timeout', 'incomplete', 'unreadable'].includes(outcome.problem) ? 'not_established' : 'fail';
      const observed = outcome.skipped ? 'missing_access' : readiness.observed === 'navigation_pending' && outcome.problem ? outcome.problem : readiness.observed;
      resolve({...page, ...outcome, verdict,
        diagnosis: {...readiness, verdict, observed, elapsed_ms}, seconds: seconds.toLocaleString('nl-NL', {minimumFractionDigits: 1, maximumFractionDigits: 1})});
    };
    // Our pages never leave the origin: a cross-origin frame is the Entra sign-in.
    const signIn = () => {
      try {
        const path = frame.contentWindow.location.pathname;
        return path === '/login' || path.startsWith('/auth/');
      } catch (_) {
        return true;
      }
    };
    const timer = setTimeout(() => finish({ok: false, problem: signIn() ? 'login' : 'timeout'}), PAGE_TIMEOUT);
    frame.addEventListener('load', () => {
      if (signIn()) {
        finish({ok: false, problem: 'login'});
        return;
      }
      const win = frame.contentWindow;
      win.addEventListener('error', () => { lateErrors += 1; });
      const inspect = () => {
        try {
          const doc = frame.contentDocument;
          const nav = win.performance.getEntriesByType('navigation')[0];
          const status = nav && nav.responseStatus ? nav.responseStatus : 0;
          const banner = doc.querySelector('[data-error-code]');
          const shell = doc.querySelector('[data-care-companion]');
          // Raad inside the frame counts from its own start; the listener only after load.
          const errors = Math.max(Number(shell && shell.dataset.errors || 0), lateErrors);
          readiness.navigation = {route:page.path, state:'loaded', status, reference:banner?.getAttribute('data-request-id') || null};
          const code = banner ? banner.getAttribute('data-error-code') || '' : '';
          // Local sign-in answers protected pages with not_authenticated, and / with a login form.
          if (signIn() || code === 'not_authenticated' || doc.querySelector('input[type=password]')) finish({ok: false, problem: 'login'});
          // A page this role may not open is not a deploy fault.
          else if (/_role_required$/.test(code) && !accountRoles().includes(code.replace(/_role_required$/, ''))) finish({ok: true, skipped: true, code});
          else if (banner) finish({ok: false, problem: 'error', code, reference: banner.getAttribute('data-request-id') || ''});
          else if (status >= 400) finish({ok: false, problem: 'status', status});
          // A page that lands elsewhere in the console did not load itself.
          else if (win.location.pathname !== page.path) finish({ok: false, problem: 'redirect', landed: win.location.pathname});
          else if (!shell) finish({ok: false, problem: 'incomplete', status});
          else if (errors) finish({ok: false, problem: 'script', errors});
          else {
            readiness = win.MetisPageReadiness ? {...win.MetisPageReadiness(page.path), navigation:readiness.navigation} : {...readiness, observed: 'readiness_unavailable'};
            if (readiness.request?.state === '401') finish({ok:false, problem:'login'});
            else if (readiness.verdict === 'pass') finish({ok: true});
            else if (['partial', 'error'].includes(readiness.observed)) finish({ok: false, problem: 'incomplete'});
            else poll = setTimeout(inspect, 100);
          }
        } catch (_) {
          finish({ok: false, problem: 'unreadable'});
        }
      };
      poll = setTimeout(inspect, SETTLE);
    });
    frame.setAttribute('src', page.path === '/inzicht' ? '/inzicht?tab=documenten' : page.path);
    document.body.append(frame);
  });

  const deployProblem = (row) => ({
    timeout: 'laadt niet binnen ' + PAGE_TIMEOUT / 1000 + ' seconden',
    login: 'vraagt om aanmelden; meld je opnieuw aan',
    error: 'toont een foutmelding; open de controledetails voor code en referentie',
    status: 'geeft foutstatus ' + row.status,
    redirect: 'stuurt door naar ' + row.landed,
    incomplete: 'is niet volledig geladen' + (row.status ? ' (status ' + row.status + ')' : ''),
    script: row.errors + ' scriptfout(en) in de pagina',
    unreadable: 'kon niet worden uitgelezen'
  }[row.problem] || 'onbekend probleem');

  const deployText = (run) => [
    'Bruikbaarheidscontrole Metis-console',
    'Tijd: ' + run.at,
    'Versie: ' + (run.version || 'niet beschikbaar'),
    'Buildreferentie: ' + (run.commit || '-'),
    ...run.rows.map((row) => (row.verdict === 'not_checked_access' ? 'NIET  ' : row.verdict === 'not_established' ? 'ONBEKEND  ' : row.ok ? 'OK    ' : 'FOUT  ') + row.label + ' (' + row.path + ') — '
      + (row.skipped ? 'geen toegang met jouw rol' : row.ok ? 'bruikbaar, ' + row.seconds + ' s' : deployProblem(row))
      + (row.diagnosis ? '\n  ' + JSON.stringify(row.diagnosis) : ''))
  ].join('\n');

  // One run per page; the panel re-renders on reopen, so the run lives here
  // and reports to whichever section is currently shown.
  let deployProgress = '';
  let deployView = null;

  const deploySection = () => {
    const status = el('p', {class: 'care-muted', role: 'status'});
    const list = el('ul', {class: 'care-list'});
    const evidence = el('div');
    const technical = disclosure('Controledetails', evidence);
    technical.hidden = true;
    const start = el('button', {type: 'button', class: new URLSearchParams(location.search).get('document') ? 'btn-secondary' : 'btn-primary', text: "Controleer alle pagina's"});
    const copy = el('button', {type: 'button', class: 'btn-secondary', text: 'Kopieer uitslag'});
    // Button classes set display, so the hidden attribute alone would not hide it.
    const actions = el('div', {class: 'care-actions'}, start);
    // sessionStorage survives a sign-out in this tab: only show a run of the same account and roles.
    const who = (document.querySelector('header.topbar .who') || {}).textContent || '';
    let last = storage((s) => JSON.parse(s.getItem(DEPLOY_KEY) || 'null'));
    if (last && (last.who !== who || last.schema !== 'task-ready-v2')) last = null;
    const show = (run) => {
      list.replaceChildren(...run.rows.map((row) => el('li', {'data-deploy-page': row.path,
        'data-deploy-result': row.verdict === 'not_checked_access' ? 'skipped' : row.ok ? 'ok' : 'problem'},
        el('strong', {text: row.label}),
        el('span', {class: 'care-muted', text: ' — ' + (row.skipped ? 'niet gecontroleerd: geen toegang met jouw rol'
          : row.ok ? 'bruikbaar · ' + row.seconds + ' s' : (row.verdict === 'not_checked_access' ? 'niet gecontroleerd: ' : row.verdict === 'not_established' ? 'niet vastgesteld: ' : 'afwijking: ') + deployProblem(row))}))));
      evidence.replaceChildren(...run.rows.map(row => el('div', {},
        el('strong', {text: row.label}),
        el('pre', {text: JSON.stringify({verdict:row.verdict, code:row.code, reference:row.reference, ...row.diagnosis}, null, 2)}),
        el('a', {href:'/inzicht?tab=systeem&route=' + encodeURIComponent(row.path) + '&q=' + encodeURIComponent(row.diagnosis?.request?.reference || row.diagnosis?.navigation?.reference || row.reference || ''), text:'Beschikbare verzoekdiagnostiek'}))));
      technical.hidden = false;
      const counts = verdict => run.rows.filter(row => row.verdict === verdict).length;
      status.textContent = counts('pass') + ' bruikbaar · ' + counts('fail') + ' afwijking(en) · '
        + counts('not_established') + ' niet vastgesteld · ' + counts('not_checked_access') + ' niet gecontroleerd.'
        + ' Versie ' + (run.version || 'niet beschikbaar') + ', gecontroleerd ' + run.at.slice(11, 16) + ' (UTC).'
        + (run.rows.some(row => row.problem === 'login') ? ' Gestopt: meld je opnieuw aan en controleer daarna opnieuw. '
          + (DEPLOY_PAGES.length - run.rows.length) + ' overige pagina’s zijn niet gecontroleerd.' : '')
        + (counts('not_established') ? ' Probeer opnieuw. Blijft de controle onvolledig? Open de controledetails of maak hieronder een melding.' : '');
      actions.append(copy);
    };
    const view = {
      progress: (text) => { start.disabled = true; list.replaceChildren(); copy.remove(); technical.hidden = true; status.textContent = text; },
      done: (run) => { last = run; start.disabled = false; show(run); }
    };
    deployView = view;
    start.addEventListener('click', async () => {
      if (deployProgress) return;
      const pages = DEPLOY_PAGES;
      const rows = [];
      for (const [index, page] of pages.entries()) {
        deployProgress = 'Bezig: ' + page.label + ' (' + (index + 1) + ' van ' + pages.length + ')…';
        deployView.progress(deployProgress);
        const row = await probePage(page);
        rows.push(row);
        // Further pages would only start more sign-in flows.
        if (row.problem === 'login') break;
      }
      const run = {schema:'task-ready-v2', at: new Date().toISOString(), commit, version, who, rows};
      storage((s) => s.setItem(DEPLOY_KEY, JSON.stringify(run)));
      deployProgress = '';
      deployView.done(run);
    });
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(deployText(last));
        status.textContent = 'Uitslag gekopieerd.';
      } catch (_) {
        status.textContent = 'Kopiëren lukte niet automatisch.';
      }
    });
    if (deployProgress) view.progress(deployProgress);
    else if (last) show(last);
    return section('Controle na deploy',
      el('p', {text: "Controleert of de belangrijkste bediening en gegevens beschikbaar zijn. Een geldige lege lijst mag slagen. Dit bewijst geen inhoudelijke juistheid."}),
      actions, status, list, technical);
  };

  const render = () => {
    const params = new URLSearchParams(location.search);
    const documentId = params.get('document') || '';
    const error = pageError();
    const parts = [
      problemSection(),
      section('Op deze pagina', el('p', {text: HELP[room] || HELP.page})),
      documentId ? viewCheckSection(documentId, params.get('attempt') || '') : null,
      deploySection(),
      documentsSection(),
      disclosure('Melding opstellen', reportSection(error))
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
  if (embedded) return;
  if (storage((s) => s.getItem(OPEN_KEY)) === '1') setOpen(true, false);
})();
