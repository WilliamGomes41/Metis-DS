"""Delegated Entra access tokens; existing Metis identity remains authoritative.

No account provisioning, sessions, token storage, or new OAuth issuer here.
"""
from dataclasses import dataclass
import os
from uuid import UUID

import jwt
from fastapi import HTTPException

from src.console_entra_v1 import ROLE_MAP


@dataclass(frozen=True)
class McpConfig:
    resource: str
    tenant: str
    audience: str
    client: str

    @property
    def issuer(self):
        return f"https://login.microsoftonline.com/{self.tenant}/v2.0"

    @property
    def scope(self):
        return f"api://{self.audience}/Metis.Read"


def configuration(identity, origin):
    if os.getenv('METIS_MCP_ENABLED', '0') != '1':
        return None, 'Uitgeschakeld'
    if identity is None or not origin or not origin.startswith('https://'):
        return None, 'Microsoft-aanmelding en een vast HTTPS-adres zijn vereist'
    try:
        audience = str(UUID(os.environ['METIS_MCP_AUDIENCE']))
        client = str(UUID(os.environ['METIS_MCP_CLIENT_ID']))
    except (KeyError, ValueError):
        return None, 'De Entra API-registratie en ChatGPT-client zijn nog niet geconfigureerd'
    return McpConfig(origin.rstrip('/') + '/mcp', identity.config.tenant_id, audience, client), 'Geconfigureerd; verbinding met ChatGPT nog testen'


class McpAuthenticator:
    def __init__(self, config, identity):
        self.config, self.identity = config, identity
        self.keys = jwt.PyJWKClient(
            f'https://login.microsoftonline.com/{config.tenant}/discovery/v2.0/keys',
            cache_jwk_set=True, lifespan=300, timeout=5,
        )

    def __call__(self, token):
        try:
            key = self.keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, key.key, algorithms=['RS256'],
                                audience=self.config.audience, issuer=self.config.issuer,
                                options={'require': ['exp', 'iat', 'nbf', 'oid', 'tid', 'scp', 'azp']})
            if (claims.get('ver') != '2.0' or claims['tid'] != self.config.tenant
                    or claims['azp'] != self.config.client
                    or 'Metis.Read' not in str(claims['scp']).split()):
                raise ValueError('invalid_claims')
            oid = str(UUID(claims['oid']))
            # A token alone never provisions an identity or overrides a local deny.
            raw_roles = claims.get('roles', [])
            if not isinstance(raw_roles, list) or any(not isinstance(r, str) for r in raw_roles):
                raise ValueError('invalid_roles')
            granted_roles = {ROLE_MAP[r] for r in raw_roles if r in ROLE_MAP}
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise HTTPException(401, 'Meld je opnieuw aan bij de Metis-koppeling.') from exc
        try:
            with self.identity.store._connect() as con:
                row = con.execute(
                    'SELECT a.account_id,a.roles FROM workflow.entra_identities e '
                    'JOIN workflow.accounts a ON a.account_id=e.account_id '
                    'WHERE e.tenant_id=%s AND e.object_id=%s AND NOT e.blocked',
                    (self.config.tenant, oid),
                ).fetchone()
        except Exception as exc:
            raise HTTPException(503, 'De toegangscontrole is tijdelijk niet beschikbaar.') from exc
        if not row:
            raise HTTPException(403, 'Geen actieve Metis-accountkoppeling. Meld je eerst aan in Metis of vraag de beheerder.')
        roles = sorted(set(row['roles']) & granted_roles)
        if not roles:
            raise HTTPException(403, 'Je account heeft geen toegang tot deze koppeling.')
        return {'account_id': row['account_id'], 'roles': roles}
