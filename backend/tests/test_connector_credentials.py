"""Tests for connector username/placeholder resolution."""

from services.connector_credentials import (
    is_placeholder_wp_username,
    resolve_wp_username,
)


def test_blank_and_known_placeholders_are_rejected():
    for value in ["", "   ", None, "admin", "your-username", "test"]:
        assert is_placeholder_wp_username(value) is True


def test_a_real_person_username_is_not_blocked():
    # Regression: the repo once listed its author's own username as a
    # placeholder sentinel, which rejected that owner's genuine credentials.
    assert is_placeholder_wp_username("nikhil_d") is False
    assert is_placeholder_wp_username("Nikhil_D") is False


def test_spelling_variants_of_placeholder_are_rejected():
    # Separator/case variants must not slip past the sentinel check.
    for value in [
        "your_username",
        "yourusername",
        "YourUsername",
        "your-name",
        "Your Name",
        "yourname",
        "your_user",
        "YourUser",
        "wp_username",
        "wp-user",
        "testuser",
        "exampleuser",
    ]:
        assert is_placeholder_wp_username(value) is True, value


def test_real_username_is_accepted():
    assert is_placeholder_wp_username("editor_jane") is False
    assert is_placeholder_wp_username("Nikhil") is False  # not the sentinel
    # A genuine name that merely contains a placeholder substring is allowed.
    assert is_placeholder_wp_username("administrator_jane") is False
    assert is_placeholder_wp_username("mytest") is False


def test_resolve_prefers_first_real_candidate():
    assert resolve_wp_username("admin", "real_user") == "real_user"
    assert resolve_wp_username("", "second_real") == "second_real"
    assert resolve_wp_username(None, None) == ""


def test_resolve_never_invents_a_fallback():
    # No candidates -> empty string, NOT a hardcoded developer account.
    assert resolve_wp_username() == ""
    assert resolve_wp_username("admin") == ""


class _FakeTable:
    def __init__(self, calls, existing_ids):
        self._calls = calls
        self._existing = existing_ids
        self._id = None

    def update(self, payload):
        self._calls.append(("update", payload))
        return self

    def insert(self, payload):
        self._calls.append(("insert", payload))
        self._existing.add(payload.get("id"))
        return self

    def eq(self, _col, value):
        self._id = value
        return self

    def execute(self):
        op, payload = self._calls[-1]
        # First write carries the verification columns, which a deployment
        # without the wp_verified* migration rejects wholesale.
        if op == "update" and any(k.startswith("wp_") for k in payload):
            raise Exception('column "wp_verified" of relation "websites" does not exist')
        if op == "update":
            # PostgREST: an UPDATE matching no row is still HTTP 200, empty body.
            return type("R", (), {"data": [{"id": self._id}] if self._id in self._existing else []})()
        return type("R", (), {"data": [payload]})()


class _FakeSupabase:
    def __init__(self, existing_ids=("w1",)):
        self.calls = []
        self.existing = set(existing_ids)

    def table(self, _name):
        return _FakeTable(self.calls, self.existing)


def test_missing_verification_columns_do_not_block_credential_save():
    from routers.wordpress import _update_website_credentials

    supabase = _FakeSupabase()
    ok = _update_website_credentials(supabase, "w1", {
        "cms_url": "https://accident.innovatcs.com",
        "cms_user": "nikhil_d",
        "app_password": "enc:secret",
        "wp_verified": False,
        "wp_last_error": "Credentials changed",
    }, domain="accident.innovatcs.com")

    assert ok is True
    updates = [p for op, p in supabase.calls if op == "update"]
    assert len(updates) == 2, "must retry after the schema rejection"
    retried = updates[1]
    assert not any(k.startswith("wp_") for k in retried), "retry must drop wp_* columns"
    # The real credentials must survive the fallback — that is the whole point.
    assert retried["cms_url"] == "https://accident.innovatcs.com"
    assert retried["cms_user"] == "nikhil_d"
    assert retried["app_password"] == "enc:secret"


def test_unknown_website_id_is_inserted_not_reported_saved():
    """An UPDATE that matches no row must insert instead of faking success."""
    from routers.wordpress import _update_website_credentials

    supabase = _FakeSupabase(existing_ids=())  # no such website row yet
    ok = _update_website_credentials(supabase, "w-new", {
        "cms_url": "https://new.example.com",
        "cms_user": "real_user",
        "app_password": "enc:secret",
        "wp_verified": False,
    }, domain="new.example.com")

    assert ok is True
    inserts = [p for op, p in supabase.calls if op == "insert"]
    assert len(inserts) == 1, "a non-matching update must fall back to an insert"
    assert inserts[0]["id"] == "w-new"
    assert inserts[0]["domain"] == "new.example.com"
    assert inserts[0]["app_password"] == "enc:secret"
