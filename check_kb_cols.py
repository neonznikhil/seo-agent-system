import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('backend/.env')
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

r = client.table('knowledge_base').select('*').limit(1).execute()
if r.data:
    print('knowledge_base columns:')
    for col in r.data[0].keys():
        print(f'  {col}')
