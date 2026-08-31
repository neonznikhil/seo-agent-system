import os, sys, json, urllib.request, ssl
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv('backend/.env')

api_key = os.getenv('OPENROUTER_API_KEY', '')

# First, list available models
url = 'https://openrouter.ai/api/v1/models'
req = urllib.request.Request(url, method='GET')
req.add_header('Authorization', f'Bearer {api_key}')

ctx = ssl.create_default_context()
try:
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        result = json.loads(resp.read())
        models = result.get('data', [])
        print(f'Total models: {len(models)}')
        # Find nvidia models
        nvidia_models = [m for m in models if 'nvidia' in m.get('id', '').lower() or 'nemotron' in m.get('id', '').lower()]
        print(f'Nvidia models: {len(nvidia_models)}')
        for m in nvidia_models[:10]:
            mid = m['id']
            print(f'  {mid}')
except Exception as e:
    print(f'Error listing models: {e}')
