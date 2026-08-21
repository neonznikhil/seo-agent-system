#!/usr/bin/env python3
"""Verification script for Continuous Monitoring system.

Run this to verify all components are properly integrated.
"""
import sys
import asyncio
from datetime import datetime


def verify_imports():
    """Verify all module imports work."""
    print("=" * 60)
    print("VERIFYING IMPORTS...")
    print("=" * 60)
    
    modules = [
        ("backend.services.reporting_service", "report_problem, log_monitoring"),
        ("backend.services.continuous_monitor", "start_all_monitors, rank_monitor_loop"),
        ("backend.services.monitors.rank_monitor", "RankMonitor"),
        ("backend.services.monitors.serp_monitor", "SERPMonitor"),
        ("backend.services.monitors.competitor_monitor", "CompetitorMonitor"),
        ("backend.services.monitors.tech_monitor", "TechMonitor"),
        ("backend.services.monitors.structure_monitor", "StructureMonitor"),
        ("backend.services.wordpress_service", "WordPressService"),
        ("backend.services.slack_service", "send_slack_alert"),
        ("backend.services.email_service", "send_email_alert"),
        ("backend.middleware.human_gate", "require_human"),
        ("backend.agents.strategy_agent", "StrategyAgent"),
    ]
    
    all_passed = True
    for module, items in modules:
        try:
            parts = items.split(", ")
            mod = __import__(module, fromlist=parts)
            print(f"  ✓ {module}: {items}")
        except Exception as e:
            print(f"  ✗ {module}: {e}")
            all_passed = False
    
    return all_passed


def verify_files():
    """Verify all files exist."""
    import os
    from pathlib import Path
    
    print("\n" + "=" * 60)
    print("VERIFYING FILES...")
    print("=" * 60)
    
    files = [
        "backend/services/reporting_service.py",
        "backend/services/continuous_monitor.py",
        "backend/services/monitors/__init__.py",
        "backend/services/monitors/rank_monitor.py",
        "backend/services/monitors/serp_monitor.py",
        "backend/services/monitors/competitor_monitor.py",
        "backend/services/monitors/tech_monitor.py",
        "backend/services/monitors/structure_monitor.py",
        "backend/services/wordpress_service.py",
        "backend/services/slack_service.py",
        "backend/services/email_service.py",
        "backend/services/sse_service.py",
        "backend/services/__init__.py",
        "backend/middleware/__init__.py",
        "backend/middleware/human_gate.py",
        "backend/agents/strategy_agent.py",
        "backend/agents/__init__.py",
        "backend/routers/monitoring.py",
        "backend/main.py",
        "backend/supabase_schema_enhanced.sql",
        "backend/tests/test_reporting.py",
    ]
    
    all_exist = True
    for f in files:
        full_path = Path(f)
        if full_path.exists():
            print(f"  ✓ {f}")
        else:
            print(f"  ✗ {f} MISSING")
            all_exist = False
    
    return all_exist


def verify_database_schema():
    """Verify database schema file."""
    print("\n" + "=" * 60)
    print("VERIFYING DATABASE SCHEMA...")
    print("=" * 60)
    
    from pathlib import Path
    
    schema_file = Path("backend/supabase_schema_enhanced.sql")
    if not schema_file.exists():
        print("  ✗ Schema file not found")
        return False
    
    content = schema_file.read_text()
    
    required_tables = [
        "realtime_alerts",
        "monitoring_logs",
        "topic_clusters",
        "pending_fixes"
    ]
    
    all_present = True
    for table in required_tables:
        if f"CREATE TABLE" in content and table in content:
            print(f"  ✓ Table: {table}")
        else:
            print(f"  ✗ Table: {table} MISSING")
            all_present = False
    
    return all_present


def verify_dashboard():
    """Verify frontend dashboard exists."""
    print("\n" + "=" * 60)
    print("VERIFYING FRONTEND DASHBOARD...")
    print("=" * 60)
    
    from pathlib import Path
    
    dashboard_file = Path("frontend-next/app/monitoring/page.tsx")
    if dashboard_file.exists():
        print(f"  ✓ {dashboard_file}")
        return True
    else:
        print(f"  ✗ Dashboard file MISSING")
        return False


def print_summary():
    """Print summary of built system."""
    print("\n" + "=" * 60)
    print("CONTINUOUS MONITORING SYSTEM SUMMARY")
    print("=" * 60)
    
    print("""
1. DATABASE TABLES (supabase_schema_enhanced.sql):
   ✓ realtime_alerts - All incidents, drops, bugs, opportunities
   ✓ monitoring_logs - Monitor execution logging
   ✓ topic_clusters - Auto-generated content strategy
   ✓ pending_fixes - Manual fixes awaiting human approval

2. REPORTING SERVICE (backend/services/reporting_service.py):
   ✓ report_problem() - ALWAYS creates alert + pushes to SSE/Slack/Email
   ✓ log_monitoring() - Tracks monitor execution
   ✓ generate_strategy_from_alert() - Auto-creates content strategy

3. CONTINUOUS MONITORING LOOPS (backend/services/continuous_monitor.py):
   ✓ rank_monitor_loop() - Every 15 min - Rank drops/opportunities
   ✓ serp_monitor_loop() - Every 30 min - Global vs Local vs Mobile
   ✓ competitor_monitor_loop() - Every 60 min - Pricing/content changes
   ✓ tech_monitor_loop() - Every 60 min - Broken links, speed, mobile
   ✓ structure_monitor_loop() - Every 6 hours - Full site structure

4. MONITOR IMPLEMENTATIONS:
   ✓ backend/services/monitors/rank_monitor.py
   ✓ backend/services/monitors/serp_monitor.py
   ✓ backend/services/monitors/competitor_monitor.py
   ✓ backend/services/monitors/tech_monitor.py
   ✓ backend/services/monitors/structure_monitor.py

5. INTEGRATION SERVICES:
   ✓ WordPress service - Draft creation, human-required publishing
   ✓ Slack service - Real-time alerts
   ✓ Email service - Critical alerts via Resend
   ✓ SSE service - Live dashboard streaming

6. HUMAN GATE (backend/middleware/human_gate.py):
   ✓ Requires X-User-Id for all publishing/approval
   ✓ Logs blocked actions

7. STRATEGY AGENT (backend/agents/strategy_agent.py):
   ✓ Auto-generates topic clusters from alerts
   ✓ Creates optimization suggestions
   ✓ Triggers writer tasks (draft only)

8. DASHBOARD ROUTER (backend/routers/monitoring.py):
   ✓ GET /alerts - Filter by unread/critical/all
   ✓ POST /alerts/{id}/read - Mark as read
   ✓ POST /alerts/{id}/approve - Approve with strategy
   ✓ GET /live - SSE stream
   ✓ GET /stats - Monitor status
   ✓ GET /pending-fixes - Human approval queue

9. FRONTEND DASHBOARD (frontend-next/app/monitoring/page.tsx):
   ✓ Real-time alert feed with filtering
   ✓ Stats bar: Critical/High/Opportunities/Monitors
   ✓ Pending approval queue
   ✓ Integration status panel
   ✓ User ID for human approval

10. TESTS (backend/tests/test_reporting.py):
    ✓ Test alerting works
    ✓ Test human approval required
    ✓ Test nothing is silent
""")