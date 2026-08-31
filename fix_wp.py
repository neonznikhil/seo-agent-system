import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('backend/.env')
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

website_id = '44666e81-1d83-4801-be22-1cb72f39801a'

# Get env values
wp_url = os.getenv('WORDPRESS_SITE_URL', 'https://accident.innovatcs.com')
wp_user = os.getenv('WORDPRESS_USERNAME', 'admin')
wp_pass = os.getenv('WORDPRESS_APP_PASSWORD', '')

print(f'Updating website {website_id}...')
print(f'  URL: {wp_url}')
print(f'  User: {wp_user}')
print(f'  Pass: {"SET" if wp_pass else "NOT SET"}')

# Update the website record
try:
    r = client.table('websites').update({
        'wordpress_url': wp_url,
        'wordpress_user': wp_user,
        'app_password': wp_pass,
        'cms_url': wp_url,
        'cms_user': wp_user,
    }).eq('id', website_id).execute()
    print(f'  Updated: {r.data}')
except Exception as e:
    print(f'  ERROR: {e}')

# Verify
r = client.table('websites').select('id,wordpress_url,wordpress_user,app_password').eq('id', website_id).execute()
for row in r.data or []:
    print(f'  Verified: url={row.get("wordpress_url")} | user={row.get("wordpress_user")} | pass={"SET" if row.get("app_password") else "NOT SET"}')
