import os, sys
sys.path.insert(0, '.')

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))

from supabase import create_client
URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Check ALL possible credential locations
print('=== 1. websites table ===')
r = client.table('websites').select('id,wordpress_url,wordpress_user,app_password,cms_url,cms_user').execute()
for row in r.data or []:
    wid = row['id'][:8]
    wp_url = row.get('wordpress_url', 'N/A')
    wp_user = row.get('wordpress_user', 'N/A')
    apppw = row.get('app_password', '')
    apppw_len = len(apppw) if apppw else 0
    cms_url = row.get('cms_url', 'N/A')
    cms_user = row.get('cms_user', 'N/A')
    print(f'  {wid}: url={wp_url} user={wp_user} pass_len={apppw_len} cms_url={cms_url} cms_user={cms_user}')

print()
print('=== 2. wordpress_oauth_tokens ===')
try:
    r = client.table('wordpress_oauth_tokens').select('*').execute()
    for row in r.data or []:
        wid = row.get('website_id', 'N/A')
        if wid != 'N/A':
            wid = wid[:8]
        site_url = row.get('site_url', 'N/A')
        username = row.get('wp_username', 'N/A')
        has_token = bool(row.get('access_token'))
        print(f'  {wid}: url={site_url} user={username} has_token={has_token}')
    if not r.data:
        print('  Empty')
except Exception as e:
    print(f'  Error: {e}')

print()
print('=== 3. wordpress_connections ===')
try:
    r = client.table('wordpress_connections').select('*').execute()
    for row in r.data or []:
        wid = row.get('website_id', 'N/A')
        if wid != 'N/A':
            wid = wid[:8]
        site_url = row.get('site_url', 'N/A')
        username = row.get('wp_username', 'N/A')
        has_pass = bool(row.get('wp_app_password_encrypted') or row.get('encrypted_password'))
        print(f'  {wid}: url={site_url} user={username} has_pass={has_pass}')
    if not r.data:
        print('  Empty')
except Exception as e:
    print(f'  Error: {e}')

print()
print('=== 4. env ===')
wp_env_url = os.getenv('WORDPRESS_SITE_URL', 'NOT SET')
wp_env_user = os.getenv('WORDPRESS_USERNAME', 'NOT SET')
wp_env_pass = os.getenv('WORDPRESS_APP_PASSWORD', 'NOT SET')
print(f'  URL: {wp_env_url}')
print(f'  User: {wp_env_user}')
print(f'  Pass: {wp_env_pass}')
