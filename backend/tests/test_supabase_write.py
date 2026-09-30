"""Regression tests for the schema-resilient `websites` writer.

A project whose `websites` table lacks an optional column (this repo ships
`wordpress_password_encrypted`, added only by the DDL migrations) made PostgREST
reject the whole INSERT/UPDATE. The API then fell back to the local mirror and
still reported success, so WordPress credentials silently never reached the
database. `write_website` must drop the offending column and persist the real
credentials.
"""

import pytest

from services.supabase_write import write_website


class _FakeQuery:
    def __init__(self, state, op, payload):
        self._state = state
        self._op = op
        self._payload = payload

    def eq(self, col, value):
        self._state["filters"].append((col, value))
        return self

    def execute(self):
        self._state["attempts"].append(self._payload)
        missing = self._state["missing"]
        offending = [k for k in self._payload if k in missing]
        if offending:
            raise Exception(
                f"Could not find the '{offending[0]}' column of 'websites' in the schema cache"
            )
        return type("R", (), {"data": [dict(self._payload)]})()


class _FakeTable:
    def __init__(self, state):
        self._state = state

    def update(self, payload):
        self._state["filters"] = []
        return _FakeQuery(self._state, "update", payload)

    def insert(self, payload):
        self._state["filters"] = []
        return _FakeQuery(self._state, "insert", payload)


class _FakeSupabase:
    def __init__(self, missing=()):
        self._state = {"missing": set(missing), "attempts": [], "filters": []}

    def table(self, _name):
        return _FakeTable(self._state)


def test_unknown_optional_column_is_stripped_and_real_creds_survive():
    supabase = _FakeSupabase(missing={"wordpress_password_encrypted"})
    rows = write_website(
        supabase,
        {
            "id": "w1",
            "cms_url": "https://accident.innovatcs.com",
            "cms_user": "nikhil_d",
            "app_password": "enc:secret",
            "wordpress_password_encrypted": "enc:secret",
        },
    )
    assert rows, "write must succeed once the unknown column is dropped"
    assert rows[0]["app_password"] == "enc:secret"
    assert rows[0]["cms_user"] == "nikhil_d"
    assert "wordpress_password_encrypted" not in rows[0]


def test_all_optional_columns_dropped_in_a_single_retry():
    supabase = _FakeSupabase(
        missing={"wordpress_password_encrypted", "wp_verified", "wp_last_error"}
    )
    rows = write_website(
        supabase,
        {
            "id": "w1",
            "cms_user": "nikhil_d",
            "app_password": "enc:secret",
            "wordpress_password_encrypted": "enc:secret",
            "wp_verified": False,
            "wp_last_error": "Credentials changed",
        },
    )
    assert rows
    # One rejected attempt + one accepted retry, not one round trip per column.
    assert len(supabase._state["attempts"]) == 2


def test_raw_postgres_missing_column_is_understood():
    class _PgError(Exception):
        pass

    supabase = _FakeSupabase()
    # Simulate the raw Postgres phrasing rather than PostgREST's.
    state = supabase._state
    state["missing"] = {"wp_verified"}

    class _Table(_FakeTable):
        def update(self, payload):
            class _Q(_FakeQuery):
                def execute(self):
                    offending = [k for k in payload if k in state["missing"]]
                    if offending:
                        raise _PgError(
                            f'column "{offending[0]}" of relation "websites" does not exist'
                        )
                    return type("R", (), {"data": [dict(payload)]})()
            return _Q(state, "update", payload)

    class _Sb:
        def table(self, _n):
            return _Table(state)

    rows = write_website(_Sb(), {"id": "w1", "wp_verified": False, "cms_user": "real"})
    assert rows and rows[0]["cms_user"] == "real"


def test_non_schema_errors_are_not_swallowed():
    class _Boom:
        def table(self, _name):
            raise RuntimeError("network down")

    with pytest.raises(RuntimeError):
        write_website(_Boom(), {"id": "w1", "domain": "x.example.com"})


def test_update_scopes_to_account_when_given():
    supabase = _FakeSupabase()
    write_website(supabase, {"cms_user": "real"}, "w1", account_id="acct-1")
    assert ("account_id", "acct-1") in supabase._state["filters"]
