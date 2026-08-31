import os, sys, json, urllib.request, ssl
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv('backend/.env')

api_key = os.getenv('OPENROUTER_API_KEY', '')

# Try different free models
free_models = [
    'nvidia/nemotron-3.5-lightning:free',
    'nvidia/nemotron-3-super-120b-a12b:free',
    'google/gemini-2.0-flash-001:free',
    'meta-llama/llama-3.1-70b-instruct:free',
]

for model in free_models:
    print(f'Testing: {model}')
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
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            result = json.loads(resp.read())
            content = result['choices'][0]['message']['content']
            print(f'  OK: {content}')
            break
    except Exception as e:
        err = str(e)[:80]
        print(f'  FAIL: {err}')
