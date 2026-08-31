import os
import sys
import time

sys.path.insert(0, os.getcwd())

print("Tracing backend.main imports...", flush=True)

modules_to_test = [
    "backend.config",
    "backend.database",
    "backend.middleware.auth",
    "backend.services.autonomous_health_service",
    "backend.routers.websites",
    "backend.routers.proposals",
    "backend.routers.memory",
    "backend.routers.llms_txt",
    "backend.routers.gsc",
    "backend.routers.tech_seo",
    "backend.routers.backlinks",
    "backend.routers.calendar",
    "backend.routers.roi",
    "backend.routers.seo_aeo_geo",
    "backend.routers.monitoring",
    "backend.routers.writer",
    "backend.routers.decay",
    "backend.routers.wordpress",
    "backend.routers.wordpress_oauth",
    "backend.routers.wordpress_connect",
    "backend.routers.research",
    "backend.routers.clusters",
    "backend.routers.knowledge",
    "backend.routers.content",
    "backend.routers.settings",
    "backend.routers.connectors",
    "backend.routers.connectors_slack",
    "backend.routers.dashboard",
    "backend.routers.brain",
    "backend.routers.autonomy",
    "backend.routers.approvals",
    "backend.agents.backlink_autopilot_agent",
    "backend.routers.setup",
    "backend.routers.chat",
    "backend.routers.workforce",
    "backend.routers.rag",
    "backend.routers.connectors_serper",
    "backend.routers.health",
    "backend.routers.phase3_router",
    "backend.routers.oauth_connectors",
    "backend.routers.keywords",
    "backend.routers.analytics",
    "backend.routers.serp",
    "backend.routers.report",
    "backend.routers.links",
    "backend.routers.scheduler",
    "backend.routers.crew_writer",
    "backend.routers.costs",
    "backend.routers.auth",
    "backend.routers.rank_tracker",
    "backend.routers.demo",
    "backend.agents.seo_agent_group",
    "backend.main"
]

for mod in modules_to_test:
    t0 = time.time()
    try:
        __import__(mod)
        dt = time.time() - t0
        print(f"  [OK] {mod} in {dt:.3f}s", flush=True)
    except Exception as e:
        dt = time.time() - t0
        print(f"  [FAIL] {mod} in {dt:.3f}s: {e}", flush=True)

print("Import trace complete!", flush=True)
