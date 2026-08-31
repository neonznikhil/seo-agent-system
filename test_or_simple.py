import os, sys, json, urllib.request, ssl
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv('backend/.env')

api_key = os.getenv('OPENROUTER_API_KEY', '')
model = os.getenv('NIM_LLM_MODEL', '')
print(f'Model: {model}')

# Test with urllib (no external deps)
url = 'https://openrouter.ai/api/v1/chat/completions'
data = json.dumps({
    'model': model,
    'messages': [{'role': 'user', 'content': 'Say hello in 3 words'}],
    'max_tokens': 10
}).encode()

req = urllib.request.Request(url, data=data, method='POST')
req.add_header('Authorization', f'Bearer {api_key}')
req.add_header('Content-Type', 'application/json')
req.add_header('HTTP-Referer', 'https://rankforge.ai')
req.add_header('X-Title', 'RankForge')

ctx = ssl.create_default_context()
try:
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        result = json.loads(resp.read())
        print(f'Status: {resp.status}')
        content = result['choices'][0]['message']['content']
        print(f'Response: {content}')
except Exception as e:
    print(f'Error: {e}')
