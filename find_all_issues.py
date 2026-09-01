import os
import re

# Find all imports that reference local modules in subdirectories
fixes = []

for dirpath, dirnames, filenames in os.walk('backend'):
    if '.venv' in dirpath:
        continue
    for filename in filenames:
        if filename.endswith('.py'):
            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Find all from xxx import statements
                matches = re.findall(r'^from ([a-zA-Z_][a-zA-Z0-9_.]*) import', content, flags=re.MULTILINE)
                for mod in set(matches):
                    top_level = mod.split('.')[0]
                    # Skip standard library and third-party
                    if top_level in ['os', 'sys', 'json', 're', 'math', 'datetime', 'time', 
                                     'uuid', 'hashlib', 'logging', 'typing', 'collections', 
                                     'functools', 'pathlib', 'asyncio', 'httpx', 'pydantic', 
                                     'fastapi', 'uvicorn', 'bs4', 'numpy', 'pandas', 'requests', 
                                     'dotenv', 'supabase', 'crewai', 'pymupdf', 'fitz', 'tenacity',
                                     'annotated_doc', 'cookiecutter', 'crawlee', 'pip', 'pytest',
                                     'markdown_it', 'typer', 'urllib3', 'uvicorn', 'zstandard',
                                     'sqlalchemy', 'starlette', 'text_unidecode', 'websockets',
                                     'wcwidth', 'stagehand', 'storage3', 'soupsieve']:
                        continue
                    
                    # Check if this is a local module that exists
                    mod_parts = mod.split('.')
                    mod_file = os.path.join(dirpath, *mod_parts) + '.py'
                    mod_dir = os.path.join(dirpath, *mod_parts)
                    
                    if os.path.exists(mod_file) or os.path.isdir(mod_dir):
                        # Module exists locally - need to fix import path
                        # Get relative path from backend/
                        rel_path = os.path.relpath(dirpath, 'backend')
                        if rel_path == '.':
                            # File is directly in backend/
                            if top_level in ['agents', 'routers', 'services', 'middleware', 'database', 'config', 'main']:
                                pass  # These are correct
                            else:
                                # Check if module exists at backend level
                                backend_mod = os.path.join('backend', top_level)
                                if os.path.exists(backend_mod + '.py') or os.path.isdir(backend_mod):
                                    fixes.append((filepath, f'from {mod} import', f'from backend.{mod} import'))
                        else:
                            # File is in a subdirectory
                            depth = rel_path.count(os.sep) + 1
                            if depth >= 1 and not mod.startswith('backend.') and not mod.startswith('agents.') and not mod.startswith('services.') and not mod.startswith('routers.') and not mod.startswith('middleware.'):
                                # Need to add the correct prefix
                                prefix = rel_path.replace(os.sep, '.')
                                if top_level in ['tools', 'rules']:
                                    if 'agents' in dirpath:
                                        fixes.append((filepath, f'from {mod} import', f'from agents.{mod} import'))
            except:
                pass

# Also find specific patterns that need fixing
specific_fixes = []

for dirpath, dirnames, filenames in os.walk('backend'):
    if '.venv' in dirpath:
        continue
    for filename in filenames:
        if filename.endswith('.py'):
            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Fix: from rules import xxx -> from backend.rules import xxx
                if re.search(r'^rules import', content, flags=re.MULTILINE):
                    if not filepath.endswith('rules.py'):
                        specific_fixes.append((filepath, 'rules', 'backend.rules'))
                
                # Fix: from tools.xxx import -> from backend.agents.tools.xxx import (if in agents/)
                if 'agents' in dirpath and re.search(r'^from tools\.', content, flags=re.MULTILINE):
                    specific_fixes.append((filepath, 'tools', 'agents.tools'))
                
                # Fix: from agents.xxx import -> from backend.agents.xxx import
                if re.search(r'^from agents\.', content, flags=re.MULTILINE):
                    specific_fixes.append((filepath, 'agents.', 'backend.agents.'))
                    
                # Fix: from routers.xxx import -> from backend.routers.xxx import  
                if re.search(r'^from routers\.', content, flags=re.MULTILINE):
                    specific_fixes.append((filepath, 'routers.', 'backend.routers.'))
                    
                # Fix: from services.xxx import -> from backend.services.xxx import
                if re.search(r'^from services\.', content, flags=re.MULTILINE):
                    specific_fixes.append((filepath, 'services.', 'backend.services.'))
                    
                # Fix: from middleware.xxx import -> from backend.middleware.xxx import
                if re.search(r'^from middleware\.', content, flags=re.MULTILINE):
                    specific_fixes.append((filepath, 'middleware.', 'backend.middleware.'))
                    
            except:
                pass

print("Specific fixes to apply:")
for filepath, old, new in specific_fixes[:30]:
    print(f"  {filepath}: {old} -> {new}")

# Also check for direct module imports like 'from rules import xxx'
print("\nDirect module imports that may need fixing:")
for dirpath, dirnames, filenames in os.walk('backend'):
    if '.venv' in dirpath:
        continue
    for filename in filenames:
        if filename.endswith('.py'):
            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                # Look for from xxx import where xxx is a module in backend/
                matches = re.findall(r'^from ([a-zA-Z_]+) import', content, flags=re.MULTILINE)
                for mod in set(matches):
                    if mod in ['rules', 'tools', 'utils', 'helpers', 'models', 'schemas']:
                        mod_file = os.path.join('backend', mod + '.py')
                        mod_dir = os.path.join('backend', mod)
                        if os.path.exists(mod_file) or os.path.isdir(mod_dir):
                            print(f"  {filepath}: from {mod} import ... (should be from backend.{mod})")
            except:
                pass
