import os, json

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Check local store for WP credentials
print('=== LOCAL STORE WP CONNECTIONS ===')
for fname in ['wordpress_connections.json', 'websites.json', 'wp_connections.json']:
    path = os.path.join(PROJECT_DIR, 'data', fname)
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        print(f'{fname}: {len(data)} entries')
        for entry in data[:3]:
            for k, v in entry.items():
                if 'password' in k.lower() or 'app' in k.lower() or 'token' in k.lower():
                    v_str = str(v)
                    if len(v_str) > 10:
                        print(f'  {k}: {v_str[:10]}...')
                    else:
                        print(f'  {k}: {v}')
                else:
                    print(f'  {k}: {v}')
    else:
        print(f'{fname}: NOT FOUND')
