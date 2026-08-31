import os, sys, json

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))

from supabase import create_client
URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Check available columns
r = client.table('websites').select('*').limit(1).execute()
if r.data:
    print('Available columns:')
    for col in r.data[0].keys():
        print(f'  {col}')

# Get the correct credentials from local store
with open(os.path.join(PROJECT_DIR, 'data', 'websites.json')) as f:
    local_sites = json.load(f)

for site in local_sites:
    enc_pass = site.get('app_password', '')
    wp_user = site.get('wordpress_user', '')
    wp_url = site.get('wordpress_url', '')
    if enc_pass and enc_pass.startswith('gAAAAAB'):
        website_id = site.get('id')
        print(f'\\nUpdating website {website_id[:8]}...')
        
        # Try updating one field at a time
        try:
            r = client.table('websites').update({'wordpress_user': wp_user}).eq('id', website_id).execute()
            print(f'  wordpress_user: OK')
        except Exception as e:
            print(f'  wordpress_user: {e}')
        
        try:
            r = client.table('websites').update({'app_password': enc_pass}).eq('id', website_id).execute()
            print(f'  app_password: OK')
        except Exception as e:
            print(f'  app_password: {e}')
        
        try:
            r = client.table('websites').update({'wordpress_url': wp_url}).eq('id', website_id).execute()
            print(f'  wordpress_url: OK')
        except Exception as e:
            print(f'  wordpress_url: {e}')
        
        try:
            r = client.table('websites').update({'cms_url': wp_url}).eq('id', website_id).execute()
            print(f'  cms_url: OK')
        except Exception as e:
            print(f'  cms_url: {e}')
        
        try:
            r = client.table('websites').update({'cms_user': wp_user}).eq('id', website_id).execute()
            print(f'  cms_user: OK')
        except Exception as e:
            print(f'  cms_user: {e}')
        
        break
