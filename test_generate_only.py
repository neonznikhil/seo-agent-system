import os, sys, asyncio

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Get website
r = client.table('websites').select('id').eq('domain', 'accident.innovatcs.com').limit(1).execute()
website_id = r.data[0]['id']
print(f'Website: {website_id}')

# Check KB count
r = client.table('knowledge_base').select('id', count='exact').eq('website_id', website_id).limit(0).execute()
print(f'KB entries: {r.count}')

print()
print('=== STARTING BLOG GENERATION ===')
print('  This will take 2-3 minutes. Please wait...')
print()

from backend.agents.crew_blog_writer import generate_blog_with_self_healing
import time
start = time.time()

result = asyncio.run(generate_blog_with_self_healing(
    topic='car accident compensation guide 2026',
    website_id=website_id,
    word_count=2500
))

elapsed = time.time() - start
print(f'  Completed in {elapsed:.1f}s')
print()
print('=== RESULT ===')
for k, v in result.items():
    if k not in ('final_html', 'html', 'html_content', 'planner_outline'):
        print(f'  {k}: {v}')

wp_url = result.get('wordpress_url', '')
blog_id = result.get('blog_id', '')
if wp_url:
    print()
    print(f'  *** WORDPRESS DRAFT: {wp_url} ***')

# Check database
if blog_id:
    print()
    print('=== DATABASE CHECK ===')
    r = client.table('blogs').select('id,title,seo_score,status,wordpress_url').eq('id', blog_id).execute()
    if r.data:
        print(f'  Blog saved: {r.data[0].get("title")}')
        print(f'  SEO: {r.data[0].get("seo_score")}')
        print(f'  WP URL: {r.data[0].get("wordpress_url", "N/A")}')
    else:
        print('  Not in blogs table, checking content_log...')
        r = client.table('content_log').select('id,title,seo_score').eq('website_id', website_id).order('created_at', desc=True).limit(3).execute()
        for row in r.data or []:
            print(f'    - {row.get("title")} (SEO: {row.get("seo_score")})')
