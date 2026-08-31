import os, sys, asyncio

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))

from supabase import create_client
from backend.services.wordpress_service import WordPressService

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Check what WordPressService sees
website_id = '44666e81-1d83-4801-be22-1cb72f39801a'
wp = WordPressService(website_id=website_id)

print('Site config:')
for k, v in wp.site.items():
    if 'password' in k.lower() or 'app' in k.lower():
        v_str = str(v)
        if len(v_str) > 20:
            print(f'  {k}: {v_str[:20]}...')
        else:
            print(f'  {k}: {v}')
    else:
        print(f'  {k}: {v}')

print()
user, password = wp._get_auth_tuple()
print(f'Auth tuple: user={user}, pass_len={len(password)}')
print(f'Pass starts with: {password[:10]}...' if len(password) > 10 else f'Pass: {password}')
