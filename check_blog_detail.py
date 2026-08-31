import os, json

with open('data/blog_approvals.json') as f:
    data = json.load(f)

if data:
    blog = data[0]
    print('=== BLOG APPROVAL ===')
    for k, v in blog.items():
        if k in ('content', 'html_content'):
            print(f'  {k}: {len(str(v))} chars')
        else:
            print(f'  {k}: {v}')
