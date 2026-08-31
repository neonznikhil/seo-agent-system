import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('backend/.env')
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Check wordpress_connections table
print('=== WP CONNECTIONS ===')
try:
    r = client.table('wordpress_connections').select('*').limit(5).execute()
    for row in r.data or []:
        print(f'  site: {row.get("site_url")} | user: {row.get("wp_username")} | has_pass: {bool(row.get("wp_app_password_encrypted") or row.get("encrypted_password"))}')
    if not r.data:
        print('  No connections found')
except Exception as e:
    print(f'  Table not found: {e}')

# Check websites table for WP config
print()
print('=== WEBSITES WP CONFIG ===')
r = client.table('websites').select('id,wordpress_url,wordpress_user,app_password,cms_url,cms_user,wordpress_password').eq('id', '44666e81-1d83-4801-be22-1cb72f39801a').execute()
for row in r.data or []:
    for k, v in row.items():
        if 'password' in k.lower() or 'app' in k.lower():
            print(f'  {k}: {"SET" if v else "NOT SET"}')
        else:
            print(f'  {k}: {v}')

# Check env
print()
print('=== ENV WP ===')
print(f'  WORDPRESS_SITE_URL: {os.getenv("WORDPRESS_SITE_URL", "NOT SET")}')
print(f'  WORDPRESS_USERNAME: {os.getenv("WORDPRESS_USERNAME", "NOT SET")}')
print(f'  WORDPRESS_APP_PASSWORD: {"SET" if os.getenv("WORDPRESS_APP_PASSWORD") else "NOT SET"}')
