import copy

import pytest

from src.api_access_v1 import (
    ApiAccessStoreError, NULLABLE_COLUMNS, REQUIRED_CHECKS, REQUIRED_COLUMNS,
    REQUIRED_KEYS, PostgresApiAccessStore,
)
from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig


class FakeConnection:
    def __init__(self, tables, columns, constraints):
        self.tables, self.columns, self.constraints = tables, columns, constraints

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql):
        if "information_schema.tables" in sql:
            self.result = self.tables
        elif "information_schema.columns" in sql:
            self.result = self.columns
        else:
            self.result = self.constraints
        return self

    def fetchall(self):
        return self.result


def schema_rows():
    tables = [{"table_name": table} for table in REQUIRED_COLUMNS]
    columns = [
        {"table_name": table, "column_name": name, "data_type": kind,
         "is_nullable": "YES" if (table, name) in NULLABLE_COLUMNS else "NO",
         "character_maximum_length": 64 if (table, name) == ("credentials", "secret_sha256") else None}
        for table, names in REQUIRED_COLUMNS.items() for name, kind in names.items()
    ]
    constraints = [
        {"table_name": table, "contype": kind, "convalidated": True,
         "confdeltype": "r", "foreign_table": foreign_table,
         "key_columns": list(keys), "foreign_columns": list(foreign_keys or ()),
         "definition": ""}
        for table, kind, keys, foreign_table, foreign_keys in REQUIRED_KEYS
    ]
    constraints.extend(
        {"table_name": table, "contype": "c", "convalidated": True,
         "confdeltype": " ", "foreign_table": None, "key_columns": [],
         "foreign_columns": [], "definition": f"CHECK (({check}))"}
        for table, check in REQUIRED_CHECKS
    )
    return tables, columns, constraints


def verify(rows):
    store = PostgresApiAccessStore(
        PostgresCanonicalConfig(dsn="unused"),
        connection_factory=lambda: FakeConnection(*rows),
    )
    store.verify_schema()


def test_migration_010_shape_passes_read_only_preflight():
    verify(schema_rows())


@pytest.mark.parametrize("damage,expected", [
    ("table", "api_access_schema_missing"),
    ("column", "credentials.secret_sha256:missing"),
    ("type", "credentials.secret_sha256:type_or_nullability"),
    ("nullability", "applications.tenant_id:type_or_nullability"),
    ("primary", "tenants:p:tenant_id"),
    ("foreign", "credentials:f:application_id"),
    ("foreign_delete", "credentials:f:application_id"),
    ("unique", "credentials:u:secret_sha256"),
    ("check", "credentials:check:"),
    ("unvalidated_check", "credentials:check:"),
])
def test_preflight_rejects_authority_schema_drift(damage, expected):
    tables, columns, constraints = copy.deepcopy(schema_rows())
    if damage == "table":
        tables[:] = [row for row in tables if row["table_name"] != "credentials"]
    elif damage == "column":
        columns[:] = [row for row in columns if (row["table_name"], row["column_name"]) != ("credentials", "secret_sha256")]
    elif damage == "type":
        next(row for row in columns if row["column_name"] == "secret_sha256")["character_maximum_length"] = 32
    elif damage == "nullability":
        next(row for row in columns if row["table_name"] == "applications" and row["column_name"] == "tenant_id")["is_nullable"] = "YES"
    elif damage in {"primary", "foreign", "foreign_delete", "unique"}:
        kind, table = {"primary": ("p", "tenants"), "foreign": ("f", "credentials"),
                       "foreign_delete": ("f", "credentials"), "unique": ("u", "credentials")}[damage]
        row = next(row for row in constraints if row["table_name"] == table and row["contype"] == kind)
        if damage == "foreign_delete":
            row["confdeltype"] = "c"
        else:
            constraints.remove(row)
    else:
        row = next(row for row in constraints if row["table_name"] == "credentials" and row["contype"] == "c")
        if damage == "check":
            constraints.remove(row)
        else:
            row["convalidated"] = False
    with pytest.raises(ApiAccessStoreError, match=expected):
        verify((tables, columns, constraints))
