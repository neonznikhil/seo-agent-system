"""End-to-end verification of the six portfolio capabilities.

Runs against a live server (no mocks) and asserts on real HTTP responses.
Usage: python tests/test_intelligence_e2e.py [base_url]
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"

# Each run gets its own site id so the suite is fully re-runnable and proves
# isolation: a scheduled ingestion job must never leak state into the next run.
# The tag combines time, pid and a random suffix so two runs started in the same
# second still get distinct ids.
RUN_TAG = f"{int(time.time())}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
WID = f"e2e-test-site-{RUN_TAG}"
RUN_DOMAIN = f"rival-{RUN_TAG}.com"

PASS, FAIL = [], []


def call(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return exc.code, {"raw": raw[:200]}


def check(name, condition, detail=""):
    (PASS if condition else FAIL).append(name)
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


print("=" * 68)
print("BULLET 1: multi-site portfolio view")
print("=" * 68)
st, integ = call("GET", "/api/intelligence/integrations")
check("integrations endpoint responds", st == 200, f"HTTP {st}")
check("unconfigured sources are labelled, not faked",
      all(v["status"] in ("ok", "unconfigured") for v in integ.values()))

st, pf = call("GET", "/api/intelligence/portfolio")
check("portfolio returns per-site rows", st == 200 and "sites" in pf)
check("portfolio declares data availability", "data_available" in pf)
check("portfolio declares storage backend", pf.get("storage") in ("supabase", "local_json"))

print()
print("=" * 68)
print("BULLET 2: prioritized action list (the product)")
print("=" * 68)
# 1,000/mo at position 18 -> target 3 : (0.099 - 0.006) x 1000 = 93 clicks
st, sp = call("GET", "/api/intelligence/actions/%s/score-preview"
              "?search_volume=1000&current_position=18&target_position=3&confidence=0.8" % WID)
check("score preview responds", st == 200, f"HTTP {st}")
expected_clicks = round(1000 * (0.099 - 0.006), 2)
check("traffic projection matches the CTR curve",
      sp.get("projected_clicks_gain") == expected_clicks,
      f"got {sp.get('projected_clicks_gain')} expected {expected_clicks}")
check("projection exposes its arithmetic", "formula" in (sp.get("evidence") or {}))
check("priority = clicks x confidence",
      sp.get("priority_score") == round(expected_clicks * 0.8, 2))

st, bad = call("GET", "/api/intelligence/actions/%s/score-preview"
               "?current_position=18&target_position=3" % WID)
check("missing search volume is refused, not guessed",
      bad.get("scorable") is False and "not scored" in bad.get("reason", ""))

# create actions out of rank order to prove sorting
for title, vol, cur, tgt in [
    ("small_win", 100, 12, 8),
    ("big_win", 9000, 15, 2),
    ("mid_win", 1500, 20, 5),
]:
    call("POST", f"/api/intelligence/actions/{WID}", {
        "title": title, "category": "content", "keyword": title,
        "search_volume": vol, "current_position": cur, "target_position": tgt,
        "effort_minutes": 45, "confidence": 0.7,
    })

st, al = call("GET", f"/api/intelligence/actions/{WID}?limit=10")
check("action list responds", st == 200, f"HTTP {st}")
titles = [a["title"] for a in al.get("actions", [])]
check("actions are ranked by estimated traffic impact",
      titles[:3] == ["big_win", "mid_win", "small_win"], f"order={titles[:3]}")
check("each action carries evidence",
      all(a.get("evidence") for a in al.get("actions", [])))
check("ranks are assigned", [a.get("rank") for a in al.get("actions", [])][:3] == [1, 2, 3])

st, curve = call("GET", "/api/intelligence/ctr-curve")
check("CTR curve is published and auditable", st == 200 and len(curve.get("curve", {})) == 20)

print()
print("=" * 68)
print("BULLET 3: leads and cost per lead by keyword")
print("=" * 68)
call("POST", f"/api/intelligence/leads/effort-cost/{WID}", {
    "cost_date": "2026-09-01", "category": "seo_work",
    "minutes": 600, "hourly_rate": 60, "api_cost": 25,
})
for page, count in [("/pricing", 12), ("/blog/seo-guide", 3)]:
    call("POST", f"/api/intelligence/leads/conversions/{WID}", {
        "conversion_date": "2026-09-10", "landing_page": page,
        "conversion_count": count, "conversion_value": count * 200,
    })

st, cpl = call("POST", f"/api/intelligence/leads/cpl/{WID}", {
    "period_start": "2026-09-01", "period_end": "2026-09-30",
    "hourly_rate": 60,
    "keyword_page_pairs": [
        {"keyword": "seo tool", "landing_page": "/pricing", "clicks": 400,
         "page_sessions": 900, "attributed_sessions": 630},
        {"keyword": "seo guide", "landing_page": "/blog/seo-guide", "clicks": 100,
         "page_sessions": 300, "attributed_sessions": 60},
    ],
})
check("CPL endpoint responds", st == 200, f"HTTP {st}")
results = {r["keyword"]: r for r in cpl.get("results", [])}
check("leads attributed to keywords via landing page",
      results.get("seo tool", {}).get("leads") == 12,
      f"got {results.get('seo tool', {}).get('leads')}")
check("cost per lead computed", results.get("seo tool", {}).get("cost_per_lead") is not None,
      f"cpl={results.get('seo tool', {}).get('cost_per_lead')}")
check("CPL is declared as effort cost, not ad spend",
      cpl.get("methodology", {}).get("cost_basis") == "production_effort")
check("attribution limitation is stated",
      "cannot expose the organic query" in cpl.get("methodology", {}).get("attribution_note", ""))
check("attribution confidence is reported",
      all("attribution_confidence" in r for r in cpl.get("results", [])))

print()
print("=" * 68)
print("BULLET 4: guardrails and rollback")
print("=" * 68)
BEFORE = "Old pricing text. Contact us for a quote."
AFTER = "New pricing text with transparent tiers."

st, pv = call("POST", f"/api/intelligence/guardrails/preview/{WID}", {
    "target_url": "https://example.com/pricing", "change_type": "content_update",
    "before_content": BEFORE, "after_content": AFTER,
})
check("preview created", st == 200 and pv.get("id"), f"HTTP {st}")
check("preview does not apply the change", pv.get("status") == "previewed")
check("unified diff generated", "+New pricing text" in (pv.get("unified_diff") or ""))
check("inverse payload stored for undo", bool(pv.get("inverse_payload")))
check("non-YMYL page not flagged", pv.get("is_ymyl") is False)
cid = pv.get("id")

st, blocked = call("POST", f"/api/intelligence/guardrails/changes/{cid}/apply", {})
check("apply without human approver is refused", st == 403, f"HTTP {st}")

st, ap = call("POST", f"/api/intelligence/guardrails/changes/{cid}/apply",
              {"approver": "alice@agency.com"})
check("apply with approver succeeds", st == 200 and ap.get("ok"))
check("undo is offered after apply", ap.get("undo_available") is True)

st, un = call("POST", f"/api/intelligence/guardrails/changes/{cid}/undo",
              {"actor": "alice@agency.com"})
check("undo succeeds", st == 200 and un.get("ok"))
check("undo restores the pre-change content", un.get("restored_content") == BEFORE,
      f"got {un.get('restored_content')!r}")

st, cl = call("GET", f"/api/intelligence/guardrails/changes/{WID}")
counts = cl.get("counts", {})
check("change log records the full lifecycle",
      counts.get("applied", 0) >= 1 and counts.get("undone", 0) >= 1, str(counts))

st, yc = call("GET", "/api/intelligence/guardrails/classify?url=https://firm.com/legal/drug-injury-claims")
check("YMYL page detected", yc.get("is_ymyl") is True, yc.get("reason", ""))
check("YMYL requires review", yc.get("review_required") is True)

st, ypv = call("POST", f"/api/intelligence/guardrails/preview/{WID}", {
    "target_url": "https://firm.com/legal/mesothelioma-settlement",
    "change_type": "content_update", "before_content": "x", "after_content": "y",
})
yid = ypv.get("id")
check("YMYL preview flagged for review", ypv.get("review_required") is True)

st, one = call("POST", f"/api/intelligence/guardrails/changes/{yid}/apply",
               {"approver": "alice@agency.com"})
check("YMYL apply blocked without second reviewer", st == 403, f"HTTP {st}")

st, same = call("POST", f"/api/intelligence/guardrails/changes/{yid}/apply",
                {"approver": "alice@agency.com", "second_reviewer": "alice@agency.com"})
check("YMYL apply blocked when reviewer == approver", st == 403, f"HTTP {st}")

st, two = call("POST", f"/api/intelligence/guardrails/changes/{yid}/apply",
               {"approver": "alice@agency.com", "second_reviewer": "bob@compliance.com"})
check("YMYL apply allowed with distinct second reviewer", st == 200 and two.get("ok"))

print()
print("=" * 68)
print("BULLET 5: competitor share of voice")
print("=" * 68)
st, sov = call("POST", f"/api/intelligence/competitors/share-of-voice/{WID}", {
    "our_positions": {"seo tool": 3, "seo guide": 7, "rank tracker": 12},
    "competitor_positions": {
        "rival.com": {"seo tool": 1, "seo guide": 2, "rank tracker": 4},
        "other.com": {"seo tool": 5, "seo guide": 9, "rank tracker": 20},
    },
})
check("SOV endpoint responds", st == 200, f"HTTP {st}")
check("SOV is between 0 and 1",
      0 < sov.get("our_share_of_voice", 0) < 1, f"sov={sov.get('our_share_of_voice')}")
check("shares sum to 1", abs(sov.get("sov_sums_to", 0) - 1.0) < 0.001,
      str(sov.get("sov_sums_to")))
check("competitors are ranked by share",
      len(sov.get("competitors", [])) == 2 and
      sov["competitors"][0]["share_of_voice"] >= sov["competitors"][1]["share_of_voice"])
check("method is stated", "CTR-at-position" in sov.get("method", ""))

for dom, kw, pos in [("our-site.com", "seo tool", 8),
                     ("our-site.com", "seo guide", 12),
                     ("rival.com", "seo tool", 1), ("rival.com", "seo guide", 2),
                     ("other.com", "rank tracker", 20)]:
    call("POST", f"/api/intelligence/competitors/rankings/{WID}",
         {"competitor_domain": dom, "keyword": kw, "position": pos,
          "captured_date": "2026-09-20"})

st, gaps = call("GET", f"/api/intelligence/competitors/gaps/{WID}?our_domain=our-site.com")
check("outrank gaps endpoint responds", st == 200)
check("gaps computed from stored rankings", gaps.get("count", 0) >= 1, str(gaps.get("count")))
gap_kws = [(g["keyword"], g["competitor"]) for g in gaps.get("gaps", [])]
check("gaps name the competitor that outranks us",
      ("seo tool", "rival.com") in gap_kws, str(gap_kws))

st, npg = call("POST", f"/api/intelligence/competitors/new-pages/{WID}", {
    "competitor_domain": RUN_DOMAIN,
    "current_urls": [
        {"url": f"https://{RUN_DOMAIN}/blog/fresh-post", "title": "Brand new"},
    ],
})
check("new-page detection responds", st == 200)
check("new pages detected on first pass", npg.get("new_page_count") == 1,
      f"count={npg.get('new_page_count')}")

# Re-scanning the same site must report nothing new, so ingestion is safe to
# run on a schedule without inflating the "their new pages" count.
st, npg2 = call("POST", f"/api/intelligence/competitors/new-pages/{WID}", {
    "competitor_domain": RUN_DOMAIN,
    "current_urls": [
        {"url": f"https://{RUN_DOMAIN}/blog/fresh-post"},
    ],
})
check("re-scan reports no duplicates", npg2.get("new_page_count") == 0,
      f"count={npg2.get('new_page_count')}")

st, npg3 = call("POST", f"/api/intelligence/competitors/new-pages/{WID}", {
    "competitor_domain": RUN_DOMAIN,
    "current_urls": [
        {"url": f"https://{RUN_DOMAIN}/blog/fresh-post"},
        {"url": f"https://{RUN_DOMAIN}/blog/second-post"},
    ],
})
check("only genuinely new pages are reported", npg3.get("new_page_count") == 1,
      f"count={npg3.get('new_page_count')}")

st, hist = call("GET", f"/api/intelligence/competitors/sov-history/{WID}")
check("SOV history stored", hist.get("count", 0) >= 1)

print()
print("=" * 68)
print("BULLET 6: prove the work (28-day lift)")
print("=" * 68)
st, win = call("POST", f"/api/intelligence/measurement/windows/{WID}", {
    "target_url": "https://example.com/pricing",
    "keyword": "seo tool", "baseline_clicks": 100,
    "baseline_position": 14.0,
    "control_urls": ["https://example.com/blog/unrelated"],
    "baseline_control_clicks": 50,
    "window_start": "2026-09-01",
})
check("measurement window opens", st == 200 and win.get("id"), f"HTTP {st}")
wid = win.get("id")

st, rep0 = call("GET", f"/api/intelligence/measurement/windows/{wid}/report")
check("report before data says awaiting_data",
      rep0.get("status") == "awaiting_data", rep0.get("status"))

for off, clicks, ctrl, pos in [(0, 100, 50, 14.0), (7, 115, 51, 11.0),
                                (14, 130, 52, 9.0), (28, 160, 55, 6.0)]:
    call("POST", f"/api/intelligence/measurement/windows/{wid}/snapshot", {
        "day_offset": off, "clicks": clicks, "impressions": clicks * 20,
        "position": pos, "control_clicks": ctrl, "control_impressions": ctrl * 20,
    })

st, rep = call("GET", f"/api/intelligence/measurement/windows/{wid}/report")
lift = rep.get("lift", {})
check("28-day report complete", rep.get("status") == "complete", rep.get("status"))
# raw = 160 - 100 = 60; control moved 55/50 - 1 = 10%, so expected drift on the
# baseline of 50 is 5 clicks. Adjusted lift = 60 - 5 = 55.
check("raw lift computed", lift.get("raw_clicks_lift") == 60, str(lift.get("raw_clicks_lift")))
check("control set adjusts for seasonality",
      lift.get("control_adjustment") == 5.0, str(lift.get("control_adjustment")))
check("adjusted lift discounts control drift",
      lift.get("adjusted_clicks_lift") == 55.0, str(lift.get("adjusted_clicks_lift")))
check("position improvement computed",
      lift.get("position_improvement") == 8.0, str(lift.get("position_improvement")))
check("series has all four snapshots", len(rep.get("series", [])) == 4)
check("control limitation stated", bool(rep.get("control_note")))

st, bychange = call("GET", f"/api/intelligence/measurement/change/{cid}")
check("window auto-linked to the applied change", st == 200, f"HTTP {st}")

print()
print("=" * 68)
print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
print("=" * 68)
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
sys.exit(1 if FAIL else 0)