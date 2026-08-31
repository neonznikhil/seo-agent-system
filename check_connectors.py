import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('backend/.env')
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Check all websites and their WP config
print('=== ALL WEBSITES ===')
r = client.table('websites').select('id,domain,wordpress_url,wordpress_user,app_password,cms_url,cms_user').execute()
for row in r.data or []:
    wid = row['id'][:8]
    domain = row.get('domain', 'N/A')
    wp_url = row.get('wordpress_url', 'N/A')
    wp_user = row.get('wordpress_user', 'N/A')
    wp_pass = 'SET' if row.get('app_password') else 'NOT SET'
    cms_url = row.get('cms_url', 'N/A')
    cms_user = row.get('cms_user', 'N/A')
    print(f'  {wid} | {domain}')
    print(f'    WP URL: {wp_url}')
    print(f'    WP User: {wp_user}')
    print(f'    WP Pass: {wp_pass}')
    print(f'    CMS URL: {cms_url}')
    print(f'    CMS User: {cms_user}')

# Check wordpress_oauth_tokens table
print()
print('=== WP OAUTH TOKENS ===')
try:
    r = client.table('wordpress_oauth_tokens').select('*').limit(5).execute()
    for row in r.data or []:
        print(f'  website: {row.get("website_id", "N/A")[:8]} | url: {row.get("site_url", "N/A")} | user: {row.get("wp_username", "N/A")}')
    if not r.data:
        print('  No tokens found')
except Exception as e:
    print(f'  Error: {e}')

# Check content_log for latest article
print()
print('=== LATEST CONTENT ===')
r = client.table('content_log').select('id,title,seo_score,status,wp_post_id,wordpress_url').order('created_at', desc=True).limit(3).execute()
for c in r.data or []:
    cid = c['id'][:8]
    title = c.get('title', 'N/A')
    seo = c.get('seo_score', 'N/A')
    status = c.get('status', 'N/A')
    wp_post = c.get('wp_post_id', 'N/A')
    wp_url = c.get('wordpress_url', 'N/A')
    print(f'  {cid} | {title} | SEO: {seo} | Status: {status} | WP Post: {wp_post} | WP URL: {wp_url}')
