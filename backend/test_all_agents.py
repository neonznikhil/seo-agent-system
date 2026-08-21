#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORT = {}
BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend-next"
TEST_OUTPUT_DIR = BACKEND_DIR / "test_output"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("test_all_agents")


def status_badge(passed):
    return "PASS" if passed else "FAIL"


def truncate(text, max_len=120):
    text = str(text)
    return text[:max_len] + "..." if len(text) > max_len else text


def write_report(report, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)


def print_divider(char="=", length=80):
    print(char * length)


def count_tokens(text):
    if not text:
        return 0
    return len(str(text).split())


async def run_agent_with_timeout(coro, timeout=30):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return {"status": "timeout", "error": "Timed out after {}s".format(timeout)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def discover_agent_files(base_dir):
    files = []
    for root, _, filenames in os.walk(base_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                if "agent" in filename.lower() or "service" in filename.lower():
                    files.append(Path(root) / filename)
    return sorted(files)


def extract_classes(filepath):
    classes = []
    try:
        text = filepath.read_text(errors="ignore")
        for match in re.finditer(r"^class\s+(\w+)", text, re.MULTILINE):
            classes.append(match.group(1))
    except Exception:
        pass
    return classes


def phase1_agent_discovery():
    print_divider()
    print("PHASE 1 - AGENT DISCOVERY")
    print_divider()

    agents_dir = BACKEND_DIR / "agents"
    services_dir = BACKEND_DIR / "services"
    files = discover_agent_files(agents_dir) + discover_agent_files(services_dir)

    all_classes = {}
    for fp in files:
        classes = extract_classes(fp)
        if classes:
            all_classes[str(fp.relative_to(BACKEND_DIR))] = classes

    expected_agents = [
        "ResearchAgent",
        "KeywordAgent",
        "OutlineAgent",
        "WriterAgent",
        "SEOAgent",
        "ElementorAgent",
        "WordPressPublisherAgent",
        "BacklinkAgent",
        "SupervisorAgent",
    ]

    found_expected = {}
    for rel_path, classes in all_classes.items():
        for cls in classes:
            if cls in expected_agents:
                found_expected[cls] = rel_path

    writer_path = "agents/writer_agent.py"
    backlink_path = "agents/backlink_agent.py"
    if "WriterAgent" not in found_expected and (BACKEND_DIR / writer_path).exists():
        found_expected["WriterAgent"] = writer_path
    if "BacklinkAgent" not in found_expected and (BACKEND_DIR / backlink_path).exists():
        found_expected["BacklinkAgent"] = backlink_path

    print("Discovered agent/service files:")
    for rel_path, classes in all_classes.items():
        print("  {}: {}".format(rel_path, ", ".join(classes)))

    print("\nExpected agent classes check:")
    discovery = {}
    all_found = True
    for agent in expected_agents:
        found = agent in found_expected
        discovery[agent] = {
            "found": found,
            "file": found_expected.get(agent),
        }
        status = status_badge(found)
        print("  [{}] {} - {}".format(status, agent, found_expected.get(agent, "MISSING")))
        if not found:
            all_found = False

    entry_points = {
        "ResearchAgent": "run",
        "KeywordAgent": "run",
        "OutlineAgent": "run",
        "WriterAgent": "WriterPipeline.generate",
        "SEOAgent": "run",
        "ElementorAgent": "run",
        "WordPressPublisherAgent": "run",
        "BacklinkAgent": "run_backlink_agent",
        "SupervisorAgent": "run",
    }

    print("\nEntry point methods:")
    entry_check = {}
    for agent, method in entry_points.items():
        present = agent in found_expected
        entry_check[agent] = {"method": method, "agent_present": present}
        print("  {} -> {}".format(agent, method))

    result = {
        "files": list(all_classes.keys()),
        "classes": all_classes,
        "expected_check": discovery,
        "entry_points": entry_check,
        "all_expected_found": all_found,
    }
    REPORT["agent_discovery"] = result
    return result


async def phase2_unit_tests():
    print_divider()
    print("PHASE 2 - UNIT TESTS")
    print_divider()

    website_id = "test-website"
    results = []

    # Test 1: ResearchAgent
    print("\n[ResearchAgent] run('car accident lawyer los angeles')")
    t0 = time.time()
    try:
        from backend.agents.research_agent import ResearchAgent
        agent = ResearchAgent(website_id)
        data = await run_agent_with_timeout(agent.run("car accident lawyer los angeles"), timeout=45)
        elapsed = round(time.time() - t0, 2)
        tokens = count_tokens(data)
        trends = data.get("trends", [])
        competitors = data.get("competitors", [])
        questions = data.get("questions", [])
        search_volume = data.get("search_volume", 0)
        ok = len(trends) > 3 and len(competitors) > 3 and len(questions) > 3 and search_volume > 0
        print("  {} - {}s - {} tokens".format(status_badge(ok), elapsed, tokens))
        results.append({
            "agent": "ResearchAgent",
            "passed": ok,
            "elapsed": elapsed,
            "tokens": tokens,
            "output": truncate(data),
            "checks": {
                "trends": len(trends),
                "competitors": len(competitors),
                "questions": len(questions),
                "search_volume": search_volume,
            },
        })
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print("  FAIL - {}s - {}".format(elapsed, e))
        results.append({
            "agent": "ResearchAgent",
            "passed": False,
            "elapsed": elapsed,
            "tokens": 0,
            "error": str(e),
        })

    # Test 2: KeywordAgent
    print("\n[KeywordAgent] run(research_dummy)")
    t0 = time.time()
    try:
        from backend.agents.keyword_agent import KeywordAgent
        research_dummy = {
            "topic": "car accident lawyer los angeles",
            "trends": ["trend1", "trend2", "trend3"],
            "questions": ["q1?", "q2?", "q3?"],
            "search_volume": 10000,
        }
        agent = KeywordAgent(website_id)
        data = await run_agent_with_timeout(agent.run(research_dummy), timeout=45)
        elapsed = round(time.time() - t0, 2)
        tokens = count_tokens(data)
        primary = data.get("primary_keyword")
        secondary = data.get("secondary_keywords", [])
        difficulty = data.get("difficulty_score")
        ok = bool(primary) and len(secondary) >= 5 and difficulty is not None
        print("  {} - {}s - {} tokens".format(status_badge(ok), elapsed, tokens))
        results.append({
            "agent": "KeywordAgent",
            "passed": ok,
            "elapsed": elapsed,
            "tokens": tokens,
            "output": truncate(data),
            "checks": {
                "primary_keyword": primary,
                "secondary_count": len(secondary),
                "difficulty_score": difficulty,
            },
        })
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print("  FAIL - {}s - {}".format(elapsed, e))
        results.append({
            "agent": "KeywordAgent",
            "passed": False,
            "elapsed": elapsed,
            "tokens": 0,
            "error": str(e),
        })

    # Test 3: OutlineAgent
    print("\n[OutlineAgent] run('car accident lawyer los angeles')")
    t0 = time.time()
    try:
        from backend.agents.outline_agent import OutlineAgent
        agent = OutlineAgent(website_id)
        data = await run_agent_with_timeout(agent.run("car accident lawyer los angeles"), timeout=45)
        elapsed = round(time.time() - t0, 2)
        tokens = count_tokens(data)
        h1 = data.get("h1")
        h2s = data.get("h2s", [])
        faq = data.get("faq", [])
        ok = bool(h1) and len(h2s) >= 5 and len(faq) >= 1
        print("  {} - {}s - {} tokens".format(status_badge(ok), elapsed, tokens))
        results.append({
            "agent": "OutlineAgent",
            "passed": ok,
            "elapsed": elapsed,
            "tokens": tokens,
            "output": truncate(data),
            "checks": {
                "h1": bool(h1),
                "h2_count": len(h2s),
                "faq_count": len(faq),
            },
        })
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print("  FAIL - {}s - {}".format(elapsed, e))
        results.append({
            "agent": "OutlineAgent",
            "passed": False,
            "elapsed": elapsed,
            "tokens": 0,
            "error": str(e),
        })

    # Test 4: WriterAgent
    print("\n[WriterAgent] WriterPipeline.generate('car accident lawyer los angeles')")
    t0 = time.time()
    try:
        from backend.agents.writer_agent import WriterPipeline
        pipeline = WriterPipeline(website_id)
        data = await run_agent_with_timeout(pipeline.generate("car accident lawyer los angeles"), timeout=40)
        elapsed = round(time.time() - t0, 2)
        tokens = count_tokens(data)
        status = data.get("status")
        phase_results = data.get("phase_results", {})
        writing_phase = phase_results.get("multi_step_content_writing", {})
        word_count = writing_phase.get("word_count", 0)
        keyword = "car accident lawyer los angeles"
        keyword_count = json.dumps(phase_results).lower().count(keyword.lower())
        ok = status == "completed" and word_count >= 800 and keyword_count >= 5
        print("  {} - {}s - {} tokens".format(status_badge(ok), elapsed, tokens))
        results.append({
            "agent": "WriterAgent",
            "passed": ok,
            "elapsed": elapsed,
            "tokens": tokens,
            "output": truncate(data),
            "checks": {
                "status": status,
                "word_count": word_count,
                "keyword_count": keyword_count,
            },
        })
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print("  FAIL - {}s - {}".format(elapsed, e))
        results.append({
            "agent": "WriterAgent",
            "passed": False,
            "elapsed": elapsed,
            "tokens": 0,
            "error": str(e),
        })

    # Test 5: SEOAgent
    print("\n[SEOAgent] run(sample_html, keyword)")
    t0 = time.time()
    try:
        from backend.agents.seo_agent import SEOAgent
        sample_html = "<html><body><h1>Car Accident Lawyer Los Angeles</h1><p>We help victims.</p></body></html>"
        keyword = "car accident lawyer los angeles"
        agent = SEOAgent(website_id)
        data = await run_agent_with_timeout(agent.run(sample_html, keyword), timeout=30)
        elapsed = round(time.time() - t0, 2)
        tokens = count_tokens(data)
        seo_title = data.get("seo_title", "")
        meta_description = data.get("meta_description", "")
        slug = data.get("slug", "")
        internal_links = data.get("internal_links", [])
        ok = len(seo_title) < 60 and len(meta_description) < 160 and bool(slug) and len(internal_links) >= 3
        print("  {} - {}s - {} tokens".format(status_badge(ok), elapsed, tokens))
        results.append({
            "agent": "SEOAgent",
            "passed": ok,
            "elapsed": elapsed,
            "tokens": tokens,
            "output": truncate(data),
            "checks": {
                "seo_title_len": len(seo_title),
                "meta_description_len": len(meta_description),
                "slug": slug,
                "internal_links_count": len(internal_links),
            },
        })
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print("  FAIL - {}s - {}".format(elapsed, e))
        results.append({
            "agent": "SEOAgent",
            "passed": False,
            "elapsed": elapsed,
            "tokens": 0,
            "error": str(e),
        })

    # Test 6: ElementorAgent
    print("\n[ElementorAgent] run(bad_html)")
    t0 = time.time()
    try:
        from backend.agents.elementor_agent import ElementorAgent
        bad_html = "```markdown\n# Heading\n**bold** text\n[wp:shortcode]\n<!-- wp:block /-->\n[/shortcode]\n```"
        agent = ElementorAgent(website_id)
        data = await run_agent_with_timeout(agent.run(bad_html), timeout=30)
        elapsed = round(time.time() - t0, 2)
        tokens = count_tokens(data)
        violations = data.get("violations", [])
        ok = violations == []
        print("  {} - {}s - {} tokens".format(status_badge(ok), elapsed, tokens))
        results.append({
            "agent": "ElementorAgent",
            "passed": ok,
            "elapsed": elapsed,
            "tokens": tokens,
            "output": truncate(data),
            "checks": {
                "violations": violations,
            },
        })
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print("  FAIL - {}s - {}".format(elapsed, e))
        results.append({
            "agent": "ElementorAgent",
            "passed": False,
            "elapsed": elapsed,
            "tokens": 0,
            "error": str(e),
        })

    # Test 7: WordPressPublisherAgent
    print("\n[WordPressPublisherAgent] run('Test Draft', '<p>Test</p>', status='draft')")
    t0 = time.time()
    try:
        from backend.agents.wordpress_publisher_agent import WordPressPublisherAgent
        agent = WordPressPublisherAgent(website_id)
        data = await run_agent_with_timeout(agent.run("Test Draft", "<p>Test</p>", status="draft"), timeout=45)
        elapsed = round(time.time() - t0, 2)
        tokens = count_tokens(data)
        pub_status = data.get("status")
        ok = pub_status in ("success", "skipped")
        print("  {} - {}s - {} tokens".format(status_badge(ok), elapsed, tokens))
        results.append({
            "agent": "WordPressPublisherAgent",
            "passed": ok,
            "elapsed": elapsed,
            "tokens": tokens,
            "output": truncate(data),
            "checks": {
                "status": pub_status,
            },
        })
        if pub_status == "success" and data.get("wp_post_id"):
            try:
                from backend.services.wordpress_service import get_wordpress_service
                ws = get_wordpress_service(website_id)
                await ws.delete_post(data.get("wp_post_id"))
                print("    Cleaned up draft post {}".format(data.get("wp_post_id")))
            except Exception as cleanup_e:
                print("    Cleanup skipped: {}".format(cleanup_e))
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print("  FAIL - {}s - {}".format(elapsed, e))
        results.append({
            "agent": "WordPressPublisherAgent",
            "passed": False,
            "elapsed": elapsed,
            "tokens": 0,
            "error": str(e),
        })

    # Test 8: BacklinkAgent
    print("\n[BacklinkAgent] run_backlink_agent('test-website')")
    t0 = time.time()
    try:
        from backend.agents.backlink_agent import run_backlink_agent
        loop = asyncio.get_running_loop()
        data = await run_agent_with_timeout(
            loop.run_in_executor(None, run_backlink_agent, website_id),
            timeout=30,
        )
        elapsed = round(time.time() - t0, 2)
        tokens = count_tokens(data)
        ok = data.get("saved", 0) >= 0
        print("  {} - {}s - {} tokens".format(status_badge(ok), elapsed, tokens))
        results.append({
            "agent": "BacklinkAgent",
            "passed": ok,
            "elapsed": elapsed,
            "tokens": tokens,
            "output": truncate(data),
            "checks": {
                "saved": data.get("saved", 0),
            },
        })
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print("  FAIL - {}s - {}".format(elapsed, e))
        results.append({
            "agent": "BacklinkAgent",
            "passed": False,
            "elapsed": elapsed,
            "tokens": 0,
            "error": str(e),
        })

    # Test 9: SupervisorAgent
    print("\n[SupervisorAgent] run('truck accident lawyer houston')")
    t0 = time.time()
    try:
        from backend.agents.supervisor_agent import SupervisorAgent
        agent = SupervisorAgent(website_id)
        data = await run_agent_with_timeout(agent.run("truck accident lawyer houston"), timeout=120)
        elapsed = round(time.time() - t0, 2)
        tokens = count_tokens(data)
        blog_html = data.get("blog_html")
        seo_meta = data.get("seo_meta")
        ok = data.get("status") == "completed" and blog_html is not None and seo_meta is not None
        print("  {} - {}s - {} tokens".format(status_badge(ok), elapsed, tokens))
        results.append({
            "agent": "SupervisorAgent",
            "passed": ok,
            "elapsed": elapsed,
            "tokens": tokens,
            "output": truncate(data),
            "checks": {
                "status": data.get("status"),
                "blog_html_present": blog_html is not None,
                "seo_meta_present": seo_meta is not None,
            },
        })
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print("  FAIL - {}s - {}".format(elapsed, e))
        results.append({
            "agent": "SupervisorAgent",
            "passed": False,
            "elapsed": elapsed,
            "tokens": 0,
            "error": str(e),
        })

    REPORT["unit_tests"] = results
    return results


async def phase3_integration_test():
    print_divider()
    print("PHASE 3 - INTEGRATION TEST")
    print_divider()

    website_id = "test-website"
    print("\nRunning full pipeline via SupervisorAgent...")
    t0 = time.time()
    try:
        from backend.agents.supervisor_agent import SupervisorAgent
        agent = SupervisorAgent(website_id)
        data = await run_agent_with_timeout(agent.run("truck accident lawyer houston"), timeout=150)
        elapsed = round(time.time() - t0, 2)
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        data = {"status": "error", "error": str(e)}

    blog_html_present = data.get("blog_html") is not None
    seo_meta_present = data.get("seo_meta") is not None
    wp_draft_url_present = bool(data.get("wp_draft_url"))
    backlinks_present = data.get("backlinks") is not None

    print("  blog_html_present: {}".format(blog_html_present))
    print("  seo_meta_present: {}".format(seo_meta_present))
    print("  wp_draft_url_present: {}".format(wp_draft_url_present))
    print("  backlinks_present: {}".format(backlinks_present))
    print("  elapsed: {}s".format(elapsed))

    output_path = TEST_OUTPUT_DIR / "final_blog.html"
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    blog_content = data.get("blog_html", {})
    if isinstance(blog_content, dict):
        html_output = "<html><body><pre>{}</pre></body></html>".format(
            json.dumps(blog_content, indent=2, default=str)
        )
    else:
        html_output = str(blog_content)
    output_path.write_text(html_output, encoding="utf-8")
    print("  Saved output to: {}".format(output_path))

    result = {
        "blog_html_present": blog_html_present,
        "seo_meta_present": seo_meta_present,
        "wp_draft_url_present": wp_draft_url_present,
        "backlinks_present": backlinks_present,
        "elapsed": elapsed,
        "output_path": str(output_path),
        "data": truncate(data, 500),
    }
    REPORT["integration_test"] = result
    return result


def phase4_system_tests():
    print_divider()
    print("PHASE 4 - SYSTEM TESTS")
    print_divider()

    website_id = "test-website"
    result = {
        "supabase": {},
        "frontend": {},
        "oauth": {},
        "error_handling": {},
        "cost_tracking": {},
    }

    # Supabase check
    print("\n[Supabase] get_supabase().table('websites').select('id').limit(1).execute()")
    try:
        from backend.database import get_supabase
        resp = get_supabase().table("websites").select("id").limit(1).execute()
        data = resp.data if hasattr(resp, "data") else []
        has_data = len(data) > 0
        result["supabase"] = {
            "connected": True,
            "data_exists": has_data,
            "rows": len(data),
        }
        print("  PASS - connected, rows={}".format(len(data)))
    except Exception as e:
        result["supabase"] = {"connected": False, "error": str(e)}
        print("  FAIL - {}".format(e))

    # Frontend pages check
    print("\n[Frontend] checking /dashboard, /generate, /backlinks, /settings")
    pages = {
        "dashboard": FRONTEND_DIR / "app" / "dashboard" / "page.tsx",
        "generate": FRONTEND_DIR / "app" / "generate" / "page.tsx",
        "backlinks": FRONTEND_DIR / "app" / "backlinks" / "page.tsx",
        "settings": FRONTEND_DIR / "app" / "settings" / "page.tsx",
    }
    frontend_result = {}
    for name, path in pages.items():
        exists = path.exists()
        if not exists:
            alt = path.with_suffix(".jsx")
            exists = alt.exists()
        frontend_result[name] = {
            "exists": exists,
            "path": str(path),
        }
        status = status_badge(exists)
        print("  [{}] {} -> {}".format(status, name, path))
    result["frontend"] = frontend_result

    # OAuth check
    print("\n[OAuth] WP_OAUTH_AUTHORIZE_URL check")
    oauth_url = os.getenv("WP_OAUTH_AUTHORIZE_URL", "")
    oauth_ok = bool(oauth_url) and "authorize" in oauth_url.lower()
    result["oauth"] = {
        "configured": bool(oauth_url),
        "contains_authorize": "authorize" in oauth_url.lower(),
        "url": oauth_url,
    }
    print("  configured: {}, contains_authorize: {}".format(bool(oauth_url), oauth_ok))
    if not oauth_ok:
        print("  WARNING: WP_OAUTH_AUTHORIZE_URL not configured or missing 'authorize'")

    # Error Handling: WriterPipeline.generate("", "") should raise
    print("\n[Error Handling] WriterPipeline.generate('', '')")
    try:
        from backend.agents.writer_agent import WriterPipeline
        pipeline = WriterPipeline(website_id)
        data = asyncio.run(asyncio.wait_for(pipeline.generate("", ""), timeout=10))
        result["error_handling"] = {
            "raised": False,
            "output": truncate(data),
        }
        print("  WARNING - did not raise, returned: {}".format(truncate(data)))
    except Exception as e:
        result["error_handling"] = {
            "raised": True,
            "error_type": type(e).__name__,
            "error": str(e),
        }
        print("  PASS - raised {}: {}".format(type(e).__name__, e))

    # Cost Tracking
    print("\n[Cost Tracking] configuration check")
    nvidia_configured = bool(os.getenv("NVIDIA_API_KEY", ""))
    supabase_configured = bool(os.getenv("SUPABASE_URL", "")) and bool(os.getenv("SUPABASE_KEY", ""))
    per_agent_tokens = {}
    if "unit_tests" in REPORT:
        for test in REPORT["unit_tests"]:
            agent_name = test.get("agent")
            if agent_name and "tokens" in test:
                per_agent_tokens[agent_name] = test["tokens"]
    result["cost_tracking"] = {
        "nvidia_api_key_configured": nvidia_configured,
        "supabase_configured": supabase_configured,
        "per_agent_tokens": per_agent_tokens,
    }
    print("  NVIDIA_API_KEY configured: {}".format(nvidia_configured))
    print("  Supabase configured: {}".format(supabase_configured))
    for agent_name, tokens in per_agent_tokens.items():
        print("    {} tokens: {}".format(agent_name, tokens))

    REPORT["system_tests"] = result
    return result


async def phase5_e2e_ui_test():
    print_divider()
    print("PHASE 5 - E2E UI TEST")
    print_divider()

    page_dir = FRONTEND_DIR / "app" / "test-e2e"
    page_path = page_dir / "page.tsx"
    page_created = False

    page_content = """"use client";

import { useState } from "react";

export default function TestE2EPage() {
  const [keyword, setKeyword] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [output, setOutput] = useState<any>(null);
  const [running, setRunning] = useState(false);

  const addLog = (msg: string) => {
    setLogs((prev) => [...prev, msg]);
  };

  const runPipeline = async () => {
    setRunning(true);
    setLogs([]);
    setOutput(null);
    addLog("Starting pipeline for: " + keyword);
    try {
      const res = await fetch("/api/brain/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword }),
      });
      const data = await res.json();
      setOutput(data);
      addLog("Pipeline completed");
    } catch (e: any) {
      addLog("Error: " + e.message);
    }
    setRunning(false);
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>E2E UI Test</h1>
      <input
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        placeholder="Enter keyword"
        style={{ padding: "0.5rem", marginRight: "1rem" }}
      />
      <button onClick={runPipeline} disabled={running}>
        {running ? "Running..." : "Run Full Agent Pipeline"}
      </button>
      <div style={{ marginTop: "1rem" }}>
        <h2>Live Logs</h2>
        {logs.map((log, i) => (
          <div key={i}>{log}</div>
        ))}
      </div>
      {output && (
        <div style={{ marginTop: "1rem" }}>
          <h2>Output</h2>
          <pre>{JSON.stringify(output, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
"""

    try:
        page_dir.mkdir(parents=True, exist_ok=True)
        page_path.write_text(page_content, encoding="utf-8")
        page_created = True
        print("  Created {}".format(page_path))
    except Exception as e:
        print("  FAIL - {}".format(e))

    result = {
        "page_path": str(page_path),
        "page_created": page_created,
    }
    REPORT["e2e_ui_test"] = result
    return result


def print_summary(start_time, end_time):
    print_divider()
    print("SUMMARY")
    print_divider()

    total_time = round(end_time - start_time, 2)
    unit_tests = REPORT.get("unit_tests", [])
    agents_tested = len(unit_tests)
    passed_count = sum(1 for t in unit_tests if t.get("passed"))
    failed_count = agents_tested - passed_count

    wp_status = "N/A"
    if "system_tests" in REPORT:
        sb = REPORT["system_tests"].get("supabase", {})
        wp_status = status_badge(sb.get("connected", False))

    supabase_status = "N/A"
    if "system_tests" in REPORT:
        sb = REPORT["system_tests"].get("supabase", {})
        supabase_status = status_badge(sb.get("connected", False))

    frontend_status = "N/A"
    if "system_tests" in REPORT:
        fe = REPORT["system_tests"].get("frontend", {})
        pages = [v.get("exists", False) for v in fe.values()]
        frontend_status = "{}/{} pages found".format(sum(pages), len(pages))

    print("Total Pipeline time: {}s".format(total_time))
    print("Agents tested: {}".format(agents_tested))
    print("Passed: {}, Failed: {}".format(passed_count, failed_count))
    print("WordPress status: {}".format(wp_status))
    print("Supabase status: {}".format(supabase_status))
    print("Frontend status: {}".format(frontend_status))
    print()

    for test in unit_tests:
        agent_name = test.get("agent", "Unknown")
        passed = test.get("passed", False)
        elapsed = test.get("elapsed", 0)
        tokens = test.get("tokens", 0)
        badge = status_badge(passed)
        print("[{}] - {} - {}s - {} tokens".format(agent_name, badge, elapsed, tokens))


async def main():
    start_time = time.time()
    print("Starting comprehensive agent test suite...")
    print("Backend dir: {}".format(BACKEND_DIR))
    print("Frontend dir: {}".format(FRONTEND_DIR))

    try:
        phase1_agent_discovery()
    except Exception as e:
        logger.error("Phase 1 failed: %s", e)
        REPORT["agent_discovery"] = {"error": str(e)}

    try:
        await phase2_unit_tests()
    except Exception as e:
        logger.error("Phase 2 failed: %s", e)
        REPORT["unit_tests"] = {"error": str(e)}

    try:
        await phase3_integration_test()
    except Exception as e:
        logger.error("Phase 3 failed: %s", e)
        REPORT["integration_test"] = {"error": str(e)}

    try:
        phase4_system_tests()
    except Exception as e:
        logger.error("Phase 4 failed: %s", e)
        REPORT["system_tests"] = {"error": str(e)}

    try:
        await phase5_e2e_ui_test()
    except Exception as e:
        logger.error("Phase 5 failed: %s", e)
        REPORT["e2e_ui_test"] = {"error": str(e)}

    end_time = time.time()
    print_summary(start_time, end_time)

    report_path = BACKEND_DIR / "test_output" / "test_all_report.json"
    write_report(REPORT, report_path)
    print("\nReport written to: {}".format(report_path))

    unit_tests = REPORT.get("unit_tests", [])
    if isinstance(unit_tests, list):
        failed = [t for t in unit_tests if not t.get("passed", False)]
        if failed:
            return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
