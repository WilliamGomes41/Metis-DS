"""Read-only publication observations; canonical storage remains the authority."""
from datetime import datetime, timezone

from src.processing_trace_v1 import clean_runtime, digest, mapping, runtime_identity, sha, token
from src.section_incident_v1 import timestamp
from src.integrity_kernel import compute_canonical_object_hash

VERSION = 'publication-evidence-v1'
MAX_ITEMS = 2048


def _identity(value):
    return token(value, r'[A-Za-z0-9_.:-]{1,160}')


def _items(rows):
    if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
        raise ValueError('publication_items_invalid_or_limit_exceeded')
    items = []
    for row in rows:
        row = mapping(row)
        item = (_identity(row.get('object_id')), _identity(row.get('object_version')), sha(row.get('content_hash')))
        if not all(item):
            raise ValueError('publication_item_identity_missing')
        items.append(item)
    if len({item[0] for item in items}) != len(items):
        raise ValueError('publication_items_duplicate')
    return sorted(items)


def _ordered(first, second, *, strict=False):
    first, second = timestamp(first), timestamp(second)
    if not first or not second:
        return False
    delta = datetime.fromisoformat(second) - datetime.fromisoformat(first)
    return delta.total_seconds() > 0 if strict else delta.total_seconds() >= 0


def collect_publication(console, *, actor_id, snapshot_id):
    """Bounded document observation: no source reconstruction, gate or mutation."""
    from src.operations_console_v1 import ConsoleError
    account = console._require_role(actor_id, 'publisher', current=True)
    if account.get('retirement'):
        raise ConsoleError('not_authenticated')
    envelope = console._envelope(snapshot_id)
    source = sha(envelope.get('sha256'))
    errors = {}
    try:
        revision = digest(console.objects_revision(snapshot_id))
    except Exception:
        revision = None
        errors['revision'] = 'document_revision_read_unavailable'
    result = {'schema': VERSION, 'snapshot_id': snapshot_id, 'source_hash': source,
              'revision_sha256': revision, 'runtime': runtime_identity(),
              'observed_at': datetime.now(timezone.utc).isoformat(), 'errors': errors,
              'release': None, 'consistent': False,
              'scope': 'canonical_release_and_registry_not_product_http'}
    store = getattr(console, 'canonical_publication_store', None)
    if store is None:
        result['errors']['release'] = 'canonical_publication_store_unavailable'
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        return result
    try:
        release = store.release_for_snapshot(snapshot_id)
        if release is not None:
            # Only compact exact tuples leave the secured authority. No content,
            # source locator, account name or exception message is exported.
            result['release'] = {'release_id': _identity(release.get('release_id')),
                'snapshot_id': _identity(release.get('snapshot_id')),
                'source_hash': sha(release.get('source_sha256')),
                'published_at': timestamp(release.get('published_at')),
                'items': _items(release.get('objects'))}
            try:
                if hasattr(store, 'active_release_items'):
                    result['registry_items'] = _items(store.active_release_items(release['release_id']))
                else:
                    # Existing injected test/development authorities support the
                    # established full projection API; production uses the bounded query.
                    selected = [r for r in store.active_publication_rows()
                        if mapping(r.get('publication')).get('release_id') == release['release_id']]
                    result['registry_items'] = _items([{'object_id': mapping(r.get('knowledge_object')).get('object_id'),
                        'object_version': mapping(r.get('knowledge_object')).get('object_version'),
                        'content_hash': compute_canonical_object_hash(r['knowledge_object'])} for r in selected])
            except Exception as error:
                result['errors']['registry'] = token(getattr(error, 'code', None), r'[a-z][a-z0-9_]{0,95}') or 'publication_registry_read_unavailable'
            # Bracket independent reads; equality is not an atomic snapshot claim.
            again = store.release_for_snapshot(snapshot_id)
            result['consistent'] = release == again
        else:
            result['consistent'] = store.release_for_snapshot(snapshot_id) is None
    except Exception as error:
        result['errors']['release'] = token(getattr(error, 'code', None), r'[a-z][a-z0-9_]{0,95}') or 'publication_authority_read_unavailable'
    after = console._envelope(snapshot_id)
    if console._require_role(actor_id, 'publisher', current=True).get('retirement'):
        raise ConsoleError('not_authenticated')
    try:
        after_revision = digest(console.objects_revision(snapshot_id))
    except Exception:
        after_revision = None
        result['errors']['revision'] = 'document_revision_read_unavailable'
    if sha(after.get('sha256')) != source or after_revision != revision:
        result['consistent'] = False
        result['errors']['context'] = 'document_changed_during_observation'
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    return result


def publication_report(observation, *, after_restart=None, route_evidence=None):
    """Compare exact observations, never infer commit/serving from HTTP 200."""
    missing, conflicts = [], []
    def inspect(raw, prefix):
        raw = mapping(raw)
        if raw.get('schema') != VERSION:
            raise ValueError('publication_observation_schema_invalid')
        release = mapping(raw.get('release'))
        errors = mapping(raw.get('errors'))
        valid = raw.get('consistent') is True and not errors
        for field in ('observed_at', 'finished_at'):
            if timestamp(raw.get(field)) is None:
                missing.append(prefix + field + '_missing')
                valid = False
        snapshot = _identity(raw.get('snapshot_id'))
        source = sha(raw.get('source_hash'))
        if not snapshot or not source or not sha(raw.get('revision_sha256')):
            missing.append(prefix + 'document_identity_missing')
            valid = False
        runtime = clean_runtime(raw.get('runtime'))
        if not runtime['version'] or not runtime['runtime_id']:
            missing.append(prefix + 'runtime_identity_incomplete')
        if not valid:
            missing.append(prefix + 'consistent_authority_read_missing')
        if not release:
            missing.append(prefix + 'canonical_release_missing')
            return raw, None, False
        if (release.get('snapshot_id') != snapshot or release.get('source_hash') != source
                or not _identity(release.get('release_id'))):
            conflicts.append(prefix + 'release_identity_disagrees')
            valid = False
        try:
            # Serialized observations store compact tuples, not object content.
            tuples = release.get('items')
            items = _items([dict(zip(('object_id','object_version','content_hash'), row, strict=True)) for row in tuples])
            registry = _items([dict(zip(('object_id','object_version','content_hash'), row, strict=True)) for row in raw.get('registry_items', [])])
        except (ValueError, TypeError):
            conflicts.append(prefix + 'release_items_invalid')
            return raw, None, False
        if not items:
            missing.append(prefix + 'release_items_missing')
            valid = False
        if 'registry_items' not in raw:
            missing.append(prefix + 'active_registry_read_missing')
        if items != registry:
            conflicts.append(prefix + 'active_registry_differs_from_release')
        if not timestamp(release.get('published_at')):
            missing.append(prefix + 'publication_timestamp_missing')
            valid = False
        identity = (snapshot, source, release.get('release_id'), items)
        return raw, identity, valid and items == registry
    before, identity, active = inspect(observation, '')
    restart = False
    if after_restart is not None:
        after, later_identity, later_active = inspect(after_restart, 'restart_')
        old_runtime = clean_runtime(before.get('runtime'))['runtime_id']
        new_runtime = clean_runtime(after.get('runtime'))['runtime_id']
        if not old_runtime or not new_runtime or old_runtime == new_runtime:
            missing.append('distinct_process_restart_not_proven')
        elif _ordered(before.get('finished_at'), after.get('observed_at'), strict=True):
            if identity != later_identity:
                conflicts.append('restart_release_identity_disagrees')
            restart = active and later_active and identity == later_identity
        else:
            conflicts.append('restart_observation_order_invalid')
    else:
        missing.append('restart_observation_missing')
    # Route evidence is an explicit captured verification, never a kernel gate.
    route = mapping(route_evidence)
    route_proven = False
    if route:
        if route.get('schema') != 'publication-route-evidence-v1':
            raise ValueError('publication_route_schema_invalid')
        if route.get('boundary_evidence_missing'):
            missing.append(token(route['boundary_evidence_missing'], r'[a-z][a-z0-9_]{0,95}') or 'publication_boundary_evidence_missing')
        browser = mapping(route.get('browser_incident'))
        readiness = mapping(route.get('readiness'))
        valid_context = (identity is not None and route.get('snapshot_id') == identity[0]
            and route.get('source_hash') == identity[1]
            and sha(route.get('review_revision_sha256')) is not None)
        if not valid_context:
            conflicts.append('route_document_identity_disagrees')
        browser_ok = (browser.get('schema') == 'metis.section-incident.v1'
            and mapping(browser.get('browser')).get('usability') == 'passed'
            and mapping(browser.get('browser')).get('route') == '/publish'
            and browser.get('correlation') == 'response_request_id'
            and mapping(browser.get('browser')).get('status') == 200
            and mapping(browser.get('browser')).get('navigation') == 'loaded'
            and mapping(browser.get('browser')).get('final_location') == 'target'
            and mapping(browser.get('browser')).get('assertion') == 'section-visible-v1'
            and mapping(browser.get('browser')).get('response_complete') is True
            and mapping(browser.get('application')).get('response_completed') is True
            and browser.get('missing_evidence') == [] and browser.get('contradictions') == [])
        # Require the exact reviewed tuple set at the command boundary, not a
        # generic ready boolean for another document or a later revision.
        try:
            reviewed = _items(route.get('reviewed_items'))
        except ValueError:
            reviewed = None
        command = mapping(route.get('publish_command'))
        command_bound = (valid_context and command.get('status') == 'PASS'
            and command.get('release_id') == identity[2]
            and command.get('revision_sha256') == route.get('review_revision_sha256')
            and command.get('snapshot_id') == identity[0]
            and command.get('source_hash') == identity[1]
            and token(command.get('request_id'), r'[0-9a-f]{32}') is not None
            and _ordered(readiness.get('observed_at'), command.get('started_at'))
            and _ordered(command.get('started_at'), mapping(before.get('release')).get('published_at'))
            and _ordered(mapping(before.get('release')).get('published_at'), command.get('finished_at'))
            and _ordered(command.get('finished_at'), before.get('observed_at')))
        ready = (command_bound and reviewed == identity[3] and readiness.get('publication_ready') is True
            and readiness.get('publish_allowed') is True and readiness.get('blockers') == []
            and readiness.get('revision_sha256') == route.get('review_revision_sha256'))
        http_ok = True
        reads = route.get('product_readbacks')
        if not isinstance(reads, list) or len(reads) != 2:
            http_ok = False
        else:
            for index, read in enumerate(reads):
                read = mapping(read)
                try:
                    served = _items(read.get('items'))
                except ValueError:
                    served = None
                product_runtime = token(read.get('runtime_id'), r'[0-9a-f]{32}')
                if (not identity or read.get('release_id') != identity[2] or served != identity[3]
                    or read.get('status') != 200 or read.get('synthetic_fixture') is not False
                    or not timestamp(read.get('observed_at')) or not product_runtime):
                    http_ok = False
                elif not _ordered(mapping(after_restart if index else observation).get('observed_at'), read.get('observed_at')):
                    http_ok = False
        if not browser_ok:
            missing.append('browser_usability_not_proven')
        if not ready:
            missing.append('readiness_and_exact_review_binding_not_proven')
        if not http_ok:
            missing.append('product_http_readback_not_proven')
        route_proven = browser_ok and ready and http_ok
    else:
        missing.extend(['browser_usability_not_supplied', 'readiness_at_publish_not_recorded',
                        'publication_revision_binding_not_recorded', 'product_http_readback_not_supplied'])
    canonical_observed = bool(identity and before.get('consistent') is True
        and not {'release','context'}.intersection(mapping(before.get('errors')))
        and 'release_identity_disagrees' not in conflicts)
    return {'schema': 'publication-report-v1', 'authority': 'diagnostic_projection_not_publication_authority',
        'provenance': 'supplied_observations_not_authenticated_by_report',
        'canonical_release_observed': canonical_observed,
        'release_id': identity[2] if identity else None,
        'snapshot_id': identity[0] if identity else None,
        'source_hash': identity[1] if identity else None,
        'exact_items': identity[3] if identity else [],
        'exact_release_active': active, 'same_release_after_process_restart': restart,
        'end_to_end_proven': bool(active and restart and route_proven and not conflicts and not missing), 'execution_authorized': False,
        'last_proven_boundary': 'same_active_release_after_restart' if restart else 'exact_active_registry_set' if active else 'canonical_release_read' if canonical_observed else 'publication_observation_only',
        'next_check': 'Verify the listed missing evidence and exact identity conflicts; read canonical state before retrying publication.',
        'snapshot_consistency': 'bracketed_independent_reads_not_atomic',
        'input_identity_sha256': digest(str(identity)),
        'missing_evidence': sorted(set(missing)), 'identity_conflicts': sorted(set(conflicts))}


def observe_publication(event, *, snapshot_id, envelope, revision=None, readiness=None,
                        release_id=None, objects=None):
    """Best-effort boundary evidence. Logging failure never changes publication."""
    try:
        import json
        from src.request_diagnostics_v1 import _LOGGER, current_request_id
        if event not in {'publication_checked', 'publication_submitted', 'publication_committed', 'publication_completed'}:
            return
        payload = {'event':event, 'timestamp':datetime.now(timezone.utc).isoformat(),
            'snapshot_id':_identity(snapshot_id), 'source_hash':sha(envelope.get('sha256')),
            'revision_sha256':digest(revision), 'runtime':runtime_identity(),
            'request_id':current_request_id(), 'release_id':_identity(release_id),
            'authority':'non_authoritative_boundary_observation'}
        if readiness is not None:
            payload['readiness'] = {name:readiness.get(name) if type(readiness.get(name)) is bool else None
                                    for name in ('publication_ready','publish_allowed')}
            payload['readiness']['blockers'] = [token(code, r'[a-z][a-z0-9_]{0,95}') or 'unrecognized_reason'
                                               for code in (readiness.get('blockers') or [])[:128]]
        if objects is not None:
            payload['items'] = [{'object_id':_identity(obj.get('object_id')),
                'object_version':_identity(obj.get('object_version')),
                'content_hash':compute_canonical_object_hash(obj)} for obj in objects[:MAX_ITEMS]]
            payload['omitted_item_count'] = max(0,len(objects)-MAX_ITEMS)
        _LOGGER.info('metis_diagnostic %s', json.dumps(payload, separators=(',', ':')))
    except Exception:
        pass


def publication_route_from_events(observation, events, *, request_id=None):
    """Join the four actual locked publication boundaries by exact request ID."""
    result = {'schema':'publication-route-evidence-v1'}
    if not isinstance(events, list) or len(events) > 1000:
        return {**result, 'boundary_evidence_missing':'publication_event_limit_exceeded'}
    release_id = mapping(mapping(observation).get('release')).get('release_id')
    candidates = [mapping(row) for row in events if mapping(row).get('event') in
        {'publication_checked','publication_submitted','publication_committed','publication_completed'}]
    ids = {row.get('request_id') for row in candidates if row.get('release_id') == release_id
           and row.get('event') == 'publication_completed' and token(row.get('request_id'), r'[0-9a-f]{32}')}
    selected = request_id if request_id in ids else next(iter(ids)) if request_id is None and len(ids) == 1 else None
    if selected is None:
        return {**result, 'boundary_evidence_missing':'publication_request_missing_or_ambiguous'}
    rows = [row for row in candidates if row.get('request_id') == selected]
    grouped = {name:[r for r in rows if r.get('event') == name] for name in
        ('publication_checked','publication_submitted','publication_committed','publication_completed')}
    if any(len(value) != 1 for value in grouped.values()):
        return {**result, 'boundary_evidence_missing':'publication_boundaries_missing_or_duplicate'}
    checked, submitted, committed, completed = [grouped[name][0] for name in grouped]
    expected = (observation.get('snapshot_id'), observation.get('source_hash'), checked.get('revision_sha256'))
    if (not sha(expected[2]) or any((row.get('snapshot_id'),row.get('source_hash'),row.get('revision_sha256')) != expected for row in rows)
        or any(row.get('release_id') != release_id for row in (submitted,committed,completed))
        or len({clean_runtime(row.get('runtime'))['runtime_id'] for row in rows}) != 1
        or submitted.get('omitted_item_count') != 0
        or not all(_ordered(a.get('timestamp'), b.get('timestamp')) for a,b in zip((checked,submitted,committed),(submitted,committed,completed)))):
        return {**result, 'boundary_evidence_missing':'publication_boundary_identity_or_order_invalid'}
    return {**result, 'snapshot_id':expected[0], 'source_hash':expected[1], 'review_revision_sha256':expected[2],
        'reviewed_items':submitted.get('items'),
        'readiness':{**mapping(checked.get('readiness')), 'revision_sha256':expected[2], 'observed_at':checked.get('timestamp')},
        'publish_command':{'status':'PASS', 'request_id':selected,'release_id':release_id,
            'snapshot_id':expected[0],'source_hash':expected[1],'revision_sha256':expected[2],
            'started_at':checked.get('timestamp'), 'finished_at':completed.get('timestamp')}}
