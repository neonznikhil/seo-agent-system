"""Regression tests for the local store's concurrency and merge behaviour.

Connecting a website fans out into several concurrent writers (knowledge crawl,
onboarding pipeline, WordPress verification) that all persist to the same JSON
file. The original read-modify-write had two defects:

  * it was not serialised, so two writers interleaved and the later save wiped
    the earlier one's changes (a lost update) — a freshly verified flag could
    silently disappear, making a connected site report "not connected";
  * the status endpoint merged Supabase over the local store with setdefault,
    so a null Supabase value masked a real local value.
"""

import threading

import pytest

from services import local_store


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(local_store, "DATA_DIR", str(tmp_path))
    return tmp_path


def test_concurrent_website_writes_do_not_lose_updates(store_dir):
    """Concurrent saves to distinct sites must all survive.

    Without the lock, each thread loads the whole file, mutates its own copy and
    writes it back; interleaving drops all but the last writer's site.
    """
    n = 40
    barrier = threading.Barrier(n)

    def worker(i):
        barrier.wait()
        local_store.save_local_website({"id": f"site-{i}", "domain": f"site-{i}.com"})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ids = {s["id"] for s in local_store.list_local_websites()}
    assert ids == {f"site-{i}" for i in range(n)}, "concurrent writes lost updates"


def test_verification_write_races_with_crawl_without_losing_verified_flag(store_dir):
    """A verification write must not be clobbered by a concurrent crawl write.

    This mirrors the connect flow: the crawl persists url/status while the
    verification persists wp_verified. Both must end up in the final record.
    """
    local_store.save_local_website({"id": "w1", "domain": "example.com"})
    barrier = threading.Barrier(2)

    def crawl():
        barrier.wait()
        for _ in range(50):
            local_store.save_local_website({"id": "w1", "status": "crawling", "url": "https://example.com"})

    def verify():
        barrier.wait()
        local_store.save_local_website({"id": "w1", "wp_verified": True, "wp_verified_role": "administrator"})

    t1 = threading.Thread(target=crawl)
    t2 = threading.Thread(target=verify)
    t1.start(); t2.start(); t1.join(); t2.join()

    record = local_store.get_local_website("w1")
    assert record.get("wp_verified") is True, "verification flag was lost to a concurrent write"
    assert record.get("wp_verified_role") == "administrator"


def test_save_is_atomic_no_partial_file(store_dir):
    """A reader must never observe a truncated/partial JSON document."""
    local_store.save_local_website({"id": "w1", "domain": "a.com"})
    errors = []
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            try:
                local_store.list_local_websites()
            except Exception as e:  # pragma: no cover - failure path
                errors.append(e)

    def writer():
        for i in range(200):
            local_store.save_local_website({"id": "w1", "domain": "a.com", "counter": i})

    r = threading.Thread(target=reader)
    r.start()
    writer()
    stop.set()
    r.join()
    assert not errors, f"reader saw a corrupt file: {errors[:3]}"
