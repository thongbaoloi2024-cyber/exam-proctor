"""Check report source links and synthetic data provenance without compiling PDF."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parent
visited=[]; errors=[]; figures=[]
def read_tree(path):
    if path in visited:
        errors.append(f'Repeated input: {path.name}');return ''
    visited.append(path)
    text=path.read_text(encoding='utf-8')
    # Comments and literal code do not contribute TeX references or environments.
    text=re.sub(r'\\begin\{Verbatim\}.*?\\end\{Verbatim\}','',text,flags=re.S)
    text=re.sub(r'(?m)(?<!\\)%.*$','',text)
    for name in re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}',text):
        figures.append(name)
        if not (ROOT/name).is_file():errors.append(f'Missing figure: {name}')
    stack=[]
    for kind,name in re.findall(r'\\(begin|end)\{([^}]+)\}',text):
        if kind=='begin':stack.append(name)
        elif not stack or stack.pop()!=name:errors.append(f'Environment mismatch: {path.name}: {name}')
    if stack:errors.append(f'Unclosed environments: {path.name}: {stack}')
    braces=0
    for char in re.sub(r'\\[{}]','',text):
        if char=='{':braces+=1
        elif char=='}':braces-=1
        if braces<0:errors.append(f'Extra closing brace: {path.name}');break
    if braces:errors.append(f'Unbalanced braces: {path.name}: {braces}')
    def expand(match):
        name=match.group(1); child=ROOT/(name if name.endswith('.tex') else name+'.tex')
        if not child.is_file():errors.append(f'Missing input: {name}');return ''
        return read_tree(child)
    return re.sub(r'\\input\{([^}]+)\}',expand,text)

all_text=read_tree(ROOT/'main.tex')
labels=re.findall(r'\\label\{([^}]+)\}',all_text)
refs=re.findall(r'\\(?:ref|eqref|pageref)\{([^}]+)\}',all_text)
keys=re.findall(r'\\bibitem\{([^}]+)\}',all_text)
cites=[k.strip() for group in re.findall(r'\\cite\{([^}]+)\}',all_text) for k in group.split(',')]
for label,n in Counter(labels).items():
    if n>1:errors.append(f'Duplicate label: {label}')
for label in set(refs)-set(labels):errors.append(f'Missing label: {label}')
for key in set(cites)-set(keys):errors.append(f'Missing citation: {key}')
if len(keys)!=len(set(keys)):errors.append('Duplicate bibliography keys')
for folder in ['synthetic_evaluation','interval_evaluation']:
    d=ROOT/'data'/folder;manifest=json.loads((d/'manifest.json').read_text(encoding='utf-8'))
    for file,key in [(d/'evaluation.json','data_sha256'),(ROOT/manifest['generator'],'generator_sha256')]:
        if hashlib.sha256(file.read_bytes()).hexdigest()!=manifest[key]:errors.append(f'Hash mismatch: {file}')
summary=dict(status='PASS' if not errors else 'FAIL',tex_files=len(visited),labels=len(labels),
             bibliography_entries=len(keys),unused_bibliography=sorted(set(keys)-set(cites)),
             unique_figures=sorted(set(figures)),errors=errors,
             scope='Source structure, links and provenance only. No TeX compilation or PDF layout check.')
(ROOT/'data'/'source_review_20260918.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
