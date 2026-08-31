import re
from backend.services.local_store import list_local_knowledge
wid='320133b7-192c-4f99-a90f-cd3f188d9140'
kb=list_local_knowledge(wid)
kbf=[k for k in kb if 'Hello world' not in (k.get('fact') or '') and (k.get('fact') or '').strip()]
kb_text=' '.join((k.get('fact') or '').lower() for k in kbf)
for kw in ['Digital Marketing Strategies For Small Business','Motorcycle Accident Compensation Steps','How To Save Money Fast']:
    kw_words=[w.lower() for w in re.findall(r"[a-zA-Z]{4,}", kw.lower())]
    overlap=sum(1 for w in kw_words if w in kb_text)
    ratio=overlap/len(kw_words) if kw_words else 0
    print(kw, kw_words, f"overlap {overlap} ratio {ratio:.2f}")
    for w in kw_words:
        print(f"  {w}: {w in kb_text}")
