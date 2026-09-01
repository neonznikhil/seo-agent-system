import os, sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('backend/.env')
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Tables to clean (all data will be deleted, tables preserved)
tables = [
    'websites',
    'knowledge_base',
    'tasks',
    'brain_memory',
    'content_log',
    'autonomous_decisions',
    'autonomous_health_log',
    'blog_approvals',
    'blogs',
    'content_articles',
    'internal_link_suggestions',
    'rank_tracking',
    'backlinks',
    'competitor_cache',
    'gsc_cache',
    'serp_cache',
    'keyword_research',
    'content_calendar',
    'proposals',
    'reports',
    'slack_messages',
    'slack_intelligence',
    'self_training_cache',
    'tone_profiles',
    'analytics_data',
    'daily_costs',
    'content_pipeline_logs',
]

print("=== CLEANING SUPABASE DATA ===\n")
total_deleted = 0

for t in tables:
    try:
        # Get count first
        r = client.table(t).select('id', count='exact').limit(0).execute()
        count = r.count or 0
        
        if count == 0:
            print(f"  {t}: already empty")
            continue
        
        # Delete all rows
        # Use a condition that matches all rows (id is not null)
        r = client.table(t).delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        deleted = len(r.data) if r.data else count
        total_deleted += deleted
        print(f"  {t}: deleted {deleted} rows")
    except Exception as e:
        err = str(e)
        if 'Could not find' in err or '42P01' in err:
            print(f"  {t}: table does not exist (skipped)")
        else:
            print(f"  {t}: ERROR - {err[:80]}")

print(f"\n=== DONE ===")
print(f"Total rows deleted: {total_deleted}")
