import os, sys, json

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))

from supabase import create_client
URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# The CORRECT website ID
website_id = '44666e81-1d83-4801-be22-1cb72f39801a'

# Get the correct credentials from local store
with open(os.path.join(PROJECT_DIR, 'data', 'websites.json')) as f:
    local_sites = json.load(f)

# Find the correct site
for site in local_sites:
    if site.get('id') == website_id:
        enc_pass = site.get('app_password', '')
        wp_user = site.get('wordpress_user', '')
        wp_url = site.get('wordpress_url', '')
        print(f'Found site: {website_id[:8]}')
        print(f'  User: {wp_user}')
        print(f'  URL: {wp_url}')
        print(f'  Pass: {enc_pass[:20]}...')
        
        # Update ALL fields
        r = client.table('websites').update({
            'wordpress_user': wp_user,
            'app_password': enc_pass,
            'wordpress_url': wp_url,
            'cms_url': wp_url,
            'cms_user': wp_user,
        }).eq('id', website_id).execute()
        
        if r.data:
            print(f'  Updated: {r.data[0]["id"][:8]}')
        else:
            print(f'  FAILED')
        break
else:
    print(f'Site {website_id} not found in local store')
