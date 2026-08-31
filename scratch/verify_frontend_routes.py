import urllib.request

routes = [
    "/",
    "/websites",
    "/writer",
    "/content",
    "/approvals",
    "/backlinks",
    "/tech-seo",
    "/monitoring",
    "/calendar",
    "/brain",
    "/knowledge",
    "/memory",
    "/llms-txt",
    "/connectors",
    "/wordpress",
    "/roi",
    "/workforce",
    "/aeo",
]

print("=" * 60)
print("RANKFORGE CORE PAGES LIVE ROUTE VERIFICATION")
print("=" * 60)

all_passed = True
for r in routes:
    url = f"http://localhost:3000{r}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RankForgeTest/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = resp.getcode()
            print(f"[PASS] {r:24} -> HTTP {code} OK")
    except Exception as e:
        print(f"[FAIL] {r:24} -> FAILED ({e})")
        all_passed = False

print("=" * 60)
if all_passed:
    print("ALL 18 CORE FUNCTIONAL PAGES RESPONDING WITH HTTP 200 OK")
else:
    print("SOME ROUTES ENCOUNTERED ERRORS")
print("=" * 60)
