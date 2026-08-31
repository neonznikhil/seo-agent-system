import os, sys, asyncio, uuid

# Set up paths - add parent of backend to sys.path so backend is a package
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Step 1: Create website
print('=== STEP 1: Create website ===')
website_id = str(uuid.uuid4())
try:
    r = client.table('websites').insert({
        'id': website_id,
        'domain': 'accident.innovatcs.com',
        'url': 'https://accident.innovatcs.com',
        'cms_url': 'https://accident.innovatcs.com',
        'wordpress_url': 'https://accident.innovatcs.com',
        'status': 'active',
        'niche': 'personal injury law'
    }).execute()
    print(f'  Created website: {website_id}')
except Exception as e:
    err_str = str(e)
    if 'duplicate' in err_str.lower() or '23505' in err_str:
        r = client.table('websites').select('id').eq('domain', 'accident.innovatcs.com').limit(1).execute()
        if r.data:
            website_id = r.data[0]['id']
            print(f'  Using existing: {website_id}')
    else:
        print(f'  ERROR: {e}')

# Check knowledge base
print()
print('=== KNOWLEDGE BASE CHECK ===')
r = client.table('knowledge_base').select('id', count='exact').eq('website_id', website_id).limit(0).execute()
kb_count = r.count or 0
print(f'  Current KB entries: {kb_count}')

if kb_count < 5:
    print()
    print('=== STEP 2: Crawl website ===')
    from backend.services.knowledge_service import crawl_and_index_website
    result = asyncio.run(crawl_and_index_website(website_id, 'https://accident.innovatcs.com'))
    print(f'  Pages found: {result["pages_found"]}')
    print(f'  Pages crawled: {result["pages_crawled"]}')
    print(f'  Chunks saved: {result["chunks_saved"]}')
    print(f'  Errors: {len(result["errors"])}')

# Check KB again
r = client.table('knowledge_base').select('id', count='exact').eq('website_id', website_id).limit(0).execute()
kb_count = r.count or 0
print(f'  KB entries after crawl: {kb_count}')

# Step 3: Generate blog
print()
print('=== STEP 3: Generate blog ===')
print('  Starting blog generation (60-120s)...')
from backend.agents.crew_blog_writer import generate_blog_with_self_healing
blog_result = asyncio.run(generate_blog_with_self_healing(
    topic='car accident compensation guide 2026',
    website_id=website_id,
    word_count=2500
))
print(f'  Success: {blog_result.get("success")}')
print(f'  Title: {blog_result.get("title", "N/A")}')
blog_id = blog_result.get('blog_id', 'N/A')
print(f'  Blog ID: {blog_id}')
print(f'  SEO Score: {blog_result.get("seo_score", "N/A")}')
print(f'  Word Count: {blog_result.get("word_count", "N/A")}')
print(f'  Status: {blog_result.get("status", "N/A")}')
print(f'  WordPress URL: {blog_result.get("wordpress_url", "N/A")}')
wp_url = blog_result.get('wordpress_url', '')
if wp_url:
    print()
    print(f'  *** WORDPRESS DRAFT CREATED: {wp_url} ***')
