import os, sys, asyncio, json

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))

from supabase import create_client
from backend.services.wordpress_service import WordPressService

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Get blog from local store
with open(os.path.join(PROJECT_DIR, 'data', 'blog_approvals.json')) as f:
    approvals = json.load(f)

if not approvals:
    print('No blog approvals found')
    exit()

blog = approvals[-1]
website_id = blog['website_id']
title = blog.get('title', 'Test')
content = blog.get('html_content', blog.get('content', ''))
keyword = blog.get('target_keyword', '')

print(f'Blog: {title}')
print(f'ID: {blog["id"][:8]}')
print(f'Content: {len(content)} chars')
print()

# Try to create WordPress draft
print('Creating WordPress draft...')
try:
    wp = WordPressService(website_id=website_id)
    print(f'WP Base URL: {wp.get_base_url()}')
    print(f'WP User: {wp.site.get("wordpress_user", "N/A")}')
    
    result = asyncio.run(wp.create_draft(
        website_id=website_id,
        title=title,
        content=content,
        keywords=[keyword] if keyword else None,
        slug='car-accident-compensation-guide'
    ))
    
    print(f'Result: {result}')
    
    if result.get('wp_post_id') or result.get('wordpress_url'):
        wp_url = result.get('wordpress_url', '')
        wp_post = result.get('wp_post_id', '')
        print(f'SUCCESS! WP Post: {wp_post}')
        print(f'WP URL: {wp_url}')
    else:
        print(f'Failed: {result.get("error", "Unknown error")}')
except Exception as e:
    print(f'ERROR: {e}')
