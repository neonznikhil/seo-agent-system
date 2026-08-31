import asyncio, sys
sys.path.insert(0, ".")
from backend.agents.scheduler import _is_keyword_grounded_in_kb, _is_keyword_denied
import pathlib, json, re
from collections import Counter

wid='320133b7-192c-4f99-a90f-cd3f188d9140'

async def test():
    for kw in [
        "Motorcycle Accident Compensation Steps",
        "Houston Car Accident Lawyer Guide",
        "Digital Marketing Strategies For Small Business",
        "How To Save Money Fast",
        "How to Start a Blog",
        "Car Accident Compensation",
    ]:
        denied=_is_keyword_denied(kw)
        grounded=await _is_keyword_grounded_in_kb(kw, wid)
        print(f"{kw!r:50} denied={denied} grounded={grounded}")

        # Debug fallback manually
        from backend.services.local_store import list_local_knowledge
        kb=list_local_knowledge(wid)
        kbf=[k for k in kb if 'Hello world' not in (k.get('fact') or k.get('content') or '') and (k.get('fact') or k.get('content') or '').strip()]
        stop={"the","and","for","with","from","that","this","your","have","are","was","were","will","would","should","could","must","can","not","but","about","after","when","what","which","their","there","been","has","had","section","general","business","overview","guides","skip","content","home","page","open","every","information"}
        words=[]
        for k in kbf:
            fact=(k.get('fact') or k.get('content') or '').lower()
            fact=re.sub(r'[^a-z ]',' ',fact)
            for w in fact.split():
                if len(w)>3 and w not in stop:
                    words.append(w)
        cnt=Counter(words)
        niche=set(w for w,c in cnt.most_common(30))
        print(f"  niche sample: {list(niche)[:10]}")
        kw_words=[w.lower() for w in re.findall(r"[a-zA-Z]{4,}", kw.lower())]
        over=sum(1 for w in kw_words if w in niche or any(v in w or w in v for v in niche))
        ratio=over/len(kw_words) if kw_words else 0
        print(f"  kw_words {kw_words} over {over}/{len(kw_words)} ratio {ratio:.2f}")

asyncio.run(test())
