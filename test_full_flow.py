import os, sys, asyncio, uuid, time

# Run as module from project root
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))

from supabase import create_client
URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

print('=== SYSTEM CHECK ===')
print(f'LLM_PROVIDER: {os.getenv("LLM_PROVIDER")}')
print(f'NIM_LLM_MODEL: {os.getenv("NIM_LLM_MODEL")}')

# Check websites
r = client.table('websites').select('id,domain,status').execute()
websites = r.data or []
print(f'Websites: {len(websites)}')
for w in websites:
    print(f'  {w["id"][:8]} | {w.get("domain")} | {w.get("status")}')

if not websites:
    print('CREATING WEBSITE...')
    website_id = str(uuid.uuid4())
    client.table('websites').insert({
        'id': website_id,
        'domain': 'accident.innovatcs.com',
        'url': 'https://accident.innovatcs.com',
        'cms_url': 'https://accident.innovatcs.com',
        'wordpress_url': 'https://accident.innovatcs.com',
        'status': 'active',
        'niche': 'personal injury law'
    }).execute()
    print(f'Created: {website_id}')
else:
    website_id = websites[0]['id']

# Check KB
r = client.table('knowledge_base').select('id', count='exact').eq('website_id', website_id).limit(0).execute()
kb_count = r.count or 0
print(f'KB entries: {kb_count}')

# Generate blog
print()
print('=== BLOG GENERATION ===')
from backend.agents.crew_blog_writer import generate_blog_with_self_healing
start = time.time()
result = asyncio.run(generate_blog_with_self_healing(
    topic='car accident compensation guide 2026',
    website_id=website_id,
    word_count=2500
))
elapsed = time.time() - start
print(f'Completed in {elapsed:.1f}s')
print(f'Success: {result.get("success")}')
print(f'Title: {result.get("title", "N/A")}')
blog_id = result.get('blog_id', '')
print(f'Blog ID: {blog_id}')
print(f'SEO: {result.get("seo_score", "N/A")}')
print(f'Words: {result.get("word_count", "N/A")}')
print(f'Status: {result.get("status", "N/A")}')
print(f'WP URL: {result.get("wordpress_url", "N/A")}')
