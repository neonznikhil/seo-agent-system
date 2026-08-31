import re
from collections import Counter
from backend.services.local_store import list_local_knowledge
wid='320133b7-192c-4f99-a90f-cd3f188d9140'
kb=list_local_knowledge(wid)
kbf=[k for k in kb if 'Hello world' not in (k.get('fact') or '') and (k.get('fact') or '').strip()]
stop={"the","and","for","with","from","that","this","your","have","are","was","were","will","would","should","could","must","can","not","but","about","after","when","what","which","their","there","been","has","had","section","general","business","overview","guides","skip","content","home","page","open","every","information"}
words=[]
for k in kbf:
    fact=(k.get('fact') or '').lower()
    fact=re.sub(r'[^a-z ]',' ',fact)
    for w in fact.split():
        if len(w)>3 and w not in stop:
            words.append(w)
cnt=Counter(words)
print("total words", len(words), "unique", len(cnt))
for w in ["accident","compensation","motorcycle","steps","digital","marketing","strategies","small","business","save","money","fast","claim","fault","crash","guide","legal","injury","insurance","houston","lawyer","personal","wrongful","death"]:
    print(f"{w}: {cnt.get(w,0)}")
print("\nTop 40:")
for w,c in cnt.most_common(40):
    print(f"{w}: {c}")
