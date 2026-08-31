import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('backend/.env')
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Check blog_approvals
r = client.table('blog_approvals').select('*').order('created_at', desc=True).limit(3).execute()
print('=== BLOG APPROVALS ===')
for a in r.data or []:
    aid = a['id'][:8]
    title = a.get('title', 'N/A')
    status = a.get('status', 'N/A')
    seo = a.get('seo_score', 'N/A')
    wp = a.get('wordpress_url', 'N/A')
    wp_post = a.get('wp_post_id', 'N/A')
    print(f'  {aid} | {title}')
    print(f'    SEO: {seo} | Status: {status} | WP: {wp} | WP Post: {wp_post}')

# Check content_log
r = client.table('content_log').select('id,title,seo_score,status').order('created_at', desc=True).limit(3).execute()
print()
print('=== CONTENT LOG ===')
for c in r.data or []:
    cid = c['id'][:8]
    title = c.get('title', 'N/A')
    seo = c.get('seo_score', 'N/A')
    status = c.get('status', 'N/A')
    print(f'  {cid} | {title} | SEO: {seo} | Status: {status}')

# Check WordPress config
print()
print('=== WP CONFIG ===')
wp_url = os.getenv('WORDPRESS_SITE_URL', 'NOT SET')
wp_user = os.getenv('WORDPRESS_USERNAME', 'NOT SET')
wp_pass = os.getenv('WORDPRESS_APP_PASSWORD', 'NOT SET')
print(f'  WP_SITE_URL: {wp_url}')
print(f'  WP_USERNAME: {wp_user}')
if wp_pass != 'NOT SET':
    print(f'  WP_APP_PASSWORD: {wp_pass[:10]}...')
else:
    print('  WP_APP_PASSWORD: NOT SET')
