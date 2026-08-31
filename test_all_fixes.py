import os, sys, asyncio, time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))

from supabase import create_client
from backend.agents.crew_blog_writer import generate_blog_with_self_healing

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

# Get website
r = client.table('websites').select('id').eq('domain', 'accident.innovatcs.com').limit(1).execute()
website_id = r.data[0]['id']
print(f'Website: {website_id}')

# Check KB
r = client.table('knowledge_base').select('id', count='exact').eq('website_id', website_id).limit(0).execute()
print(f'KB entries: {r.count}')

print()
print('=== GENERATING BLOG ===')
start = time.time()
result = asyncio.run(generate_blog_with_self_healing(
    topic='car accident compensation guide 2026',
    website_id=website_id,
    word_count=2500
))
elapsed = time.time() - start

print(f'Completed in {elapsed:.1f}s')
print(f'Title: {result.get("title", "N/A")}')
blog_id = result.get('blog_id', '')
print(f'Blog ID: {blog_id}')
print(f'SEO: {result.get("seo_score", "N/A")}')
print(f'Words: {result.get("word_count", "N/A")}')
print(f'Status: {result.get("status", "N/A")}')
wp_url = result.get('wordpress_url', '')
print(f'WP URL: {wp_url or "N/A"}')

# Verification checks
print()
print('=== VERIFICATION CHECKS ===')
html = result.get('final_html', result.get('html', ''))

# Check 1: No fake quotes
fake_names = ['Maria Gonzalez', 'James Chen', 'Robert Kim', 'Sarah Johnson', 'Michael Brown']
fake_found = [name for name in fake_names if name.lower() in html.lower()]
print(f'CHECK 1 - Fake quotes: {"PASS" if not fake_found else "FAIL: " + str(fake_found)}')

# Check 2: No duplicate placeholder paragraphs
placeholders = [
    'to establish strong evidentiary backing when addressing',
    'meticulous chronological documentation prevents insurance',
]
dup_found = [p for p in placeholders if p in html.lower()]
print(f'CHECK 2 - No placeholder paragraphs: {"PASS" if not dup_found else "FAIL"}')

# Check 3: No duplicate tables
from collections import Counter
import re
tables = re.findall(r'<table.*?</table>', html, re.DOTALL | re.IGNORECASE)
table_texts = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t)).strip()[:100] for t in tables]
table_counts = Counter(table_texts)
dups = {k: v for k, v in table_counts.items() if v > 1}
print(f'CHECK 3 - No duplicate tables: {"PASS" if not dups else "FAIL: " + str(len(dups)) + " duplicates"}')

# Check 4: No broken sentences
import re
broken_patterns = [r'\bof$', r'\bthe$', r'\band$', r'\bto$', r'\ba$']
broken_found = 0
for p in html.split('>'):
    text = re.sub(r'<[^>]+>', '', p).strip()
    for pat in broken_patterns:
        if re.search(pat, text) and len(text) > 20:
            broken_found += 1
            break
print(f'CHECK 4 - No broken sentences: {"PASS" if broken_found == 0 else "FAIL: " + str(broken_found) + " found"}')

# Check 5: FAQ accordion
has_accordion = 'rf-faq-container' in html and 'rf-faq-question' in html
has_faq_schema = 'FAQPage' in html
print(f'CHECK 5 - FAQ accordion: {"PASS" if has_accordion else "FAIL (no accordion)"} | Schema: {"PASS" if has_faq_schema else "FAIL"}')

# Check 6: Real website data
has_real_data = 'accident' in html.lower() or 'houston' in html.lower() or 'texas' in html.lower()
print(f'CHECK 6 - Real website data: {"PASS" if has_real_data else "WARN (no location data found)"}')
