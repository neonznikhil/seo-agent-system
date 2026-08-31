import os, sys, json
sys.path.insert(0, '.')

# Check local store files
data_dir = 'data'
files = ['blog_approvals.json', 'content_log.json', 'websites.json', 'knowledge_base.json']

for f in files:
    path = os.path.join(data_dir, f)
    if os.path.exists(path):
        with open(path) as fh:
            data = json.load(fh)
        print(f'{f}: {len(data)} entries')
        if data:
            latest = data[-1]
            print(f'  Latest: {latest.get("title", latest.get("id", "N/A"))[:60]}')
    else:
        print(f'{f}: NOT FOUND')
