"""PostgreSQL authority for operational view checks, never document state."""
from __future__ import annotations

import hashlib
import json
import secrets
from uuid import uuid4

from psycopg.rows import dict_row


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class ViewCheckConflict(ValueError):
    pass


class ViewCheckStore:
    def __init__(self, connect):
        self.connect = connect

    def verify(self):
        with self.connect() as con:
            con.execute('SELECT id, request_aliases, capability_hash, events FROM workflow.view_checks LIMIT 0')

    @staticmethod
    def public(row):
        if row is None:
            return None
        return {key: value for key, value in dict(row).items()
                if key not in {'capability_hash', 'lease_until'}}

    def register(self, owner, snapshot, request_key, context):
        encoded = json.dumps(context, sort_keys=True)
        fingerprint = digest(encoded)
        with self.connect() as con, con.cursor(row_factory=dict_row) as cur:
            # Also serializes active-scope deduplication across different keys.
            cur.execute('SELECT pg_advisory_xact_lock(807019)')
            cur.execute('SELECT * FROM workflow.view_checks WHERE owner_account_id=%s '
                        'AND (request_key=%s OR request_aliases ? %s)', (owner, request_key, request_key))
            previous = cur.fetchone()
            if previous:
                if previous['snapshot_id'] != snapshot or previous['context_hash'] != fingerprint:
                    raise ViewCheckConflict('request_key_conflict')
                return self.public(previous)
            cur.execute("SELECT * FROM workflow.view_checks WHERE owner_account_id=%s AND snapshot_id=%s "
                        "AND context_hash=%s AND state IN ('queued','running')", (owner, snapshot, fingerprint))
            active = cur.fetchone()
            if active:
                cur.execute('UPDATE workflow.view_checks SET request_aliases=request_aliases||'
                            'jsonb_build_array(%s::text) WHERE id=%s', (request_key, active['id']))
                return self.public(active)
            identifier = uuid4().hex
            cur.execute("INSERT INTO workflow.view_checks(id,owner_account_id,snapshot_id,request_key,context,"
                        "context_hash,state,events) VALUES(%s,%s,%s,%s,%s::jsonb,%s,'queued',"
                        "jsonb_build_array(jsonb_build_object('event','requested','at',CURRENT_TIMESTAMP))) RETURNING *",
                        (identifier, owner, snapshot, request_key, encoded, fingerprint))
            return self.public(cur.fetchone())

    def claim(self):
        capability = secrets.token_urlsafe(32)
        with self.connect() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT pg_advisory_xact_lock(807019)')
            cur.execute("UPDATE workflow.view_checks SET state=CASE WHEN attempt<2 THEN 'queued' ELSE 'failed' END,"
                        "capability_hash=NULL,lease_until=NULL,updated_at=CURRENT_TIMESTAMP,"
                        "result=jsonb_build_object('reason','worker_interrupted','checks','[]'::jsonb),"
                        "events=events||jsonb_build_array(jsonb_build_object('event','lease_expired','at',CURRENT_TIMESTAMP)) "
                        "WHERE state='running' AND lease_until<=CURRENT_TIMESTAMP")
            # One browser globally; no unbounded load from multiple web workers.
            cur.execute("SELECT 1 FROM workflow.view_checks WHERE state='running' LIMIT 1")
            if cur.fetchone():
                return None
            cur.execute("SELECT id FROM workflow.view_checks WHERE state='queued' ORDER BY created_at LIMIT 1 FOR UPDATE")
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("UPDATE workflow.view_checks SET state='running',attempt=attempt+1,capability_hash=%s,"
                        "lease_until=CURRENT_TIMESTAMP+INTERVAL '60 seconds',updated_at=CURRENT_TIMESTAMP,"
                        "events=events||jsonb_build_array(jsonb_build_object('event','claimed','at',CURRENT_TIMESTAMP)) "
                        "WHERE id=%s RETURNING *", (digest(capability), row['id']))
            return dict(cur.fetchone()), capability

    def capability(self, token):
        if not isinstance(token, str) or not 40 <= len(token) <= 64:
            return None
        with self.connect() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM workflow.view_checks WHERE capability_hash=%s AND state='running' "
                        "AND lease_until>CURRENT_TIMESTAMP", (digest(token),))
            return cur.fetchone()

    def finish(self, identifier, attempt, token, result, *, failed=False):
        with self.connect() as con:
            cursor = con.execute("UPDATE workflow.view_checks SET state=%s,result=%s::jsonb,capability_hash=NULL,"
                                 "lease_until=NULL,updated_at=CURRENT_TIMESTAMP,events=events||"
                                 "jsonb_build_array(jsonb_build_object('event',%s::text,'at',CURRENT_TIMESTAMP)) "
                                 "WHERE id=%s AND attempt=%s AND capability_hash=%s AND state='running' "
                                 "AND lease_until>CURRENT_TIMESTAMP",
                                 ('failed' if failed else 'completed', json.dumps(result),
                                  'failed' if failed else 'completed', identifier, attempt, digest(token)))
            return cursor.rowcount == 1

    def get(self, identifier):
        with self.connect() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT * FROM workflow.view_checks WHERE id=%s', (identifier,))
            return self.public(cur.fetchone())

    def history(self, snapshot):
        with self.connect() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT * FROM workflow.view_checks WHERE snapshot_id=%s ORDER BY created_at DESC LIMIT 20',
                        (snapshot,))
            return [self.public(row) for row in cur.fetchall()]

    def cancel(self, identifier, owner):
        with self.connect() as con:
            return con.execute("UPDATE workflow.view_checks SET state='cancelled',capability_hash=NULL,lease_until=NULL,"
                               "updated_at=CURRENT_TIMESTAMP,events=events||jsonb_build_array("
                               "jsonb_build_object('event','cancelled','at',CURRENT_TIMESTAMP)) "
                               "WHERE id=%s AND owner_account_id=%s AND state IN ('queued','running')",
                               (identifier, owner)).rowcount == 1
