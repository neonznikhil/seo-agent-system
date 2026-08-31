import os, sys, httpx, asyncio
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv('backend/.env')

provider = os.getenv('LLM_PROVIDER', 'nvidia')
api_key = os.getenv('OPENROUTER_API_KEY', '')
model = os.getenv('NIM_LLM_MODEL', '')
print(f'Provider: {provider}')
print(f'Model: {model}')
print(f'API Key: {api_key[:10]}...')

async def test():
    async with httpx.AsyncClient(timeout=30) as h:
        r = await h.post('https://openrouter.ai/api/v1/chat/completions',
            json={'model': model, 'messages': [{'role': 'user', 'content': 'Say hello in 3 words'}], 'max_tokens': 10},
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://rankforge.ai',
                'X-Title': 'RankForge'
            })
        print(f'Status: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            content = data['choices'][0]['message']['content']
            print(f'Response: {content}')
        else:
            print(f'Error: {r.text[:200]}')

asyncio.run(test())
