import os, sys, asyncio, uuid

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Get or create website
print('=== WEBSITE ===')
r = client.table('websites').select('id').eq('domain', 'accident.innovatcs.com').limit(1).execute()
if r.data:
    website_id = r.data[0]['id']
    print(f'  Using existing: {website_id}')
else:
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
    print(f'  Created: {website_id}')

# Check KB
r = client.table('knowledge_base').select('id', count='exact').eq('website_id', website_id).limit(0).execute()
kb_count = r.count or 0
print(f'  KB entries: {kb_count}')

if kb_count < 5:
    print()
    print('=== CRAWLING (this takes ~30s) ===')
    from backend.services.knowledge_service import crawl_and_index_website
    result = asyncio.run(crawl_and_index_website(website_id, 'https://accident.innovatcs.com'))
    print(f'  Pages found: {result["pages_found"]}')
    print(f'  Pages crawled: {result["pages_crawled"]}')
    print(f'  Chunks saved: {result["chunks_saved"]}')
    print(f'  Errors: {len(result["errors"])}')
    if result['errors']:
        for e in result['errors'][:3]:
            print(f'    - {e}')

print()
print('=== DONE ===')
