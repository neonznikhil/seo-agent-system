import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('backend/.env')
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

r = client.table('websites').select('id,wordpress_user,app_password').limit(5).execute()
for row in r.data or []:
    has_pass = bool(row.get('app_password'))
    wid = row['id'][:8]
    user = row.get('wordpress_user')
    print(f'{wid} | user={user} | pass={has_pass}')
