"""API access settings on the production console and real PostgreSQL authority."""
from tests.semantic_fixture_support import bind_fixture_selections
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api_access_v1 import PostgresApiAccessStore
from tests.test_api_access_lifecycle_v1 import _provision


@pytest.fixture
def access(production_console, production_app, complete_postgres, monkeypatch):
    from src import operations_console_app
    store = PostgresApiAccessStore(complete_postgres)
    calls, issued = [], []
    for name in ('provision_consumer', 'set_application_grant', 'issue_credential'):
        real = getattr(store, name)
        def observe(*args, _real=real, _name=name, **kwargs):
            calls.append({'command':_name, **kwargs})
            result = _real(*args, **kwargs)
            if getattr(result, 'credential', None):
                issued.append(result.credential)
            return result
        monkeypatch.setattr(store, name, observe)
    # Reuse the real authority for instrumentation; no synthetic state or writer.
    monkeypatch.setattr(operations_console_app, 'PostgresApiAccessStore', lambda:store)
    console = production_console(processing_binder=bind_fixture_selections,
                                 environment={'METIS_API_ACCESS_STORE':'postgres'})
    console.create_account(username='publisher.carla', password='publisher-secret', roles=['publisher'])
    console.create_account(username='researcher.rik', password='researcher-secret', roles=['researcher'])
    def client(username='publisher.carla'):
        value = TestClient(production_app(console), base_url='https://testserver')
        password = 'publisher-secret' if username=='publisher.carla' else 'researcher-secret'
        assert value.post('/login', data={'username':username,'password':password}, follow_redirects=False).status_code==303
        return value
    def provision():
        item = _provision(store, name='Hospital fixture')
        calls.clear()
        issued.clear()
        return item
    return SimpleNamespace(store=store, console=console, calls=calls, issued=issued, client=client, provision=provision)


def _provision_payload():
    return {'tenant_name':'Hospital A','tenant_content_scope':'RESOURCE_SET',
        'tenant_document_ids':'doc-a\ndoc-b','tenant_scopes':['retrieve','documents:read'],
        'tenant_requests_per_minute':'200','tenant_max_top_k':'10',
        'application_name':'Hospital A EPD','environment':'PRODUCTION',
        'application_content_scope':'RESOURCE_SET','application_document_ids':'doc-a',
        'application_scopes':['retrieve'],'application_requests_per_minute':'100','application_max_top_k':'5'}


def _grant_payload(version):
    return {'expected_version':str(version),'content_scope':'RESOURCE_SET','document_ids':'doc-b',
            'scopes':['retrieve'],'requests_per_minute':'50','max_top_k':'3'}


def _grant_path(item):
    return f'/settings/api-access/tenants/{item.tenant_id}/applications/{item.application_id}/grant'


def test_settings_exposes_api_access_through_technical_management(access):
    client = access.client()
    response = client.get('/settings')
    assert response.status_code==200
    assert 'href="/settings/technical"' in response.text
    assert 'href="/settings/api-access"' not in response.text
    technical = client.get('/settings/technical')
    assert technical.status_code==200
    assert 'href="/settings/api-access"' in technical.text and 'API-toegang' in technical.text


def test_publisher_can_provision_consumer_and_secret_is_only_in_issue_response(access):
    client = access.client()
    response = client.post('/settings/api-access/provision', data=_provision_payload())
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    [secret] = access.issued
    assert secret in response.text and 'na deze pagina niet opnieuw getoond' in response.text
    assert len(access.calls)==1
    assert access.calls[0]['tenant_document_ids']==['doc-a','doc-b']
    assert access.calls[0]['application_document_ids']==['doc-a']
    listing = client.get('/settings/api-access')
    assert listing.status_code==200 and 'Hospital A EPD' in listing.text and secret not in listing.text
    assert len(access.store.list_consumers())==1


def test_non_publisher_cannot_provision_api_access(access):
    response = access.client('researcher.rik').post('/settings/api-access/provision', data=_provision_payload())
    assert response.status_code==403
    assert access.calls==[] and access.store.list_consumers()==[]


def test_publisher_can_change_application_grant_through_existing_settings_surface(access):
    item = access.provision()
    actor = next(a['account_id'] for a in access.console.list_accounts() if a['username']=='publisher.carla')
    for version in (1,2):
        access.store.set_application_grant(actor_id=actor, tenant_id=item.tenant_id, application_id=item.application_id,
            expected_version=version, content_scope='RESOURCE_SET', document_ids=['doc-a'], scopes=['retrieve'],
            requests_per_minute=101-version,max_top_k=5)
    access.calls.clear()
    response = access.client().post(_grant_path(item),data=_grant_payload(3),follow_redirects=False)
    assert response.status_code==303
    [call] = access.calls
    assert call['command']=='set_application_grant'
    assert call['tenant_id']==item.tenant_id and call['application_id']==item.application_id
    assert call['expected_version']==3 and call['document_ids']==['doc-b']
    assert access.store.list_consumers()[0]['application_policy_version']==4


def test_stale_console_policy_edit_returns_conflict_instead_of_overwriting(access):
    item = access.provision()
    before = access.store.list_consumers()
    response = access.client().post(_grant_path(item),data=_grant_payload(2))
    assert response.status_code==409 and 'intussen gewijzigd' in response.text
    assert access.store.list_consumers()==before


def test_rotated_credential_response_is_one_time_and_non_cacheable(access):
    item = access.provision()
    client = access.client()
    response = client.post(f'/settings/api-access/tenants/{item.tenant_id}/applications/{item.application_id}/credentials')
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    [secret] = access.issued
    assert secret in response.text and secret not in client.get('/settings/api-access').text
    assert access.store.authenticate(secret).application_id==item.application_id


def test_non_publisher_cannot_change_existing_application_grant(access):
    item = access.provision()
    before = access.store.list_consumers()
    response = access.client('researcher.rik').post(_grant_path(item),data=_grant_payload(1))
    assert response.status_code==403 and access.calls==[]
    assert access.store.list_consumers()==before
