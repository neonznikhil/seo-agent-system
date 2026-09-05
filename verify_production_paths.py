"""Final production-path verification for AEO/GEO modules."""
import sys
sys.path.insert(0, "backend")

# 1. Verify AEO pipeline wiring in crew_blog_writer
with open("backend/agents/crew_blog_writer.py", encoding="utf-8") as f:
    content = f.read()

checks = [
    ("base = await process_blog_output(", "AEO pipeline wired to base pipeline"),
    ("inject_citations(step7, target_keyword, website_id)", "Citations in AEO pipeline"),
    ("inject_term_definitions(step7a, \"legal\")", "Definitions in AEO pipeline"),
    ("build_quick_facts_table(outline or {}", "Quick facts in AEO pipeline"),
    ("generate_article_schema(", "Schema generator in AEO pipeline"),
    ("generate_markdown_version(", "Markdown version in AEO pipeline"),
    ("final_html = await process_blog_output_aeo(", "generate_blog_autonomous uses AEO"),
]

for pattern, desc in checks:
    assert pattern in content, f"FAIL: {desc}"
    print(f"OK: {desc}")

# 2. Verify scheduler uses AEO writer
with open("backend/agents/scheduler.py", encoding="utf-8") as f:
    sched = f.read()
assert "result = await run_crew_blog_writer_with_retry(" in sched, "Scheduler not using AEO writer"
print("OK: Scheduler uses AEO writer")

# 3. Verify all AEO services use real APIs
services_checks = [
    ("backend/services/citation_injector.py", "serper_search_safe", "Real Serper for citations"),
    ("backend/services/schema_generator.py", "call_nim_llm", "Real NIM for entities"),
    ("backend/services/ai_visibility_monitor.py", "serper_search_safe", "Real Serper for visibility"),
    ("backend/services/ai_visibility_monitor.py", "ai_visibility", "Real DB table for visibility"),
    ("backend/services/llm_content_server.py", "article_markdown_cache", "Real DB table for markdown"),
    ("backend/services/reddit_service.py", "serper_search_safe", "Real Serper for Reddit"),
    ("backend/services/reddit_service.py", "call_nim_llm", "Real NIM for Reddit comments"),
]

for filepath, pattern, desc in services_checks:
    with open(filepath, encoding="utf-8") as f:
        code = f.read()
    assert pattern in code, f"FAIL: {desc} in {filepath}"
    print(f"OK: {desc}")

# 4. Verify no mock/test data in AEO files
aeo_files = [
    "backend/services/citation_injector.py",
    "backend/services/schema_generator.py",
    "backend/services/chunking_service.py",
    "backend/services/ai_visibility_monitor.py",
    "backend/services/llm_content_server.py",
    "backend/services/reddit_service.py",
    "backend/routers/aeo.py",
]

mock_indicators = ["mock.Mock", "MagicMock", "test_data", "fake_data", "dummy_data", "TESTING = True"]
for filepath in aeo_files:
    with open(filepath, encoding="utf-8") as f:
        code = f.read()
    for indicator in mock_indicators:
        assert indicator not in code, f"FAIL: Found mock indicator '{indicator}' in {filepath}"
    print(f"OK: No mock data in {filepath}")

print("\n=== ALL PRODUCTION PATH CHECKS PASSED ===")
