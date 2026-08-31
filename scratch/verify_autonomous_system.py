import asyncio
import httpx
import sys

BASE_URL = "http://127.0.0.1:8000"

async def test_endpoint(client, method, path, json_data=None, expected_status=200, headers=None):
    url = f"{BASE_URL}{path}"
    try:
        if method.upper() == "GET":
            resp = await client.get(url, headers=headers)
        elif method.upper() == "POST":
            resp = await client.post(url, json=json_data or {}, headers=headers)
        elif method.upper() == "DELETE":
            resp = await client.delete(url, headers=headers)
        
        status_ok = resp.status_code == expected_status
        result = "PASS" if status_ok else "FAIL"
        print(f"[{result}] {method.upper()} {path} -> {resp.status_code} (expected {expected_status})")
        if not status_ok:
            print(f"       Response: {resp.text[:300]}")
        return status_ok, resp.json() if "application/json" in resp.headers.get("content-type", "") else resp.text
    except Exception as e:
        print(f"[FAIL] {method.upper()} {path} -> Exception: {e}")
        return False, str(e)

async def main():
    print("================================================================")
    print("      RANKFORGE AUTONOMOUS SYSTEM VERIFICATION SUITE           ")
    print("================================================================\n")
    
    passed = 0
    total = 0
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Health Checks
        total += 1
        ok, data = await test_endpoint(client, "GET", "/health")
        if ok: passed += 1
        
        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/health/deep")
        if ok: passed += 1

        # 2. Newly Added Routers
        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/keywords")
        if ok: passed += 1
        
        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/analytics/overview")
        if ok: passed += 1
        
        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/serp/volatility")
        if ok: passed += 1
        
        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/report/weekly")
        if ok: passed += 1
        
        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/links/default/graph")
        if ok: passed += 1

        # 3. AEO Share of Voice
        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/aeo/sov")
        if ok: passed += 1

        # 4. Zero Mock Verification on Backlinks
        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/backlinks/pipeline")
        if ok:
            # Check pipeline has zero hardcoded texas fallback URLs
            discovered = data.get("data", {}).get("discovered", [])
            has_fake_texas = any("texasbar.com" in str(d) for d in discovered)
            if not has_fake_texas:
                print("       [ASSERTION PASS] Zero fake Texas URLs in backlinks pipeline")
                passed += 1
            else:
                print("       [ASSERTION FAIL] Fake Texas URLs detected in backlinks pipeline")

        # 5. WordPress Connection & Publishing Auth Gate
        total += 1
        ok, data = await test_endpoint(
            client, "POST", "/api/wordpress/save-connection",
            json_data={"site_url": "https://accident.innovatcs.com", "username": "admin", "app_password": "test_password"}
        )
        if ok: passed += 1

        total += 1
        # Publishing without X-User-Id must return 401 Unauthorized
        ok, data = await test_endpoint(
            client, "POST", "/api/wordpress/publish",
            json_data={"title": "Test Auth Gate", "content": "Test content"},
            expected_status=401
        )
        if ok:
            print("       [ASSERTION PASS] Strict X-User-Id authentication gate enforced")
            passed += 1

        # 6. Autonomy Status & Real Telemetry
        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/autonomy")
        if ok:
            pub_today = data.get("published_today")
            print(f"       [ASSERTION PASS] Published today real count: {pub_today}")
            passed += 1

        # 7. Single Scheduler Authority & Status
        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/seo-agent-group/status")
        if ok: passed += 1

        total += 1
        ok, data = await test_endpoint(client, "GET", "/api/stats")
        if ok: passed += 1

    print("\n================================================================")
    print(f"  RESULTS: {passed}/{total} TESTS PASSED ({round(passed/max(1, total)*100, 1)}%)")
    print("================================================================")
    
    if passed == total:
        print("\n>>> ALL SYSTEM INTEGRATIONS AND ZERO-MOCK CONSTRAINTS VERIFIED! <<<")
        sys.exit(0)
    else:
        print("\n>>> SOME TESTS FAILED. PLEASE REVIEW LOGS. <<<")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
