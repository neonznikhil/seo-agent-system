import sys
sys.path.insert(0, "backend")

# 1. Syntax check all files
import ast
files = [
    "backend/services/citation_injector.py",
    "backend/services/chunking_service.py",
    "backend/services/schema_generator.py",
    "backend/services/ai_visibility_monitor.py",
    "backend/services/llm_content_server.py",
    "backend/services/reddit_service.py",
    "backend/routers/aeo.py",
    "backend/main.py",
    "backend/agents/scheduler.py",
    "backend/agents/crew_blog_writer.py",
]
for f in files:
    ast.parse(open(f, encoding="utf-8").read())
print("1. Syntax check: ALL OK")

# 2. Import check
from services.citation_injector import inject_citations, inject_term_definitions, build_quick_facts_table, inject_quick_facts_table, validate_chunk_lengths, auto_fix_chunk_lengths
from services.schema_generator import generate_article_schema
from services.chunking_service import validate_chunk_lengths as vcl, auto_fix_chunk_lengths as afc
from services.ai_visibility_monitor import check_ai_visibility, run_ai_visibility_check_all_sites
from services.llm_content_server import generate_markdown_version, get_cached_markdown
from services.reddit_service import RedditService
from routers.aeo import router
print("2. Import check: ALL OK")

# 3. Router registration in main.py
with open("backend/main.py", encoding="utf-8") as f:
    main_content = f.read()
assert "from routers.aeo import router as aeo_router" in main_content, "aeo_router import missing"
assert "app.include_router(aeo_router, prefix=\"/api\")" in main_content, "aeo_router registration missing"
print("3. Router registration: OK")

# 4. Scheduler job registration
with open("backend/agents/scheduler.py", encoding="utf-8") as f:
    sched_content = f.read()
assert "job_ai_visibility_monitor" in sched_content, "AI visibility job ID missing"
assert "Every 12h AI Search Visibility Check" in sched_content, "AI visibility job name missing"
assert "run_ai_visibility_check_all_sites" in sched_content, "AI visibility function missing"
print("4. Scheduler job: OK")

# 5. process_blog_output_aeo in crew_blog_writer
with open("backend/agents/crew_blog_writer.py", encoding="utf-8") as f:
    writer_content = f.read()
assert "async def process_blog_output_aeo" in writer_content, "process_blog_output_aeo missing"
assert "inject_citations" in writer_content, "inject_citations call missing"
assert "inject_term_definitions" in writer_content, "inject_term_definitions call missing"
assert "build_quick_facts_table" in writer_content, "build_quick_facts_table call missing"
assert "generate_article_schema" in writer_content, "generate_article_schema call missing"
assert "generate_markdown_version" in writer_content, "generate_markdown_version call missing"
print("5. Blog pipeline integration: OK")

# 6. Database migration SQL
with open("backend/supabase_schema_aeo.sql", encoding="utf-8") as f:
    sql = f.read()
assert "CREATE TABLE IF NOT EXISTS public.ai_visibility" in sql, "ai_visibility table missing"
assert "CREATE TABLE IF NOT EXISTS public.article_markdown_cache" in sql, "article_markdown_cache table missing"
assert "CREATE TABLE IF NOT EXISTS public.reddit_opportunities" in sql, "reddit_opportunities table missing"
print("6. Database migration SQL: OK")

# 7. Frontend page sections
with open("frontend-next/app/aeo/page.tsx", encoding="utf-8") as f:
    page = f.read()
assert "AI Visibility Score" in page, "Section 1 missing"
assert "Keyword" in page and "Tracking" in page, "Section 2 missing"
assert "Reddit" in page, "Section 3 missing"
assert "Semantic" in page, "Section 4 missing"
assert "Schema Health" in page, "Section 5 missing"
assert "/api/aeo/semantic-score" in page, "semantic-score endpoint missing"
assert "/api/aeo/reddit/opportunities" in page, "reddit opportunities endpoint missing"
assert "/api/aeo/reddit/generate-comment" in page, "reddit generate-comment endpoint missing"
print("7. Frontend page sections + API endpoints: OK")

# 8. .env.example
with open(".env.example", encoding="utf-8") as f:
    env = f.read()
assert "REDDIT_CLIENT_ID" in env, "Reddit env var missing"
assert "REDDIT_CLIENT_SECRET" in env, "Reddit secret missing"
assert "REDDIT_USER_AGENT" in env, "Reddit user agent missing"
print("8. .env.example: OK")

print("\n=== ALL CONNECTIVITY CHECKS PASSED ===")
